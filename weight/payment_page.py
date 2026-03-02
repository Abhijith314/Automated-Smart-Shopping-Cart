import tkinter as tk
import razorpay
import qrcode
from PIL import Image, ImageTk
import threading
import time
import os

THEME = {
    "bg": "#101622", "card": "#151a25", "primary": "#135bec",
    "primary_hover": "#2563eb", "white": "#ffffff", "gray": "#92a4c9",
    "success": "#10b981", "danger": "#ef4444"
}

class PaymentPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller # This is AuthApp
        
        self.box = tk.Frame(self, bg=THEME["bg"])
        self.box.place(relx=0.5, rely=0.5, anchor="center")
        
        self.header = tk.Label(self.box, text="Complete Payment", bg=THEME["bg"], fg="white", font=controller.fonts["hero"])
        self.header.pack(pady=10)
        
        self.amount_lbl = tk.Label(self.box, text="", bg=THEME["bg"], fg=THEME["primary"], font=controller.fonts["header"])
        self.amount_lbl.pack(pady=5)

        # Container for the QR Code
        self.qr_label = tk.Label(self.box, bg=THEME["bg"])
        self.qr_label.pack(pady=15)
        
        self.status_lbl = tk.Label(self.box, text="Generating QR Code...", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["input"])
        self.status_lbl.pack(pady=10)

        tk.Button(self.box, text="← Cancel Checkout", bg=THEME["bg"], fg="gray", borderwidth=0, 
                  command=self.cancel_payment).pack(pady=10)

        self.payment_link_id = None
        self.polling_active = False

    def on_show(self):
        """Called whenever this page is brought to the front"""
        main_app = self.controller.controller
        amount = main_app.shared_data["cart_info"].get("grand_total", 0.0)
        self.amount_lbl.config(text=f"Total: ₹{amount:.2f}")
        self.status_lbl.config(text="Generating QR Code...", fg=THEME["gray"])
        self.qr_label.config(image='') # Clear any previous image
        
        self.polling_active = True
        
        # We run the API calls in a background thread so the UI doesn't freeze
        threading.Thread(target=self.generate_and_monitor_payment, daemon=True).start()

    def generate_and_monitor_payment(self):
        main_app = self.controller.controller
        amount = main_app.shared_data["cart_info"].get("grand_total", 0.0)
        
        # Razorpay strictly requires amounts in paise
        amount_paise = int(amount * 100)
        user_email = main_app.shared_data["user_info"].get("email", "guest@example.com")
        user_phone = main_app.shared_data["user_info"].get("phone", "0000000000")

        if not user_phone.startswith("+"):
            user_phone = "+91" + user_phone[-10:]

        try:
            client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))
            
            payment_link = client.payment_link.create({
                "amount": amount_paise,
                "currency": "INR",
                "description": "Smart Cart Checkout",
                "customer": {
                    "name": main_app.shared_data["user_info"].get("name", "User"),
                    "email": user_email,
                    "contact": user_phone
                },
                "notify": {"sms": False, "email": False} # We handle UI notifications ourselves
            })

            self.payment_link_id = payment_link["id"]
            qr_url = payment_link["short_url"]

            # Generate the QR Code image
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((200, 200))
            
            # Keep a persistent reference to the image so Python's garbage collector doesn't delete it
            self.photo = ImageTk.PhotoImage(img) 
            
            # Update the UI safely from the background thread
            self.controller.after(0, self.update_qr_ui)

            # Begin polling Razorpay to see if the customer paid
            self.poll_status(client)

        except Exception as e:
            print(f"Razorpay Error: {e}")
            self.controller.after(0, lambda: self.status_lbl.config(text="Error generating payment link.", fg=THEME["danger"]))

    def update_qr_ui(self):
        self.qr_label.config(image=self.photo)
        self.status_lbl.config(text="Scan QR code with any UPI app to pay", fg="white")

    def poll_status(self, client):
        while self.polling_active:
            time.sleep(3) # Check the status every 3 seconds
            try:
                link_info = client.payment_link.fetch(self.payment_link_id)
                status = link_info.get("status")
                
                if status == "paid":
                    self.polling_active = False
                    self.controller.after(0, self.payment_success)
                    break
                elif status in ["cancelled", "expired"]:
                    self.polling_active = False
                    self.controller.after(0, lambda: self.status_lbl.config(text="Payment cancelled.", fg=THEME["danger"]))
                    break
            except Exception as e:
                print(f"Polling error: {e}")

    def payment_success(self):
        self.status_lbl.config(text="Payment Successful!", fg=THEME["success"])
        # Wait 1.5 seconds for the user to read the success message, then proceed to the Welcome/Save screen
        self.controller.after(1500, lambda: self.controller.show_internal("WelcomePage"))

    def cancel_payment(self):
        self.polling_active = False
        if self.payment_link_id:
            try:
                # Cancel the link so it cannot be used later
                client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))
                client.payment_link.cancel(self.payment_link_id)
            except:
                pass
        
        # Send user back to the cart
        self.controller.controller.show_frame("SmartCartApp")