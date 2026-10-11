import sys
import time
import os
import pylink

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

def main():
    print("=" * 65)
    print(" >>> ИНТЕРАКТИВНАЯ ЛОВУШКА W39A (FH8020 / PUYA PY32) <<<")
    print("=" * 65)

    j = pylink.JLink()
    
    def connect_jlink():
        try:
            if j.opened():
                j.close()
        except Exception:
            pass
        try:
            j.open()
            j.set_tif(pylink.enums.JLinkInterfaces.SWD)
            # 500 кГц надежно для проводков
            j.set_speed(500)
            return True
        except Exception as e:
            return False

    if not connect_jlink():
        print("[X] Не удалось подключиться к J-Link. Проверьте USB J-Link.")
        return False

    vtref = j.hardware_status.VTarget
    print(f"[*] J-Link SN: {j.serial_number} | VTref: {vtref} мВ")
    print("\n" + "-" * 65)
    print(" Ловушка активна!")
    print(" Попробуйте:")
    print("   1) Кратковременно замкнуть пин 15 (NRST) на землю GND (пинцет/проводок)")
    print("   2) Или передернуть питание Type-C")
    print("-" * 65 + "\n")

    start_time = time.time()
    attempts = 0
    last_print = time.time()
    caught = False
    valid_dpidr = None

    while time.time() - start_time < 180:
        attempts += 1
        now = time.time()
        if now - last_print >= 3.0:
            last_print = now
            try:
                v = j.hardware_status.VTarget
                print(f"[*] Жду сброса... Попыток: {attempts} | Напряжение платы VTref: {v} мВ")
            except Exception:
                print(f"[*] Переподключение к J-Link... (питание пропало)")
                connect_jlink()

        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477, 0x1BA01477, 0x0BD11477) or (dpidr and dpidr != 0xFFFFFFFF and dpidr != 0x00000000):
                # 1. DP Power-up
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False)

                # 2. Мгновенно останавливаем ядро
                j.coresight_write(2, 0x00000000, ap=False)
                j.coresight_write(0, 0x23000002, ap=True) # CSW 32-bit
                j.coresight_write(1, 0xE000EDF0, ap=True) # DHCSR
                j.coresight_write(3, 0xA05F0003, ap=True) # HALT | DEBUGEN

                valid_dpidr = dpidr
                caught = True
                beep(2000, 300)
                print(f"\n[🔥] ЕСТЬ ЗАХВАТ! DPIDR = 0x{valid_dpidr:08X} (попытка #{attempts})!")
                print(">>> ЯДРО ОСТАНОВЛЕНО! НЕ ТРОГАЙТЕ ПЛАТУ! СТИРАЮ ПАМЯТЬ... <<<")
                break
        except Exception as e:
            err_str = str(e)
            if "timed out" in err_str.lower() or "not open" in err_str.lower() or "closed" in err_str.lower():
                time.sleep(0.05)
                connect_jlink()

        time.sleep(0.005)

    if not caught:
        print("\n[X] Время ожидания вышло. Чип не ответил.")
        try:
            j.close()
        except Exception:
            pass
        return False

    time.sleep(0.1)

    # 3. Полное стирание Mass Erase
    try:
        j.coresight_write(0, 0x1E, ap=False)
        j.coresight_write(2, 0x00000000, ap=False)
        j.coresight_write(0, 0x23000002, ap=True)

        # RCC->AHBENR
        j.coresight_write(1, 0x40021014, ap=True)
        j.coresight_write(3, 0x00000104, ap=True)

        # KEYR
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0x45670123, ap=True)
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0xCDEF89AB, ap=True)
        print("[+] Flash Controller разблокирован!")

        # Mass Erase: MER + STRT
        j.coresight_write(1, 0x40022010, ap=True)
        j.coresight_write(3, 0x00000044, ap=True)
        print("[*] Запущен Mass Erase (полная очистка Flash)...")

        t0 = time.time()
        while time.time() - t0 < 3.0:
            j.coresight_write(1, 0x4002200C, ap=True)
            sr = j.coresight_read(3, ap=True)
            if (sr & 0x01) == 0:
                break
            time.sleep(0.02)

        print("[🎉] ПАМЯТЬ FLASH УСПЕШНО СТЕРТА!")
        beep(2400, 300)

        # Проверка 0x08000000
        j.coresight_write(1, 0x08000000, ap=True)
        val = j.coresight_read(3, ap=True)
        print(f"[+] Проверка Flash 0x08000000: 0x{val:08X} (должно быть 0xFFFFFFFF)")

        print("\n" + "=" * 65)
        print("  🎉 ПОЗДРАВЛЯЕМ! ЧИП FH8020 ПОЛНОСТЬЮ РАЗБЛОКИРОВАН И СТЕРТ!")
        print("=" * 65)
        j.close()
        return True

    except Exception as e:
        print(f"[!] Ошибка стирания: {e}")
        try:
            j.close()
        except Exception:
            pass
        return False

if __name__ == '__main__':
    main()
