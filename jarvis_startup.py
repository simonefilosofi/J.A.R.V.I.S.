#!/usr/bin/env python3
"""
JARVIS Startup Sequence
Animazione stile Iron Man + voce "Good morning, Mr. Stark"
"""

import tkinter as tk
import subprocess
import threading
import time
import math
import datetime
import requests


def detect_city():
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        return r.json().get("city", "Unknown")
    except Exception:
        return "Unknown"


CITY = detect_city()

BG       = "#020c10"
CYAN     = "#00d4ff"
DIM      = "#005f73"
ORANGE   = "#ff6b35"

GREETING_HOUR = {
    range(5, 12):  "Good morning",
    range(12, 18): "Good afternoon",
    range(18, 24): "Good evening",
    range(0, 5):   "Good night",
}


def get_greeting():
    h = datetime.datetime.now().hour
    for r, g in GREETING_HOUR.items():
        if h in r:
            return g
    return "Hello"


def speak(text):
    """Voce macOS — usa la voce 'Daniel' (accento britannico)."""
    subprocess.Popen(["say", "-v", "Daniel", "-r", "165", text])


class StartupScreen(tk.Tk):

    def __init__(self):
        super().__init__()
        self.attributes("-fullscreen", True)
        self.configure(bg=BG)
        self.attributes("-topmost", True)

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.W = self.winfo_screenwidth()
        self.H = self.winfo_screenheight()
        self.cx = self.W // 2
        self.cy = self.H // 2

        self._phase = 0
        self._angle = 0
        self._ring_radii = [120, 160, 200, 250]
        self._ring_speeds = [2, -1.5, 1, -0.8]
        self._opacity = 0.0

        self.attributes("-alpha", 0.0)
        self._fade_in()

    # ── Fade in ──────────────────────────────────────────────

    def _fade_in(self):
        self._opacity = min(self._opacity + 0.04, 1.0)
        self.attributes("-alpha", self._opacity)
        if self._opacity < 1.0:
            self.after(30, self._fade_in)
        else:
            self._start_animation()

    # ── Animazione principale ────────────────────────────────

    def _start_animation(self):
        self._anim_start = time.time()
        self._ring_angles = [0.0] * len(self._ring_radii)
        self._progress = 0.0
        self._text_alpha = 0
        self._animate()

        # Voce dopo 1.5 secondi
        greeting = get_greeting()
        h = datetime.datetime.now().hour
        threading.Timer(
            1.5,
            lambda: speak(f"{greeting}, Mister Stark. All systems are online.")
        ).start()

        # Chiudi dopo 5 secondi
        self.after(5500, self._close)

    def _animate(self):
        elapsed = time.time() - self._anim_start
        self.canvas.delete("all")
        c = self.canvas

        # ── Griglia di sfondo ────────────────────────────────
        for x in range(0, self.W, 60):
            c.create_line(x, 0, x, self.H, fill="#030f15", width=1)
        for y in range(0, self.H, 60):
            c.create_line(0, y, self.W, y, fill="#030f15", width=1)

        # ── Anelli rotanti ───────────────────────────────────
        for i, (r, speed) in enumerate(zip(self._ring_radii, self._ring_speeds)):
            self._ring_angles[i] += speed
            a = math.radians(self._ring_angles[i])
            # Arco principale
            dash = (12, 8) if i % 2 == 0 else (6, 14)
            c.create_oval(
                self.cx - r, self.cy - r,
                self.cx + r, self.cy + r,
                outline=DIM, width=1, dash=dash
            )
            # Dot rotante sull'anello
            dx = self.cx + r * math.cos(a)
            dy = self.cy + r * math.sin(a)
            c.create_oval(dx - 4, dy - 4, dx + 4, dy + 4,
                          fill=CYAN, outline="")

        # ── Arc reactor centrale ─────────────────────────────
        for radius, alpha in [(55, "33"), (40, "66"), (28, "aa"), (18, "ff")]:
            color = f"#00d4ff{alpha}" if len(f"#00d4ff{alpha}") == 9 else CYAN
        # cerchi concentrici
        c.create_oval(self.cx-55, self.cy-55, self.cx+55, self.cy+55,
                      outline="#00d4ff22", width=2)
        c.create_oval(self.cx-40, self.cy-40, self.cx+40, self.cy+40,
                      outline="#00d4ff55", width=2)
        c.create_oval(self.cx-25, self.cy-25, self.cx+25, self.cy+25,
                      outline=CYAN, width=3)
        c.create_oval(self.cx-10, self.cy-10, self.cx+10, self.cy+10,
                      fill=CYAN, outline="")

        # ── Barra di avanzamento ─────────────────────────────
        self._progress = min(elapsed / 3.5, 1.0)
        bar_w = 320
        bar_h = 4
        bx = self.cx - bar_w // 2
        by = self.cy + 290
        c.create_rectangle(bx, by, bx + bar_w, by + bar_h,
                            fill=DIM, outline="")
        c.create_rectangle(bx, by, bx + int(bar_w * self._progress), by + bar_h,
                            fill=CYAN, outline="")
        pct = int(self._progress * 100)
        c.create_text(self.cx, by + 20,
                      text=f"INITIALIZING SYSTEMS  {pct}%",
                      fill=DIM, font=("Courier New", 9))

        # ── Testo greeting ───────────────────────────────────
        if elapsed > 0.8:
            greeting = get_greeting().upper()
            c.create_text(self.cx, self.cy - 310,
                          text="◈  J.A.R.V.I.S.  ◈",
                          fill=CYAN, font=("Courier New", 22, "bold"))
            c.create_text(self.cx, self.cy - 275,
                          text="JUST A RATHER VERY INTELLIGENT SYSTEM",
                          fill=DIM, font=("Courier New", 9))

        if elapsed > 1.5:
            c.create_text(self.cx, self.cy + 230,
                          text=f"{greeting}, Mr. Stark.",
                          fill=CYAN, font=("Courier New", 28, "bold"))
            c.create_text(self.cx, self.cy + 265,
                          text=f"ALL SYSTEMS ONLINE  ·  {CITY.upper()}",
                          fill=DIM, font=("Courier New", 11))

        # ── Dati laterali ────────────────────────────────────
        import psutil, datetime as dt
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        now_str = dt.datetime.now().strftime("%H:%M:%S")

        for i, (key, val) in enumerate([
            ("CPU", f"{cpu:.0f}%"),
            ("RAM", f"{ram:.0f}%"),
            ("TIME", now_str),
            ("STATUS", "ONLINE"),
        ]):
            y = self.cy - 60 + i * 30
            c.create_text(self.cx - 340, y, text=key,
                          fill=DIM, font=("Courier New", 9), anchor="w")
            c.create_text(self.cx - 200, y, text=val,
                          fill=CYAN, font=("Courier New", 9, "bold"), anchor="w")

        self.after(33, self._animate)  # ~30fps

    def _close(self):
        self._fade_out()

    def _fade_out(self, alpha=1.0):
        alpha = max(alpha - 0.05, 0.0)
        self.attributes("-alpha", alpha)
        if alpha > 0:
            self.after(30, lambda: self._fade_out(alpha))
        else:
            self.destroy()


if __name__ == "__main__":
    import psutil
    psutil.cpu_percent(interval=None)
    time.sleep(0.1)
    app = StartupScreen()
    app.mainloop()
