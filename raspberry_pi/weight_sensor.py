"""
weight_sensor.py — HX711 driver for Smart Shopping Cart (Raspberry Pi 4)

AUTO-DETECTS which hx711 library is installed:
  • tatobari/hx711py   → set_reference_unit / get_weight / power_down / power_up
  • gandalf15/HX711    → set_scale_ratio / get_raw_data_mean / zero

HOW TO FIND YOUR INSTALLED LIBRARY:
    pip show hx711
    pip show HX711

ONLY ONE PROCESS SHOULD USE GPIO 5+6 AT A TIME.
Close/kill preview_weight.py before running the cart app.
"""

import time, threading, platform

# ── Pi detection: /proc/cpuinfo covers 32-bit AND 64-bit OS ──────────────────
def _is_raspberry_pi() -> bool:
    for path in ("/proc/device-tree/model", "/proc/cpuinfo"):
        try:
            with open(path, "r", errors="ignore") as f:
                if any(k in f.read() for k in ("Raspberry Pi", "BCM2")):
                    return True
        except Exception:
            pass
    m = platform.machine().lower()
    return m.startswith("aarch") or m.startswith("arm")

IS_RASPBERRY_PI = _is_raspberry_pi()
print("[WeightSensor] IS_RASPBERRY_PI =", IS_RASPBERRY_PI,
      " | machine =", platform.machine())

HX711_DT_PIN   = 5
HX711_SCK_PIN  = 6
REFERENCE_UNIT = 107.0303   # tatobari: raw-per-gram
CALIBRATION_FACTOR = -7050  # gandalf15 raw mode fallback (update after recal)

TOLERANCE_PERCENT   = 20
MIN_TOLERANCE_GRAMS = 10


