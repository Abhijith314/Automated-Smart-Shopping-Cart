import tkinter as tk
from tkinter import font

class WelcomeScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        # --- Theme Colors ---
        self.colors = {
            "bg": "#101622",           
            "primary": "#135bec",      
            "primary_hover": "#2563eb",
            "white": "#ffffff",
            "gray": "#92a4c9"
        }
        
        self.configure(bg=self.colors["bg"])

        # --- Fonts ---
        self.fonts = {
            "hero": font.Font(family="Helvetica", size=32, weight="bold"),
            "sub": font.Font(family="Helvetica", size=14),
            "btn": font.Font(family="Helvetica", size=16, weight="bold"),
            "small": font.Font(family="Arial", size=10)
        }

        # --- Layout ---
        self.create_admin_button()
        self.create_center_content()
        self.create_footer()

    def create_admin_button(self):
        """Discreet Admin Button in Bottom-Left Corner"""
        self.admin_btn_frame = tk.Frame(self, bg=self.colors["bg"], cursor="hand2")
        self.admin_btn_frame.place(x=20, rely=1.0, anchor="sw", y=-20)

        icon_lbl = tk.Label(self.admin_btn_frame, text="⚙️", bg=self.colors["bg"], fg=self.colors["gray"], font=("Arial", 16))
        icon_lbl.pack(side="left")
        
        text_lbl = tk.Label(self.admin_btn_frame, text="ADMIN", bg=self.colors["bg"], fg=self.colors["gray"], font=("Helvetica", 10, "bold"))
        text_lbl.pack(side="left", padx=5)

        # Bind events
        for widget in [self.admin_btn_frame, icon_lbl, text_lbl]:
            widget.bind("<Button-1>", lambda e: self.open_admin_panel())

    def create_center_content(self):
        """Centered Welcome Text and Start Button"""
        center_frame = tk.Frame(self, bg=self.colors["bg"])
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center_frame, text="SMART SHOPPING CART", bg=self.colors["bg"], fg=self.colors["white"], font=self.fonts["hero"]).pack(pady=(0, 5))
        tk.Label(center_frame, text="for automated billing", bg=self.colors["bg"], fg=self.colors["gray"], font=self.fonts["sub"]).pack(pady=(0, 40))

        # Start Button
        self.start_btn = tk.Frame(center_frame, bg=self.colors["primary"], width=200, height=60, cursor="hand2")
        self.start_btn.pack_propagate(False)
        self.start_btn.pack()

        self.start_label = tk.Label(self.start_btn, text="GET STARTED  →", bg=self.colors["primary"], fg=self.colors["white"], font=self.fonts["btn"])
        self.start_label.place(relx=0.5, rely=0.5, anchor="center")

        # Bindings
        for widget in [self.start_btn, self.start_label]:
            widget.bind("<Enter>", lambda e: self.start_btn.configure(bg=self.colors["primary_hover"]))
            widget.bind("<Leave>", lambda e: self.start_btn.configure(bg=self.colors["primary"]))
            widget.bind("<Button-1>", lambda e: self.start_app())

    def create_footer(self):
        footer = tk.Label(self, text="v1.0.0 • System Ready", bg=self.colors["bg"], fg="#334155", font=self.fonts["small"])
        footer.place(relx=0.5, rely=0.95, anchor="center")

    def start_app(self):
        # Go to the Shopping Cart first
        self.controller.show_frame("SmartCartApp")

    def open_admin_panel(self):
        print("Requesting Admin Access...")