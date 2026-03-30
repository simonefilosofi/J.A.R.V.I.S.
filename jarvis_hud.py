#!/usr/bin/env python3
"""
JARVIS HUD - Iron Man Style
Serve una dashboard HTML aggiornata ogni secondo, aperta in Chrome.
"""

import http.server
import threading
import subprocess
import time
import json
import psutil
import datetime
import requests
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from groq import Groq as _Groq
    _groq_client = _Groq(api_key=os.environ.get("GROQ_API_KEY", "")) if os.environ.get("GROQ_API_KEY") else None
except ImportError:
    _groq_client = None

try:
    from jarvis_calendar import TOOL_DEF as _TOOL_DEF, dispatch_tool_call as _dispatch_tool_call
except ImportError:
    _TOOL_DEF = None
    _dispatch_tool_call = None

chat_history = []

def _get_system_prompt():
    now = datetime.datetime.now()
    return (
        f"You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the AI assistant of Simone Filosofi.\n"
        f"CURRENT TIME: {now.strftime('%H:%M:%S')}  DATE: {now.strftime('%A, %d %B %Y').upper()}\n"
        "Your personality: highly intelligent, precise, slightly witty. Address the user as 'Mr. Filosofi' occasionally.\n"
        "Keep replies concise and clear. Never break character. Respond in the same language the user writes in."
    )

def chat_with_jarvis(user_message):
    global chat_history
    if not _groq_client:
        return "GROQ_API_KEY not configured. Add it to your .env file."
    chat_history.append({"role": "user", "content": user_message})
    if len(chat_history) > 40:
        chat_history = chat_history[-40:]
    try:
        system_prompt = _get_system_prompt()
        kwargs = {"model": "llama-3.3-70b-versatile", "max_tokens": 400,
                  "messages": [{"role": "system", "content": system_prompt}] + chat_history}
        if _TOOL_DEF:
            kwargs["tools"] = [_TOOL_DEF]
            kwargs["tool_choice"] = "auto"

        resp = _groq_client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        # ── Tool call handling ────────────────────────────────
        if msg.tool_calls and _dispatch_tool_call:
            chat_history.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]
            })
            for tc in msg.tool_calls:
                result_str = _dispatch_tool_call(tc.function.name, tc.function.arguments)
                chat_history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
            resp2 = _groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=400,
                messages=[{"role": "system", "content": system_prompt}] + chat_history,
            )
            reply = resp2.choices[0].message.content
            chat_history.append({"role": "assistant", "content": reply})
            return reply

        reply = msg.content
        chat_history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        return f"System error: {str(e)[:80]}"

voice_process = None

PORT = 7879

# ── Rilevamento città ────────────────────────────────────────
def detect_city():
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        return r.json().get("city", "Unknown")
    except Exception:
        return "Unknown"

CITY = detect_city()

# ── Meteo ────────────────────────────────────────────────────
weather_cache = {"temp": "--", "desc": "...", "icon": "◈"}

def fetch_weather():
    while True:
        try:
            r = requests.get(f"https://wttr.in/{CITY}?format=j1", timeout=5)
            j = r.json()
            cur = j["current_condition"][0]
            temp = cur["temp_C"]
            desc = cur["weatherDesc"][0]["value"]
            code = int(cur["weatherCode"])
            if code == 113:   icon = "☀"
            elif code < 200:  icon = "⛅"
            elif code < 300:  icon = "☁"
            elif code < 400:  icon = "🌧"
            elif code < 400:  icon = "❄"
            elif code >= 386: icon = "⛈"
            else:             icon = "◈"
            weather_cache.update({"temp": temp, "desc": desc, "icon": icon})
        except Exception:
            pass
        time.sleep(300)

threading.Thread(target=fetch_weather, daemon=True).start()