# =============================================================================
# HX711Scale  —  auto-detect library, background reader thread
# =============================================================================
class HX711Scale:
    """
    Works with BOTH hx711 library flavours:
      tatobari  →  set_reference_unit / get_weight / power_down / power_up
      gandalf15 →  set_scale_ratio / get_raw_data_mean / zero

    All chip I/O runs inside _reader_loop (daemon thread).
    read_grams() returns the cached value — instant, Tkinter-safe.
    """

    def __init__(self):
        self._last_grams  = 0.0
        self._lock        = threading.Lock()
        self._tare_event  = threading.Event()
        self._running     = False
        self._available   = False
        self._api         = None
        self._hx          = None

        if not IS_RASPBERRY_PI:
            print("[WeightSensor] Not a Pi — hardware skipped.")
            return

        print("[WeightSensor] Initialising HX711 DT=GPIO%d SCK=GPIO%d ..."
              % (HX711_DT_PIN, HX711_SCK_PIN))
        try:
            import RPi.GPIO as GPIO
            from hx711 import HX711

            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Positional args work for BOTH tatobari and gandalf15
            self._hx = HX711(HX711_DT_PIN, HX711_SCK_PIN)

            # ── Auto-detect library by inspecting available methods ──────────
            if hasattr(self._hx, "set_reference_unit"):
                # ── Tatobari/hx711py ────────────────────────────────────────
                self._api = "tatobari"
                print("[WeightSensor] Library detected: tatobari/hx711py")
                try:
                    self._hx.set_reading_format("MSB", "MSB")
                except AttributeError:
                    pass
                self._hx.set_reference_unit(REFERENCE_UNIT)
                self._hx.reset()
                print("[WeightSensor] Taring (keep scale empty)...")
                self._hx.tare()

            elif hasattr(self._hx, "zero") or hasattr(self._hx, "set_scale_ratio"):
                # ── Gandalf15/HX711_Python3 ─────────────────────────────────
                self._api = "gandalf15"
                print("[WeightSensor] Library detected: gandalf15/HX711_Python3")
                if hasattr(self._hx, "set_scale_ratio"):
                    # Use tatobari's reference_unit — same physical meaning
                    self._hx.set_scale_ratio(REFERENCE_UNIT)
                    print("[WeightSensor] set_scale_ratio(%.4f)" % REFERENCE_UNIT)
                print("[WeightSensor] Taring (keep scale empty)...")
                self._hx.zero()

            else:
                raise RuntimeError(
                    "Unknown HX711 library. Methods found: " +
                    str([m for m in dir(self._hx) if not m.startswith("_")])
                )

            self._available = True
            self._running   = True
            t = threading.Thread(target=self._reader_loop, daemon=True,
                                 name="HX711-reader")
            t.start()
            print("[WeightSensor] Tare done. Background reader started. API=%s"
                  % self._api)

        except Exception as e:
            print("[WeightSensor] *** INIT FAILED: %s ***" % e)
            import traceback; traceback.print_exc()

    # ─────────────────────────────────────────────────────────────────────────
    # Background reader — ONE thread, ONE GPIO owner, no contention
    # ─────────────────────────────────────────────────────────────────────────
    def _reader_loop(self):
        print("[WeightSensor] Reader thread running (API=%s)" % self._api)
        while self._running:

            # ── Tare request ─────────────────────────────────────────────────
            if self._tare_event.is_set():
                try:
                    if self._api == "tatobari":
                        self._hx.tare()
                    else:
                        self._hx.zero()
                    with self._lock:
                        self._last_grams = 0.0
                    print("[WeightSensor] Tare complete.")
                except Exception as e:
                    print("[WeightSensor] Tare error:", e)
                finally:
                    self._tare_event.clear()
                continue

            # ── Read ─────────────────────────────────────────────────────────
            try:
                if self._api == "tatobari":
                    # get_weight(1) × 5 with power cycles — identical to
                    # preview_weight.py's LoadCell.read_grams(samples=5)
                    total, n = 0.0, 0
                    for _ in range(5):
                        val = self._hx.get_weight(1)
                        total += val
                        n += 1
                        self._hx.power_down()
                        self._hx.power_up()
                        time.sleep(0.05)
                    if n > 0:
                        grams = round(total / n, 1)
                        with self._lock:
                            self._last_grams = grams

                else:  # gandalf15
                    if hasattr(self._hx, "get_weight_mean"):
                        # Calibrated path — uses set_scale_ratio value
                        result = self._hx.get_weight_mean(5)
                        if result is not False and result is not None:
                            with self._lock:
                                self._last_grams = round(float(result), 1)
                    else:
                        # Raw fallback — divide by REFERENCE_UNIT manually
                        raw = self._hx.get_raw_data_mean(5)
                        if raw is not False and raw is not None:
                            with self._lock:
                                self._last_grams = round(
                                    float(raw) / REFERENCE_UNIT, 1)
                    time.sleep(0.1)

            except Exception as e:
                print("[WeightSensor] Read error:", e)
                time.sleep(0.5)

    # ── Public API ────────────────────────────────────────────────────────────
    def read_grams(self, samples=1) -> float:
        """Non-blocking — returns cached value from reader thread."""
        with self._lock:
            return self._last_grams

    def tare(self):
        """Signals reader thread to tare. Returns immediately."""
        if self._available:
            self._tare_event.set()
            print("[WeightSensor] Tare requested.")

    def stable_reading(self, timeout=3.0, **_) -> float:
        if not self._available:
            return 0.0
        deadline = time.time() + min(timeout, 3.0)
        prev = self.read_grams()
        while time.time() < deadline:
            time.sleep(0.15)
            curr = self.read_grams()
            if abs(curr - prev) < 2.0:
                return curr
            prev = curr
        return self.read_grams()

    def cleanup(self):
        self._running = False
        time.sleep(0.3)
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except Exception:
            pass


# =============================================================================
# SimulatedScale — used on non-Pi
# =============================================================================
class SimulatedScale:
    def __init__(self):
        self._grams = 0.0
        print("[WeightSensor] SIMULATED scale (no hardware).")

    def read_grams(self, samples=1): return round(self._grams, 1)
    def tare(self): self._grams = 0.0
    def stable_reading(self, timeout=1.0, **_):
        time.sleep(0.1); return self.read_grams()
    def simulate_add(self, g): self._grams += g
    def cleanup(self): pass


