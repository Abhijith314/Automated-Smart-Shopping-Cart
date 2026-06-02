# weight_sensor.py

import time
import RPi.GPIO as GPIO
from hx711 import HX711   # adjust import if your package name differs


class LoadCell:
    """
    Simple wrapper around HX711 for a single 20kg load cell.
    Uses channel A, gain 128, and returns weight in grams.
    """

    def __init__(self, dout_pin=5, sck_pin=6, reference_unit=105.5373):
        """
        dout_pin, sck_pin: BCM GPIO numbers (NOT physical pin numbers).
        reference_unit: calibration factor (raw units per gram).
        """
        self.dout_pin = dout_pin
        self.sck_pin = sck_pin
        
        GPIO.setmode(GPIO.BCM)          # ← ADD THIS LINE before HX711 init
        GPIO.setwarnings(False)         # optional: suppresses "already in use" warnings
        
        self.hx = HX711(self.dout_pin, self.sck_pin)

        # Some libs need reading format, some don't; if unsupported, remove this line.
        try:
            self.hx.set_reading_format("MSB", "MSB")
        except AttributeError:
            pass

        self.reference_unit = reference_unit
        self.hx.set_reference_unit(self.reference_unit)
        self.hx.reset()
        self.hx.tare()
        print("[HX711] Tare done, zero set.")

    def read_grams(self, samples=5):
        """
        Returns average weight in grams over N samples.
        """
        total = 0
        for _ in range(samples):
            val = self.hx.get_weight(1)
            total += val
            self.hx.power_down()
            self.hx.power_up()
            time.sleep(0.05)

        avg_raw = total / samples
        grams = avg_raw
        return grams

    def cleanup(self):
        GPIO.cleanup()


def interactive_calibration():
    """
    1. Empty platform -> tare
    2. Place known weight -> compute reference unit
    """
    lc = LoadCell(dout_pin=5, sck_pin=6, reference_unit=1.0)

    try:
        input("Remove all weight from platform and press ENTER to tare...")
        lc.hx.tare()
        print("Tare done.")

        known = float(input("Place a known weight (grams) and type its value: "))

        print("Collecting samples...")
        raw_vals = []
        for i in range(10):
            raw = lc.hx.get_weight(1)
            raw_vals.append(raw)
            print(f"{i+1}: {raw}")
            lc.hx.power_down()
            lc.hx.power_up()
            time.sleep(0.1)

        avg_raw = sum(raw_vals) / len(raw_vals)
        ref_unit = avg_raw / known
        print(f"\nCalculated reference_unit = {ref_unit:.4f}")
        print("Use this value in LoadCell(reference_unit=...).")

    finally:
        lc.cleanup()


if __name__ == "__main__":
    interactive_calibration()
