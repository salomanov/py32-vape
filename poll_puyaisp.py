import sys
import time
import os
import puyaisp
from puyaisp import puyaisp as pi

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

try:
    import winsound
    def beep(freq=1800, dur=250):
        winsound.Beep(freq, dur)
except Exception:
    def beep(freq=1800, dur=250):
        print('\a', end='', flush=True)

def main():
    print("=" * 65)
    print(" >>> НЕПРЕРЫВНЫЙ ЗАХВАТ И РАЗБЛОКИРОВКА PUYA ЧЕРЕЗ UART <<<")
    print("=" * 65)
    print("Питание VCC и BOOT0 (контакты 1 и 2) уже подтянуты к 3.3В.")
    print("СЕЙЧАС:")
    print("👉 Коснитесь пинцетом пина 15 (NRST) на землю GND (контакт 5)")
    print("   на полсекунды И ОТПУСТИТЕ!")
    print("=" * 65 + "\n")

    attempts = 0
    start = time.time()
    last_print = time.time()

    while time.time() - start < 180:
        attempts += 1
        now = time.time()
        if now - last_print >= 2.0:
            last_print = now
            print(f"[*] Жду касания NRST на GND... Попытка #{attempts}")

        try:
            isp = pi.Programmer()
            # Если Programmer() не выкинул Exception — значит СВЯЗЬ ЕСТЬ!
            beep(1800, 200)
            print("\n" + "=" * 65)
            print(f"[🔥] ЕСТЬ ОТВЕТ ОТ ЗАГРУЗЧИКА НА {isp.port}!")
            print("=" * 65)

            isp.readinfo()
            print(f"[+] Найден чип с PID: 0x{isp.pid:04X}, Bootloader v{isp.verstr}")

            print("[*] Выполняю полное снятие защиты и очистку памяти (UNLOCK)...")
            isp.unlock()
            beep(2400, 400)
            print("\n" + "=" * 65)
            print("  🎉 ПОЗДРАВЛЯЕМ! ЧИП PUYA УСПЕШНО РАЗБЛОКИРОВАН И СТЕРТ!")
            print("  Защита снята, Flash полностью свободен!")
            print("=" * 65)
            isp.reset()
            return True

        except Exception as e:
            # Ожидаем сброса
            pass

        time.sleep(0.05)

    print("\n[X] Время вышло (3 минуты).")
    return False

if __name__ == '__main__':
    main()
