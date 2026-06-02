"""
cart.py – Smart Cart Dashboard
Display  : 5-inch 800x480 Raspberry Pi touchscreen
Camera   : Picamera2 (Pi) or cv2.VideoCapture (desktop) — preview at BOTTOM
Scanner  : Background decode thread with ROI box + 3s debounce
Weight   : Live HX711 polling after barcode scan (no race condition)

Workflow (matches System-Workflow.jpg):
  1. Scan barcode → fetch product from SQLite → show ProductPopup
  2. User selects quantity and presses CONFIRM
  3. Baseline weight is captured immediately on confirm
  4. Status bar shows live "Xg detected / Yg expected" every 500ms
  5. When delta matches expected (±20% / min 10g) → auto-add to cart
  6. 15s timeout → WeightCheckPopup with staff override option
"""

import os, time, platform, threading, sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, font
import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
from PIL import Image, ImageTk
from weight_sensor import WeightValidator

IS_RASPBERRY_PI = platform.system() == "Linux" and (platform.machine().startswith("aarch") or platform.machine().startswith("arm"))

# ── Scanner settings (from picam_scanner.py) ─────────────────────────────────
BOX_SIZE   = 400    # ROI bounding box pixels
SCAN_DELAY = 3.0    # seconds before same barcode fires again

# ── Weight tolerance (mirrors weight_sensor.py) ───────────────────────────────
TOLERANCE_PERCENT    = 20
MIN_TOLERANCE_GRAMS  = 10
WEIGHT_WAIT_TIMEOUT  = 15.0   # seconds to wait for item placement
WEIGHT_STABLE_DELAY  = 0.5    # poll interval (seconds)

# ── Theme ─────────────────────────────────────────────────────────────────────
THEME = {
    "bg":            "#101622",
    "card":          "#151a25",
    "primary":       "#135bec",
    "primary_hover": "#2563eb",
    "white":         "#ffffff",
    "gray":          "#92a4c9",
    "success":       "#10b981",
    "danger":        "#ef4444",
    "warning":       "#f59e0b",
}

def beep():
    try:
        if platform.system() == "Windows":
            import winsound; winsound.Beep(1000, 200)
        elif platform.system() == "Linux":
            os.system("echo -e '\a'")
    except Exception:
        pass


# =============================================================================
# Camera stream classes
# =============================================================================
class PiCameraStream:
    """Picamera2 – background capture thread for Raspberry Pi."""
    def __init__(self):
        from picamera2 import Picamera2
        self._cam = Picamera2()
        self._cam.configure(self._cam.create_video_configuration({"size": (640, 480)}))
        self._cam.start()
        self.frame   = None
        self.running = True
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            raw        = self._cam.capture_array()
            self.frame = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)

    def read(self): return self.frame

    def stop(self):
        self.running = False
        try: self._cam.stop(); self._cam.close()
        except Exception: pass


class DesktopCameraStream:
    """cv2.VideoCapture – background capture thread for desktop testing."""
    def __init__(self, index=0):
        self.cap     = cv2.VideoCapture(index)
        self.frame   = None
        self.running = True
        _, self.frame = self.cap.read()
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret: self.frame = frame

    def read(self): return self.frame

    def stop(self):
        self.running = False
        self.cap.release()


