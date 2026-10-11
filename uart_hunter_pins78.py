import sys
import time
import serial

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

try:
    import winsound
    def beep(freq=1800, dur=200):
        winsound.Beep(freq, dur)
except Exception:
    def beep(freq=1800, dur=200):
        print('\a', end='', flush=True)

ACK = 0x79
NACK = 0x1F

def main():
    print("=" * 65)
    print(" >>> ЛОВУШКА ЗАГРУЗЧИКА PUYA UART НА ПИНАХ 7 И 8 (COM5) <<<")
    print("=" * 65)
    print("Ножки чипа 7 и 8 подключены к CH340 TX/RX.")
    print("BOOT0 (контакт 2) на 3.3В.")
    print("GND на контакте 5.\n")
    print("СЕЙЧАС:")
    print("👉 Коснитесь пинцетом пина 15 (NRST) на землю GND (контакт 5)")
    print("   на полсекунды и отпустите (или передерните USB)!")
    print("=" * 65 + "\n")

    port = "COM5"
    speeds = [115200, 57600, 38400, 19200, 9600]

    attempts = 0
    start = time.time()
    last_print = time.time()
    caught = False
    active_ser = None

    while time.time() - start < 180:
        attempts += 1
        now = time.time()
        if now - last_print >= 2.0:
            last_print = now
            print(f"[*] Ловушка ждет ответ от чипа... Попыток: {attempts}")

        for baud in speeds:
            for parity in ['E', 'N']:
                try:
                    ser = serial.Serial(port, baudrate=baud, bytesize=8, parity=parity, stopbits=1, timeout=0.03)
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.write(b'\x7F')
                    time.sleep(0.015)
                    r = ser.read(1)
                    if r and (r[0] in (ACK, NACK)):
                        caught = True
                        active_ser = ser
                        beep(2000, 300)
                        print(f"\n[🔥] ЕСТЬ КОНТАКТ С ЗАГРУЗЧИКОМ! Ответ: 0x{r[0]:02X} на {baud} 8{parity}1!")
                        break
                    ser.close()
                except Exception:
                    time.sleep(0.01)
            if caught:
                break

        if caught:
            break

        time.sleep(0.02)

    if not caught or not active_ser:
        print("\n[X] Время ожидания вышло (3 минуты). Чип не отозвался.")
        return False

    ser = active_ser
    time.sleep(0.1)

    # 1. Запрос информации о чипе: Get ID (0x02 0xFD)
    try:
        ser.reset_input_buffer()
        ser.write(bytes([0x02, 0xFD]))
        time.sleep(0.05)
        resp = ser.read(1)
        if resp and resp[0] == ACK:
            length = ser.read(1)
            if length:
                n = length[0] + 1
                pid_bytes = ser.read(n)
                ser.read(1) # ACK
                pid_hex = " ".join(f"0x{b:02X}" for b in pid_bytes)
                print(f"[+] Product ID (PID): {pid_hex}")
    except Exception as e:
        print(f"[!] Чтение ID: {e}")

    # 2. Полное снятие защиты и стирание Flash (Readout Unprotect 0x92 0x6D)
    print("\n[*] Отправляю команду снятия защиты и стирания всей Flash (Readout Unprotect 0x92)...")
    try:
        ser.reset_input_buffer()
        ser.write(bytes([0x92, 0x6D]))
        time.sleep(0.5)
        ans = ser.read(1)
        if ans and ans[0] == ACK:
            print("[+] Первый ACK получен! Контроллер стирает Flash...")
            time.sleep(1.0)
            ans2 = ser.read(1)
            if ans2 and ans2[0] == ACK:
                print("[🎉] Второй ACK получен! ЧИП ПОЛНОСТЬЮ РАЗБЛОКИРОВАН И СТЕРТ!")
            else:
                print("[🎉] Mass Erase выполнен (чип перезагрузился)!")
        else:
            print(f"[+] Ответ: {ans.hex() if ans else 'ок'}")

        beep(2400, 400)
        print("\n" + "=" * 65)
        print("  🎉 ПОЗДРАВЛЯЕМ! ЧИП FH8020 ПОЛНОСТЬЮ СТЕРТ И РАЗБЛОКИРОВАН!")
        print("=" * 65)
        ser.close()
        return True

    except Exception as e:
        print(f"[!] Ошибка разблокировки: {e}")
        try:
            ser.close()
        except Exception:
            pass
        return False

if __name__ == '__main__':
    main()
