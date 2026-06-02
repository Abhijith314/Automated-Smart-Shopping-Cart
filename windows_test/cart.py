from itertools import product
import tkinter as tk
from tkinter import ttk, messagebox, font
import winsound
import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import sqlite3
import threading

# --- Theme Constants ---
THEME = {
    "bg": "#101622", "card": "#151a25", "primary": "#135bec",
    "primary_hover": "#2563eb", "white": "#ffffff", "gray": "#92a4c9",
    "success": "#10b981", "danger": "#ef4444"
}

class SmartCartApp(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg=THEME["bg"])
        
        self.cart_items = {}
        self.total = 0.0
        self.saved = 0.0
        # self.tax_rate = 0.05

        self.fonts = {
            "header": font.Font(family="Helvetica", size=24, weight="bold"),
            "sub": font.Font(family="Helvetica", size=14),
            "table": font.Font(family="Arial", size=11),
            "total": font.Font(family="Arial", size=16, weight="bold")
        }

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._configure_styles()
        self._create_widgets()
        self._update_totals()
        self._toggle_cart_view()

    def on_show(self):
        """Called when this screen appears"""
        self.status_bar.config(text="System Ready. Background Scanning Active.")
        # Optional: Clear cart if coming from a fresh start
        # self.cart_items = {}
        # self._update_cart_display()
        # Start background scanning thread
        self.stop_scanner = False
        self.scan_thread = threading.Thread(target=self.scan_with_camera, daemon=True)
        self.scan_thread.start()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=THEME["bg"])
        style.configure('TLabel', background=THEME["bg"], foreground=THEME["white"])
        style.configure('Card.TFrame', background=THEME["card"], relief='flat')
        style.configure('Treeview', background=THEME["card"], fieldbackground=THEME["card"], foreground=THEME["white"], font=self.fonts["table"], rowheight=35, borderwidth=0)
        style.configure('Treeview.Heading', background=THEME["bg"], foreground=THEME["gray"], font=("Helvetica", 10, "bold"))
        style.map('Treeview', background=[('selected', THEME["primary"])])
        
        # Buttons
        style.configure('TButton', font=("Helvetica", 11, "bold"), padding=10, borderwidth=0, background=THEME["card"], foreground=THEME["gray"])
        style.map('TButton', background=[('active', THEME["primary"]), ('pressed', THEME["primary_hover"])], foreground=[('active', THEME["white"])])
        
        style.configure('Accent.TButton', background=THEME["primary"], foreground=THEME["white"])
        style.map('Accent.TButton', background=[('active', THEME["primary_hover"])])
        style.configure('Success.TButton', background=THEME["success"], foreground=THEME["white"])
        style.configure('Danger.TButton', background=THEME["danger"], foreground=THEME["white"])
        
        style.configure('Totals.TFrame', background=THEME["card"])
        style.configure('Totals.TLabel', background=THEME["card"], foreground=THEME["gray"], font=self.fonts["sub"])
        style.configure('GrandTotal.TLabel', background=THEME["card"], foreground=THEME["primary"], font=self.fonts["total"])

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="30")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Header
        ttk.Label(main_frame, text="SMART CART DASHBOARD", font=self.fonts["header"]).grid(row=0, column=0, sticky="w", pady=(0, 25))

        # Cart List
        self.cart_frame = ttk.Frame(main_frame, style='Card.TFrame')
        self.cart_frame.grid(row=1, column=0, sticky="nsew")
        self.cart_frame.columnconfigure(0, weight=1)
        self.cart_frame.rowconfigure(0, weight=1)

        columns = ("name", "quantity", "price", "discount", "total")
        self.tree = ttk.Treeview(self.cart_frame, columns=columns, show="headings", height=12)
        self.tree.heading("name", text="PRODUCT NAME")
        self.tree.heading("quantity", text="QTY")
        self.tree.heading("price", text="UNIT PRICE")
        self.tree.heading("discount", text="DISCOUNT")
        self.tree.heading("total", text="TOTAL")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Empty State
        self.empty_cart_label = ttk.Label(main_frame, text="CART IS EMPTY", font=("Helvetica", 18), foreground=THEME["gray"], anchor="center")

        # Totals
        totals_frame = ttk.Frame(main_frame, padding=20, style='Totals.TFrame')
        totals_frame.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        totals_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.subtotal_label = ttk.Label(totals_frame, text="Subtotal: ₹0.00", style='Totals.TLabel')
        self.subtotal_label.grid(row=0, column=0, sticky="w")
        self.saved_label = ttk.Label(totals_frame, text="You saved: ₹0.00", style='Totals.TLabel')
        self.saved_label.grid(row=0, column=1, sticky="w")
        self.total_label = ttk.Label(totals_frame, text="Total: ₹0.00", style='GrandTotal.TLabel')
        self.total_label.grid(row=0, column=3, sticky="e")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, sticky="ew", pady=30)
        btn_frame.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(btn_frame, text="📷 SCAN", command=self.scan_with_camera, style='Accent.TButton').grid(row=0, column=0, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="🎲 SIMULATE", command=self.simulate_scan).grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="🗑 REMOVE", command=self.remove_item, style='Danger.TButton').grid(row=0, column=2, padx=5, sticky="ew")
        ttk.Button(btn_frame, text="✔ CHECKOUT", command=self.checkout, style='Success.TButton').grid(row=0, column=3, padx=5, sticky="ew")

        # Status Bar
        self.status_bar = ttk.Label(self, text="Welcome", padding=10, background=THEME["primary"], foreground=THEME["white"])
        self.status_bar.grid(row=1, column=0, sticky="ew")
        
    #scan with camera
    def scan_with_camera(self):
        # --- TESTING TOGGLE ---
        SHOW_CAMERA_WINDOW = True  # Set to False to hide the camera view
        # ----------------------

        active_index = 1
        cap = cv2.VideoCapture(active_index)
        
        if not cap.isOpened():
            self.update_status("Scanner Error: Camera not found.", "error")
            return

        last_barcode = None

        while not self.stop_scanner:
            success, frame = cap.read()
            if not success:
                break

            display_frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(display_frame, cv2.COLOR_BGR2GRAY)

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
                    
                    if barcode_data != last_barcode:
                        winsound.Beep(1000, 200) 
                        last_barcode = barcode_data
                        
                        # Use self.after to interact with UI from a background thread safely
                        self.after(0, self._process_barcode, barcode_data)
            
            # --- Logic to Hide/Show Window ---
            if SHOW_CAMERA_WINDOW:
                cv2.imshow('Background Scanner', display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                # Still need waitKey for OpenCV to process background events
                cv2.waitKey(10) 

        cap.release()
        cv2.destroyAllWindows()
        
        
    def _process_barcode(self, barcode_data):
        """Helper to handle DB lookup and UI updates on the main thread"""
        try:
            conn = sqlite3.connect('cart_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT barcode, product_name, mrp, discount, quantity_value, quantity_unit FROM products WHERE barcode=?", (barcode_data,))
            product = cursor.fetchone()
            conn.close()

            if product:
                ProductPopup(self, product, self.confirm_add_item)
                self.update_status(f"Previewing: {product[1]}")
            else:
                self.update_status(f"Barcode {barcode_data} not found.", "error")
        except sqlite3.Error as e:
            self.update_status(f"Database error: {e}", "error")

    #Scan with Camera
    # def scan_with_camera(self):
    #     self.update_status("Opening scanner... Please show a barcode.")
    #     cap = cv2.VideoCapture(1) # Standard index is 0, changed from 1 for general compatibility
        
    #     if not cap.isOpened():
    #         messagebox.showerror("Scanner Error", "Could not open the scanner.")
    #         self.update_status("Failed to scan the barcode.", "error")
    #         return

    #     found_barcode = False
    #     while not found_barcode:
    #         success, img = cap.read()
    #         if not success:
    #             continue

    #         for barcode in decode(img):
    #             barcode_data = barcode.data.decode('utf-8')
    #             self.update_status(f"Barcode found: {barcode_data}")
    #             last_barcode = barcode_data
                
    #             if barcode_data != last_barcode:
    #                 print(f"Scanned: {barcode_data}")
    #                 winsound.Beep(1000, 200) 
    #                 last_barcode = barcode_data
                
    #             # Look up product in DB
    #             try:
    #                 conn = sqlite3.connect('cart_database.db')
    #                 cursor = conn.cursor()
    #                 cursor.execute("SELECT barcode, product_name, mrp, discount, quantity_value, quantity_unit FROM products WHERE barcode=?", (barcode_data,))
    #                 product = cursor.fetchone()
    #                 conn.close()

    #                 if product:
    #                     ProductPopup(self, product, self.confirm_add_item)
    #                     self.update_status(f"Previewing: {product[1]}")
    #                     # barcode, product_name, price, discount, quantity_value, quantity_unit = product
    #                     # self.add_item(barcode, product_name, price, discount, quantity_value, quantity_unit)
    #                     # self.update_status(f"Scanned: {product_name}")
                        
    #                 else:
    #                     self.update_status(f"Barcode {barcode_data} not found in database.", "error")
                    
    #                 found_barcode = True
    #                 break # Exit inner loop
                
    #             except sqlite3.Error as e:
    #                 self.update_status(f"Database error: {e}", "error")

    #         cv2.imshow('Barcode Scanner', img)
    #         if cv2.waitKey(1) & 0xFF == ord('q') or \
    #             cv2.getWindowProperty('Barcode Scanner', cv2.WND_PROP_VISIBLE) < 1:
    #             break
        
    #     cap.release()
    #     cv2.destroyAllWindows()
    #     if not found_barcode:
    #         self.update_status("Camera closed. No item scanned.")
        
        
    # Simulate Scan from Database
    def simulate_scan(self):
        """Simulates scanning a random item from the database."""
        try:
            conn = sqlite3.connect('cart_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT barcode, product_name, mrp, discount, quantity_value, quantity_unit FROM products ORDER BY RANDOM() LIMIT 1")
            product = cursor.fetchone()
            conn.close()

            if product:
                ProductPopup(self, product, self.confirm_add_item)
                self.update_status(f"Previewing: {product[1]}")
                # barcode, product_name, price, discount, quantity_value, quantity_unit = product
                # self.add_item(barcode, product_name, price, discount, quantity_value, quantity_unit)
                # self.update_status(f"Scanned: {product_name}")
            else:
                self.update_status("Database is empty. No item to scan.", "error")
        except sqlite3.Error as e:
            self.update_status(f"Database error: {e}", "error")
            messagebox.showinfo("Info", "Error accessing database.")



    def confirm_add_item(self, product_data, quantity):
        """Callback from popup to finalise the addition"""
        barcode, product_name, price, discount, quantity_value, quantity_unit = product_data
        self.add_item(barcode, product_name, price, discount, quantity_value, quantity_unit, quantity)

    def add_item(self, barcode, name, price, discount, quantity_value, quantity_unit, quantity=1):
        if barcode in self.cart_items:
            self.cart_items[barcode]['quantity'] += quantity
        else:
            self.cart_items[barcode] = {
                'name': name, 
                'price': price, 
                'quantity': quantity, 
                'discount': discount, 
                'quantity_value': quantity_value, 
                'quantity_unit': quantity_unit
            }
        self._update_cart_display()
        self.update_status(f"Added {quantity}x {name}", "success")
    
    
    # def add_item(self, barcode, name, price, discount, quantity_value, quantity_unit):
    #     if barcode in self.cart_items:
    #         self.cart_items[barcode]['quantity'] += 1
    #     else:
    #         self.cart_items[barcode] = {'name': name, 'price': price, 'quantity': 1, 'discount' : discount, 'quantity_value': quantity_value, 'quantity_unit': quantity_unit}
    #     self._update_cart_display()
    #     self.status_bar.config(text=f"Added: {name}")

    def remove_item(self):
        selected = self.tree.selection()
        if not selected: return
        item_name = self.tree.item(selected[0], 'values')[0]
        
        # Find barcode by name (inefficient but works for small lists)
        target_code = next((code for code, det in self.cart_items.items() if det['name'] == item_name), None)
        if target_code:
            if self.cart_items[target_code]['quantity'] > 1:
                self.cart_items[target_code]['quantity'] -= 1
            else:
                del self.cart_items[target_code]
        self._update_cart_display()

    def _update_cart_display(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for code, item in self.cart_items.items():
            sub_total = item['price'] * item['quantity']
            discount = round((item['price'] * (item['discount'] / 100)) * item['quantity'], 2)
            total = sub_total - discount
            self.tree.insert("", "end", values=(item['name'], item['quantity'], f"₹{item['price']}", f"₹{discount}", f"₹{total}"))
        self._update_totals()
        self._toggle_cart_view()

    def _toggle_cart_view(self):
        if not self.cart_items:
            self.empty_cart_label.grid(row=1, column=0, sticky="nsew")
            self.cart_frame.grid_remove()
        else:
            self.empty_cart_label.grid_remove()
            self.cart_frame.grid()

    # Bottom config
    def _update_totals(self):
        self.subtotal = sum(i['price'] * i['quantity'] for i in self.cart_items.values())
        # self.tax = self.subtotal * self.tax_rate
        # self.total = self.subtotal + self.tax
        self.discount = sum((i['price'] * (i['discount'] / 100)) * i['quantity'] for i in self.cart_items.values())
        self.grand_total = self.subtotal - self.discount
        self.saved = self.discount
        
        self.subtotal_label.config(text=f"SUBTOTAL: ₹{self.subtotal:.2f}")
        # self.tax_label.config(text=f"TAX (5%): ₹{self.tax:.2f}")
        self.saved_label.config(text=f"YOU SAVED: ₹{self.saved:.2f}")
        self.total_label.config(text=f"TOTAL: ₹{self.grand_total:.2f}")
        
        
    def update_status(self, message, level="info"):
        self.status_bar.config(text=f"  {message}")
        if level == "error":
            self.status_bar.config(background=THEME["danger"], foreground="white")
        elif level == "success":
            self.status_bar.config(background=THEME["success"], foreground="white")
        else:
            self.status_bar.config(background=THEME["primary"], foreground="white")
    
    
    def checkout(self):
        """Handles the checkout process with confirmation."""
        if not self.cart_items:
            messagebox.showwarning("Empty", "Your cart is empty. Please scan items to checkout.")
            return

        checkout_message = f"Your total bill is ₹{self.grand_total:.2f}.\n\nWould you like to proceed to login and finish your order?"

        confirm = messagebox.askokcancel("Confirm Checkout", checkout_message)

        if confirm:
            self.controller.shared_data["cart_items"] = self.cart_items
            self.controller.shared_data["cart_info"] = {"grand_total": self.grand_total, "subtotal": self.subtotal, "total_discount": self.saved}
            self.controller.shared_data["pending_checkout"] = True

            self.update_status("Redirecting to Login...", "success")
            
            self.controller.show_frame("AuthApp")
        else:
            self.update_status("Checkout paused.", "info")

    

    # def checkout(self):
    #     if not self.cart_items:
    #         messagebox.showwarning("Empty", "Cart is empty!")
    #         return
        
    #     checkout_message = f"Your total bill is ₹{self.total:.2f}.\n\nThank you for shopping with us!"
    #     messagebox.showinfo("Checkout Successful", checkout_message)
    #     self.update_status("Checkout complete! Thank you.", "success")
        
    #     # --- CRITICAL: PASS DATA TO CONTROLLER ---
    #     self.controller.shared_data["cart_items"] = self.cart_items
    #     self.controller.shared_data["cart_total"] = self.total
    #     self.controller.shared_data["pending_checkout"] = True
        
    #     # Switch to Auth for payment/verification
    #     self.controller.show_frame("AuthApp")
    
    
class ProductPopup(tk.Toplevel):
    def __init__(self, parent, product_data, callback):
        super().__init__(parent)
        self.title("Product Scanned")
        self.geometry("400x450")
        self.configure(bg=THEME["card"])
        self.resizable(False, False)
        
        # Make it a modal window
        self.transient(parent)
        self.grab_set()
        
        self.product_data = product_data # (barcode, name, price, discount, qty_val, qty_unit)
        self.callback = callback
        self.quantity = tk.IntVar(value=1)

        # UI
        tk.Label(self, text="ITEM SCANNED", bg=THEME["card"], fg=THEME["primary"], font=("Helvetica", 12, "bold")).pack(pady=20)
        
        # Product Name
        tk.Label(self, text=product_data[1], bg=THEME["card"], fg="white", font=("Helvetica", 18, "bold"), wraplength=350).pack()
        
        # Product Price info
        mrp = product_data[2]
        disc = product_data[3]
        final_price = round(mrp - (mrp * disc/100), 2)
        tk.Label(self, text=f"Price: ₹{final_price} (MRP: ₹{mrp})", bg=THEME["card"], fg=THEME["gray"], font=("Helvetica", 11)).pack(pady=5)

        # Quantity Selector
        qty_frame = tk.Frame(self, bg=THEME["card"])
        qty_frame.pack(pady=30)

        tk.Button(qty_frame, text="−", font=("Arial", 18, "bold"), width=3, bg=THEME["bg"], fg="white", 
                  relief="flat", command=self.decrement).grid(row=0, column=0)
        
        self.qty_lbl = tk.Label(qty_frame, textvariable=self.quantity, font=("Arial", 22, "bold"), bg=THEME["card"], fg="white", width=4)
        self.qty_lbl.grid(row=0, column=1, padx=10)

        tk.Button(qty_frame, text="+", font=("Arial", 18, "bold"), width=3, bg=THEME["bg"], fg="white", 
                  relief="flat", command=self.increment).grid(row=0, column=2)

        # Buttons
        btn_frame = tk.Frame(self, bg=THEME["card"])
        btn_frame.pack(pady=20, side="bottom", fill="x")

        tk.Button(btn_frame, text="CANCEL", font=("Helvetica", 10, "bold"), bg=THEME["danger"], fg="white", 
                  relief="flat", width=15, pady=10, command=self.destroy).pack(side="left", padx=20, pady=20)
        
        tk.Button(btn_frame, text="ADD TO CART", font=("Helvetica", 10, "bold"), bg=THEME["success"], fg="white", 
                  relief="flat", width=15, pady=10, command=self.add_and_close).pack(side="right", padx=20, pady=20)

    def increment(self):
        self.quantity.set(self.quantity.get() + 1)

    def decrement(self):
        if self.quantity.get() > 1:
            self.quantity.set(self.quantity.get() - 1)

    def add_and_close(self):
        # Call back to main app with quantity
        self.callback(self.product_data, self.quantity.get())
        print(self.quantity.get(),self.product_data)
        self.destroy()