# ── HTML della dashboard ─────────────────────────────────────
HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>JARVIS · SYSTEM MONITOR</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
  * { margin:0; padding:0; box-sizing:border-box; }

  :root { --c: #00d4ff; --dim: #005f73; --bg: #020c10; --warn: #ff6b35; --crit: #ff2251; }

  body {
    background: var(--bg);
    color: var(--c);
    font-family: 'Share Tech Mono', 'Courier New', monospace;
    min-height: 100vh;
    overflow: hidden;
    transition: background 0.3s;
  }
  body.alert { animation: alertbg 0.5s ease-in-out infinite alternate; }
  @keyframes alertbg {
    from { background: #020c10; }
    to   { background: #200005; }
  }

  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  /* ── Main ── */
  #main { opacity: 0; transition: opacity 0.8s; }
  #main.visible { opacity: 1; }

  .scanline {
    position: fixed; left: 0; right: 0; height: 2px;
    background: rgba(0,212,255,0.07);
    animation: scan 4s linear infinite;
    pointer-events: none; z-index: 99;
  }
  @keyframes scan { 0%{top:-2px} 100%{top:100%} }

  body { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
  .container { padding: 24px 36px; width: 860px; max-width: 98vw; position: relative; z-index: 1; }

  /* Header */
  .header {
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid var(--dim);
    padding-bottom: 10px; margin-bottom: 14px;
  }
  .header h1 { font-size: 17px; letter-spacing: 3px; }
  .header span { font-size: 9px; color: var(--dim); letter-spacing: 2px; }

  /* Arc reactor */
  .reactor-wrap { display: flex; justify-content: center; margin: 4px 0 10px; }
  #reactor { display: block; }

  /* Clock */
  .clock { text-align: center; margin-bottom: 10px; }
  .clock .time { font-size: 48px; letter-spacing: 4px; line-height:1; transition: color 0.4s; }
  .clock .date { font-size: 10px; color: var(--dim); letter-spacing: 2px; margin-top: 4px; }

  .sep { border: none; border-top: 1px solid var(--dim); margin: 10px 0; }

  /* Gauges */
  .gauges { display: flex; justify-content: space-around; margin: 8px 0; }

  /* Grid layout */
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 32px; }
  .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 24px; }
  .full  { grid-column: 1 / -1; }

  /* Stats */
  .stats { font-size: 11px; }
  .stat-row {
    display: flex; justify-content: space-between;
    padding: 4px 0; border-bottom: 1px solid #011a22;
  }
  .stat-key { color: var(--dim); letter-spacing: 1px; }
  .stat-val { color: var(--c); font-weight: bold; transition: color 0.4s; }

  /* Alert banner */
  #alert-banner {
    display: none; text-align: center;
    font-size: 11px; letter-spacing: 3px;
    color: var(--crit); padding: 5px 0;
    border: 1px solid var(--crit);
    animation: blink 0.6s step-start infinite;
    margin-bottom: 8px;
  }
  @keyframes blink { 50% { opacity: 0; } }
  #alert-banner.visible { display: block; }

  /* Weather */
  .weather { margin-top: 10px; }
  .weather-title { font-size: 9px; color: var(--dim); letter-spacing: 2px; margin-bottom: 4px; }
  .weather-main { font-size: 18px; }
  .weather-desc { font-size: 9px; color: var(--dim); letter-spacing: 1px; margin-top: 2px; }
</style>
</head>
<body>

<!-- Main HUD -->
<div id="main">
  <div class="scanline"></div>
  <div class="container">

    <div class="header">
      <h1>◈ J.A.R.V.I.S.</h1>
      <span>STARK INDUSTRIES</span>
    </div>

    <div id="alert-banner">⚠ SYSTEM OVERLOAD DETECTED ⚠</div>

    <!-- Pulsanti JARVIS Voice + Chat -->
    <div style="text-align:center;margin-bottom:10px;">
      <div style="display:inline-flex;gap:10px;align-items:center;">
        <button id="voice-btn" onclick="toggleVoice()" style="
          background:transparent; border:1px solid #005f73; color:#00d4ff;
          font-family:'Share Tech Mono','Courier New',monospace; font-size:11px;
          letter-spacing:2px; padding:8px 28px; cursor:pointer;
          transition:all 0.3s;
        ">◈ ACTIVATE JARVIS</button>
        <button onclick="window.open('/chat','_blank')" style="
          background:transparent; border:1px solid #005f73; color:#00d4ff;
          font-family:'Share Tech Mono','Courier New',monospace; font-size:11px;
          letter-spacing:2px; padding:8px 28px; cursor:pointer;
          transition:all 0.3s;
        " onmouseover="this.style.borderColor='#00d4ff';this.style.boxShadow='0 0 10px #00d4ff44'"
           onmouseout="this.style.borderColor='#005f73';this.style.boxShadow='none'"
        >◈ CHAT</button>
      </div>
      <div id="voice-status" style="font-size:9px;color:#005f73;letter-spacing:1px;margin-top:4px;"></div>
    </div>

    <!-- ROW 1: Reactor + Clock -->
    <div style="display:flex;align-items:center;justify-content:center;gap:32px;margin-bottom:10px;">
      <svg id="reactor" width="72" height="72" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="36" fill="none" stroke="#005f73" stroke-width="1" stroke-dasharray="4 6"/>
        <circle id="r-ring1" cx="40" cy="40" r="36" fill="none" stroke="#00d4ff" stroke-width="1.5" stroke-dasharray="30 200" stroke-linecap="round"/>
        <circle cx="40" cy="40" r="28" fill="none" stroke="#003344" stroke-width="4"/>
        <circle id="r-ring2" cx="40" cy="40" r="28" fill="none" stroke="#00d4ff" stroke-width="2" stroke-dasharray="15 160" stroke-linecap="round"/>
        <polygon id="r-hex" points="40,22 54,31 54,49 40,58 26,49 26,31" fill="none" stroke="#00d4ff" stroke-width="1.5" opacity="0.6"/>
        <circle cx="40" cy="40" r="10" fill="#020c10" stroke="#00d4ff" stroke-width="2"/>
        <circle id="r-core" cx="40" cy="40" r="6" fill="#00d4ff" opacity="0.9"/>
        <circle cx="40" cy="40" r="3" fill="white" opacity="0.8"/>
      </svg>
      <div class="clock" style="margin:0;text-align:left;">
        <div class="time" id="time">--:--:--</div>
        <div class="date" id="date">...</div>
      </div>
    </div>

    <hr class="sep">

    <!-- ROW 2: CPU gauge | gauges | RAM gauge -->
    <div class="gauges">
      <svg width="130" height="100" viewBox="0 0 110 90">
        <path d="M 15 78 A 40 40 0 1 1 95 78" fill="none" stroke="#005f73" stroke-width="6" stroke-linecap="round"/>
        <path id="cpu-arc" d="M 15 78 A 40 40 0 1 1 95 78" fill="none" stroke="#00d4ff" stroke-width="6"
              stroke-linecap="round" stroke-dasharray="0 220" style="transition:stroke-dasharray 0.5s,stroke 0.5s"/>
        <text x="55" y="54" text-anchor="middle" fill="#00d4ff" font-family="Courier New" font-size="15" font-weight="bold" id="cpu-pct">--%</text>
        <text x="55" y="68" text-anchor="middle" fill="#005f73" font-family="Courier New" font-size="9">CPU</text>
      </svg>
      <svg width="130" height="100" viewBox="0 0 110 90">
        <path d="M 15 78 A 40 40 0 1 1 95 78" fill="none" stroke="#005f73" stroke-width="6" stroke-linecap="round"/>
        <path id="ram-arc" d="M 15 78 A 40 40 0 1 1 95 78" fill="none" stroke="#00d4ff" stroke-width="6"
              stroke-linecap="round" stroke-dasharray="0 220" style="transition:stroke-dasharray 0.5s,stroke 0.5s"/>
        <text x="55" y="54" text-anchor="middle" fill="#00d4ff" font-family="Courier New" font-size="15" font-weight="bold" id="ram-pct">--%</text>
        <text x="55" y="68" text-anchor="middle" fill="#005f73" font-family="Courier New" font-size="9">RAM</text>
      </svg>
    </div>

    <hr class="sep">

    <!-- ROW 3: dati sistema | batteria+rete -->
    <div class="grid2">

      <!-- Colonna sinistra: sistema -->
      <div class="stats">
        <div style="font-size:9px;color:#005f73;letter-spacing:2px;margin-bottom:6px;">◈ SYSTEM</div>
        <div class="stat-row"><span class="stat-key">CPU FREQ</span><span class="stat-val" id="cpu-freq">--</span></div>
        <div class="stat-row"><span class="stat-key">CPU TEMP</span><span class="stat-val" id="cpu-temp">--</span></div>
        <div class="stat-row"><span class="stat-key">RAM USED</span><span class="stat-val" id="ram-used">--</span></div>
        <div class="stat-row"><span class="stat-key">DISK  /</span> <span class="stat-val" id="disk">--</span></div>
        <div class="stat-row"><span class="stat-key">UPTIME</span>  <span class="stat-val" id="uptime">--</span></div>
      </div>

      <!-- Colonna destra: batteria + rete -->
      <div>
        <div class="stats" style="margin-bottom:14px;">
          <div style="font-size:9px;color:#005f73;letter-spacing:2px;margin-bottom:6px;">◈ POWER</div>
          <div class="stat-row">
            <span class="stat-key">BATTERY</span>
            <span class="stat-val" id="bat-pct">--%</span>
          </div>
          <div style="margin:5px 0 4px;">
            <div style="background:#011a22;height:6px;border-radius:3px;overflow:hidden;">
              <div id="bat-bar" style="height:6px;width:0%;border-radius:3px;background:#00d4ff;transition:width 0.5s,background 0.5s;"></div>
            </div>
            <div id="bat-status" style="font-size:9px;color:#005f73;letter-spacing:1px;margin-top:3px;"></div>
          </div>
        </div>
        <div class="stats">
          <div style="font-size:9px;color:#005f73;letter-spacing:2px;margin-bottom:6px;">◈ NETWORK</div>
          <div class="stat-row"><span class="stat-key">PING</span>    <span class="stat-val" id="ping">--</span></div>
          <div class="stat-row"><span class="stat-key">UPLOAD</span>  <span class="stat-val" id="net-up">--</span></div>
          <div class="stat-row"><span class="stat-key">DOWNLOAD</span><span class="stat-val" id="net-dn">--</span></div>
        </div>
      </div>
    </div>

    <hr class="sep">

    <!-- ROW 4: top processi | meteo -->
    <div class="grid2">
      <div>
        <div style="font-size:9px;color:#005f73;letter-spacing:2px;margin-bottom:6px;">◈ TOP PROCESSES</div>
        <div class="stats" id="procs"></div>
      </div>
      <div class="weather">
        <div class="weather-title">◈ ENVIRONMENT · <span id="city">...</span></div>
        <div class="weather-main" id="weather-main" style="font-size:26px;margin-top:6px;">◈  -- °C</div>
        <div class="weather-desc" id="weather-desc" style="margin-top:6px;">LOADING...</div>
      </div>
    </div>

  </div>
</div>

<script>

// ── Arc reactor animation ────────────────────────────────────
let reactorAngle1 = 0, reactorAngle2 = 0;
function animateReactor(color) {
  reactorAngle1 += 1.8;
  reactorAngle2 -= 1.1;
  const r1 = document.getElementById('r-ring1');
  const r2 = document.getElementById('r-ring2');
  const core = document.getElementById('r-core');
  if (r1) {
    r1.setAttribute('transform', `rotate(${reactorAngle1}, 40, 40)`);
    r1.setAttribute('stroke', color);
  }
  if (r2) {
    r2.setAttribute('transform', `rotate(${reactorAngle2}, 40, 40)`);
    r2.setAttribute('stroke', color);
  }
  if (core) core.setAttribute('fill', color);
  requestAnimationFrame(() => animateReactor(color));
}

// ── HUD data ─────────────────────────────────────────────────
const ARC_LEN = 207;

function loadColor(pct) {
  if (pct >= 90) return '#ff2251';
  if (pct >= 70) return '#ff6b35';
  return '#00d4ff';
}

function setArc(arcId, pctId, pct) {
  const arc = document.getElementById(arcId);
  const txt = document.getElementById(pctId);
  const color = loadColor(pct);
  const filled = ARC_LEN * (pct / 100);
  arc.setAttribute('stroke-dasharray', filled + ' ' + (ARC_LEN - filled));
  arc.setAttribute('stroke', color);
  txt.setAttribute('fill', color);
  txt.textContent = pct.toFixed(0) + '%';
}

let currentReactorColor = '#00d4ff';

function update() {
  fetch('/data')
    .then(r => r.json())
    .then(d => {
      document.getElementById('time').textContent = d.time;
      document.getElementById('date').textContent = d.date;
      setArc('cpu-arc', 'cpu-pct', d.cpu);
      setArc('ram-arc', 'ram-pct', d.ram);
      document.getElementById('cpu-freq').textContent  = d.cpu_freq;
      document.getElementById('cpu-temp').textContent  = d.cpu_temp;
      document.getElementById('ram-used').textContent  = d.ram_used;
      document.getElementById('disk').textContent      = d.disk;
      document.getElementById('uptime').textContent    = d.uptime;

      // Batteria
      const batBar = document.getElementById('bat-bar');
      const batPct = document.getElementById('bat-pct');
      const batStatus = document.getElementById('bat-status');
      batBar.style.width = d.bat_pct + '%';
      batBar.style.background = d.bat_pct <= 20 ? '#ff2251' : d.bat_pct <= 40 ? '#ff6b35' : '#00d4ff';
      batPct.textContent = d.bat_pct + '%';
      batPct.style.color = d.bat_pct <= 20 ? '#ff2251' : d.bat_pct <= 40 ? '#ff6b35' : '#00d4ff';
      batStatus.textContent = d.bat_status;

      // Rete
      document.getElementById('ping').textContent   = d.ping;
      document.getElementById('net-up').textContent = d.net_up;
      document.getElementById('net-dn').textContent = d.net_dn;

      // Top processi
      const procsEl = document.getElementById('procs');
      procsEl.innerHTML = d.procs.map(p =>
        `<div class="stat-row">
          <span class="stat-key" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.name}</span>
          <span class="stat-val">CPU ${p.cpu}%  MEM ${p.mem}%</span>
        </div>`
      ).join('');

      document.getElementById('city').textContent      = d.city;
      document.getElementById('weather-main').textContent = d.weather_main;
      document.getElementById('weather-desc').textContent = d.weather_desc;

      // Colore reattore e orologio in base al carico
      const maxLoad = Math.max(d.cpu, d.ram);
      currentReactorColor = loadColor(maxLoad);
      document.getElementById('time').style.color = currentReactorColor;
      document.getElementById('r-hex').setAttribute('stroke', currentReactorColor);

      // Alert mode
      const isAlert = d.cpu >= 90 || d.ram >= 90;
      document.body.classList.toggle('alert', isAlert);
      document.getElementById('alert-banner').classList.toggle('visible', isAlert);
    })
    .catch(() => {});
}

function startHUD() {
  document.getElementById('main').classList.add('visible');
  animateReactor('#00d4ff');
  update();
  setInterval(update, 1000);
}

// ── JARVIS Voice toggle ───────────────────────────────────────
let voiceActive = false;

function toggleVoice() {
  const btn = document.getElementById('voice-btn');
  const status = document.getElementById('voice-status');

  if (!voiceActive) {
    const jarvisWin = window.open('/jarvis', '_blank');
    fetch('/voice/start')
      .then(r => r.json())
      .then(d => {
        if (d.ok) {
          voiceActive = true;
          btn.textContent = '◈ DEACTIVATE JARVIS';
          btn.style.borderColor = '#00d4ff';
          btn.style.color = '#00d4ff';
          btn.style.boxShadow = '0 0 10px #00d4ff44';
          status.textContent = 'VOICE SYSTEM ONLINE · SAY HEY JARVIS';
          status.style.color = '#00d4ff';
        } else {
          if (jarvisWin) jarvisWin.close();
          status.textContent = d.error || 'ERRORE AVVIO';
          status.style.color = '#ff2251';
        }
      })
      .catch(() => {
        if (jarvisWin) jarvisWin.close();
        status.textContent = 'ERRORE CONNESSIONE';
        status.style.color = '#ff2251';
      });
  } else {
    fetch('/voice/stop')
      .then(r => r.json())
      .then(() => {
        voiceActive = false;
        btn.textContent = '◈ ACTIVATE JARVIS';
        btn.style.borderColor = '#005f73';
        btn.style.color = '#00d4ff';
        btn.style.boxShadow = 'none';
        status.textContent = 'VOICE SYSTEM OFFLINE';
        status.style.color = '#005f73';
      });
  }
}

startHUD();
</script>
</body>
</html>"""

# ── Chat Page ────────────────────────────────────────────────
CHAT_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>J.A.R.V.I.S. · CHAT</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  :root{--c:#00d4ff;--dim:#005f73;--bg:#020c10;--warn:#ff6b35;}
  body{
    background:var(--bg);color:var(--c);
    font-family:'Share Tech Mono','Courier New',monospace;
    height:100vh;display:flex;flex-direction:column;overflow:hidden;
  }
  body::before{
    content:'';position:fixed;inset:0;
    background-image:linear-gradient(rgba(0,212,255,0.02) 1px,transparent 1px),
      linear-gradient(90deg,rgba(0,212,255,0.02) 1px,transparent 1px);
    background-size:40px 40px;pointer-events:none;z-index:0;
  }
  .scanline{position:fixed;left:0;right:0;height:2px;background:rgba(0,212,255,0.06);
    animation:scan 4s linear infinite;pointer-events:none;z-index:99;}
  @keyframes scan{0%{top:-2px}100%{top:100%}}
  .corner{position:fixed;width:20px;height:20px;border-color:var(--dim);border-style:solid;opacity:0.5;}
  .corner.tl{top:12px;left:12px;border-width:1px 0 0 1px;}
  .corner.tr{top:12px;right:12px;border-width:1px 1px 0 0;}
  .corner.bl{bottom:12px;left:12px;border-width:0 0 1px 1px;}
  .corner.br{bottom:12px;right:12px;border-width:0 1px 1px 0;}
  #header{
    padding:16px 24px;border-bottom:1px solid var(--dim);
    font-size:11px;letter-spacing:4px;text-align:center;
    position:relative;z-index:1;flex-shrink:0;
  }
  #header .sub{font-size:8px;color:var(--dim);letter-spacing:2px;margin-top:4px;}
  #messages{
    flex:1;overflow-y:auto;padding:20px 60px;display:flex;flex-direction:column;gap:14px;
    position:relative;z-index:1;
  }
  #messages::-webkit-scrollbar{width:4px;}
  #messages::-webkit-scrollbar-track{background:transparent;}
  #messages::-webkit-scrollbar-thumb{background:var(--dim);border-radius:2px;}
  .msg{max-width:68%;padding:10px 14px;line-height:1.65;font-size:12px;letter-spacing:0.3px;}
  .msg.user{
    align-self:flex-end;border:1px solid rgba(255,107,53,0.4);
    color:#ff6b35;background:rgba(255,107,53,0.04);
  }
  .msg.user::before{content:'[ YOU ]';font-size:7px;color:rgba(255,107,53,0.6);letter-spacing:2px;display:block;margin-bottom:4px;}
  .msg.jarvis{
    align-self:flex-start;border:1px solid rgba(0,212,255,0.25);
    color:var(--c);background:rgba(0,212,255,0.03);
  }
  .msg.jarvis::before{content:'[ J.A.R.V.I.S. ]';font-size:7px;color:rgba(0,212,255,0.5);letter-spacing:2px;display:block;margin-bottom:4px;}
  .msg.thinking{
    align-self:flex-start;border:1px solid var(--dim);
    color:var(--dim);font-size:11px;animation:blink 1s infinite;
  }
  @keyframes blink{0%,100%{opacity:1}50%{opacity:0.35}}
  #input-area{
    border-top:1px solid var(--dim);padding:14px 60px;
    display:flex;gap:10px;align-items:center;
    position:relative;z-index:1;flex-shrink:0;
  }
  #msg-input{
    flex:1;background:transparent;border:1px solid var(--dim);
    color:var(--c);font-family:'Share Tech Mono','Courier New',monospace;
    font-size:12px;letter-spacing:0.5px;padding:10px 14px;outline:none;
    transition:border-color 0.2s;
  }
  #msg-input:focus{border-color:var(--c);}
  #msg-input::placeholder{color:var(--dim);}
  #send-btn{
    background:transparent;border:1px solid var(--dim);color:var(--c);
    font-family:'Share Tech Mono','Courier New',monospace;font-size:11px;
    letter-spacing:2px;padding:10px 22px;cursor:pointer;transition:all 0.2s;
  }
  #send-btn:hover:not(:disabled){border-color:var(--c);box-shadow:0 0 8px #00d4ff33;}
  #send-btn:disabled{opacity:0.35;cursor:default;}
</style>
</head>
<body>
<div class="scanline"></div>
<div class="corner tl"></div><div class="corner tr"></div>
<div class="corner bl"></div><div class="corner br"></div>

<div id="header">
  ◈ J.A.R.V.I.S. · TEXT INTERFACE ◈
  <div class="sub">STARK INDUSTRIES — SECURE CHANNEL</div>
</div>

<div id="messages">
  <div class="msg jarvis">Online and ready, Mr. Filosofi. How may I assist you today?</div>
</div>

<div id="input-area">
  <input id="msg-input" type="text" placeholder="TYPE YOUR MESSAGE..." autocomplete="off"/>
  <button id="send-btn" onclick="sendMsg()">◈ SEND</button>
</div>

<script>
const input = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');
const messages = document.getElementById('messages');

input.addEventListener('keydown', e => { if(e.key === 'Enter' && !sendBtn.disabled) sendMsg(); });

function addMsg(text, type) {
  const div = document.createElement('div');
  div.className = 'msg ' + type;
  if(type === 'thinking') div.textContent = '◈ PROCESSING ···';
  else div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function typewriter(el, text) {
  el.textContent = '';
  let i = 0;
  function step() {
    if(i < text.length) { el.textContent += text[i++]; setTimeout(step, 20); }
    messages.scrollTop = messages.scrollHeight;
  }
  step();
}

async function sendMsg() {
  const text = input.value.trim();
  if(!text) return;
  input.value = '';
  sendBtn.disabled = true;
  input.disabled = true;
  addMsg(text, 'user');
  const thinking = addMsg('', 'thinking');
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await res.json();
    thinking.remove();
    const d = addMsg('', 'jarvis');
    typewriter(d, data.reply || 'No response received.');
  } catch(e) {
    thinking.remove();
    addMsg('Connection error. Please try again.', 'jarvis');
  } finally {
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}
input.focus();
</script>
</body>
</html>"""

# ── Jarvis Interface Page ─────────────────────────────────────
JARVIS_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>J.A.R.V.I.S.</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  :root{--c:#00d4ff;--dim:#005f73;--bg:#020c10;}
  body{
    background:var(--bg);color:var(--c);
    font-family:'Share Tech Mono','Courier New',monospace;
    overflow:hidden;height:100vh;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
  }
  body::before{
    content:'';position:fixed;inset:0;
    background-image:linear-gradient(rgba(0,212,255,0.02) 1px,transparent 1px),
      linear-gradient(90deg,rgba(0,212,255,0.02) 1px,transparent 1px);
    background-size:40px 40px;pointer-events:none;
  }
  .scanline{position:fixed;left:0;right:0;height:2px;background:rgba(0,212,255,0.06);
    animation:scan 4s linear infinite;pointer-events:none;z-index:99;}
  @keyframes scan{0%{top:-2px}100%{top:100%}}
  #title{position:fixed;top:6%;text-align:center;letter-spacing:8px;font-size:15px;}
  #title .sub{font-size:8px;color:var(--dim);letter-spacing:3px;margin-top:5px;}
  #orb-wrap{position:relative;width:480px;height:480px;display:flex;align-items:center;justify-content:center;}
  #canvas{position:absolute;width:480px;height:480px;border-radius:50%;}
  #hud-svg{position:absolute;width:480px;height:480px;pointer-events:none;}
  #status{position:fixed;bottom:16%;text-align:center;width:100%;}
  #state-label{font-size:10px;letter-spacing:4px;color:var(--dim);margin-bottom:10px;transition:color 0.3s;}
  #text-box{font-size:13px;letter-spacing:1px;color:var(--c);max-width:560px;margin:0 auto;
    min-height:20px;line-height:1.6;}
  #mic-wrap{position:fixed;bottom:7%;display:flex;gap:3px;align-items:flex-end;height:32px;}
  .mbar{width:4px;min-height:3px;background:var(--dim);border-radius:2px;transition:height 0.05s,background 0.1s;}
  .corner{position:fixed;width:20px;height:20px;border-color:var(--dim);border-style:solid;opacity:0.5;}
  .corner.tl{top:12px;left:12px;border-width:1px 0 0 1px;}
  .corner.tr{top:12px;right:12px;border-width:1px 1px 0 0;}
  .corner.bl{bottom:12px;left:12px;border-width:0 0 1px 1px;}
  .corner.br{bottom:12px;right:12px;border-width:0 1px 1px 0;}
</style>
</head>
<body>
<div class="scanline"></div>
<div class="corner tl"></div><div class="corner tr"></div>
<div class="corner bl"></div><div class="corner br"></div>

<div id="title">◈ J.A.R.V.I.S. ◈
  <div class="sub">JUST A RATHER VERY INTELLIGENT SYSTEM · STARK INDUSTRIES</div>
</div>

<div id="orb-wrap">
  <canvas id="canvas" width="480" height="480"></canvas>
  <svg id="hud-svg" viewBox="0 0 480 480">
    <circle cx="240" cy="240" r="226" fill="none" stroke="#005f73" stroke-width="0.5" stroke-dasharray="3 9" opacity="0.4"/>
    <g id="rg1"><circle cx="240" cy="240" r="210" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="50 282" stroke-linecap="round" opacity="0.7"/></g>
    <g id="rg2"><circle cx="240" cy="240" r="196" fill="none" stroke="#00d4ff" stroke-width="0.5" stroke-dasharray="25 264" stroke-linecap="round" opacity="0.4"/></g>
    <line x1="240" y1="14" x2="240" y2="34" stroke="#005f73" stroke-width="1"/>
    <line x1="240" y1="446" x2="240" y2="466" stroke="#005f73" stroke-width="1"/>
    <line x1="14" y1="240" x2="34" y2="240" stroke="#005f73" stroke-width="1"/>
    <line x1="446" y1="240" x2="466" y2="240" stroke="#005f73" stroke-width="1"/>
    <path d="M118 128 L118 118 L128 118" fill="none" stroke="#005f73" stroke-width="1" opacity="0.5"/>
    <path d="M362 128 L362 118 L352 118" fill="none" stroke="#005f73" stroke-width="1" opacity="0.5"/>
    <path d="M118 352 L118 362 L128 362" fill="none" stroke="#005f73" stroke-width="1" opacity="0.5"/>
    <path d="M362 352 L362 362 L352 362" fill="none" stroke="#005f73" stroke-width="1" opacity="0.5"/>
  </svg>
</div>

<div id="status">
  <div id="state-label">◈ STANDBY ◈</div>
  <div id="text-box"></div>
</div>
<div id="mic-wrap"></div>

<script>
const canvas=document.getElementById('canvas');
const gl=canvas.getContext('webgl',{alpha:true,premultipliedAlpha:false});

const VS=`attribute vec4 a_pos;void main(){gl_Position=a_pos;}`;

const FS=`
precision highp float;
uniform float u_t;
uniform float u_amp;
uniform vec2 u_res;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){
  vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
  return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);
}
float fbm(vec2 p){
  float v=0.0,a=0.5;
  for(int i=0;i<6;i++){v+=a*n(p);p=p*2.1+vec2(0.3*float(i),0.7*float(i));a*=0.5;}
  return v;
}
void main(){
  vec2 uv=(gl_FragCoord.xy-u_res*0.5)/min(u_res.x,u_res.y);
  float d=length(uv);
  float sp=0.35+u_amp*2.0;float t=u_t*sp;
  vec2 q=vec2(fbm(uv+t*0.15),fbm(uv+vec2(1.7,9.2)+t*0.12));
  vec2 r=vec2(fbm(uv+3.5*q+vec2(1.7,9.2)+t*0.2),fbm(uv+3.5*q+vec2(8.3,2.8)+t*0.15));
  float f=fbm(uv+3.5*r+t*0.1);
  float orb=pow(max(0.0,1.0-smoothstep(0.12,0.44,d)),1.3);
  float glow=pow(max(0.0,1.0-smoothstep(0.35,0.65,d)),2.5)*0.4;
  float gas=f*orb;
  vec3 cD=vec3(0.0,0.04,0.1),cM=vec3(0.0,0.28,0.65),cC=vec3(0.0,0.83,1.0),cW=vec3(0.75,0.97,1.0);
  vec3 col=cD;
  col=mix(col,cM,smoothstep(0.0,0.4,gas));
  col=mix(col,cC,smoothstep(0.3,0.7,gas));
  col=mix(col,cW,smoothstep(0.6,0.95,gas*(1.0+u_amp*0.4)));
  col+=cC*glow*(0.4+u_amp*0.6);
  if(u_amp>0.25){
    float rip=sin(d*28.0-t*9.0)*0.5+0.5;
    rip*=(1.0-smoothstep(0.38,0.58,d));
    col+=cC*rip*(u_amp-0.25)*0.5;
  }
  float alpha=clamp((gas+glow)*1.9,0.0,1.0);
  gl_FragColor=vec4(col*alpha,alpha);
}`;

function mkS(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);return s;}
const prog=gl.createProgram();
gl.attachShader(prog,mkS(gl.VERTEX_SHADER,VS));
gl.attachShader(prog,mkS(gl.FRAGMENT_SHADER,FS));
gl.linkProgram(prog);gl.useProgram(prog);
const buf=gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER,buf);
gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
const posLoc=gl.getAttribLocation(prog,'a_pos');
gl.enableVertexAttribArray(posLoc);
gl.vertexAttribPointer(posLoc,2,gl.FLOAT,false,0,0);
const uT=gl.getUniformLocation(prog,'u_t');
const uAmp=gl.getUniformLocation(prog,'u_amp');
const uRes=gl.getUniformLocation(prog,'u_res');
gl.uniform2f(uRes,480,480);
gl.enable(gl.BLEND);
gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);

