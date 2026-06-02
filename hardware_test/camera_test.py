import cv2
import time
import threading
import numpy as np
from pyzbar.pyzbar import decode, ZBarSymbol

# Import the professional Pi camera library
try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ Error: picamera2 is not installed.")
    print("Run: sudo apt install python3-picamera2")
    exit()

# Global variables to share data safely between threads
current_frame = None
running = True
detected_barcodes = []

def background_scanner():
    """Runs on a separate CPU thread, looking for barcodes every 0.25 seconds."""
    global current_frame, running, detected_barcodes
    
    while running:
        if current_frame is not None:
            try:
                # Copy the frame so the main thread doesn't overwrite it while we scan
                scan_target = current_frame.copy()
                gray = cv2.cvtColor(scan_target, cv2.COLOR_BGR2GRAY)
                # Shrink it to make the math extremely fast
                scan_target = cv2.resize(gray, (320, 240))
                
                barcodes = decode(scan_target, symbols=[
                    ZBarSymbol.QRCODE, ZBarSymbol.EAN13, ZBarSymbol.CODE128])
                
                # Update the global list so the main thread can draw the text
                detected_barcodes = barcodes
            except Exception as e:
                print(f"Scanner error: {e}")
                
        # Sleep to let the Pi's CPU breathe! (4 scans per second)
        time.sleep(0.25)

def run_camera_test():
    global current_frame, running, detected_barcodes
    
    print("Initializing Picamera2 high-speed video stream...")
    
    # 1. Initialize the Camera
    cam = Picamera2()
    
    # 2. Configure for Video Stream (not still photos)
    config = cam.create_video_configuration({"size": (640, 480)})
    cam.configure(config)
    cam.start() # This turns the sensor on and leaves it running!
    print("✅ Camera streaming started.")
    print("Press 'q' in the video window to quit.")
    
    # 3. Start the Background Scanner Thread
    threading.Thread(target=background_scanner, daemon=True).start()
    
    prev_time = time.time()
    
    try:
        while True:
            # Grab the latest frame instantly from the running stream
            raw_frame = cam.capture_array()
            
            # Convert RGB (Picamera2 default) to BGR (OpenCV default)
            frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)

            # Share the frame with our background thread
            current_frame = frame

            # Calculate FPS
            current_time = time.time()
            fps = 1 / (current_time - prev_time)
            prev_time = current_time

            # Draw FPS
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Draw any found barcodes
            for barcode in detected_barcodes:
                data = barcode.data.decode("utf-8")
                cv2.putText(frame, f"Scanned: {data}", (10, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Show Window
            cv2.imshow("High-Speed Camera Test", frame)

            # Quit if 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Cleanup
        running = False # Tell the background thread to stop
        print("Stopping camera...")
        cam.stop()
        cam.close()
        cv2.destroyAllWindows()
        print("Camera hardware released.")

if __name__ == "__main__":
    run_camera_test()