# =============================================================================
# SmartCartApp
# =============================================================================
class SmartCartApp(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg=THEME["bg"])

        # Cart state
        self.cart_items  = {}
        self.stop_scanner = True

        # Camera state
        self._cam              = None
        self._cam_photo        = None
        self._last_scanned     = {}
        self._current_frame    = None
        self._detected_barcodes = []
        self._decode_lock      = threading.Lock()

        # Weight-wait state
        self._weight_wait_active = False   # True while polling for item placement
        self._baseline_weight    = 0.0

        # Fonts scaled for 800x480
        self.fonts = {
            "header": font.Font(family="Helvetica", size=13, weight="bold"),
            "sub":    font.Font(family="Helvetica", size=10),
            "table":  font.Font(family="Arial",     size=9),
            "total":  font.Font(family="Arial",     size=11, weight="bold"),
            "btn":    font.Font(family="Helvetica", size=9,  weight="bold"),
        }

        self.weight_validator = WeightValidator()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._configure_styles()
        self._create_widgets()
        self._update_totals()
        self._toggle_cart_view()
        self._poll_weight()       # start live weight display

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def on_show(self):
        if not self.stop_scanner:
            return
        self.stop_scanner = False
        self.update_status("Starting camera…")
        self._start_camera()

    # ── Styles ─────────────────────────────────────────────────────────────
    def _configure_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame",     background=THEME["bg"])
        s.configure("TLabel",     background=THEME["bg"], foreground=THEME["white"])
        s.configure("Card.TFrame",background=THEME["card"], relief="flat")
        s.configure("Treeview",
                    background=THEME["card"], fieldbackground=THEME["card"],
                    foreground=THEME["white"], font=self.fonts["table"],
                    rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading",
                    background=THEME["bg"], foreground=THEME["gray"],
                    font=("Helvetica", 8, "bold"))
        s.map("Treeview", background=[("selected", THEME["primary"])])
        s.configure("TButton",
                    font=self.fonts["btn"], padding=6,
                    borderwidth=0, background=THEME["card"], foreground=THEME["gray"])
        s.map("TButton",
              background=[("active", THEME["primary"]), ("pressed", THEME["primary_hover"])],
              foreground=[("active", THEME["white"])])
        s.configure("Accent.TButton",  background=THEME["primary"],  foreground=THEME["white"])
        s.map("Accent.TButton",  background=[("active", THEME["primary_hover"])])
        s.configure("Success.TButton", background=THEME["success"],  foreground=THEME["white"])
        s.configure("Danger.TButton",  background=THEME["danger"],   foreground=THEME["white"])
        s.configure("Totals.TFrame",   background=THEME["card"])
        s.configure("Totals.TLabel",   background=THEME["card"],
                    foreground=THEME["gray"], font=self.fonts["sub"])
        s.configure("GrandTotal.TLabel", background=THEME["card"],
                    foreground=THEME["primary"], font=self.fonts["total"])

    # ── Widgets ────────────────────────────────────────────────────────────
    def _create_widgets(self):
        # ── Outer frame ───────────────────────────────────────────────────
        mf = ttk.Frame(self, padding="8 6 8 0")   # tight padding for small screen
        mf.grid(row=0, column=0, sticky="nsew")
        mf.columnconfigure(0, weight=1)
        mf.rowconfigure(1, weight=1)               # cart table stretches

        # ── Row 0: Header ─────────────────────────────────────────────────
        hdr = ttk.Frame(mf)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        hdr.columnconfigure(0, weight=1)

        ttk.Label(hdr, text="SMART CART DASHBOARD",
                  font=self.fonts["header"]).grid(row=0, column=0, sticky="w")

        self.weight_display = tk.Label(
            hdr, text="⚖ 0.0 g",
            bg=THEME["card"], fg=THEME["gray"],
            font=("Arial", 10), padx=8, pady=2)
        self.weight_display.grid(row=0, column=1, sticky="e")

        # ── Row 1: Cart table ─────────────────────────────────────────────
        self.cart_frame = ttk.Frame(mf, style="Card.TFrame")
        self.cart_frame.grid(row=1, column=0, sticky="nsew")
        self.cart_frame.columnconfigure(0, weight=1)
        self.cart_frame.rowconfigure(0, weight=1)

        cols = ("name", "qty", "price", "disc", "total", "wt")
        self.tree = ttk.Treeview(self.cart_frame, columns=cols,
                                 show="headings", height=5)
        for col, label, w in [
            ("name",  "PRODUCT",   200),
            ("qty",   "QTY",        40),
            ("price", "PRICE",      80),
            ("disc",  "DISC",       60),
            ("total", "TOTAL",      80),
            ("wt",    "WEIGHT",     60),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor="center")
        self.tree.column("name", anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.empty_cart_label = ttk.Label(
            mf, text="CART IS EMPTY",
            font=("Helvetica", 14), foreground=THEME["gray"], anchor="center")

        # ── Row 2: Totals ─────────────────────────────────────────────────
        tot = ttk.Frame(mf, padding="10 4", style="Totals.TFrame")
        tot.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        tot.columnconfigure((0, 1, 2, 3), weight=1)

        self.subtotal_label = ttk.Label(tot, text="Subtotal: ₹0.00",
                                        style="Totals.TLabel")
        self.subtotal_label.grid(row=0, column=0, sticky="w")
        self.saved_label = ttk.Label(tot, text="Saved: ₹0.00",
                                     style="Totals.TLabel")
        self.saved_label.grid(row=0, column=1, sticky="w")
        self.total_label = ttk.Label(tot, text="Total: ₹0.00",
                                     style="GrandTotal.TLabel")
        self.total_label.grid(row=0, column=3, sticky="e")

        # ── Row 3: Buttons ────────────────────────────────────────────────
        btn = ttk.Frame(mf)
        btn.grid(row=3, column=0, sticky="ew", pady=4)
        btn.columnconfigure((0, 1, 2, 3, 4), weight=1)

        ttk.Button(btn, text="📷 SCAN",     command=self.on_show,
                   style="Accent.TButton").grid(row=0, column=0, padx=3, sticky="ew")
        ttk.Button(btn, text="⏹ STOP",     command=self._stop_camera_manual
                   ).grid(row=0, column=1, padx=3, sticky="ew")
        ttk.Button(btn, text="⚖ TARE",     command=self._tare_scale
                   ).grid(row=0, column=2, padx=3, sticky="ew")
        ttk.Button(btn, text="🗑 REMOVE",  command=self.remove_item,
                   style="Danger.TButton").grid(row=0, column=3, padx=3, sticky="ew")
        ttk.Button(btn, text="✔ CHECKOUT", command=self.checkout,
                   style="Success.TButton").grid(row=0, column=4, padx=3, sticky="ew")

        # ── Row 4: Camera preview (BOTTOM, hidden until SCAN) ─────────────
        self.camera_panel = ttk.Frame(mf, style="Card.TFrame", height=140)
        self.camera_panel.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        self.camera_panel.grid_remove()   # hidden by default
        self.camera_panel.grid_propagate(False)

        self.camera_label = tk.Label(
            self.camera_panel,
            text="📷 Camera Preview  (Press SCAN to start)",
            bg=THEME["card"], fg=THEME["gray"],
            font=("Arial", 10))
        self.camera_label.pack(expand=True, fill="both", padx=4, pady=4)

        # ── Status bar ────────────────────────────────────────────────────
        self.status_bar = ttk.Label(
            self, text=" Welcome", padding="6 4",
            background=THEME["primary"], foreground=THEME["white"],
            font=self.fonts["sub"])
        self.status_bar.grid(row=1, column=0, sticky="ew")

    # ── Live weight display (top-right, every 1s) ──────────────────────────
    # ── 1. Live weight display in header (top-right) ───────────────────────
    def _poll_weight(self):
        """
        Runs on Tkinter thread every 500 ms.
        read_grams() is now non-blocking (cached from background reader thread).
        """
        try:
            g = self.weight_validator.scale.read_grams()
            self.weight_display.config(text=("%.1f g" % g))
        except Exception:
            pass
        self.after(500, self._poll_weight)   # 500 ms — snappier display

    def _tare_scale(self):
        self._weight_wait_active = False    # cancel any pending weight-wait
        self.weight_validator.tare()
        self.update_status("Scale tared (zeroed).", "info")

    # ── Background barcode decoder ─────────────────────────────────────────
    def _background_decoder(self):
        while not self.stop_scanner:
            frame = self._current_frame
            if frame is not None:
                try:
                    h, w = frame.shape[:2]
                    x1 = int(w/2 - BOX_SIZE/2); y1 = int(h/2 - BOX_SIZE/2)
                    x2 = int(w/2 + BOX_SIZE/2); y2 = int(h/2 + BOX_SIZE/2)
                    roi  = frame[y1:y2, x1:x2]
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    barcodes = decode(gray, symbols=[
                        ZBarSymbol.QRCODE, ZBarSymbol.EAN13, ZBarSymbol.CODE128])

                    now = time.time()
                    for bc in barcodes:
                        data = bc.data.decode("utf-8")
                        # Skip new scans while waiting for weight placement
                        if self._weight_wait_active:
                            break
                        if (now - self._last_scanned.get(data, 0)) > SCAN_DELAY:
                            beep()
                            self._last_scanned[data] = now
                            self.after(0, self._process_barcode, data)

                    with self._decode_lock:
                        self._detected_barcodes = barcodes
                except Exception as e:
                    print(f"[Decoder] {e}")
            time.sleep(0.1)

    # ── Camera lifecycle ───────────────────────────────────────────────────
    def _start_camera(self):
        self._last_scanned      = {}
        self._detected_barcodes = []
        try:
            if IS_RASPBERRY_PI:
                self._cam = PiCameraStream()
                self.update_status("Pi Camera ready — scanning active.", "success")
            else:
                self._cam = DesktopCameraStream(0)
                if self._cam.frame is None:
                    raise RuntimeError("Webcam index 0 not found.")
                self.update_status("Desktop camera ready.", "success")
        except Exception as e:
            self.update_status(f"Camera failed: {e}", "error")
            self._cam = None; self.stop_scanner = True; return

        threading.Thread(target=self._background_decoder, daemon=True).start()
        self.camera_panel.grid()
        self.after(33, self._poll_camera)

    def _poll_camera(self):
        if self.stop_scanner or self._cam is None:
            self._stop_camera(); return

        frame = self._cam.read()
        if frame is None:
            self.after(33, self._poll_camera); return

        self._current_frame = frame.copy()

        # Draw ROI box
        h, w = frame.shape[:2]
        x1 = int(w/2 - BOX_SIZE/2); y1 = int(h/2 - BOX_SIZE/2)
        x2 = int(w/2 + BOX_SIZE/2); y2 = int(h/2 + BOX_SIZE/2)

        with self._decode_lock:
            barcodes = list(self._detected_barcodes)

        if barcodes:
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 3)
            for bc in barcodes:
                cv2.putText(frame, bc.data.decode("utf-8"), (x1, y1-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
        else:
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2)
            cv2.putText(frame, "Align Barcode", (x1, y1-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,255), 1)

        # Resize to fit bottom panel (wide, short)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img   = Image.fromarray(frame_rgb).resize((520, 130))
        photo = ImageTk.PhotoImage(img)
        self.camera_label.config(image=photo, text="")
        self._cam_photo = photo
        self.after(33, self._poll_camera)

    def _stop_camera(self):
        try:
            if self._cam: self._cam.stop()
        except Exception: pass
        self._cam = self._cam_photo = self._current_frame = None
        self.camera_label.config(image="", text="📷 Camera Stopped")
        self.camera_panel.grid_remove()

    def _stop_camera_manual(self):
        self.stop_scanner = True
        self._stop_camera()
        self.update_status("Scanner stopped.")

    # ── Barcode → DB lookup ────────────────────────────────────────────────
    def _process_barcode(self, barcode_data: str):
        if self._weight_wait_active:
            return   # ignore scans while waiting for item placement
        try:
            conn = sqlite3.connect("cart_database.db")
            cur  = conn.cursor()
            cur.execute(
                "SELECT barcode, product_name, mrp, discount, quantity_value, quantity_unit "
                "FROM products WHERE barcode=?", (barcode_data,))
            product = cur.fetchone()
            conn.close()
            if product:
                self.update_status(f"Scanned: {product[1]}")
                ProductPopup(self, product, self._on_popup_confirmed)
            else:
                self.update_status(f"Barcode {barcode_data} not in database.", "error")
        except sqlite3.Error as e:
            self.update_status(f"DB error: {e}", "error")

    # ==========================================================================
    # Weight validation — Live polling flow (matches System-Workflow.jpg)
    # ==========================================================================
    # ── 2. Confirm handler: capture baseline and start weight-wait loop ────
    def _on_popup_confirmed(self, product_data, quantity):
        """
        Called when user presses CONFIRM in ProductPopup.
        Captures baseline immediately (non-blocking), then starts polling.
        Called when user presses CONFIRM in ProductPopup.
        Step 1: Capture baseline weight (platform should be EMPTY at this moment).
        Step 2: Tell user to place item.
        Step 3: Poll every 500 ms until weight delta matches expected.
        """
        barcode, name, price, discount, qty_value, qty_unit = product_data
        expected_g = (self.weight_validator.unit_to_grams(qty_value, qty_unit)
                      * quantity)

        # Non-blocking snapshot — reader thread keeps running
        self._baseline_weight    = self.weight_validator.scale.read_grams()
        self._weight_wait_active = True

        self.update_status(
            ("Place %dx %s on scale  (%.0fg expected)"
             % (quantity, name, expected_g)), "info")

        self.after(500, self._wait_for_weight_match,
                   product_data, quantity, expected_g,
                   self._baseline_weight, time.time())

    # ── 3. Live weight-wait polling loop ──────────────────────────────────
    def _wait_for_weight_match(self, product_data, quantity, expected_g,
                                baseline, t0):
        """
        Runs on Tkinter thread via after() every 500 ms.
        read_grams() is non-blocking — returns cached value immediately.
        No hardware contention with _poll_weight.
        Runs on Tkinter main thread via after().
        Polls the load cell and compares delta against expected weight.
        Auto-adds to cart when matched; shows override popup on timeout.
        """
        if not self._weight_wait_active:
            return

        barcode, name, price, discount, qty_value, qty_unit = product_data

        current   = self.weight_validator.scale.read_grams()   # non-blocking
        delta     = current - baseline
        elapsed   = time.time() - t0
        remaining = int(WEIGHT_WAIT_TIMEOUT - elapsed)
        tolerance = max(MIN_TOLERANCE_GRAMS,
                        expected_g * TOLERANCE_PERCENT / 100)
        diff      = abs(delta - expected_g)

        self.update_status(
            ("Weighing %s  |  Live: %.0fg  /  Expected: %.0fg  |  %ds"
             % (name, delta, expected_g, remaining)), "info")

        if delta >= 5 and diff <= tolerance:
            self._weight_wait_active = False
            self.add_item(barcode, name, price, discount,
                          qty_value, qty_unit, quantity)
            self.update_status(
                ("Added %dx %s  (%.0fg detected)" % (quantity, name, delta)),
                "success")
            return

        if elapsed >= WEIGHT_WAIT_TIMEOUT:
            self._weight_wait_active = False
            result = {
                "valid":    False,
                "expected": expected_g,
                "actual":   delta,
                "delta":    delta - expected_g,
                "message":  ("Timeout: expected ~%.0fg, detected %.0fg. "
                             "Place item correctly or use override."
                             % (expected_g, delta)),
            }
            WeightCheckPopup(self, result, product_data, quantity,
                             on_override=self._force_add_item)
            return

        self.after(500, self._wait_for_weight_match,
                   product_data, quantity, expected_g, baseline, t0)

    def _force_add_item(self, product_data, quantity):
        barcode, name, price, discount, qty_value, qty_unit = product_data
        self.add_item(barcode, name, price, discount, qty_value, qty_unit, quantity)
        self.update_status(f"⚠ Added {quantity}× {name} (override)", "warning")

    # ── Cart operations ────────────────────────────────────────────────────
    def add_item(self, barcode, name, price, discount,
                 quantity_value, quantity_unit, quantity=1):
        if barcode in self.cart_items:
            self.cart_items[barcode]["quantity"] += quantity
        else:
            self.cart_items[barcode] = {
                "name": name, "price": price, "quantity": quantity,
                "discount": discount,
                "quantity_value": quantity_value, "quantity_unit": quantity_unit,
            }
        self._update_cart_display()

    def remove_item(self):
        sel = self.tree.selection()
        if not sel: return
        self._weight_wait_active = False   # cancel weight-wait if active
        name   = self.tree.item(sel[0], "values")[0]
        target = next((c for c, d in self.cart_items.items()
                       if d["name"] == name), None)
        if target:
            if self.cart_items[target]["quantity"] > 1:
                self.cart_items[target]["quantity"] -= 1
            else:
                del self.cart_items[target]
        self._update_cart_display()

    # ── Display helpers ────────────────────────────────────────────────────
    def _update_cart_display(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for code, item in self.cart_items.items():
            sub   = item["price"] * item["quantity"]
            disc  = round(item["price"] * (item["discount"]/100) * item["quantity"], 2)
            total = sub - disc
            wt    = f"{item['quantity_value'] * item['quantity']:.0f}{item['quantity_unit']}"
            self.tree.insert("", "end", values=(
                item["name"], item["quantity"],
                f"₹{item['price']}", f"₹{disc}", f"₹{total}", wt))
        self._update_totals()
        self._toggle_cart_view()

    def _toggle_cart_view(self):
        if not self.cart_items:
            self.empty_cart_label.grid(row=1, column=0, sticky="nsew")
            self.cart_frame.grid_remove()
        else:
            self.empty_cart_label.grid_remove()
            self.cart_frame.grid()

    def _update_totals(self):
        self.subtotal    = sum(i["price"] * i["quantity"]
                               for i in self.cart_items.values())
        self.discount    = sum(i["price"] * (i["discount"]/100) * i["quantity"]
                               for i in self.cart_items.values())
        self.grand_total = self.subtotal - self.discount
        self.saved       = self.discount

        self.subtotal_label.config(text=f"Subtotal: ₹{self.subtotal:.2f}")
        self.saved_label.config(   text=f"Saved: ₹{self.saved:.2f}")
        self.total_label.config(   text=f"TOTAL: ₹{self.grand_total:.2f}")

        self.controller.shared_data["cart_items"] = dict(self.cart_items)
        self.controller.shared_data["cart_info"]  = {
            "grand_total": self.grand_total,
            "subtotal":    self.subtotal,
            "total_discount": self.saved,
        }

    def update_status(self, msg, level="info"):
        colours = {
            "info":    (THEME["primary"], "white"),
            "success": (THEME["success"], "white"),
            "error":   (THEME["danger"],  "white"),
            "warning": (THEME["warning"], "black"),
        }
        bg, fg = colours.get(level, (THEME["primary"], "white"))
        self.status_bar.config(text=f" {msg}", background=bg, foreground=fg)

    # ── Checkout ───────────────────────────────────────────────────────────
    def checkout(self):
        if not self.cart_items:
            messagebox.showwarning("Empty", "Cart is empty.")
            return

        msg = ("Total: Rs.%.2f" % self.grand_total) + "\nProceed to payment?"

        if messagebox.askokcancel("Checkout", msg):
            self._weight_wait_active = False
            self.controller.shared_data["pending_checkout"] = True
            self.stop_scanner = True
            self._stop_camera()
            self.weight_validator.tare()
            self.update_status("Redirecting to login...", "success")
            self.controller.show_frame("AuthApp")
        else:
            self.update_status("Checkout paused.", "info")


# =============================================================================
# ProductPopup — shown immediately after barcode scan
# =============================================================================
class ProductPopup(tk.Toplevel):
    """
    Shows product info + quantity selector.
    User presses CONFIRM → weight-wait polling begins.
    Sized for 800x480 (smaller than before).
    """
    def __init__(self, parent, product_data, callback):
        super().__init__(parent)
        self.title("Item Scanned")
        self.geometry("360x300")
        self.configure(bg=THEME["card"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.product_data = product_data
        self.callback     = callback
        self.quantity     = tk.IntVar(value=1)

        barcode, name, mrp, disc, qty_val, qty_unit = product_data
        final_price = round(mrp - mrp * disc / 100, 2)

        tk.Label(self, text="ITEM SCANNED", bg=THEME["card"],
                 fg=THEME["primary"], font=("Helvetica", 10, "bold")).pack(pady=10)
        tk.Label(self, text=name, bg=THEME["card"], fg="white",
                 font=("Helvetica", 14, "bold"), wraplength=320).pack()
        tk.Label(self, text=f"₹{final_price}  (MRP ₹{mrp})  •  {qty_val} {qty_unit}",
                 bg=THEME["card"], fg=THEME["gray"],
                 font=("Helvetica", 10)).pack(pady=4)

        qf = tk.Frame(self, bg=THEME["card"])
        qf.pack(pady=12)
        tk.Button(qf, text="−", font=("Arial", 14, "bold"), width=3,
                  bg=THEME["bg"], fg="white", relief="flat",
                  command=self._dec).grid(row=0, column=0)
        tk.Label(qf, textvariable=self.quantity,
                 font=("Arial", 18, "bold"), bg=THEME["card"],
                 fg="white", width=4).grid(row=0, column=1, padx=8)
        tk.Button(qf, text="+", font=("Arial", 14, "bold"), width=3,
                  bg=THEME["bg"], fg="white", relief="flat",
                  command=self._inc).grid(row=0, column=2)

        tk.Label(self, text="After confirming, place item on the scale.",
                 bg=THEME["card"], fg=THEME["gray"],
                 font=("Arial", 8)).pack(pady=(0, 6))

        bf = tk.Frame(self, bg=THEME["card"])
        bf.pack(side="bottom", fill="x", pady=10)
        tk.Button(bf, text="CANCEL", font=("Helvetica", 9, "bold"),
                  bg=THEME["danger"], fg="white", relief="flat",
                  width=12, pady=8,
                  command=self.destroy).pack(side="left", padx=15)
        tk.Button(bf, text="CONFIRM →", font=("Helvetica", 9, "bold"),
                  bg=THEME["success"], fg="white", relief="flat",
                  width=14, pady=8,
                  command=self._confirm).pack(side="right", padx=15)

    def _inc(self): self.quantity.set(self.quantity.get() + 1)
    def _dec(self):
        if self.quantity.get() > 1: self.quantity.set(self.quantity.get() - 1)

    def _confirm(self):
        self.callback(self.product_data, self.quantity.get())
        self.destroy()


# =============================================================================
# WeightCheckPopup — shown on timeout / mismatch (staff override)
# =============================================================================
class WeightCheckPopup(tk.Toplevel):
    def __init__(self, parent, result, product_data, quantity, on_override):
        super().__init__(parent)
        self.title("⚠ Weight Mismatch")
        self.geometry("380x280")
        self.configure(bg=THEME["card"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_override  = on_override
        self.product_data = product_data
        self.quantity     = quantity

        tk.Label(self, text="⚠ WEIGHT MISMATCH",
                 bg=THEME["card"], fg=THEME["warning"],
                 font=("Helvetica", 13, "bold")).pack(pady=(16, 6))
        tk.Label(self, text=result["message"],
                 bg=THEME["card"], fg="white",
                 font=("Helvetica", 9), wraplength=350,
                 justify="center").pack(padx=14)

        inf = tk.Frame(self, bg=THEME["bg"])
        inf.pack(pady=10, padx=16, fill="x")
        for row, (lbl, val) in enumerate([
            ("Expected",   f"{result['expected']:.0f} g"),
            ("Detected",   f"{result['actual']:.0f} g"),
            ("Difference", f"{abs(result['delta']):.0f} g"),
        ]):
            tk.Label(inf, text=lbl, bg=THEME["bg"], fg=THEME["gray"],
                     font=("Arial", 9)).grid(row=row, column=0, sticky="w", padx=8, pady=2)
            tk.Label(inf, text=val, bg=THEME["bg"], fg="white",
                     font=("Arial", 9, "bold")).grid(row=row, column=1, sticky="w", padx=8)

        bf = tk.Frame(self, bg=THEME["card"])
        bf.pack(side="bottom", fill="x", pady=10)
        tk.Button(bf, text="REMOVE", font=("Helvetica", 9, "bold"),
                  bg=THEME["danger"], fg="white", relief="flat",
                  width=12, pady=7,
                  command=self.destroy).pack(side="left", padx=12)
        tk.Button(bf, text="ADD ANYWAY", font=("Helvetica", 9, "bold"),
                  bg=THEME["warning"], fg="black", relief="flat",
                  width=14, pady=7,
                  command=self._override).pack(side="right", padx=12)

    def _override(self):
        self.on_override(self.product_data, self.quantity)
        self.destroy()
