import sys
import time
import os
import pylink

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

def main():
    print("=" * 65)
    print(" >>> ЗАХВАТ И ПРОВЕРКА СВЯЗИ С ПЛАТОЙ W39A (FH8020 / PUYA) <<<")
    print("=" * 65)

    j = pylink.JLink()
    try:
        j.open('774496021')
    except Exception:
        try:
            j.open()
        except Exception as e:
            print(f"[X] Не удалось открыть J-Link: {e}")
            return False

    j.set_tif(pylink.enums.JLinkInterfaces.SWD)
    j.set_speed(200) # 200 kHz for jumper wires

    status = j.hardware_status
    vtref = status.VTarget if hasattr(status, 'VTarget') else 0
    print(f"[*] J-Link SN: {j.serial_number}, Напряжение платы VTref: {vtref} мВ")

    if vtref < 2000:
        print("[!] ВНИМАНИЕ: Напряжение VTref ниже 2.0В! Проверьте провод питания VCC (контакт 1) и GND (контакт 5).")

    print("\n[*] Запускаю непрерывный опрос CoreSight SWD...")
    print("    Если провод RESET подключен — скрипт будет периодически сбрасывать чип.")
    print("    Если сброс ручной — можете кратковременно коснуться пина 12 (или 10) на землю GND.\n")

    start_time = time.time()
    attempts = 0
    last_print = time.time()
    caught = False
    valid_dpidr = None

    while time.time() - start_time < 60:
        attempts += 1
        now = time.time()
        if now - last_print >= 2.0:
            last_print = now
            print(f"[*] Попытка #{attempts}... Ожидаю ответа ARM Cortex-M0+...")

        # Попытка через Coresight
        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr and dpidr != 0xFFFFFFFF and dpidr != 0x00000000:
                valid_dpidr = dpidr
                caught = True
                break
        except Exception:
            pass

        # Пробуем дернуть Reset
        if attempts % 50 == 0:
            try:
                j.set_reset_pin_low()
                time.sleep(0.01)
                j.set_reset_pin_high()
                time.sleep(0.01)
            except Exception:
                pass

        time.sleep(0.005)

    if not caught:
        print("\n[X] Чип не ответил по SWD за 30 секунд.")
        print("    Возможные причины:")
        print("    1. SWDIO и NRST перепутаны местами (попробуйте поменять местами контакты 2 и 3).")
        print("    2. Плохой контакт на одном из проводов.")
        j.close()
        return False

    print("\n" + "=" * 65)
    print(f"[🔥] УСПЕХ! ЯДРО ОТВЕТИЛО! DPIDR = 0x{valid_dpidr:08X} (попытка #{attempts})")
    print("=" * 65)

    try:
        # 1. Включаем питание DP
        j.coresight_write(1, 0x50000000, ap=False)
        j.coresight_write(0, 0x1E, ap=False)

        # 2. Останавливаем ядро (DHCSR = HALT | DEBUGEN)
        j.coresight_write(2, 0x00000000, ap=False)
        j.coresight_write(0, 0x23000002, ap=True) # CSW
        j.coresight_write(1, 0xE000EDF0, ap=True) # DHCSR
        j.coresight_write(3, 0xA05F0003, ap=True) # HALT
        print("[+] Ядро Cortex-M0+ успешно ОСТАНОВЛЕНО (HALT)!")

        # 3. Читаем регистр Device ID (0x1FFF0F00 или 0x40015800)
        j.coresight_write(1, 0x1FFF0F00, ap=True)
        dev_id = j.coresight_read(3, ap=True)
        print(f"[+] Device ID: 0x{dev_id:08X}")

        # Читаем CPUID
        j.coresight_write(1, 0xE000ED00, ap=True)
        cpuid = j.coresight_read(3, ap=True)
        print(f"[+] ARM CPUID: 0x{cpuid:08X}")

        print("\n>>> СВЯЗЬ ПОЛНОСТЬЮ УСТАНОВЛЕНА! ЧИП ГОТОВ К СТИРАНИЮ / ПРОШИВКЕ! <<<")
        j.close()
        return True
    except Exception as e:
        print(f"[!] Ошибка работы с ядром после захвата: {e}")
        j.close()
        return False

if __name__ == '__main__':
    main()
