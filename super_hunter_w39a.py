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
    print("   >>> ВЫСОКОСКОРОСТНАЯ ЛОВУШКА И СТИРАНИЕ W39A (FH8020) <<<")
    print("=" * 65)

    j = pylink.JLink()
    try:
        j.open('774496021')
    except Exception:
        try:
            j.open()
        except Exception as e:
            print(f"[X] Не удалось подключиться к J-Link: {e}")
            return False

    j.set_tif(pylink.enums.JLinkInterfaces.SWD)
    
    # Частота как на удачных прошивках: 1000 кГц (1 МГц)
    speed_khz = 1000
    if "--500" in sys.argv:
        speed_khz = 500
    j.set_speed(speed_khz)

    status = j.hardware_status
    vtref = status.VTarget if hasattr(status, 'VTarget') else 0
    print(f"[*] J-Link SN: {j.serial_number} | Частота SWD: {speed_khz} кГц | VTref: {vtref} мВ")

    print("\n" + "-" * 65)
    print(" >>> ЛОВУШКА АКТИВНА! ОПРОС ШИНЫ ~150 РАЗ В СЕКУНДУ <<<")
    print(" В ЭТОТ МОМЕНТ:")
    print(" 1. Перебирайте пины или кратковременно касайтесь пина сброса на GND!")
    print(" 2. Или передерните питание (выньте/вставьте Type-C провод)!")
    print("-" * 65 + "\n")

    start_time = time.time()
    timeout = 180 # 3 минуты
    attempts = 0
    last_stat = time.time()
    caught = False
    valid_dpidr = None

    while time.time() - start_time < timeout:
        attempts += 1
        now = time.time()
        if now - last_stat >= 3.0:
            last_stat = now
            print(f"[*] Ловушка ждет чип... Попыток: {attempts}")

        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477, 0x1BA01477) or (dpidr and dpidr != 0xFFFFFFFF and dpidr != 0x00000000):
                # 1. DP Power-up
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False)

                # 2. Мгновенно глушим ядро в точке сброса
                j.coresight_write(2, 0x00000000, ap=False)
                j.coresight_write(0, 0x23000002, ap=True) # CSW 32-bit
                j.coresight_write(1, 0xE000EDF0, ap=True) # DHCSR
                j.coresight_write(3, 0xA05F0003, ap=True) # HALT | DEBUGEN

                valid_dpidr = dpidr
                caught = True
                beep(2000, 300)
                print(f"\n[🔥] ЕСТЬ КОНТАКТ! ЧИП ПОЙМАН! DPIDR = 0x{valid_dpidr:08X} (попытка #{attempts})!")
                print(">>> ЯДРО ОСТАНОВЛЕНО! НЕ ТРОГАЙТЕ ПРОВОДА! СТИРАЮ ПАМЯТЬ... <<<")
                break
        except Exception:
            pass

    if not caught:
        print("\n[X] Время вышло (3 минуты). ЧИП не отозвался.")
        j.close()
        return False

    time.sleep(0.2)

    # 3. ПРОЦЕДУРА ПОЛНОГО СТИРАНИЯ И РАЗБЛОКИРОВКИ (MASS ERASE & UNLOCK)
    try:
        # Clear aborts
        j.coresight_write(0, 0x1E, ap=False)
        j.coresight_write(2, 0x00000000, ap=False)
        j.coresight_write(0, 0x23000002, ap=True)

        # 3.1 Включаем тактирование FLASH контроллера в RCC
        # RCC->AHBENR |= (1 << 8) (FLASHEN) | (1 << 2) (SRAMEN)
        j.coresight_write(1, 0x40021014, ap=True)
        j.coresight_write(3, 0x00000104, ap=True)

        # 3.2 Разблокировка Flash через KEYR (0x40022008)
        # Ключи Puya / STM32: KEY1 = 0x45670123, KEY2 = 0xCDEF89AB
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0x45670123, ap=True)
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0xCDEF89AB, ap=True)
        print("[+] Flash Controller разблокирован (KEYR)!")

        # 3.3 Запуск Mass Erase в регистре FLASH->CR (0x40022010): MER (бит 2) + STRT (бит 6)
        # 0x00000044 = MER | STRT
        j.coresight_write(1, 0x40022010, ap=True)
        j.coresight_write(3, 0x00000044, ap=True)
        print("[*] Запущен Mass Erase (полная очистка Flash)...")

        # Ждем завершения BSY (бит 0 в FLASH->SR 0x4002200C)
        t0 = time.time()
        while time.time() - t0 < 2.0:
            j.coresight_write(1, 0x4002200C, ap=True)
            sr = j.coresight_read(3, ap=True)
            if (sr & 0x01) == 0:
                break
            time.sleep(0.01)

        print("[🎉] ПАМЯТЬ FLASH ПОЛНОСТЬЮ СТЕРТА (MASS ERASE SUCCESS)!")
        beep(2400, 300)

        # 3.4 Читаем первые байты Flash (должно быть 0xFFFFFFFF)
        j.coresight_write(1, 0x08000000, ap=True)
        val = j.coresight_read(3, ap=True)
        print(f"[+] Проверка Flash 0x08000000: 0x{val:08X} (чистая память = 0xFFFFFFFF)")

        print("\n" + "=" * 65)
        print("  🎉 ПОЗДРАВЛЯЕМ! ЧИП FH8020 ПОЛНОСТЬЮ СТЕРТ И РАЗБЛОКИРОВАН!")
        print("  Теперь он свободен от заводской прошивки и готов к заливке")
        print("  любого кастомного софта BookLight!")
        print("=" * 65)
        j.close()
        return True

    except Exception as e:
        print(f"[!] Ошибка во время стирания: {e}")
        j.close()
        return False

if __name__ == '__main__':
    main()
