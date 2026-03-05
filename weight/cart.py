"""
cart.py  –  Smart Cart Dashboard with HX711 weight validation.

Changes from original:
  • winsound replaced with cross-platform beep utility
  • WeightValidator imported and wired into the scan/add flow
  • WeightCheckPopup shows validation result before item lands in cart
  • Simulate mode triggers simulated weight addition for easy testing
"""
import time
import tkinter as tk
from tkinter import ttk, messagebox, font
import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import sqlite3
import threading
import platform
import os

from weight_sensor import WeightValidator

# ── Theme ─────────────────────────────────────────────────────────────────────
THEME = {
    "bg": "#101622", "card": "#151a25", "primary": "#135bec",
    "primary_hover": "#2563eb", "white": "#ffffff", "gray": "#92a4c9",
    "success": "#10b981", "danger": "#ef4444", "warning": "#f59e0b",
}


# ── Cross-platform beep ───────────────────────────────────────────────────────
def beep():
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.Beep(1000, 200)
        elif platform.system() == "Linux":
            # Works on Pi with a buzzer on GPIO or via system bell
            os.system("echo -e '\a'")
        # macOS / other: silent fallback
    except Exception:
        pass


# =============================================================================
class SmartCartApp(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg=THEME["bg"])

        self.cart_items  = {}
        self.total       = 0.0
        self.saved       = 0.0
        self.stop_scanner = True   # background scan flag

        self.fonts = {
            "header": font.Font(family="Helvetica", size=24, weight="bold"),
            "sub":    font.Font(family="Helvetica", size=14),
            "table":  font.Font(family="Arial",     size=11),
            "total":  font.Font(family="Arial",     size=16, weight="bold"),
        }

        # Weight validator (works on Pi with real HX711, or simulated elsewhere)
        self.weight_validator = WeightValidator()
        self._baseline_weight = 0.0   # captured just before an item is added

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._configure_styles()
        self._create_widgets()
        self._update_totals()
        self._toggle_cart_view()

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_show(self):
        self.status_bar.config(text="System Ready. Background Scanning Active.")
        self.stop_scanner = False
        self.scan_thread = threading.Thread(target=self._background_scan, daemon=True)
        self.scan_thread.start()

    # ── Styles ────────────────────────────────────────────────────────────────
    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame",         background=THEME["bg"])
        style.configure("TLabel",         background=THEME["bg"], foreground=THEME["white"])
        style.configure("Card.TFrame",    background=THEME["card"], relief="flat")
        style.configure("Treeview",       background=THEME["card"], fieldbackground=THEME["card"],
                        foreground=THEME["white"], font=self.fonts["table"],
                        rowheight=35, borderwidth=0)
        style.configure("Treeview.Heading", background=THEME["bg"],
                        foreground=THEME["gray"], font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", THEME["primary"])])
        style.configure("TButton",        font=("Helvetica", 11, "bold"), padding=10,
                        borderwidth=0,    background=THEME["card"], foreground=THEME["gray"])
        style.map("TButton",
                  background=[("active", THEME["primary"]), ("pressed", THEME["primary_hover"])],
                  foreground=[("active", THEME["white"])])
        style.configure("Accent.TButton",  background=THEME["primary"],  foreground=THEME["white"])
        style.map("Accent.TButton",        background=[("active", THEME["primary_hover"])])
        style.configure("Success.TButton", background=THEME["success"],  foreground=THEME["white"])
        style.configure("Danger.TButton",  background=THEME["danger"],   foreground=THEME["white"])
        style.configure("Totals.TFrame",   background=THEME["card"])
        style.configure("Totals.TLabel",   background=THEME["card"],
                        foreground=THEME["gray"], font=self.fonts["sub"])
        style.configure("GrandTotal.TLabel", background=THEME["card"],
                        foreground=THEME["primary"], font=self.fonts["total"])

    # ── Widgets ───────────────────────────────────────────────────────────────
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="30")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Header row: title + weight indicator
        header_row = ttk.Frame(main_frame)
        header_row.grid(row=0, column=0, sticky="ew", pady=(0, 25))
        header_row.columnconfigure(0, weight=1)

        ttk.Label(header_row, text="SMART CART DASHBOARD",
                  font=self.fonts["header"]).grid(row=0, column=0, sticky="w")

        # Live weight display (top-right)
        self.weight_display = tk.Label(header_row, text="⚖  0.0 g",
                                       bg=THEME["card"], fg=THEME["gray"],
                                       font=("Arial", 11), padx=12, pady=4)
        self.weight_display.grid(row=0, column=1, sticky="e")

        # Cart list
        self.cart_frame = ttk.Frame(main_frame, style="Card.TFrame")
        self.cart_frame.grid(row=1, column=0, sticky="nsew")
        self.cart_frame.columnconfigure(0, weight=1)
        self.cart_frame.rowconfigure(0, weight=1)

        columns = ("name", "quantity", "price", "discount", "total", "weight")
        self.tree = ttk.Treeview(self.cart_frame, columns=columns,
                                 show="headings", height=12)
        self.tree.heading("name",     text="PRODUCT NAME")
        self.tree.heading("quantity", text="QTY")
        self.tree.heading("price",    text="UNIT PRICE")
        self.tree.heading("discount", text="DISCOUNT")
        self.tree.heading("total",    text="TOTAL")
        self.tree.heading("weight",   text="WEIGHT")
        self.tree.column("weight", width=90, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.empty_cart_label = ttk.Label(main_frame, text="CART IS EMPTY",
                                          font=("Helvetica", 18),
                                          foreground=THEME["gray"], anchor="center")

        # Totals
        totals_frame = ttk.Frame(main_frame, padding=20, style="Totals.TFrame")
        totals_frame.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        totals_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.subtotal_label = ttk.Label(totals_frame, text="Subtotal: ₹0.00",
                                        style="Totals.TLabel")
        self.subtotal_label.grid(row=0, column=0, sticky="w")
        self.saved_label = ttk.Label(totals_frame, text="You saved: ₹0.00",
                                     style="Totals.TLabel")
        self.saved_label.grid(row=0, column=1, sticky="w")
        self.total_label = ttk.Label(totals_frame, text="Total: ₹0.00",
                                     style="GrandTotal.TLabel")
        self.total_label.grid(row=0, column=3, sticky="e")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, sticky="ew", pady=30)
        btn_frame.columnconfigure((0, 1, 2, 3, 4), weight=1)

        ttk.Button(btn_frame, text="📷 SCAN",     command=self.on_show,
                   style="Accent.TButton").grid(row=0, column=0, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="🎲 SIMULATE", command=self.simulate_scan
                   ).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="⚖ TARE",      command=self._tare_scale
                   ).grid(row=0, column=2, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="🗑 REMOVE",   command=self.remove_item,
                   style="Danger.TButton").grid(row=0, column=3, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="✔ CHECKOUT",  command=self.checkout,
                   style="Success.TButton").grid(row=0, column=4, padx=5, sticky="ew")

        # Status bar
        self.status_bar = ttk.Label(self, text="Welcome", padding=10,
                                    background=THEME["primary"],
                                    foreground=THEME["white"])
        self.status_bar.grid(row=1, column=0, sticky="ew")

        # Start live weight poll (every 1 s)
        self._poll_weight()

    # ── Live weight display ───────────────────────────────────────────────────
    def _poll_weight(self):
        try:
            grams = self.weight_validator.scale.read_grams()
            self.weight_display.config(text=f"⚖  {grams:.1f} g")
        except Exception:
            pass
        self.after(1000, self._poll_weight)

    def _tare_scale(self):
        self.weight_validator.tare()
        self.update_status("Scale tared (zeroed).", "info")

    # ── Background camera scanner ─────────────────────────────────────────────
    def _background_scan(self):
        SHOW_WINDOW = False   # Set True for debugging on a desktop with a display
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.after(0, lambda: self.update_status(
                "Scanner: Camera not found.", "error"))
            return

        last_barcode = None
        while not self.stop_scanner:
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(cv2.resize(frame, (640, 480)),
                                cv2.COLOR_BGR2GRAY)
            barcodes = decode(gray, symbols=[
                ZBarSymbol.QRCODE, ZBarSymbol.EAN13, ZBarSymbol.CODE128])

            if not barcodes:
                last_barcode = None
            else:
                for bc in barcodes:
                    data = bc.data.decode("utf-8")
                    if data != last_barcode:
                        beep()
                        last_barcode = data
                        self.after(0, self._process_barcode, data)

            if SHOW_WINDOW:
                cv2.imshow("Scanner", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                time.sleep(0.01)   # ← replaces cv2.waitKey(10); no GUI needed

        cap.release()
        if SHOW_WINDOW:            # ← only call when a window was actually opened
            cv2.destroyAllWindows()


    # ── Barcode → DB lookup ───────────────────────────────────────────────────
    def _process_barcode(self, barcode_data: str):
        try:
            conn   = sqlite3.connect("cart_database.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT barcode, product_name, mrp, discount, quantity_value, quantity_unit "
                "FROM products WHERE barcode=?", (barcode_data,))
            product = cursor.fetchone()
            conn.close()

            if product:
                # Capture baseline weight BEFORE showing popup
                self._baseline_weight = self.weight_validator.capture_baseline()
                ProductPopup(self, product, self._on_popup_confirmed)
                self.update_status(f"Previewing: {product[1]}")
            else:
                self.update_status(f"Barcode {barcode_data} not found.", "error")
        except sqlite3.Error as e:
            self.update_status(f"Database error: {e}", "error")

    # ── Simulate scan (for testing without camera) ────────────────────────────
    def simulate_scan(self):
        try:
            conn   = sqlite3.connect("cart_database.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT barcode, product_name, mrp, discount, quantity_value, quantity_unit "
                "FROM products ORDER BY RANDOM() LIMIT 1")
            product = cursor.fetchone()
            conn.close()

            if product:
                self._baseline_weight = self.weight_validator.capture_baseline()
                ProductPopup(self, product, self._on_popup_confirmed)
                self.update_status(f"Previewing: {product[1]}")
            else:
                self.update_status("Database empty.", "error")
        except sqlite3.Error as e:
            self.update_status(f"Database error: {e}", "error")

    # ── Weight validation flow ────────────────────────────────────────────────
    def _on_popup_confirmed(self, product_data, quantity: int):
        """
        Called after user presses ADD TO CART in ProductPopup.
        Starts weight validation in a background thread to keep UI responsive.
        """
        barcode, name, price, discount, qty_value, qty_unit = product_data
        expected_grams = (
            self.weight_validator.unit_to_grams(qty_value, qty_unit) * quantity
        )

        self.update_status(
            f"Place {quantity}× {name} in cart — validating weight…", "info")

        def _do_validate():
            result = self.weight_validator.validate(
                expected_grams, self._baseline_weight, timeout=10.0
            )
            # Schedule UI update back on main thread
            self.after(0, self._show_weight_result,
                       product_data, quantity, result)

        # On simulated scale, fake the weight being added
        if hasattr(self.weight_validator.scale, "simulate_add"):
            self.weight_validator.scale.simulate_add(expected_grams)

        threading.Thread(target=_do_validate, daemon=True).start()

    def _show_weight_result(self, product_data, quantity, result):
        """Show weight check popup, then add or reject."""
        barcode, name, price, discount, qty_value, qty_unit = product_data

        if result["valid"]:
            self.add_item(barcode, name, price, discount,
                          qty_value, qty_unit, quantity)
            self.update_status(
                f"✓ Added {quantity}× {name}  |  {result['message']}", "success")
        else:
            WeightCheckPopup(self, result, product_data, quantity,
                             on_override=self._force_add_item)

    def _force_add_item(self, product_data, quantity):
        """Called when staff overrides a weight mismatch."""
        barcode, name, price, discount, qty_value, qty_unit = product_data
        self.add_item(barcode, name, price, discount, qty_value, qty_unit, quantity)
        self.update_status(f"⚠ Added {quantity}× {name} (weight override)", "info")

    # ── Cart manipulation ─────────────────────────────────────────────────────
    def add_item(self, barcode, name, price, discount,
                 quantity_value, quantity_unit, quantity=1):
        if barcode in self.cart_items:
            self.cart_items[barcode]["quantity"] += quantity
        else:
            self.cart_items[barcode] = {
                "name": name, "price": price, "quantity": quantity,
                "discount": discount,
                "quantity_value": quantity_value,
                "quantity_unit": quantity_unit,
            }
        self._update_cart_display()

    def remove_item(self):
        selected = self.tree.selection()
        if not selected:
            return
        item_name = self.tree.item(selected[0], "values")[0]
        target = next(
            (c for c, d in self.cart_items.items() if d["name"] == item_name),
            None)
        if target:
            if self.cart_items[target]["quantity"] > 1:
                self.cart_items[target]["quantity"] -= 1
            else:
                del self.cart_items[target]
            # Update baseline so next scan starts from correct weight
            self._baseline_weight = self.weight_validator.capture_baseline()
        self._update_cart_display()

    # ── Display helpers ───────────────────────────────────────────────────────
    def _update_cart_display(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for code, item in self.cart_items.items():
            sub     = item["price"] * item["quantity"]
            disc    = round((item["price"] * (item["discount"] / 100))
                            * item["quantity"], 2)
            total   = sub - disc
            wt_str  = (f"{item['quantity_value'] * item['quantity']:.0f}"
                       f" {item['quantity_unit']}")
            self.tree.insert("", "end", values=(
                item["name"], item["quantity"],
                f"₹{item['price']}", f"₹{disc}", f"₹{total}", wt_str))
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
        self.subtotal   = sum(i["price"] * i["quantity"]
                              for i in self.cart_items.values())
        self.discount   = sum((i["price"] * (i["discount"] / 100)) * i["quantity"]
                              for i in self.cart_items.values())
        self.grand_total = self.subtotal - self.discount
        self.saved       = self.discount

        self.subtotal_label.config(text=f"SUBTOTAL: ₹{self.subtotal:.2f}")
        self.saved_label.config(text=f"YOU SAVED: ₹{self.saved:.2f}")
        self.total_label.config(text=f"TOTAL: ₹{self.grand_total:.2f}")

    def update_status(self, message, level="info"):
        colours = {
            "error":   (THEME["danger"],  "white"),
            "success": (THEME["success"], "white"),
            "warning": (THEME["warning"], "black"),
            "info":    (THEME["primary"], "white"),
        }
        bg, fg = colours.get(level, (THEME["primary"], "white"))
        self.status_bar.config(text=f"  {message}",
                               background=bg, foreground=fg)

    # ── Checkout ──────────────────────────────────────────────────────────────
    def checkout(self):
        if not self.cart_items:
            messagebox.showwarning("Empty",
                "Your cart is empty. Scan items before checking out.")
            return

        msg = (f"Your total bill is ₹{self.grand_total:.2f}.\n\n"
               "Proceed to login and payment?")
        if messagebox.askokcancel("Confirm Checkout", msg):
            self.controller.shared_data["cart_items"] = self.cart_items
            self.controller.shared_data["cart_info"] = {
                "grand_total":    self.grand_total,
                "subtotal":       self.subtotal,
                "total_discount": self.saved,
            }
            self.controller.shared_data["pending_checkout"] = True
            self.stop_scanner = True          # stop camera thread
            self.weight_validator.tare()      # reset scale for next customer
            self.update_status("Redirecting to Login…", "success")
            self.controller.show_frame("AuthApp")
        else:
            self.update_status("Checkout paused.", "info")


# =============================================================================
#  Product Preview Popup
# =============================================================================
class ProductPopup(tk.Toplevel):
    """Shows product details and lets user choose quantity before adding."""

    def __init__(self, parent, product_data, callback):
        super().__init__(parent)
        self.title("Product Scanned")
        self.geometry("400x460")
        self.configure(bg=THEME["card"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.product_data = product_data
        self.callback     = callback
        self.quantity     = tk.IntVar(value=1)

        barcode, name, mrp, disc, qty_val, qty_unit = product_data
        final_price = round(mrp - (mrp * disc / 100), 2)

        tk.Label(self, text="ITEM SCANNED", bg=THEME["card"],
                 fg=THEME["primary"], font=("Helvetica", 12, "bold")).pack(pady=20)
        tk.Label(self, text=name, bg=THEME["card"], fg="white",
                 font=("Helvetica", 18, "bold"), wraplength=350).pack()
        tk.Label(self, text=f"Price: ₹{final_price}  (MRP: ₹{mrp})",
                 bg=THEME["card"], fg=THEME["gray"],
                 font=("Helvetica", 11)).pack(pady=3)
        tk.Label(self, text=f"Pack size: {qty_val} {qty_unit}",
                 bg=THEME["card"], fg=THEME["gray"],
                 font=("Helvetica", 10)).pack(pady=2)

        qty_frame = tk.Frame(self, bg=THEME["card"])
        qty_frame.pack(pady=25)
        tk.Button(qty_frame, text="−", font=("Arial", 18, "bold"), width=3,
                  bg=THEME["bg"], fg="white", relief="flat",
                  command=self._decrement).grid(row=0, column=0)
        tk.Label(qty_frame, textvariable=self.quantity,
                 font=("Arial", 22, "bold"), bg=THEME["card"],
                 fg="white", width=4).grid(row=0, column=1, padx=10)
        tk.Button(qty_frame, text="+", font=("Arial", 18, "bold"), width=3,
                  bg=THEME["bg"], fg="white", relief="flat",
                  command=self._increment).grid(row=0, column=2)

        btn_frame = tk.Frame(self, bg=THEME["card"])
        btn_frame.pack(side="bottom", fill="x", pady=20)
        tk.Button(btn_frame, text="CANCEL", font=("Helvetica", 10, "bold"),
                  bg=THEME["danger"], fg="white", relief="flat",
                  width=15, pady=10, command=self.destroy).pack(
                      side="left", padx=20, pady=20)
        tk.Button(btn_frame, text="ADD TO CART",
                  font=("Helvetica", 10, "bold"), bg=THEME["success"],
                  fg="white", relief="flat", width=15, pady=10,
                  command=self._add_and_close).pack(
                      side="right", padx=20, pady=20)

    def _increment(self): self.quantity.set(self.quantity.get() + 1)
    def _decrement(self):
        if self.quantity.get() > 1:
            self.quantity.set(self.quantity.get() - 1)

    def _add_and_close(self):
        self.callback(self.product_data, self.quantity.get())
        self.destroy()


# =============================================================================
#  Weight Check Popup  (shown on validation failure)
# =============================================================================
class WeightCheckPopup(tk.Toplevel):
    """
    Shown when the detected weight doesn't match the expected weight.
    Staff can override (add anyway) or reject the item.
    """

    def __init__(self, parent, result: dict, product_data, quantity: int,
                 on_override):
        super().__init__(parent)
        self.title("⚠ Weight Mismatch")
        self.geometry("420x320")
        self.configure(bg=THEME["card"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_override  = on_override
        self.product_data = product_data
        self.quantity     = quantity

        tk.Label(self, text="⚠ WEIGHT MISMATCH",
                 bg=THEME["card"], fg=THEME["warning"],
                 font=("Helvetica", 16, "bold")).pack(pady=(25, 10))

        tk.Label(self, text=result["message"],
                 bg=THEME["card"], fg="white",
                 font=("Helvetica", 11), wraplength=380,
                 justify="center").pack(padx=20)

        # Detail grid
        info_frame = tk.Frame(self, bg=THEME["bg"])
        info_frame.pack(pady=15, padx=20, fill="x")
        for row, (label, val) in enumerate([
            ("Expected", f"{result['expected']:.0f} g"),
            ("Detected", f"{result['actual']:.0f} g"),
            ("Difference", f"{abs(result['delta']):.0f} g"),
        ]):
            tk.Label(info_frame, text=label, bg=THEME["bg"],
                     fg=THEME["gray"], font=("Arial", 10)).grid(
                         row=row, column=0, sticky="w", padx=10, pady=2)
            tk.Label(info_frame, text=val, bg=THEME["bg"],
                     fg="white", font=("Arial", 10, "bold")).grid(
                         row=row, column=1, sticky="w", padx=10, pady=2)

        tk.Label(self, text="Staff may override or remove the item.",
                 bg=THEME["card"], fg=THEME["gray"],
                 font=("Arial", 9)).pack()

        btn_frame = tk.Frame(self, bg=THEME["card"])
        btn_frame.pack(side="bottom", fill="x", pady=20)
        tk.Button(btn_frame, text="REMOVE ITEM",
                  font=("Helvetica", 10, "bold"), bg=THEME["danger"],
                  fg="white", relief="flat", width=15, pady=10,
                  command=self.destroy).pack(side="left", padx=20)
        tk.Button(btn_frame, text="ADD ANYWAY (OVERRIDE)",
                  font=("Helvetica", 10, "bold"), bg=THEME["warning"],
                  fg="black", relief="flat", width=20, pady=10,
                  command=self._override).pack(side="right", padx=20)

    def _override(self):
        self.on_override(self.product_data, self.quantity)
        self.destroy()
