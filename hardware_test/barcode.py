import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import winsound

def find_working_camera():
    # Try indices in order of likelihood
    for index in [1, 2, 0]:
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            success, frame = cap.read()
            if success:
                print(f"Successfully started stream on Camera Index: {index}")
                return cap, index
            cap.release()
    return None, None

cap, active_index = find_working_camera()

if not cap:
    print("Could not find an active camera stream. Please ensure DroidCam Client is 'Started'.")
    exit()

last_barcode = None

while True:
    success, frame = cap.read()
    if not success:
        break

    # Standardize frame size for pyzbar performance
    # Phone cameras can be 1080p+, which slows down decoding
    display_frame = cv2.resize(frame, (640, 480))
    gray = cv2.cvtColor(display_frame, cv2.COLOR_BGR2GRAY)

    # Use specific symbols to avoid the 'databar' error
    detectedBarcodes = decode(gray, symbols=[
        ZBarSymbol.QRCODE, 
        ZBarSymbol.EAN13, 
        ZBarSymbol.CODE128
    ])

    if not detectedBarcodes:
        last_barcode = None
    else:
        for barcode in detectedBarcodes:
            barcode_data = barcode.data.decode('utf-8')
            
            # Draw bounding box and text
            (x, y, w, h) = barcode.rect
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(display_frame, barcode_data, (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            if barcode_data != last_barcode:
                print(f"Scanned: {barcode_data}")
                winsound.Beep(1000, 200) 
                last_barcode = barcode_data

    cv2.imshow(f'Scanner (Camera {active_index})', display_frame)

    # Exit logic: press 'q' or click the 'X'
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or cv2.getWindowProperty(f'Scanner (Camera {active_index})', cv2.WND_PROP_VISIBLE) < 1:
        break

cap.release()
cv2.destroyAllWindows()