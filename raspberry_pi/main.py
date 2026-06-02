"""
main.py – Entry point for the Smart Shopping Cart application.
Optimised for 5-inch 800x480 Raspberry Pi touchscreen.
Run: python main.py
"""

import tkinter as tk
from start_page import WelcomeScreen
from cart       import SmartCartApp
from user_auth  import AuthApp

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Shopping Cart")
        self.geometry("800x480")          # 5-inch display resolution
        self.configure(bg="#101622")
        self.resizable(False, False)
        # Uncomment for true fullscreen on Pi touchscreen:
        # self.attributes("-fullscreen", True)

        self.shared_data = {
            "user_info":        {"name": "", "email": "", "phone": ""},
            "cart_items":       {},
            "cart_info":        {},
            "pending_checkout": False,
        }

        container = tk.Frame(self, bg="#101622")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for Page in (WelcomeScreen, SmartCartApp, AuthApp):
            name  = Page.__name__
            frame = Page(parent=container, controller=self)
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("WelcomeScreen")

    def show_frame(self, page_name: str):
        frame = self.frames[page_name]
        if hasattr(frame, "on_show"):
            frame.on_show()
        frame.tkraise()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
