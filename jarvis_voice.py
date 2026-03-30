#!/usr/bin/env python3
"""
JARVIS Voice Assistant - powered by Groq
Say "Hey JARVIS" -> JARVIS listens and replies like a real AI
"""

import json
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import speech_recognition as sr
from groq import Groq
import subprocess
import threading
import tempfile
import time
import os
import sys
import datetime

# ── Load environment variables from .env file ────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── State file (IPC with web interface) ──────────────────────
STATE_FILE = "/tmp/jarvis_state.json"

def write_state(state, user_text="", jarvis_text=""):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"state": state, "user_text": user_text, "jarvis_text": jarvis_text, "ts": time.time()}, f)
    except Exception:
        pass

# ── Config ───────────────────────────────────────────────────
WAKE_WORD      = "jarvis"
LISTEN_TIMEOUT = 6        # listen window in seconds after wake word
THRESHOLD      = 0.02     # microphone sensitivity
SAMPLE_RATE    = 16000
VOICE          = "Daniel"
VOICE_RATE     = 165

# ── Groq client ──────────────────────────────────────────────
API_KEY = os.environ.get("GROQ_API_KEY", "")
if not API_KEY:
    print("\n  ERROR: GROQ_API_KEY environment variable is not set.")
    print("  Choose one option:")
    print("  1) Copy .env.example to .env and add your API key")
    print("  2) Run: export GROQ_API_KEY='gsk_...'")
    print("\n  Get a free key at console.groq.com")
    sys.exit(1)

client = Groq(api_key=API_KEY)

def get_system_prompt():
    """Generate system prompt with real-time date and time."""
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%A, %d %B %Y").upper()
    
    return f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the AI assistant of Simone Filosofi.

CURRENT SYSTEM TIME: {current_time}
CURRENT DATE: {current_date}

Your personality:
- Highly intelligent, precise, and slightly witty
- Address the user as "Mr. Filosofi" occasionally, but not every sentence
- Concise — voice responses should be short (2-4 sentences max) since they will be read aloud
- Always refer to the current time above when asked (e.g., "It's currently {current_time}")
- You can discuss any topic: science, technology, philosophy, current events, advice, jokes, Iron Man lore, etc.
- Occasionally make subtle references to Stark Industries, the suits, or the Avengers when relevant
- Never break character. You are JARVIS, not an AI assistant.
- Respond in the same language the user speaks (Italian or English)
- Keep responses SHORT — they will be spoken aloud, so avoid long lists or markdown formatting"""

conversation_history = []

# ── TTS ──────────────────────────────────────────────────────
def speak(text, wait=True):
    # Remove characters that sound odd when spoken aloud.
    clean = text.replace("*", "").replace("#", "").replace("`", "").replace("_", " ")
    print(f"\n  JARVIS: {clean}\n")
    fn = subprocess.run if wait else subprocess.Popen
    fn(["say", "-v", VOICE, "-r", str(VOICE_RATE), clean])

# ── Claude API ────────────────────────────────────────────────
def ask_claude(user_text):
    global conversation_history

    conversation_history.append({"role": "user", "content": user_text})

    # Keep up to 20 conversation turns.
    if len(conversation_history) > 40:
        conversation_history = conversation_history[-40:]

    try:
        # Get real-time system prompt with current date/time
        system_prompt_with_time = get_system_prompt()
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            messages=[{"role": "system", "content": system_prompt_with_time}] + conversation_history,
        )
        reply = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        err = str(e).lower()
        if "auth" in err or "api key" in err:
            return "Invalid API key. Check it on console.groq.com."
        if "rate" in err:
            return "Too many requests in a short time. Please wait a moment."
        return f"System error: {str(e)[:60]}"

# ── Registrazione audio ───────────────────────────────────────
def record(seconds=6):
    chunks = []
    total = int(SAMPLE_RATE * seconds)
    recorded = 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype='float32', blocksize=1024) as stream:
        deadline = time.time() + seconds + 1
        while recorded < total and time.time() < deadline:
            data, _ = stream.read(1024)
            chunks.append(data.copy())
            recorded += 1024

    if not chunks:
        return None

    audio = np.concatenate(chunks).flatten()
    audio_int16 = (audio * 32767).astype(np.int16)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(tmp.name, SAMPLE_RATE, audio_int16)
    return tmp.name

# ── Trascrizione ─────────────────────────────────────────────
recognizer = sr.Recognizer()

def transcribe(wav_path, language="it-IT"):
    try:
        with sr.AudioFile(wav_path) as src:
            audio = recognizer.record(src)
        # Try Italian first, then English.
        try:
            return recognizer.recognize_google(audio, language="it-IT").lower()
        except sr.UnknownValueError:
            try:
                return recognizer.recognize_google(audio, language="en-US").lower()
            except sr.UnknownValueError:
                return None
    except sr.RequestError:
        speak("Speech transcription service is not available.")
        return None
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass

# ── Wake word detection ───────────────────────────────────────
def listen_for_wake_word():
    chunk = 4096
    buf = []
    max_buf = int(SAMPLE_RATE * 3 / chunk)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype='float32', blocksize=chunk) as stream:
        while True:
            data, _ = stream.read(chunk)
            buf.append(data.copy())
            if len(buf) > max_buf:
                buf.pop(0)

            if np.max(np.abs(data)) < THRESHOLD:
                continue

            audio = np.concatenate(buf).flatten()
            audio_int16 = (audio * 32767).astype(np.int16)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav.write(tmp.name, SAMPLE_RATE, audio_int16)

            try:
                with sr.AudioFile(tmp.name) as src:
                    a = recognizer.record(src)
                text = recognizer.recognize_google(a, language="it-IT").lower()
                if WAKE_WORD in text:
                    return
                text2 = recognizer.recognize_google(a, language="en-US").lower()
                if WAKE_WORD in text2:
                    return
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

# ── Main ──────────────────────────────────────────────────────
def main():
    print("\n" + "="*52)
    print("  J.A.R.V.I.S. — powered by Groq / Llama 3.3 70B")
    print("="*52)
    print("  Wake word : 'Hey JARVIS'")
    print("  Languages : Italian / English")
    print("  Press Ctrl+C to shut down")
    print("="*52 + "\n")

    write_state("idle")
    speak("JARVIS system online. I am ready, Mr. Stark.", wait=True)

    while True:
        print("  Listening... (say 'Hey JARVIS')")
        write_state("listening")
        listen_for_wake_word()

        write_state("listening")
        speak("How can I help you?", wait=False)
        print("  Wake word detected. Listening for your command...")

        wav_path = record(seconds=LISTEN_TIMEOUT)
        if not wav_path:
            write_state("speaking", jarvis_text="I did not hear anything, Mr. Stark.")
            speak("I did not hear anything, Mr. Stark.")
            write_state("idle")
            continue

        user_text = transcribe(wav_path)
        if not user_text:
            write_state("speaking", jarvis_text="I did not understand. Could you repeat that?")
            speak("I did not understand. Could you repeat that?")
            write_state("idle")
            continue

        print(f"  You: {user_text}")
        write_state("thinking", user_text=user_text)

        # Get model response.
        reply = ask_claude(user_text)
        write_state("speaking", user_text=user_text, jarvis_text=reply)
        speak(reply, wait=True)
        write_state("idle", jarvis_text=reply)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  JARVIS offline. Have a great day, Mr. Filosofi.")
