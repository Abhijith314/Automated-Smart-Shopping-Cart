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
    "bg": "#101622", "card": "#151a25", "primary": "#135bec",
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

        for F in (EmailPage, RegisterPage, OTPPage, PaymentPage, WelcomePage):
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
        
        # Sync with SQLite
        try:
            conn = sqlite3.connect("cart_database.db")
            cursor = conn.cursor()
            
            # Save to local AuthApp and global MainApp
            self.controller.shared_data["email"] = email
            self.controller.controller.shared_data["user_info"]["email"] = email
            
            cursor.execute("SELECT username, phone_no FROM users WHERE email=?", (email,))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.controller.shared_data["username"] = result[0]
                self.controller.shared_data["mobile"] = result[1]
                self.controller.controller.shared_data["user_info"]["phone"] = result[1]
                self.controller.controller.shared_data["user_info"]["name"] = result[0]
                self.controller.show_internal("OTPPage")
            else:
                # checkout_message = "You have not . Please register to proceed with checkout."
                confirm = messagebox.askokcancel("Register email", f"You have not registered with the mail \"{email}\".\n\nPlease register to proceed with checkout.")
                if confirm:
                    self.controller.show_internal("RegisterPage")
                else:
                    self.controller.show_internal("EmailPage")
        except sqlite3.Error as e:
            messagebox.showerror("DB Error", str(e))

class RegisterPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller
        
        box = tk.Frame(self, bg=THEME["bg"])
        box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(box, text="Registration", bg=THEME["bg"], fg=THEME["white"], font=controller.fonts["header"]).pack(pady=(0, 10))
        tk.Label(box, text="We need a few details.", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["sub"]).pack(pady=(0, 30))

        tk.Label(box, text="Username", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["small"]).pack(anchor="w", pady=(0,5))
        # FIXED: Passing actual font object
        self.user_entry = StyledEntry(box, controller.fonts["input"])
        self.user_entry.pack(ipadx=10, ipady=10, fill="x", pady=(0, 15))

        tk.Label(box, text="Mobile Number", bg=THEME["bg"], fg=THEME["gray"], font=controller.fonts["small"]).pack(anchor="w", pady=(0,5))
        # FIXED: Passing actual font object
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
        
        if username and mobile:
            # Update Local AuthApp Data
            self.controller.shared_data["username"] = username
            self.controller.shared_data["mobile"] = mobile
            
            # Update Global MainApp Data
            self.controller.controller.shared_data["user_info"]["name"] = username
            self.controller.controller.shared_data["user_info"]["phone"] = mobile
            total_amount = main_app.shared_data["cart_info"].get("grand_total", 0.0)
            user_data = (mobile, username, email, mobile, "NULL", "NULL", total_amount, "NULL", "NULL", "0", "2025-12-23 19:21:06.361401+00")
                        
            try:
                conn = sqlite3.connect("cart_database.db")
                cursor = conn.cursor()
                # url = os.getenv("SUPABASE_URL")
                # key = os.getenv("SUPABASE_KEY")
                # supabase = create_client(url, key)

                cursor.execute("""
                    INSERT INTO users
                        (id, username, email, phone_no, last_time_spend, avg_time, last_spend, avg_spend,
                        last_purchase, total_purchase, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, user_data)
                conn.commit()
                conn.close()
                # currentDate = datetime.datetime.now()
                # user_info = {"id": mobile, "username": username,"email": email, "phoneNumber": mobile, "last_purchase": str(currentDate)}
                # response = supabase.table("users").insert(user_info).execute()
                # if response:
                #     print("User registered in Supabase.")
                #     response = supabase.auth.sign_in_with_otp(
                #         {
                #             "email": email,
                #             "options": {
                #                 "should_create_user": True,
                #             },
                #         }
                #     )
                    
                #     print("OTP sent! Please check your email.")
                
                #     if response:
                #         messagebox.showinfo("Registration", "Details saved. Proceeding to OTP verification.")
                #         self.controller.show_internal("OTPPage")
                    
                self.controller.show_internal("OTPPage")
                # supabase.table("users").insert(user_data).execute()
                
            except sqlite3.Error as e:
                messagebox.showerror("DB Error", str(e))
                self.controller.show_internal("RegisterPage")
           
        else:
            messagebox.showwarning("Input Error", "All fields are required.")

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
        # Here you would normally insert the NEW user into DB if they came from RegisterPage
        # For simplicity, we proceed to welcome
        main_app = self.controller.controller
        otp = self.otp_entry.get().strip()
        # url = os.getenv("SUPABASE_URL")
        # key = os.getenv("SUPABASE_KEY")
        # try:
        #     supabase = create_client(url, key)
        #     try:
        #         response = supabase.auth.verify_otp({
        #             'email': main_app.shared_data["user_info"]["email"],
        #             'token': otp,
        #             'type': 'email',
        #         })
        #         # If successful, response.session will contain the access_token
        #         if response.session:
        #             main_app.shared_data["pending_checkout"] = True
        #             self.controller.show_internal("PaymentPage")
        #         else:
        #             messagebox.showerror("OTP Error", "Invalid or expired OTP.")
                
        #     except Exception as e:
        #         print("DEBUG ERROR:", repr(e))
                
        # except Exception as e:
        #     print(f"Supabase Connection Error: {e}")
        if otp == "1234":
            if main_app.shared_data.get("pending_checkout"):
                # Send them to the new payment page!
                self.controller.show_internal("PaymentPage")
            else:
                self.controller.show_internal("WelcomePage")
        else: 
            messagebox.askretrycancel("Invalid OTP", "Please enter the valid otp")
            
    # def verify_otp(email, token):
    # """Step 2: Verify the OTP to create a session"""
    # try:
    #     response = supabase.auth.verify_otp({
    #         'email': email,
    #         'token': token,
    #         'type': 'email',
    #     })
    #     # If successful, response.session will contain the access_token
    #     if response.session:
    #         return True, response.user
    #     else:
    #         return False, "Invalid or expired OTP."
    # except Exception as e:
    #     return False, repr(e)

class WelcomePage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=THEME["bg"])
        self.controller = controller 
        
        self.box = tk.Frame(self, bg=THEME["bg"])
        self.box.place(relx=0.5, rely=0.5, anchor="center")
        
        self.header = tk.Label(self.box, text="Success", bg=THEME["bg"], fg=THEME["primary"], font=controller.fonts["hero"])
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
                self.header.config(text=f"Welcome, {user}")
                self.msg.config(text="Authentication Successful.")
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
        
        # mobile = "8848385318"
        # username = "Abhijith"
        # email = "test@gmail.com"
        # total_amount = "1234"
        
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

            
            # items_list = [
            #     {"barcode": barcode, "name": item['name'], "quantity": item['quantity'], "price": item['price']}
            #     for barcode, item in main_app.shared_data["cart_items"].values()
            # ]
            # print(items_list)
            
            # mobile = main_app.shared_data["user_info"].get("mobile")
            # total = main_app.shared_data["cart_total"]

            # try:
                
            
            # except Exception as e:
            #     self.header.config(text="Error", fg="red")
            #     self.msg.config(text=f"Supabase Error: {e}")
                
            # conn.close()
            
        except Exception as e:
            self.header.config(text="Error", fg="red")
            self.msg.config(text=str(e))
            
        return True


    # def save_order(self, main_app):
    #     # Credentials from Supabase Settings -> API
    #     url = os.getenv("SUPABASE_URL")
    #     key = os.getenv("SUPABASE_KEY")
    #     try:
    #         supabase = create_client(url, key)
    #     except Exception as e:
    #         print(f"Supabase Connection Error: {e}")
        
    #     print(main_app.shared_data["cart_items"])
    #     print(main_app.shared_data["user_info"])
    #     print(main_app.shared_data["cart_total"])
    #     print("Successfully check out - Supabase code commented out for now.")

    #     # Convert cart dict to list for JSONB storage in Supabase
    #     items_list = []

    #     for barcode, item in main_app.shared_data["cart_items"].items():
    #         items_list.append({
    #             "barcode": barcode,
    #             "name": item["name"],
    #             "quantity": item["quantity"],
    #             "price": item["price"]
    # })
    #     # items_list = [
    #     #     {"barcode": barcode, "name": item['name'], "quantity": item['quantity'], "price": item['price']}
    #     #     for barcode, item in main_app.shared_data["cart_items"].values()
    #     # ]
    #     print(items_list)
        
    #     mobile = main_app.shared_data["user_info"].get("mobile")
    #     total = main_app.shared_data["cart_total"]

    #     try:
    #         # 1. Insert into Supabase 'orders' table
    #         data = {"user_id": mobile, "purchase_items": items_list, "grand_total": total}
    #         response = supabase.table("billing").insert(data).execute()
            
    #         # 2. Extract the unique ID for the link
    #         order_uuid = response.data[0]['bill_id']

    #     #     # 3. This link triggers the Edge Function to render bill.html
    #         bill_url = f"{url}/functions/v1/view-bill?id={order_uuid}"

    #         self.header.config(text="Order Successful!")
    #         self.msg.config(text=f"Bill link generated for {mobile}")
    #         print(f"Generated Bill Link: {bill_url}")

    #     except Exception as e:
    #         self.header.config(text="Error", fg="red")
    #         print(f"Supabase Error: {e}")



    def finish(self):
        # Reset Cart
        self.controller.controller.shared_data["pending_checkout"] = False
        self.controller.controller.shared_data["cart_items"] = {}
        self.controller.controller.shared_data["cart_info"] = {}
        self.controller.controller.show_frame("WelcomeScreen")