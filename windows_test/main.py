import tkinter as tk
from start_page import WelcomeScreen
from user_auth import AuthApp
from cart import SmartCartApp

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Home System")
        self.geometry("1024x600")
        self.resizable(True, True)
        
        # --- Shared Data Store (The "Bridge") ---
        self.shared_data = {
            "user_info": {},        # Stores { 'email': '...', 'name': '...' }
            "cart_items": {},       # Stores items passed from Cart
            "cart_total": 0.0,      # Stores bill amount
            "pending_checkout": False # Flag to trigger DB save after login
        }

        # --- Main Container ---
        # This frame holds all other pages stacked on top of each other
        self.container = tk.Frame(self, bg="#101622")
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        # --- Initialize All Pages ---
        # We pass 'self' as the controller so pages can access shared_data
        for F in (WelcomeScreen, AuthApp, SmartCartApp):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Start at Welcome Screen
        self.show_frame("WelcomeScreen")

    def show_frame(self, page_name):
        """Bring the requested frame to the front"""
        frame = self.frames[page_name]
        
        # Helper: If the page has an 'on_show' method, call it to refresh data
        if hasattr(frame, "on_show"):
            frame.on_show()
            
        frame.tkraise()

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()