let t=0,amp=0.12,tAmp=0.12,state='idle',sT=0;

// HUD rings
let r1a=0,r2a=0;
function animRings(){
  r1a+=0.35+amp*0.8;r2a-=0.22+amp*0.5;
  document.getElementById('rg1').setAttribute('transform','rotate('+r1a+',240,240)');
  document.getElementById('rg2').setAttribute('transform','rotate('+r2a+',240,240)');
}

// Mic bars
const mw=document.getElementById('mic-wrap');
const NB=24;const bars=[];
for(let i=0;i<NB;i++){const b=document.createElement('div');b.className='mbar';mw.appendChild(b);bars.push(b);}
let micVol=0;
async function setupMic(){
  try{
    const s=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
    const ac=new AudioContext();const src=ac.createMediaStreamSource(s);
    const an=ac.createAnalyser();an.fftSize=64;src.connect(an);
    const d=new Uint8Array(an.frequencyBinCount);
    function tick(){
      an.getByteFrequencyData(d);
      micVol=d.reduce((s,v)=>s+v,0)/d.length/255;
      for(let i=0;i<NB;i++){const v=d[Math.floor(i*d.length/NB)]/255;
        bars[i].style.height=(3+v*29)+'px';bars[i].style.background=v>0.4?'#00d4ff':'#005f73';}
      requestAnimationFrame(tick);
    }tick();
  }catch(e){}
}
setupMic();

