"""
weight_sensor.py
HX711 Load Cell driver and WeightValidator for the Smart Shopping Cart.

On Raspberry Pi  : uses RPi.GPIO + hx711 library (real hardware).
On other systems : falls back to SimulatedScale for development.
"""

import time
import platform

# ── Platform Detection ────────────────────────────────────────────────────────
IS_RASPBERRY_PI = platform.system() == "Linux" and platform.machine().startswith("aarch")

# ── GPIO Pin Configuration ────────────────────────────────────────────────────
# Connect HX711 as follows:
#   HX711 DT  (Data)  → GPIO 5  (Pin 29)
#   HX711 SCK (Clock) → GPIO 6  (Pin 31)
#   HX711 VCC         → 5V (Pin 2 or 4)
#   HX711 GND         → GND (Pin 6 or any GND pin)
HX711_DT_PIN  = 5   # BCM numbering
HX711_SCK_PIN = 6   # BCM numbering

# ── Calibration ───────────────────────────────────────────────────────────────
# After first boot, run:   python weight_sensor.py --calibrate
# and update CALIBRATION_FACTOR with the printed value.
CALIBRATION_FACTOR = -7050   # Update after running calibration!
WEIGHT_OFFSET      = 0       # Tare offset (auto-set on startup)

# ── Validation Thresholds ─────────────────────────────────────────────────────
TOLERANCE_PERCENT = 20        # ±20% of expected weight
MIN_TOLERANCE_GRAMS = 10      # Minimum ±10g absolute tolerance


# =============================================================================
#  Real Hardware Scale (Raspberry Pi)
# =============================================================================
class HX711Scale:
    """Wraps the hx711 library for real load-cell readings."""

    def __init__(self):
        try:
            from hx711 import HX711
            self._hx = HX711(dout_pin=HX711_DT_PIN, pd_sck_pin=HX711_SCK_PIN)
            self._hx.set_scale_ratio(CALIBRATION_FACTOR)
            self.tare()
            self._available = True
            print("[WeightSensor] HX711 initialised successfully.")
        except Exception as e:
            print(f"[WeightSensor] HX711 init failed: {e}")
            self._available = False

    def tare(self):
        """Zero the scale (call when cart is empty or after removing item)."""
        if self._available:
            try:
                self._hx.zero()
                print("[WeightSensor] Scale tared (zeroed).")
            except Exception as e:
                print(f"[WeightSensor] Tare failed: {e}")

    def read_grams(self, samples: int = 5) -> float:
        """Return averaged weight reading in grams. Returns 0.0 on error."""
        if not self._available:
            return 0.0
        try:
            readings = self._hx.get_weight_mean(samples)
            return max(0.0, round(readings, 1))
        except Exception as e:
            print(f"[WeightSensor] Read error: {e}")
            return 0.0

    def stable_reading(self, timeout: float = 5.0, stable_window: float = 0.5,
                       tolerance: float = 2.0) -> float:
        """
        Block until the reading is stable (not changing by more than
        `tolerance` grams for `stable_window` seconds), then return it.
        Falls back to a single snapshot after `timeout` seconds.
        """
        deadline = time.time() + timeout
        last_value = self.read_grams()
        stable_since = time.time()

        while time.time() < deadline:
            time.sleep(0.1)
            current = self.read_grams()
            if abs(current - last_value) <= tolerance:
                if time.time() - stable_since >= stable_window:
                    return current
            else:
                last_value = current
                stable_since = time.time()

        return self.read_grams()  # fallback single read


# =============================================================================
#  Simulated Scale (Development / Windows / Mac)
# =============================================================================
class SimulatedScale:
    """
    Fake scale for development without hardware.
    Simulates realistic weight accumulation so you can test
    the validation logic without a physical load cell.
    """

    def __init__(self):
        self._accumulated_grams = 0.0
        self._pending_addition  = 0.0
        print("[WeightSensor] Using SIMULATED scale (no hardware detected).")

    def tare(self):
        self._accumulated_grams = 0.0
        print("[WeightSensor] Simulated scale tared.")

    def read_grams(self, samples: int = 5) -> float:
        return round(self._accumulated_grams + self._pending_addition, 1)

    def stable_reading(self, timeout: float = 5.0, **_) -> float:
        """Simulate a short delay then return current weight."""
        time.sleep(0.4)
        return self.read_grams()

    # ── Simulation helpers (not used in production) ──────────────────────────
    def simulate_add(self, grams: float):
        """Call this to fake placing an item on the scale."""
        self._accumulated_grams += grams
        self._pending_addition = 0.0

    def simulate_noise(self, grams: float):
        """Simulate a wrong item being placed (triggers validation failure)."""
        self._pending_addition = grams


