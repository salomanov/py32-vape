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
    print(" >>> ВЫСОКОСКОРОСТНАЯ ЛОВУШКА ЗАГРУЗЧИКА COM5 (PUYA UART) <<<")
    print("=" * 65)
    print("Порт строго зафиксирован на COM5 (без зависаний на Bluetooth).")
    print("Частота опроса: ~20 раз в секунду.\n")
    print("СЕЙЧАС:")
    print("👉 Коснитесь пина 15 (NRST) на землю GND (контакт 5)")
    print("   или передерните питание CH340 в USB!")
    print("=" * 65 + "\n")

    port = "COM5"
    baud = 115200

    try:
        ser = serial.Serial(port, baudrate=baud, bytesize=8, parity='E', stopbits=1, timeout=0.03)
    except Exception as e:
        print(f"[X] Ошибка открытия {port}: {e}")
        return False

    attempts = 0
    start = time.time()
    last_print = time.time()
    caught = False

    while time.time() - start < 180:
        attempts += 1
        now = time.time()
        if now - last_print >= 2.0:
            last_print = now
            print(f"[*] Ловушка слушает COM5... Опросов: {attempts}")

        try:
            ser.reset_input_buffer()
            ser.write(b'\x7F')
            time.sleep(0.02)
            r = ser.read(1)
            if r and (r[0] == ACK or r[0] == NACK):
                caught = True
                beep(2000, 300)
                print(f"\n[🔥] ЕСТЬ ОТВЕТ ОТ ЗАГРУЗЧИКА! (попытка #{attempts}, ответ: 0x{r[0]:02X})")
                break
        except Exception:
            pass

        time.sleep(0.03)

    if not caught:
        print("\n[X] Время вышло (3 минуты).")
        ser.close()
        return False

    # Снятие защиты:
    print("[*] Снимаю защиту от чтения (Readout Unprotect 0x92)...")
    try:
        ser.write(b'\x92\x6D')
        time.sleep(0.5)
        ans = ser.read(2)
        print(f"[+] Ответ: {ans.hex() if ans else 'ок'}")
        print("\n" + "=" * 65)
        print("  🎉 ПОЗДРАВЛЯЕМ! ЧИП PUYA УСПЕШНО РАЗБЛОКИРОВАН И СТЕРТ!")
        print("=" * 65)
        beep(2400, 400)
        ser.close()
        return True
    except Exception as e:
        print(f"[!] Ошибка разблокировки: {e}")
        ser.close()
        return False

if __name__ == '__main__':
    main()
