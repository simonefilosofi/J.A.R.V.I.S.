# J.A.R.V.I.S.
**Just A Rather Very Intelligent System**

An Iron Man-themed personal AI assistant for macOS. Combines a wake-word voice assistant, a real-time system monitor dashboard, a cinematic startup sequence, and clap-triggered gesture control.

---

## Features

### Startup Animation (`jarvis_startup.py`)
- Full-screen animated splash screen with rotating arc reactor rings
- Auto-detects your city via IP geolocation
- Time-aware greeting ("Good morning", "Good evening", etc.) spoken aloud in a British accent (macOS `say`, Daniel voice)
- Live CPU/RAM stats overlaid on the animation
- Auto-closes after ~5.5 seconds with a fade-out

### Voice Assistant (`jarvis_voice.py`)
- Wake word: **"Hey JARVIS"** or **"JARVIS"**
- Bilingual: listens in Italian first, falls back to English
- Speech-to-text via Google Speech Recognition (no API key required)
- AI responses powered by **Groq API** (Llama 3.3 70B)
- Maintains up to 40 turns of conversation history
- Responds with the JARVIS personality — witty, intelligent, occasionally calls you "Mr. Filosofi"
- Text-to-speech via macOS `say` (Daniel voice, 165 wpm)
- Writes state to `/tmp/jarvis_state.json` for dashboard integration

### System Monitor Dashboard (`jarvis_hud.py`)
A web-based HUD served at `http://127.0.0.1:7879`, auto-opened in Safari fullscreen.

- **Arc reactor** — animated rotating rings with a pulsing core
- **CPU & RAM gauges** — color-coded: cyan (normal) → orange (warning) → red (critical > 90%)
- **System stats** — CPU frequency, temperature, RAM, disk usage, uptime
- **Battery** — percentage, charging status, time remaining
- **Network** — real-time ping to 8.8.8.8, upload/download speed
- **Weather** — current conditions and temperature (via wttr.in, refreshed every 5 min)
- **Top processes** — top 3 processes by CPU usage
- **Digital clock** — large format with seconds
- **Alert banner** — appears when CPU or RAM exceeds 90%
- **JARVIS voice panel** — activate/deactivate the voice assistant directly from the dashboard; opens a separate `/jarvis` page with a WebGL-rendered orb that reacts to listening/thinking/speaking states

### Clap Detection (`clap_ironman.py`)
- Continuously monitors the microphone at 44.1 kHz
- Detects 2 claps within 1.5 seconds
- On trigger:
  - Opens the Iron Man theme (Back in Black) on YouTube
  - Minimizes Chrome
  - Kills any existing process on port 7879
  - Launches the JARVIS dashboard

---

## Tech Stack

| Component | Technologies |
|-----------|-------------|
| Startup animation | Python, tkinter, psutil, requests |
| Voice assistant | sounddevice, numpy, scipy, SpeechRecognition, groq, python-dotenv |
| Dashboard | Python HTTP server, HTML/CSS/JS, WebGL shaders, psutil, requests |
| Clap detection | sounddevice, numpy, AppleScript |
| AI model | Groq API — `llama-3.3-70b-versatile` |
| External services | ipinfo.io (geolocation), wttr.in (weather), Google STT (speech recognition) |

> **macOS only.** The system uses `say` for TTS, AppleScript for window management, and assumes Safari/Chrome are available.

---

## Setup

### 1. Clone the repo
```bash
git clone <repo-url>
cd J.A.R.V.I.S.
```

### 2. Install dependencies
```bash
pip install psutil requests sounddevice numpy scipy SpeechRecognition groq python-dotenv
```

Optional — enables CPU temperature display on the dashboard:
```bash
brew install osx-cpu-temp
```

### 3. Configure environment
```bash
cp .env.example .env
```
Edit `.env` and add your Groq API key (free tier available at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=gsk_your_api_key_here
```

---

## Usage

Run each module independently depending on what you want:

```bash
# Cinematic startup sequence (~5 seconds)
python3 jarvis_startup.py

# Voice assistant (requires GROQ_API_KEY)
python3 jarvis_voice.py

# System monitor dashboard (opens in Safari on port 7879)
python3 jarvis_hud.py

# Clap-to-launch detection
python3 clap_ironman.py
```

The dashboard can also start and stop the voice assistant via its UI — no need to run `jarvis_voice.py` separately.

---

## Configuration

| Variable | File | Default | Description |
|----------|------|---------|-------------|
| `GROQ_API_KEY` | `.env` | — | Required for voice assistant |
| `CITY` | `.env` | auto-detected | Override geolocation city name |
| `WAKE_WORD` | `jarvis_voice.py` | `"jarvis"` | Wake word (case-insensitive) |
| `LISTEN_TIMEOUT` | `jarvis_voice.py` | `6` sec | How long to wait for a command |
| `THRESHOLD` | `clap_ironman.py` | `0.3` | Clap volume sensitivity |
| Dashboard port | `jarvis_hud.py` | `7879` | HTTP server port |

---

## Project Structure

```
J.A.R.V.I.S./
├── jarvis_startup.py   # Startup animation with arc reactor and voice greeting
├── jarvis_voice.py     # Wake-word voice assistant with Groq LLM
├── jarvis_hud.py       # Web-based system monitor dashboard
├── clap_ironman.py     # Clap gesture detection
├── .env.example        # Environment variable template
└── .gitignore
```