# =============================================================================
#  Weight Validator
# =============================================================================
class WeightValidator:
    """
    High-level interface used by cart.py.

    Typical usage:
        validator = WeightValidator()
        baseline = validator.capture_baseline()
        # ... user places item in cart ...
        result = validator.validate(expected_grams, baseline)
        if result['valid']:
            # add to cart
        else:
            # show warning
    """

    def __init__(self):
        if IS_RASPBERRY_PI:
            self.scale = HX711Scale()
        else:
            self.scale = SimulatedScale()

    # ─── Public API ───────────────────────────────────────────────────────────

    def tare(self):
        """Zero the scale. Call once on startup and after each complete checkout."""
        self.scale.tare()

    def capture_baseline(self) -> float:
        """
        Read and return the current weight before an item is added.
        Store this and pass it to validate() after the item is placed.
        """
        return self.scale.stable_reading()

    def validate(self, expected_grams: float, baseline_grams: float,
                 timeout: float = 8.0) -> dict:
        """
        Wait for a stable reading then compare the weight change against
        the expected weight.

        Returns:
            {
              'valid':    bool,
              'expected': float,   # grams expected
              'actual':   float,   # grams measured (delta)
              'delta':    float,   # actual − expected
              'message':  str,
            }
        """
        # Give user time to place the item
        new_weight = self.scale.stable_reading(timeout=timeout)
        delta      = new_weight - baseline_grams
        tolerance  = max(MIN_TOLERANCE_GRAMS,
                         expected_grams * TOLERANCE_PERCENT / 100)

        diff   = abs(delta - expected_grams)
        valid  = diff <= tolerance

        if valid:
            msg = f"Weight OK: expected {expected_grams:.0f}g, detected {delta:.0f}g"
        elif delta < 0:
            msg = (f"Weight mismatch: scale decreased by {abs(delta):.0f}g. "
                   "Make sure the item is in the cart.")
        else:
            msg = (f"Weight mismatch: expected ~{expected_grams:.0f}g, "
                   f"detected {delta:.0f}g (Δ {diff:.0f}g). "
                   "Possible wrong item or quantity.")

        print(f"[WeightValidator] {msg}")
        return {
            "valid":    valid,
            "expected": expected_grams,
            "actual":   delta,
            "delta":    delta - expected_grams,
            "message":  msg,
        }

    def unit_to_grams(self, value: float, unit: str) -> float:
        """Convert a product's quantity_value + quantity_unit to grams."""
        unit = unit.lower().strip()
        conversions = {
            "g":   1.0,
            "kg":  1000.0,
            "mg":  0.001,
            "oz":  28.3495,
            "lb":  453.592,
            "ml":  1.0,   # Approximate: 1ml ≈ 1g for water-based products
            "l":   1000.0,
            "fl_oz": 29.5735,
        }
        return value * conversions.get(unit, 1.0)


# =============================================================================
#  CLI Calibration Helper
# =============================================================================
def calibrate():
    """
    Interactive calibration routine.
    Run from terminal:  python weight_sensor.py --calibrate
    """
    try:
        from hx711 import HX711
    except ImportError:
        print("hx711 library not found. Run: pip install hx711")
        return

    print("\n=== HX711 Calibration Wizard ===")
    hx = HX711(dout_pin=HX711_DT_PIN, pd_sck_pin=HX711_SCK_PIN)

    input("Remove ALL items from the scale and press Enter...")
    hx.zero()
    print("Scale zeroed.")

    weight_str = input("Enter the weight of your calibration object in grams: ")
    known_weight = float(weight_str)

    input(f"Place the {known_weight}g calibration object on the scale and press Enter...")

    raw = hx.get_raw_data_mean(20)
    factor = raw / known_weight
    print(f"\n✅ Calibration complete!")
    print(f"   Raw reading     : {raw:.1f}")
    print(f"   CALIBRATION_FACTOR = {factor:.1f}")
    print(f"\nUpdate CALIBRATION_FACTOR in weight_sensor.py to: {factor:.1f}")

    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
    except Exception:
        pass


if __name__ == "__main__":
    import sys
    if "--calibrate" in sys.argv:
        calibrate()
    else:
        # Quick test
        print("=== Weight Sensor Test ===")
        v = WeightValidator()
        print(f"Current reading: {v.capture_baseline():.1f}g")
        print("unit_to_grams(500, 'ml') =", v.unit_to_grams(500, "ml"), "g")
        print("unit_to_grams(1, 'kg')   =", v.unit_to_grams(1, "kg"), "g")
