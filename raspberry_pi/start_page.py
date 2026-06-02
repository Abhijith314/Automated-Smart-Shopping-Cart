"""
start_page.py – Welcome screen
Optimised for 5-inch 800x480 Raspberry Pi touchscreen.
"""

import tkinter as tk
from tkinter import font

class WelcomeScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.colors = {
            "bg":            "#101622",
            "primary":       "#135bec",
            "primary_hover": "#2563eb",
            "white":         "#ffffff",
            "gray":          "#92a4c9",
        }
        self.configure(bg=self.colors["bg"])

        # Fonts scaled for 5-inch display
        self.fonts = {
            "hero":  font.Font(family="Helvetica", size=22, weight="bold"),
            "sub":   font.Font(family="Helvetica", size=11),
            "btn":   font.Font(family="Helvetica", size=13, weight="bold"),
            "small": font.Font(family="Arial",     size=9),
        }

        self._create_admin_button()
        self._create_center_content()
        self._create_footer()

    def _create_admin_button(self):
        self.admin_btn_frame = tk.Frame(self, bg=self.colors["bg"], cursor="hand2")
        self.admin_btn_frame.place(x=20, rely=1.0, anchor="sw", y=-15)

        icon_lbl = tk.Label(self.admin_btn_frame, text="⚙️",
                            bg=self.colors["bg"], fg=self.colors["gray"],
                            font=("Arial", 12))
        icon_lbl.pack(side="left")
        text_lbl = tk.Label(self.admin_btn_frame, text="ADMIN",
                            bg=self.colors["bg"], fg=self.colors["gray"],
                            font=("Helvetica", 9, "bold"))
        text_lbl.pack(side="left", padx=4)

        for w in [self.admin_btn_frame, icon_lbl, text_lbl]:
            w.bind("<Button-1>", lambda e: self._open_admin_panel())

    def _create_center_content(self):
        center = tk.Frame(self, bg=self.colors["bg"])
        center.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(center, text="SMART SHOPPING CART",
                 bg=self.colors["bg"], fg=self.colors["white"],
                 font=self.fonts["hero"]).pack(pady=(0, 4))
        tk.Label(center, text="Automated barcode billing with weight verification",
                 bg=self.colors["bg"], fg=self.colors["gray"],
                 font=self.fonts["sub"]).pack(pady=(0, 30))

        self.start_btn = tk.Frame(center, bg=self.colors["primary"],
                                  width=180, height=48, cursor="hand2")
        self.start_btn.pack_propagate(False)
        self.start_btn.pack()

        self.start_label = tk.Label(self.start_btn, text="GET STARTED →",
                                    bg=self.colors["primary"],
                                    fg=self.colors["white"],
                                    font=self.fonts["btn"])
        self.start_label.place(relx=0.5, rely=0.5, anchor="center")

        for w in [self.start_btn, self.start_label]:
            w.bind("<Enter>",    lambda e: self.start_btn.configure(bg=self.colors["primary_hover"]))
            w.bind("<Leave>",    lambda e: self.start_btn.configure(bg=self.colors["primary"]))
            w.bind("<Button-1>", lambda e: self._start_app())

    def _create_footer(self):
        tk.Label(self, text="v1.0.0  •  System Ready",
                 bg=self.colors["bg"], fg="#334155",
                 font=self.fonts["small"]
                 ).place(relx=0.5, rely=0.96, anchor="center")

    def _start_app(self):
        self.controller.show_frame("SmartCartApp")

    def _open_admin_panel(self):
        print("Requesting Admin Access…")

    # Alias for backward compatibility
    def start_app(self):       self._start_app()
    def open_admin_panel(self): self._open_admin_panel()
