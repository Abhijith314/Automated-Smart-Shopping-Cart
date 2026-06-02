# preview_weight.py
from weight_sensor import LoadCell

lc = LoadCell(dout_pin=5, sck_pin=6, reference_unit=107.0303)

print("Live weight preview — press Ctrl+C to stop\n")
try:
    while True:
        grams = lc.read_grams(samples=5)
        kg = grams / 1000
        print(f"\rWeight: {grams:8.1f} g  ({kg:.3f} kg)   ", end="", flush=True)

except KeyboardInterrupt:
    print("\nStopped.")
    lc.cleanup()