// State polling
let lastJT='',twTimer=null;
function typewriter(el,text){
  if(twTimer)clearTimeout(twTimer);el.textContent='';let i=0;
  function step(){if(i<text.length){el.textContent+=text[i++];twTimer=setTimeout(step,28);}}step();
}

function poll(){
  fetch('/jarvis/status').then(r=>r.json()).then(d=>{
    state=d.state||'idle';
    const lbl=document.getElementById('state-label');
    const tb=document.getElementById('text-box');
    const labels={idle:'◈ STANDBY ◈',listening:'◈ LISTENING ◈',thinking:'◈ PROCESSING ◈',speaking:'◈ J.A.R.V.I.S. ◈'};
    lbl.textContent=labels[state]||'◈ STANDBY ◈';
    lbl.style.color=state==='speaking'||state==='listening'?'#00d4ff':state==='thinking'?'#ff6b35':'#005f73';
    if(state==='speaking'&&d.jarvis_text&&d.jarvis_text!==lastJT){
      lastJT=d.jarvis_text;tb.style.color='#00d4ff';typewriter(tb,d.jarvis_text);
    }else if(state==='thinking'&&d.user_text){
      tb.style.color='#005f73';tb.textContent='"'+d.user_text+'"';
    }else if(state==='listening'){tb.textContent='';}
  }).catch(()=>{});
}
setInterval(poll,250);

