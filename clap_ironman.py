#!/usr/bin/env python3
"""
Batti le mani → Back in Black (Iron Man) su YouTube
"""

import sounddevice as sd
import numpy as np
import webbrowser
import subprocess
import time
import sys
import threading

# URL YouTube - Back in Black (Iron Man soundtrack)
YOUTUBE_URL = "https://www.youtube.com/watch?v=qRrElw4TSB4"

# Impostazioni rilevamento applauso
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
THRESHOLD = 0.3          # soglia volume (0.0 - 1.0), abbassa se non rileva
MIN_CLAP_INTERVAL = 0.1  # secondi minimi tra picchi dello stesso applauso
CLAPS_NEEDED = 2         # numero di applausi necessari per attivare
CLAP_WINDOW = 1.5        # secondi entro cui contare gli applausi

clap_times = []
last_clap_time = 0
last_triggered = 0
trigger_event = threading.Event()
COOLDOWN = 10  # secondi di pausa dopo ogni attivazione

def detect_clap(indata, frames, time_info, status):
    global last_clap_time, clap_times, last_triggered

    volume = np.max(np.abs(indata))
    now = time.time()

    # Ignora tutto durante il cooldown
    if now - last_triggered < COOLDOWN:
        return

    if volume > THRESHOLD and (now - last_clap_time) > MIN_CLAP_INTERVAL:
        last_clap_time = now
        clap_times.append(now)
        print(f"  Botto rilevato! (volume: {volume:.2f})")

        clap_times = [t for t in clap_times if now - t <= CLAP_WINDOW]

        if len(clap_times) >= CLAPS_NEEDED:
            clap_times.clear()
            last_triggered = now
            print("\n  ATTIVATO! Apro Back in Black su YouTube...\n")
            subprocess.Popen(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", YOUTUBE_URL])
            # Minimizza Chrome dopo 1 secondo
            min_script = '''
delay 1
tell application "Google Chrome" to activate
delay 0.3
tell application "System Events"
    tell process "Google Chrome"
        set frontmost to true
        click (first button of front window whose description is "minimize button")
    end tell
end tell
'''
            subprocess.Popen(["osascript", "-e", min_script])
            trigger_event.set()

print("=" * 50)
print("  JARVIS Clap Detector - Iron Man Edition")
print("=" * 50)
print(f"  Batti le mani {CLAPS_NEEDED} volte entro {CLAP_WINDOW}s")
print(f"  Soglia volume: {THRESHOLD}")
print("  Premi Ctrl+C per uscire")
print("=" * 50 + "\n")

try:
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        dtype='float32',
        callback=detect_clap
    ):
        while True:
            if trigger_event.wait(timeout=0.1):
                trigger_event.clear()
                # Libera la porta e lancia la dashboard
                subprocess.run(
                    "lsof -ti :7879 | xargs kill -9 2>/dev/null; true",
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                time.sleep(0.4)
                subprocess.Popen(
                    [sys.executable, "/Users/simonefilosofi/Desktop/tonystark/jarvis_hud.py"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
except KeyboardInterrupt:
    print("\nUscito.")
