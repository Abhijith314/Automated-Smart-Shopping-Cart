from enum import verify
import tkinter as tk
from tkinter import font, messagebox
import sqlite3
from supabase import create_client
import os
import datetime
from payment_page import PaymentPage
from dotenv import load_dotenv
load_dotenv()

THEME = {
    "bg": "#101622", "card": "#151a25", "primary": "#135bec", "success": "#00ff1e",
    "primary_hover": "#2563eb", "white": "#ffffff", "gray": "#92a4c9" 
}

class AuthApp(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller # This is MainApp
        self.configure(bg=THEME["bg"])
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        # CHANGED: Renamed to shared_data to match what sub-pages expect
        self.shared_data = {"email": "", "username": "", "mobile": ""}
        
        self.fonts = {
            "hero": font.Font(family="Helvetica", size=32, weight="bold"),
            "header": font.Font(family="Helvetica", size=24, weight="bold"),
            "sub": font.Font(family="Helvetica", size=14),
            "input": font.Font(family="Arial", size=12),
            "small": font.Font(family="Arial", size=10, weight="bold")
        }

        # Internal container for swapping Auth pages
        self.container = tk.Frame(self, bg=THEME["bg"])
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        for F in (EmailPage, RegisterPage, OTPPage, PaymentPage, SuccessPage):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_internal("EmailPage")

    def show_internal(self, page_name):
        frame = self.frames[page_name]
        if hasattr(frame, "on_show"): frame.on_show()
        frame.tkraise()

    def on_show(self):
        """Reset auth flow when MainApp switches here"""
        self.show_internal("EmailPage")

# --- UI Helpers ---
class StyledEntry(tk.Entry):
    def __init__(self, parent, font_obj):
        super().__init__(parent, bg=THEME["card"], fg="white", font=font_obj, insertbackground="white", relief="flat")

class PrimaryButton(tk.Button):
    def __init__(self, parent, text, command):
        super().__init__(parent, text=text, command=command, bg=THEME["primary"], fg="white", font=("Arial", 12, "bold"), relief="flat", padx=20, pady=10)

# --- Pages ---

class EmailPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller # This is AuthApp
        
        box = tk.Frame(self, bg=THEME["bg"])
        box.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(box, text="Sign In", bg=THEME["bg"], fg="white", font=controller.fonts["hero"]).pack(pady=10)
        tk.Label(box, text="Enter Email", bg=THEME["bg"], fg="gray").pack(anchor="w")
        
        self.entry = StyledEntry(box, controller.fonts["input"])
        self.entry.pack(pady=5, ipadx=10, ipady=10, fill="x")
        
        PrimaryButton(box, "NEXT →", self.process_email).pack(pady=20)
        
        tk.Button(self, text="← Cancel", bg=THEME["bg"], fg="gray", borderwidth=0, 
                  command=lambda: controller.controller.show_frame("SmartCartApp")).place(x=20, rely=0.9)

    def process_email(self):
        email = self.entry.get().strip()
        if not email:
            messagebox.showwarning("Input Error", "Enter email to continue.")
            return

        # Save email to shared data immediately
        self.controller.shared_data["email"] = email
        self.controller.controller.shared_data["user_info"]["email"] = email

        # --- Connect to Supabase ---
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            messagebox.showerror("Config Error", "Supabase credentials are missing from environment.")
            return

        try:
            supabase = create_client(url, key)
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to Supabase:\n{repr(e)}")
            return

        # --- Check if user exists in Supabase ---
        try:
            response = supabase.table("users").select(
                "id, username, phoneNumber"
            ).eq("email", email).single().execute()

            user = response.data  # None if not found

        except Exception as e:
            error_msg = repr(e)
            # PostgREST returns an error (PGRST116) when .single() finds no rows
            if "PGRST116" in error_msg or "JSON object" in error_msg or "0 rows" in error_msg:
                user = None
            else:
                messagebox.showerror("Lookup Error", f"Could not check user:\n{error_msg}")
                return

        if user:
            # --- Existing user: populate shared data and send OTP ---
            username = user.get("username", "User")
            mobile = str(user.get("phoneNumber", ""))
            user_id = str(user.get("id", ""))

            self.controller.shared_data["username"] = username
            self.controller.shared_data["mobile"] = mobile
            self.controller.controller.shared_data["user_info"]["name"] = username
            self.controller.controller.shared_data["user_info"]["phone"] = mobile

            # Also sync to local SQLite cache
            try:
                conn = sqlite3.connect("cart_database.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO users
                        (id, username, email, phoneNumber)
                    VALUES (?, ?, ?, ?)
                """, (user_id, username, email, mobile))
                conn.commit()
                conn.close()
            except sqlite3.Error as e:
                print(f"[SQLite] Cache sync failed (non-fatal): {e}")

            # Send OTP to existing user
            try:
                supabase.auth.sign_in_with_otp({
                    "email": email,
                    "options": {"should_create_user": False},
                })
                messagebox.showinfo("OTP Sent", f"A verification code has been sent to:\n{email}\n\nPlease check your inbox.")
                self.controller.show_internal("OTPPage")

            except Exception as e:
                messagebox.showerror("OTP Error", f"Failed to send OTP:\n{repr(e)}")

        else:
            # --- New user: ask to register ---
            confirm = messagebox.askokcancel(
                "Register",
                f'"{email}" is not registered.\n\nWould you like to register to proceed with checkout?'
            )
            if confirm:
                self.controller.show_internal("RegisterPage")
            else:
                self.controller.show_internal("EmailPage")

class RegisterPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller
        
        box = tk.Frame(self, bg=THEME["bg"])
        box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(box, text="Registration", bg=THEME["bg"], fg=THEME["white"], font=controller.fonts["header"]).pack(pady=(0, 10))
        tk.Label(box, text="We need a few details.", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["sub"]).pack(pady=(0, 30))

        tk.Label(box, text="Username", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["small"]).pack(anchor="w", pady=(0,5))

        self.user_entry = StyledEntry(box, controller.fonts["input"])
        self.user_entry.pack(ipadx=10, ipady=10, fill="x", pady=(0, 15))

        tk.Label(box, text="Mobile Number", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["small"]).pack(anchor="w", pady=(0,5))

        self.mobile_entry = StyledEntry(box, controller.fonts["input"])
        self.mobile_entry.pack(ipadx=10, ipady=10, fill="x", pady=(0, 30))

        PrimaryButton(box, "NEXT →", self.process_register).pack(pady=20)

        tk.Button(self, text="← Cancel", bg=THEME["bg"], fg="gray", borderwidth=0, 
                  command=lambda: controller.controller.show_frame("SmartCartApp")).place(x=20, rely=0.9)

    def process_register(self):
        main_app = self.controller.controller
        username = self.user_entry.get().strip()
        mobile = self.mobile_entry.get().strip()
        email = self.controller.shared_data["email"]

        if not username or not mobile:
            messagebox.showwarning("Input Error", "All fields are required.")
            return

        # Basic mobile validation
        if not mobile.isdigit() or len(mobile) < 10:
            messagebox.showwarning("Input Error", "Please enter a valid mobile number.")
            return

        # Update Local AuthApp Data
        self.controller.shared_data["username"] = username
        self.controller.shared_data["mobile"] = mobile

        # Update Global MainApp Data
        main_app.shared_data["user_info"]["name"] = username
        main_app.shared_data["user_info"]["phone"] = mobile

        # --- Step 1: Connect to Supabase ---
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            messagebox.showerror("Config Error", "Supabase credentials are missing from environment.")
            return

        try:
            supabase = create_client(url, key)
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to Supabase:\n{repr(e)}")
            return

        # --- Step 2: Insert user into Supabase 'users' table ---
        try:
            current_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
            total_amount = main_app.shared_data["cart_info"].get("grand_total", 0.0)

            user_info = {
                "id": int(mobile),          # numeric in schema
                "username": username,
                "email": email,
                "phoneNumber": int(mobile), # ← correct column name (not phone_no)
                "last_time_spend": None,
                "avg_time": None,
                "last_spend": total_amount,
                "avg_spend": None,
                "last_purchase": None,
                "total_purchase": 0,
                "created_at": current_date,
            }

            response = supabase.table("users").insert(user_info).execute()

            if not response.data:
                messagebox.showerror("Registration Error", "Failed to save user data. Please try again.")
                return

            print(f"[Supabase] User registered: {response.data}")

        except Exception as e:
            error_msg = repr(e)
            # Handle duplicate user gracefully
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                print(f"[Supabase] User already exists, proceeding to OTP.")
            else:
                messagebox.showerror("Registration Error", f"Could not register user:\n{error_msg}")
                return

        # --- Step 3: Also save to local SQLite as backup ---
        try:
            current_date_local = datetime.datetime.now().isoformat()
            user_data = (
                mobile, username, email, mobile,
                None, None, total_amount, None,
                None, 0, current_date_local
            )
            conn = sqlite3.connect("cart_database.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users
                    (id, username, email, phone_no, last_time_spend, avg_time,
                    last_spend, avg_spend, last_purchase, total_purchase, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, user_data)
            conn.commit()
            conn.close()
            print("[SQLite] User saved locally.")

        except sqlite3.Error as e:
            # Non-fatal: log but don't block the flow
            print(f"[SQLite] Local save failed (non-fatal): {e}")

        # --- Step 4: Send OTP via Supabase ---
        try:
            otp_response = supabase.auth.sign_in_with_otp(
                {
                    "email": email,
                    "options": {
                        "should_create_user": True,
                    },
                }
            )

            print(f"[Supabase] OTP sent to {email}")
            messagebox.showinfo("OTP Sent", f"A verification code has been sent to:\n{email}\n\nPlease check your inbox.")
            self.controller.show_internal("OTPPage")

        except Exception as e:
            error_msg = repr(e)
            print(f"[Supabase] OTP send error: {error_msg}")
            messagebox.showerror("OTP Error", f"Failed to send OTP to {email}:\n{error_msg}")
            # Don't navigate — let user retry

class OTPPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller
        
        box = tk.Frame(self, bg=THEME["bg"])
        box.place(relx=0.5, rely=0.5, anchor="center")
        
        self.lbl = tk.Label(box, text="Verify", bg=THEME["bg"], fg="white", font=controller.fonts["hero"])
        self.lbl.pack(pady=10)
        
        self.otp_entry = StyledEntry(box, controller.fonts["input"])
        self.otp_entry.pack(pady=5, ipadx=10, ipady=10, fill="x")
        
        PrimaryButton(box, "VERIFY", self.verify).pack(pady=20)

    def on_show(self):
        email = self.controller.shared_data["email"]
        self.lbl.config(text=f"OTP sent to {email}")


    def verify(self):
        main_app = self.controller.controller
        otp = self.otp_entry.get().strip()

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            messagebox.showerror("Config Error", "Database URL or Key is not set in environment variables.")
            return

        try:
            supabase = create_client(url, key)
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to Database:\n{e}")
            return

        try:
            response = supabase.auth.verify_otp({
                "email": main_app.shared_data["user_info"]["email"],
                "token": otp,
                "type": "email",
            })

            if response.session:
                if main_app.shared_data.get("pending_checkout"):
                    self.controller.show_internal("PaymentPage")
                else:
                    self.controller.show_internal("SuccessPage")
            else:
                retry = messagebox.askretrycancel("Invalid OTP", "The OTP is invalid or expired. Please try again.")
                if retry:
                    self.otp_entry.delete(0, "end")  # Clear the entry for re-entry

        except Exception as e:
            error_msg = repr(e)
            # Handle specific Supabase auth errors gracefully
            if "Token has expired" in error_msg or "expired" in error_msg.lower():
                messagebox.showerror("OTP Expired", "Your OTP has expired. Please request a new one.")
            elif "Invalid" in error_msg or "invalid" in error_msg.lower():
                retry = messagebox.askretrycancel("Invalid OTP", "Please enter the correct OTP.")
                if retry:
                    self.otp_entry.delete(0, "end")
            else:
                messagebox.showerror("Verification Error", f"An error occurred:\n{error_msg}")


class SuccessPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller 

        self.box = tk.Frame(self, bg=THEME["bg"])
        self.box.place(relx=0.5, rely=0.5, anchor="center")

        self.header = tk.Label(self.box, text="Success", bg=THEME["bg"], fg=THEME["success"], font=controller.fonts["hero"])
        self.header.pack(pady=10)

        self.msg = tk.Label(self.box, text="", bg=THEME["bg"], fg="white", font=controller.fonts["input"])
        self.msg.pack(pady=10)

        PrimaryButton(self.box, "DONE", self.finish).pack(pady=20)

    def on_show(self):
        main_app = self.controller.controller
        if main_app.shared_data.get("pending_checkout"):
            saved = self.save_order(main_app)
            if saved:
                user = main_app.shared_data["user_info"].get("name", "User")
                self.header.config(text=f"Payment Confirmed, {user}")
                self.msg.config(text="Your payment has been successfully processed. Thank you for shopping with us!")
            else:
                self.header.config(text="Error", fg="red")
                self.msg.config(text="Failed to save order.")
            
        else:
            user = main_app.shared_data["user_info"].get("name", "User")
            self.header.config(text=f"Welcome, {user}")
            self.msg.config(text="Authentication Successful.")
            
            
    def save_order(self, main_app):
        cart = main_app.shared_data["cart_items"].items()
        email = main_app.shared_data["user_info"].get("email", "Guest")
        username = main_app.shared_data["user_info"].get("name", "User")
        mobile = main_app.shared_data["user_info"].get("phone", "0000000000")
        subtotal = main_app.shared_data["cart_info"].get("subtotal", 0.0)
        total_discount = main_app.shared_data["cart_info"].get("total_discount")
        total_amount = main_app.shared_data["cart_info"].get("grand_total")
        currentDate = datetime.datetime.now()
        print(currentDate)
        
        
        try:
            # user_data = (mobile, username, email, mobile, "NULL", "NULL", total_amount, "NULL", "NULL", "0", str(currentDate))
            # print(user_data)
            # conn = sqlite3.connect("cart_database.db")
            # cursor = conn.cursor()
            # cursor.execute("""
            #     INSERT INTO users
            #         (id, username, email, phone_no, last_time_spend, avg_time, last_spend, avg_spend,
            #         last_purchase, total_purchase, created_at)
            #         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            #         """, user_data)    
            # conn.commit()
            print("User data inserted into SQLite database.\nInitialised Supabase insertion...")
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
            try:
                # Convert cart dict to list for JSONB storage in Supabase
                items_list = []

                for barcode, item in cart:
                    items_list.append({
                        "barcode": barcode,
                        "name": item["name"],
                        "quantity": item["quantity"],
                        "price": item["price"]
                    })
                
                supabase = create_client(url, key)
                # 1. Insert into Supabase table
                # user_info = {"id": mobile, "username": username,"email": email, "phoneNumber": mobile, "last_purchase": str(currentDate)}
                # response = supabase.table("users").insert(user_info).execute()
                
                bill = {"user_id": mobile, "purchase_items": items_list, "subtotal": subtotal, "total_discount": total_discount, "grand_total": total_amount, "payment_status": "Paid"}
                response = supabase.table("billing").insert(bill).execute()
                
                bill_id = response.data[0]['bill_id']
                data = {"bill_id": bill_id, "user_id": mobile, "cart_id": "A101", "total_amount": total_amount, "payment_status": "Paid"}
                response = supabase.table("orders").insert(data).execute()
                
                # 2. Extract the unique ID for the link
                # order_uuid = response.data[0]['bill_id']

                # 3. This link triggers the Edge Function to render bill.html
                bill_url = f"http://127.0.0.1:5500/modified/view-bill.html?id={bill_id}"

                self.header.config(text="Order Successful!")
                self.msg.config(text=f"Bill link generated for {mobile}")
                print(f"Generated Bill Link: {bill_url}")
                
                self.header.config(text="Order Placed!")
                self.msg.config(text=f"Amount ₹{total_amount:.2f} billed to {email}")
                
        
                
            except Exception as e:
                print(f"Supabase Connection Error: {e}")
                self.header.config(text="Error", fg="red")
                self.msg.config(text=f"Supabase Error: {e}")
                return False
            
            # print(main_app.shared_data["cart_items"])
            # print(main_app.shared_data["user_info"])
            # print(main_app.shared_data["cart_total"])
            print("Successfully check out - Supabase code commented out for now.")
            
        except Exception as e:
            self.header.config(text="Error", fg="red")
            self.msg.config(text=str(e))
            
        return True


    def finish(self):
        # Only show security popup if it was a checkout/payment flow
        main_app = self.controller.controller
        if main_app.shared_data.get("pending_checkout"):
            self._show_security_popup()
        else:
            self._go_to_welcome()
            
    def _show_security_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Security Verification")
        popup.resizable(False, False)
        popup.grab_set()  # Make it modal — blocks interaction with main window

        # Center the popup on the screen
        popup_width, popup_height = 420, 220
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        x = (screen_w // 2) - (popup_width // 2)
        y = (screen_h // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup.configure(bg=THEME["bg"])

        # Lock icon label
        tk.Label(
            popup,
            text="🔒",
            font=("Helvetica", 28),
            bg=THEME["bg"],
            fg=THEME["success"]
        ).pack(pady=(18, 4))

        # Warning message
        tk.Label(
            popup,
            text="Do not close the window for exit security verification.\nClose it only after the security verification.",
            bg=THEME["bg"],
            fg="white",
            font=self.controller.fonts["input"],
            justify="center",
            wraplength=370
        ).pack(pady=(4, 16))

        # Button row
        btn_frame = tk.Frame(popup, bg=THEME["bg"])
        btn_frame.pack()

        # Cancel — stay on SuccessPage
        tk.Button(
            btn_frame,
            text="Cancel",
            width=12,
            bg=THEME.get("secondary", "#555555"),
            fg="white",
            font=self.controller.fonts["input"],
            relief="flat",
            cursor="hand2",
            command=popup.destroy          # Just close the popup, stay on page
        ).pack(side="left", padx=10)

        # Done — proceed to WelcomeScreen
        tk.Button(
            btn_frame,
            text="Done",
            width=12,
            bg=THEME["success"],
            fg="white",
            font=self.controller.fonts["input"],
            relief="flat",
            cursor="hand2",
            command=lambda: self._confirm_exit(popup)
        ).pack(side="left", padx=10)

    def _confirm_exit(self, popup):
        popup.destroy()
        self._go_to_welcome()

    def _go_to_welcome(self):
        main_app = self.controller.controller   # MainApp (has show_frame)
        main_app.shared_data["pending_checkout"] = False
        main_app.shared_data["cart_items"] = {}
        main_app.shared_data["cart_info"] = {}
        main_app.show_frame("WelcomeScreen") 