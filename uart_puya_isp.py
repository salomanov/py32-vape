import sys
import time
import serial
import serial.tools.list_ports

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

def find_ch340_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        hwid = p.hwid.lower()
        if "ch34" in desc or "ch34" in hwid or "1a86:5523" in hwid or "1a86:7523" in hwid or "usb-serial" in desc:
            return p.device
    for p in ports:
        if "bluetooth" not in p.description.lower():
            return p.device
    return None

def sync_bootloader(ser):
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(bytes([0x7F]))
        time.sleep(0.04)
        resp = ser.read(1)
        if resp and resp[0] in (ACK, NACK):
            return True
    except Exception:
        pass
    return False

def get_id(ser):
    try:
        ser.reset_input_buffer()
        ser.write(bytes([0x02, 0xFD]))
        resp = ser.read(1)
        if not resp or resp[0] != ACK:
            return None
        length = ser.read(1)
        if not length:
            return None
        n = length[0] + 1
        pid_bytes = ser.read(n)
        ser.read(1) # ACK
        return pid_bytes
    except Exception:
        return None

def readout_unprotect(ser):
    print("[*] Отправляю команду Readout Unprotect (0x92) для полного снятия защиты...")
    try:
        ser.reset_input_buffer()
        ser.write(bytes([0x92, 0x6D]))
        resp = ser.read(1)
        if not resp or resp[0] != ACK:
            print(f"[X] Команда 0x92 не принята: {resp.hex() if resp else 'нет ответа'}")
            return False
        print("[+] Первый ACK получен! Контроллер стирает Flash-память...")
        time.sleep(1.0)
        resp2 = ser.read(1)
        if resp2 and resp2[0] == ACK:
            print("[🎉] Второй ACK получен! ЧИП ПОЛНОСТЬЮ РАЗБЛОКИРОВАН И СТЕРТ!")
            beep(2400, 400)
            return True
        else:
            print("[+] Mass Erase запущен (чип перезагружается).")
            beep(2000, 300)
            return True
    except Exception as e:
        print(f"[!] Ошибка во время стирания: {e}")
        return False

def main():
    print("=" * 65)
    print(" >>> НЕУБИВАЕМЫЙ ПРОШИВЩИК / РАЗБЛОКИРОВЩИК UART (CH340) <<<")
    print("=" * 65)

    speeds = [115200, 57600, 38400, 19200, 9600]
    attempt = 0

    while True:
        port = find_ch340_port()
        if not port:
            print("[*] Вставьте CH340 в USB... жду устройство...")
            while not port:
                time.sleep(1.0)
                port = find_ch340_port()
            print(f"[+] CH340 обнаружен на порту: {port}")

        attempt += 1
        print(f"\n[*] Цикл #{attempt} на {port}...")

        connected = False
        for baud in speeds:
            try:
                ser = serial.Serial(port, baudrate=baud, bytesize=8, parity='E', stopbits=1, timeout=0.08)
            except Exception:
                time.sleep(0.1)
                break # порт отвалился, перепроверим порт

            if sync_bootloader(ser):
                print(f"\n[🔥] СВЯЗЬ С ЗАГРУЗЧИКОМ УСТАНОВЛЕНА! Скорость: {baud} бод (8E1)")
                beep(1800, 250)

                pid = get_id(ser)
                if pid:
                    pid_hex = " ".join(f"0x{b:02X}" for b in pid)
                    print(f"[+] Chip Product ID (PID): {pid_hex}")

                if readout_unprotect(ser):
                    print("\n" + "=" * 65)
                    print("  🎉 ПОЗДРАВЛЯЕМ! ЧИП FH8020 ПОЛНОСТЬЮ СТЕРТ И РАЗБЛОКИРОВАН!")
                    print("=" * 65)
                    ser.close()
                    return True
                connected = True
                ser.close()
                break

            try:
                ser.close()
            except Exception:
                pass

        time.sleep(0.3)

if __name__ == '__main__':
    main()
