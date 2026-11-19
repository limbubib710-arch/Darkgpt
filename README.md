# Darkgpt-# DARKGPT v1.0 ULTIMATE
"YOUR AI. YOUR CODE. YOUR CYBER LAB."

AI-powered coding & cybersecurity assistant for Termux / Pydroid 3 / Linux.

## The AI honesty model
- WITH config: connects to any OpenAI-compatible endpoint. The free,
  no-paid-API route is a local Ollama server:
      ai_endpoint: "http://localhost:11434/v1"
      ai_model:    "llama3"
- WITHOUT config: OFFLINE mode — built-in knowledge base (10 core security/
  programming topics) + the complete toolkit. The app clearly labels offline
  answers and NEVER fabricates LLM output.

## Install (Termux)
    pkg update && pkg upgrade -y
    pkg install python git -y
    git clone <repo> && cd darkgpt
    pip install -r requirements.txt
    python darkgpt.py

## Install (Pydroid 3)
Paste darkgpt.py → Menu ☰ → Pip → install requests, rich, colorama,
psutil, beautifulsoup4 → Run.

## Commands
chat, ask, code, debug, explain, history  — AI & coding workspace
ip, dns, whois, scan, local, ssl, headers, tech, ping — network recon
hash, integrity, secrets — code/file security
lab sql, lab xss — isolated local vulnerability labs
sys, files, run, export, ai, persona, help, exit

## Security posture
- No DDoS. No credential theft. No malware. No auth bypass. Ever.
- Port scanning requires typed confirmation for non-loopback hosts.
- Labs run in local SQLite / in-memory strings only.
- All tool results come from real queries; unavailable data is labeled.