// Render
function render(){
  if(state==='speaking'){sT+=0.12;tAmp=0.55+Math.sin(sT*7)*0.2+Math.sin(sT*13)*0.1+Math.cos(sT*3)*0.08;}
  else if(state==='listening'){tAmp=0.28+micVol*0.7;}
  else if(state==='thinking'){sT+=0.05;tAmp=0.2+Math.abs(Math.sin(sT*2))*0.15;}
  else{tAmp=0.1+micVol*0.3;sT=0;}
  amp+=(tAmp-amp)*0.05;t+=0.016;
  gl.uniform1f(uT,t);gl.uniform1f(uAmp,amp);
  gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
  gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  animRings();requestAnimationFrame(render);
}
render();
</script>
</body>
</html>"""

# ── Ping in background ───────────────────────────────────────
ping_cache = {"ms": "--"}

def fetch_ping():
    while True:
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-t", "2", "8.8.8.8"],
                capture_output=True, text=True, timeout=4
            )
            line = [l for l in r.stdout.split("\n") if "time=" in l]
            if line:
                ms = line[0].split("time=")[1].split(" ")[0]
                ping_cache["ms"] = f"{float(ms):.0f} ms"
            else:
                ping_cache["ms"] = "timeout"
        except Exception:
            ping_cache["ms"] = "--"
        time.sleep(5)

threading.Thread(target=fetch_ping, daemon=True).start()

# ── CPU temp ──────────────────────────────────────────────────
def get_cpu_temp():
    try:
        r = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    except Exception:
        return "--"

# ── Server HTTP ───────────────────────────────────────────────
net_prev = psutil.net_io_counters()
net_prev_time = time.time()

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, *args): pass  # silenzia i log

    def do_GET(self):
        global net_prev, net_prev_time

        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/data":
            now = datetime.datetime.now()
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            freq = psutil.cpu_freq()

            net_cur = psutil.net_io_counters()
            t_now = time.time()
            dt = t_now - net_prev_time or 1
            up_kb = (net_cur.bytes_sent - net_prev.bytes_sent) / dt / 1024
            dn_kb = (net_cur.bytes_recv - net_prev.bytes_recv) / dt / 1024
            net_prev = net_cur
            net_prev_time = t_now

            # Batteria
            bat = psutil.sensors_battery()
            bat_pct = int(bat.percent) if bat else 0
            if bat:
                if bat.power_plugged:
                    bat_status = "CHARGING" if bat.percent < 100 else "FULLY CHARGED"
                else:
                    mins = bat.secsleft // 60 if bat.secsleft > 0 else 0
                    bat_status = f"ON BATTERY · {mins//60}h {mins%60}m LEFT"
            else:
                bat_status = "NO BATTERY"

            # Uptime
            boot = psutil.boot_time()
            uptime_s = int(time.time() - boot)
            h, rem = divmod(uptime_s, 3600)
            m, s = divmod(rem, 60)
            uptime_str = f"{h}h {m}m {s}s"

            # Top 3 processi per CPU
            procs = []
            for p in sorted(psutil.process_iter(['name','cpu_percent','memory_percent']),
                            key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:3]:
                procs.append({
                    "name": p.info['name'][:22],
                    "cpu": f"{p.info['cpu_percent'] or 0:.0f}",
                    "mem": f"{p.info['memory_percent'] or 0:.1f}",
                })

            w = weather_cache
            data = {
                "time": now.strftime("%H:%M:%S"),
                "date": now.strftime("%A, %d %B %Y").upper(),
                "cpu": cpu,
                "ram": ram.percent,
                "cpu_freq": f"{freq.current:.0f} MHz" if freq else "--",
                "cpu_temp": get_cpu_temp(),
                "ram_used": f"{ram.used/1e9:.1f} / {ram.total/1e9:.1f} GB",
                "disk": f"{disk.used/1e9:.0f}/{disk.total/1e9:.0f} GB ({disk.percent}%)",
                "uptime": uptime_str,
                "bat_pct": bat_pct,
                "bat_status": bat_status,
                "ping": ping_cache["ms"],
                "net_up": f"↑ {up_kb:.0f} KB/s",
                "net_dn": f"↓ {dn_kb:.0f} KB/s",
                "procs": procs,
                "city": CITY,
                "weather_main": f"{w['icon']}  {w['temp']}°C",
                "weather_desc": w["desc"].upper(),
            }
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/jarvis":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(JARVIS_HTML.encode())

        elif self.path == "/chat":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(CHAT_HTML.encode())

        elif self.path == "/jarvis/status":
            try:
                with open("/tmp/jarvis_state.json") as f:
                    data = json.load(f)
            except Exception:
                data = {"state": "idle", "user_text": "", "jarvis_text": ""}
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/voice/start":
            body = self._voice_start()
            self._json(body)

        elif self.path == "/voice/stop":
            body = self._voice_stop()
            self._json(body)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                user_msg = payload.get("message", "").strip()
                if not user_msg:
                    self._json({"reply": "Empty message."})
                    return
                reply = chat_with_jarvis(user_msg)
                self._json({"reply": reply})
            except Exception as e:
                self._json({"reply": f"Error: {str(e)[:80]}"})
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _voice_start(self):
        global voice_process
        if voice_process and voice_process.poll() is None:
            return {"ok": True, "msg": "already running"}

        env = os.environ.copy()
        # API key deve essere impostata via variabile di ambiente GROQ_API_KEY
        voice_script = os.path.join(os.path.dirname(__file__), "jarvis_voice.py")
        try:
            voice_process = subprocess.Popen(
                [sys.executable, voice_script],
                env=env
            )
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _voice_stop(self):
        global voice_process
        if voice_process and voice_process.poll() is None:
            voice_process.terminate()
            voice_process = None
        return {"ok": True}


def start_server():
    # Libera la porta se occupata da un processo precedente
    subprocess.run(
        f"lsof -ti :{PORT} | xargs kill -9 2>/dev/null; true",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(0.3)
    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    server.serve_forever()

if __name__ == "__main__":
    psutil.cpu_percent(interval=None)
    time.sleep(0.1)

    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(0.8)

    # Apri in Safari a schermo intero
    script = f'''
tell application "Safari"
    activate
    open location "http://127.0.0.1:{PORT}"
end tell
delay 1.5
tell application "System Events"
    tell process "Safari"
        set frontmost to true
        keystroke "f" using {{command down, control down}}
    end tell
end tell
'''
    subprocess.Popen(["osascript", "-e", script])

    print(f"JARVIS HUD attivo su http://127.0.0.1:{PORT}")
    print("Premi Ctrl+C per fermare.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Fermato.")
