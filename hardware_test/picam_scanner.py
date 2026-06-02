import cv2
import time
import threading
import numpy as np
from pyzbar.pyzbar import decode, ZBarSymbol

try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ Error: picamera2 is not installed.")
    exit()

# --- CONFIGURATION AREA ---
# Increase this number to make the box bigger. 
# Keep it smaller than 480 (the height of the video) to stay centered.
BOX_SIZE = 400 
SCAN_DELAY = 3.0 

running = True
current_frame = None
detected_barcodes = []
last_scanned_times = {}

def background_scanner():
    global current_frame, running, detected_barcodes, last_scanned_times
    
    while running:
        if current_frame is not None:
            try:
                h, w = current_frame.shape[:2]
                # Calculate coordinates based on the current BOX_SIZE
                x1 = int(w/2 - BOX_SIZE/2)
                y1 = int(h/2 - BOX_SIZE/2)
                x2 = int(w/2 + BOX_SIZE/2)
                y2 = int(h/2 + BOX_SIZE/2)
                
                # Crop the ROI (Region of Interest)
                roi = current_frame[y1:y2, x1:x2]
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                
                barcodes = decode(gray_roi, symbols=[
                    ZBarSymbol.QRCODE, ZBarSymbol.EAN13, ZBarSymbol.CODE128])
                
                current_time = time.time()
                for barcode in barcodes:
                    data = barcode.data.decode("utf-8")
                    if data not in last_scanned_times or (current_time - last_scanned_times[data]) > SCAN_DELAY:
                        print(f"✅ Scanned: {data}")
                        last_scanned_times[data] = current_time
                
                detected_barcodes = barcodes
                
            except Exception as e:
                print(f"Scanner error: {e}")
                
        time.sleep(0.1)

def run_picam_scanner():
    global current_frame, running, detected_barcodes
    
    cam = Picamera2()
    # Camera resolution is set to 640x480
    config = cam.create_video_configuration({"size": (640, 480)})
    cam.configure(config)
    cam.start()
    
    threading.Thread(target=background_scanner, daemon=True).start()
    
    prev_time = time.time()
    
    try:
        while True:
            raw_frame = cam.capture_array()
            frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)
            current_frame = frame.copy()

            fps = 1 / (time.time() - prev_time)
            prev_time = time.time()

            # Dynamic UI drawing based on BOX_SIZE
            h, w = frame.shape[:2]
            x1, y1 = int(w/2 - BOX_SIZE/2), int(h/2 - BOX_SIZE/2)
            x2, y2 = int(w/2 + BOX_SIZE/2), int(h/2 + BOX_SIZE/2)

            if detected_barcodes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                for barcode in detected_barcodes:
                    data = barcode.data.decode("utf-8")
                    cv2.putText(frame, data, (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "Align Barcode", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("PiCam Barcode Scanner", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        running = False
        cam.stop()
        cam.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run_picam_scanner()