# =============================================================================
# LoadCell — used ONLY by preview_weight.py (standalone, NOT inside cart app)
# Also auto-detects library.
# =============================================================================
class LoadCell:
    """
    Single-user, blocking driver for preview_weight.py.
    DO NOT run simultaneously with the cart app (GPIO conflict).
    """
    def __init__(self, dout_pin=HX711_DT_PIN, sck_pin=HX711_SCK_PIN,
                 reference_unit=REFERENCE_UNIT):
        import RPi.GPIO as GPIO
        from hx711 import HX711
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self._hx = HX711(dout_pin, sck_pin)
        self._ref = reference_unit

        if hasattr(self._hx, "set_reference_unit"):
            self._api = "tatobari"
            try:
                self._hx.set_reading_format("MSB", "MSB")
            except AttributeError:
                pass
            self._hx.set_reference_unit(reference_unit)
            self._hx.reset()
            self._hx.tare()
        elif hasattr(self._hx, "zero") or hasattr(self._hx, "set_scale_ratio"):
            self._api = "gandalf15"
            if hasattr(self._hx, "set_scale_ratio"):
                self._hx.set_scale_ratio(reference_unit)
            self._hx.zero()
        else:
            self._api = "unknown"
        print("[HX711] LoadCell ready. API=%s" % self._api)

    def read_grams(self, samples: int = 5) -> float:
        total = 0.0
        if self._api == "tatobari":
            for _ in range(samples):
                total += self._hx.get_weight(1)
                self._hx.power_down()
                self._hx.power_up()
                time.sleep(0.05)
            return total / samples
        else:  # gandalf15
            if hasattr(self._hx, "get_weight_mean"):
                r = self._hx.get_weight_mean(samples)
                return round(float(r), 1) if r is not False else 0.0
            raw = self._hx.get_raw_data_mean(samples)
            return round(float(raw) / self._ref, 1) if raw is not False else 0.0

    def cleanup(self):
        import RPi.GPIO as GPIO
        GPIO.cleanup()


# =============================================================================
# WeightValidator — used by cart.py
# =============================================================================
class WeightValidator:
    def __init__(self):
        self.scale = HX711Scale() if IS_RASPBERRY_PI else SimulatedScale()
        print("[WeightValidator] Scale: %s  available=%s  api=%s" % (
            type(self.scale).__name__,
            getattr(self.scale, "_available", "N/A"),
            getattr(self.scale, "_api", "N/A")))

    def tare(self): self.scale.tare()
    def capture_baseline(self): return self.scale.read_grams()

    def unit_to_grams(self, value: float, unit: str) -> float:
        table = {
            "g": 1.0, "kg": 1000.0, "mg": 0.001,
            "oz": 28.3495, "lb": 453.592,
            "ml": 1.0, "l": 1000.0, "fl_oz": 29.5735,
        }
        return float(value) * table.get(str(unit).lower().strip(), 1.0)


# =============================================================================
# CLI  —  python3 weight_sensor.py  to verify hardware
# =============================================================================
if __name__ == "__main__":
    import sys

    if "--calibrate" in sys.argv:
        # Quick reference-unit calibration
        print("\n=== Calibration ===")
        try:
            import RPi.GPIO as GPIO
            from hx711 import HX711
            GPIO.setmode(GPIO.BCM); GPIO.setwarnings(False)
            hx = HX711(HX711_DT_PIN, HX711_SCK_PIN)
            api = "tatobari" if hasattr(hx, "set_reference_unit") else "gandalf15"
            hx.set_reference_unit(1.0) if api == "tatobari" else None
            input("Remove all weight. Press Enter to zero/tare...")
            hx.tare() if api == "tatobari" else hx.zero()
            known = float(input("Weight of calibration object (g): "))
            input("Place object. Press Enter...")
            raw_total = 0.0
            N = 10
            for i in range(N):
                v = hx.get_weight(1) if api == "tatobari" else None
                if v is None:
                    v = hx.get_raw_data_mean(1)
                raw_total += v
                if api == "tatobari":
                    hx.power_down(); hx.power_up()
                time.sleep(0.1)
            factor = (raw_total / N) / known
            print("\nREFERENCE_UNIT = %.4f" % factor)
            print("Update REFERENCE_UNIT in weight_sensor.py")
            GPIO.cleanup()
        except Exception as e:
            print("Calibration error:", e)
    else:
        print("\n=== HX711 Quick Test ===")
        v = WeightValidator()
        if not getattr(v.scale, "_available", False):
            print("\nERROR: HX711 not available. Check wiring and library.\n")
            print("Run:  pip show hx711    to see installed library")
            print("      pip show HX711   (gandalf15 version)")
        else:
            print("\nWaiting 1 s for first reading...")
            time.sleep(1.0)
            print("Place/remove items to verify readings:\n")
            for i in range(20):
                time.sleep(0.4)
                g = v.scale.read_grams()
                bar = "#" * max(0, int(g / 5))
                print("  [%2d]  %7.1f g  %s" % (i + 1, g, bar))
            print("\nIf all 0.0 → calibration factor wrong. Run --calibrate")
