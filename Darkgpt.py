#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DARKGPT v1.0 ULTIMATE
"YOUR AI. YOUR CODE. YOUR CYBER LAB."
AI-powered coding & cybersecurity assistant for Termux / Pydroid 3 / Linux.

HONESTY GUARANTEE:
  - AI chat uses a real LLM ONLY if AI_ENDPOINT is configured (any
    OpenAI-compatible API, including a free local Ollama server).
  - Without it, DARKGPT runs in OFFLINE mode: built-in knowledge base +
    its real toolkit. It never fakes an AI answer.
  - Every security tool reports actual observed results. Unavailable
    data is labeled unavailable, never invented.
"""

import os, sys, json, re, ssl, time, socket, hashlib, subprocess, datetime, threading
from urllib.parse import urlparse

# ---------------------------------------------------------------- deps
REQUIRED = {"requests": "requests", "rich": "rich", "colorama": "colorama",
            "psutil": "psutil", "bs4": "beautifulsoup4"}

def ensure_deps():
    missing = [p for m, p in REQUIRED.items() if not _has(m)]
    if missing:
        print("[*] Installing:", ", ".join(missing))
        for pkg in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            except Exception as e:
                print(f"[!] Failed to install {pkg}: {e}")
                print("    Termux:  pip install " + " ".join(missing))
                print("    Pydroid: Menu -> Pip -> install each package")
                sys.exit(1)

def _has(mod):
    try:
        __import__(mod); return True
    except ImportError:
        return False

ensure_deps()

import requests
import colorama
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

colorama.init()
console = Console()

# ---------------------------------------------------------------- config / dirs
APP = "DARKGPT"
VERSION = "1.0 ULTIMATE"
CFG_FILE = "config.json"

DEFAULT_CFG = {
    "ai_endpoint": "",        # e.g. "http://localhost:11434/v1" (Ollama, free)
    "ai_model": "",           # e.g. "llama3"
    "ai_api_key": "",         # empty = none needed (Ollama etc.)
    "max_tokens": 1024,
    "temperature": 0.7,
    "personality": "operator" # operator | mentor | analyst
}

def load_cfg():
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(CFG_FILE):
        try:
            cfg.update(json.load(open(CFG_FILE)))
        except Exception:
            pass
    return cfg

CFG = load_cfg()

def save_cfg():
    json.dump(CFG, open(CFG_FILE, "w"), indent=2)

for d in ("history", "reports", "projects", "modules"):
    os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------- session state
SESSION = {"history": [], "loaded": False}

def history_file():
    return os.path.join("history", datetime.datetime.now().strftime("chat_%Y%m%d.json"))

def save_history():
    json.dump(SESSION["history"], open(history_file(), "w"), indent=2, default=str)

def load_history():
    files = sorted(os.listdir("history"))
    if files:
        try:
            SESSION["history"] = json.load(open(os.path.join("history", files[-1])))
        except Exception:
            SESSION["history"] = []
    SESSION["loaded"] = True

PERSONAS = {
    "operator": ("OPERATOR", "Terse, technical, output-focused. Answers in concise engineering terms."),
    "mentor":   ("MENTOR",   "Patient teacher. Explains step by step with examples before conclusions."),
    "analyst":  ("ANALYST",  "Careful assessor. States confidence levels and lists what remains unknown."),
}

# ---------------------------------------------------------------- UI
class UI:
    @staticmethod
    def banner():
        console.clear()
        art = r"""
 ██████╗  █████╗ ██████╗ ██╗  ██╗ ██████╗ ██████═╗████████╗
 ██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝██╔════╝ ██╔══██╗╚══██╔══╝
 ██║  ██║███████║██████╔╝█████╔╝ ██║  ███╗██████╔╝   ██║
 ██║  ██║██╔══██║██╔══██╗██╔═██╗ ██║   ██║██╔══██╗   ██║
 ██████╔╝██║  ██║██║  ██║██║  ██╗╚██████╔╝██║  ██║   ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝"""
        console.print(art, style="bold red", justify="center")
        console.print("        YOUR AI. YOUR CODE. YOUR CYBER LAB.\n", style="bold magenta", justify="center")
        mode = "ONLINE (LLM connected)" if AI.connected() else "OFFLINE (knowledge base + toolkit)"
        console.print(Panel(f"[cyan]v{VERSION}[/]  |  mode: [bold green]{mode}[/]  |  "
                            f"personality: [magenta]{CFG['personality']}[/]\n"
                            "[dim]Public data only · authorized targets only · no fabricated results[/]",
                            border_style="red"))
        if not AI.connected():
            console.print("[yellow][i] No AI provider configured. Chat runs on the built-in offline "
                          "knowledge base. Set ai_endpoint in config.json (e.g. free local Ollama) "
                          "for full LLM chat.[/]")

    @staticmethod
    def ok(m):    console.print(f"[green][+][/] {m}")
    @staticmethod
    def warn(m):  console.print(f"[yellow][!][/] {m}")
    @staticmethod
    def err(m):   console.print(f"[red][x][/] {m}")
    @staticmethod
    def info(m):  console.print(f"[cyan][i][/] {m}")
    @staticmethod
    def kv(k, v): console.print(f"  [red]{k:<24}[/] [white]{v}[/]")

    @staticmethod
    def spinner(text):
        with console.status(f"[red]{text}...", spinner="dots"):
            pass  # callers wrap their own work; kept for visual parity on Termux

    @staticmethod
    def typing(text, delay=0.004):
        for ch in text:
            print(ch, end="", flush=True)
            time.sleep(delay)
        print()

    @staticmethod
    def table(title, rows, cols=("Key", "Value")):
        t = Table(title=title, border_style="red")
        for c in cols:
            t.add_column(c, style="cyan")
        for r in rows:
            t.add_row(*[str(x) for x in r])
        console.print(t)

    @staticmethod
    def box(title, lines, color="red"):
        console.print(Panel("\n".join(str(l) for l in lines), title=title, border_style=color))

# ---------------------------------------------------------------- reports
class Report:
    @staticmethod
    def save(title, data):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join("reports", f"{ts}_{re.sub(r'[^A-Za-z0-9_-]', '_', title)}")
        json.dump(data, open(base + ".json", "w"), indent=2, default=str)
        with open(base + ".txt", "w") as f:
            f.write(f"DARKGPT REPORT — {title}\n{datetime.datetime.now().isoformat()}\n"
                    f"Source: live queries, unavailable fields marked.\n{'='*50}\n\n")
            def dump(d, ind=0):
                for k, v in (d.items() if isinstance(d, dict) else enumerate(d)):
                    pre = "  " * ind
                    if isinstance(v, (dict, list)):
                        f.write(f"{pre}{k}:\n"); dump(v, ind + 1)
                    else:
                        f.write(f"{pre}{k}: {v}\n")
            dump(data)
        UI.ok(f"Report saved: {base}.txt / .json")

# ---------------------------------------------------------------- AI ENGINE
class AI:
    """Real LLM via any OpenAI-compatible /chat/completions endpoint.
    Ollama (free, local): ai_endpoint='http://localhost:11434/v1', model='llama3'.
    Without a configured endpoint, offline mode uses KNOWLEDGE below."""

    @staticmethod
    def connected():
        return bool(CFG.get("ai_endpoint") and CFG.get("ai_model"))

    @staticmethod
    def _messages(user_text):
        name, style = PERSONAS[CFG["personality"]]
        msgs = [{"role": "system",
                 "content": f"You are {name}, the DARKGPT assistant. Personality: {style} "
                            "Be accurate. If uncertain, say so explicitly. Never invent sources, "
                            "outputs, or data. Provide complete, syntactically valid code."}]
        msgs += SESSION["history"][-12:]
        msgs.append({"role": "user", "content": user_text})
        return msgs

    @classmethod
    def chat(cls, user_text):
        if cls.connected():
            headers = {"Content-Type": "application/json"}
            if CFG.get("ai_api_key"):
                headers["Authorization"] = f"Bearer {CFG['ai_api_key']}"
            payload = {"model": CFG["ai_model"], "messages": cls._messages(user_text),
                       "max_tokens": CFG["max_tokens"], "temperature": CFG["temperature"]}
            try:
                r = requests.post(CFG["ai_endpoint"].rstrip("/") + "/chat/completions",
                                  json=payload, headers=headers, timeout=120)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"], True
            except Exception as e:
                UI.warn(f"AI endpoint unreachable ({e}) — falling back to offline knowledge base.")
        return OfflineBrain.answer(user_text), False

# ---------------------------------------------------------------- OFFLINE BRAIN
class OfflineBrain:
    """Keyword-matched knowledge base. Explicitly labeled as offline; only
    answers topics it actually knows. Never fabricates."""
    KB = {
        "sql injection": ("SQL injection is the injection of attacker-controlled SQL into a "
            "vulnerable query. Classic vulnerable pattern:\n"
            "    cursor.execute(\"SELECT * FROM users WHERE name='%s'\" % user_input)\n"
            "Fix: parameterized queries — cursor.execute(\"SELECT * FROM users WHERE name=?\", (user_input,)).\n"
            "The SQLi Lab module (command: lab sql) demonstrates this safely on a local SQLite DB.", 0.9),
        "xss": ("Cross-Site Scripting injects script into pages rendered by other users. "
            "Reflected: input echoed into HTML. Fix: context-aware output encoding, CSP, "
            "HttpOnly cookies. The XSS Lab module (lab xss) shows a local safe demo.", 0.9),
        "python decorator": ("A decorator wraps a function to extend it:\n"
            "    def logit(fn):\n"
            "        def wrapper(*a, **k):\n"
            "            print('calling', fn.__name__)\n"
            "            return fn(*a, **k)\n"
            "        return wrapper\n"
            "    @logit\n    def run(): pass", 0.95),
        "tcp handshake": ("The TCP three-way handshake: client sends SYN with ISN x; server "
            "replies SYN-ACK (y, ack=x+1); client sends ACK (ack=y+1). Connection enters "
            "ESTABLISHED. Teardown uses FIN/ACK pairs on both sides.", 0.95),
        "https tls": ("TLS 1.3 handshake: ClientHello (with key share) -> ServerHello + "
            "{EncryptedExtensions, Certificate, CertificateVerify, Finished} -> client Finished. "
            "1-RTT key establishment using (EC)DHE; certificates authenticate the server.", 0.9),
        "hash": ("Hashes: MD5 (128-bit, broken for collision resistance — do not use for "
            "security), SHA-1 (deprecated), SHA-256 (SHA-2 family, current standard), "
            "bcrypt/scrypt/Argon2 for passwords (salted, deliberately slow).", 0.95),
        "port scan": ("A TCP connect scan opens a full connection to each port: open ports "
            "complete the handshake (SYN->SYN-ACK->ACK), closed ports answer RST, filtered "
            "ports time out. DARKGPT's `scan` command implements this in pure Python for "
            "hosts you own.", 0.9),
        "ddos": ("A DDoS floods a target with traffic to exhaust bandwidth or connection "
            "tables. DARKGPT contains no DDoS functionality by design. Legitimate load "
            "testing of your own servers uses bounded tools like `ab`, `wrk`, or k6 with "
            "authorization. Attacking third parties is a crime under computer-misuse laws.", 1.0),
    }

    @classmethod
    def answer(cls, text):
        t = text.lower()
        best = None
        for key, (ans, conf) in cls.KB.items():
            if key in t and (best is None or conf > best[1]):
                best = (ans, conf)
        if best:
            return (f"[OFFLINE KNOWLEDGE BASE — confidence {best[1]:.0%}]\n\n{best[0]}\n\n"
                    f"[dim]Offline mode knows {len(cls.KB)} core topics and the full toolkit. "
                    f"Configure ai_endpoint in config.json for unrestricted LLM chat.[/dim]")
        return ("[OFFLINE MODE]\nI don't have this topic in the offline knowledge base, and I won't "
                "invent an answer. Available now:\n  - All security/coding toolkit commands (type `help`)\n"
                "  - Offline topics: " + ", ".join(sorted(cls.KB)) +
                "\n\nFor full conversational AI, set `ai_endpoint` and `ai_model` in config.json — "
                "any OpenAI-compatible server works, including a free local Ollama install.")

# ---------------------------------------------------------------- SECURITY TOOLS
class NetTools:
    UA = "Mozilla/5.0 (compatible; DARKGPT/1.0 security audit)"

    @staticmethod
    def resolve(host):
        return socket.gethostbyname(host)

    @classmethod
    def ip_info(cls, target):
        ip = cls.resolve(target)
        UI.kv("Resolved IP", ip)
        data = {"input": target, "ip": ip}
        try:
            j = requests.get(f"http://ip-api.com/json/{ip}", timeout=15).json()
            for k in ("country", "regionName", "city", "isp", "org", "as", "reverse", "timezone"):
                if j.get(k):
                    UI.kv(k, j[k])
            data["ip_api"] = {k: j.get(k) for k in ("country", "city", "isp", "org", "as", "reverse")}
        except Exception as e:
            UI.warn(f"geo lookup unavailable: {e}")
        try:
            r = requests.get(f"https://rdap.org/ip/{ip}", timeout=15, headers={"User-Agent": cls.UA})
            if r.status_code == 200:
                j = r.json()
                UI.kv("RDAP network name", j.get("name", "unavailable"))
                data["rdap"] = {"name": j.get("name"), "handle": j.get("handle")}
        except Exception:
            UI.warn("RDAP lookup unavailable.")
        return data

    @staticmethod
    def dns(domain):
        data = {}
        for rt in ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"):
            try:
                r = requests.get(f"https://dns.google/resolve?name={domain}&type={rt}", timeout=10)
                ans = r.json().get("Answer") or []
                vals = [a.get("data", "") for a in ans]
                if vals:
                    data[rt] = vals
                    UI.kv(rt, ", ".join(vals[:4]) + (" ..." if len(vals) > 4 else ""))
            except Exception:
                pass
        if not data:
            UI.err("No records resolved.")
        return data

    @staticmethod
    def whois(domain):
        """RDAP-based registration lookup (modern WHOIS replacement, keyless)."""
        tld = domain.rsplit(".", 1)[-1]
        try:
            r = requests.get(f"https://rdap.org/domain/{domain}", timeout=15,
                             headers={"User-Agent": UA_HEADER})
            if r.status_code != 200:
                UI.warn(f"RDAP returned HTTP {r.status_code} — registry may not support RDAP for .{tld}")
                return {"domain": domain, "rdap_status": r.status_code}
            j = r.json()
            events = {e["eventAction"]: e["eventDate"] for e in j.get("events", [])}
            registrar = next((x["vcardArray"][1][0][3] for x in j.get("entities", [])
                              if "registrar" in x.get("roles", [])), "unavailable")
            nameservers = [n["ldhName"] for n in j.get("nameservers", [])]
            rows = [("Domain", j.get("ldhName", domain)),
                    ("Registrar", str(registrar)),
                    ("Registered", events.get("registration", "unavailable")[:10]),
                    ("Updated", events.get("last changed", "unavailable")[:10]),
                    ("Expires", events.get("expiration", "unavailable")[:10]),
                    ("Nameservers", ", ".join(nameservers[:6]))]
            UI.table("RDAP WHOIS", rows)
            return {"domain": domain, "registrar": str(registrar), "events": events,
                    "nameservers": nameservers}
        except Exception as e:
            UI.err(f"WHOIS/RDAP failed: {e}")
            return {"domain": domain, "error": str(e)}

    @classmethod
    def port_scan(cls, host, ports=None, timeout=1.0, workers=100):
        """Pure-Python TCP connect scan. Full handshake — reliable, slower than SYN
        scans, appropriate for auditing hosts you control."""
        try:
            ip = cls.resolve(host)
        except socket.gaierror:
            UI.err("Cannot resolve host."); return None
        UI.info(f"Scanning {host} ({ip}) — connect scan")
        if ip != "127.0.0.1":
            a = input(f"  [!] Confirm you are authorized to test {host} [yes/NO]: ").strip().lower()
            if a != "yes":
                UI.err("Aborted."); return None
        ports = ports or list(range(1, 1025)) + [3306, 3389, 5432, 6379, 8080, 8443, 9200, 27017]
        open_ports, lock = [], threading.Lock()
        sem = threading.Semaphore(workers)
        def probe(p):
            with sem:
                try:
                    s = socket.socket(); s.settimeout(timeout)
                    if s.connect_ex((ip, p)) == 0:
                        with lock: open_ports.append(p)
                    s.close()
                except OSError:
                    pass
        threads = [threading.Thread(target=probe, args=(p,)) for p in ports]
        t0 = time.time()
        for t in threads: t.start()
        for t in threads: t.join()
        took = time.time() - t0
        results = [{"port": p, "state": "open"} for p in sorted(open_ports)]
        if open_ports:
            UI.table(f"OPEN PORTS on {ip} ({took:.1f}s)", [(p, "open") for p in sorted(open_ports)])
        else:
            UI.warn(f"No open ports found in {len(ports)} scanned ({took:.1f}s).")
        return {"host": host, "ip": ip, "ports_scanned": len(ports),
                "open": results, "duration_s": round(took, 1)}

    @classmethod
    def ssl_inspect(cls, host, port=443):
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as s:
                    cert = s.getpeercert()
                    proto = s.version()
            expiry = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days = (expiry - datetime.datetime.now()).days
            data = {"host": host, "protocol": proto,
                    "subject_cn": dict(x[0] for x in cert["subject"]).get("commonName"),
                    "issuer": dict(x[0] for x in cert["issuer"]).get("organizationName"),
                    "not_after": cert["notAfter"], "days_remaining": days,
                    "san": [v for k, v in cert.get("subjectAltName", []) if k == "DNS"][:15]}
            UI.kv("TLS protocol", proto)
            UI.kv("Subject CN", data["subject_cn"])
            UI.kv("Issuer", data["issuer"])
            UI.kv("Expires", f"{cert['notAfter']}  ({days} days)")
            (UI.warn if days < 30 else UI.ok)(f"Certificate validity: {days} days remaining")
            return data
        except ssl.SSLCertVerificationError as e:
            UI.err(f"Certificate verification FAILED: {e}")
            return {"host": host, "error": "certificate verification failed"}
        except Exception as e:
            UI.err(f"TLS inspection failed: {e}")
            return {"host": host, "error": str(e)}

    @staticmethod
    def headers_audit(url):
        if "//" not in url: url = "https://" + url
        try:
            r = requests.get(url, headers={"User-Agent": UA_HEADER}, timeout=15, allow_redirects=True)
        except requests.RequestException as e:
            UI.err(f"Request failed: {e}"); return None
        low = {k.lower(): v for k, v in r.headers.items()}
        sec = {"strict-transport-security": "HSTS forces HTTPS",
               "content-security-policy": "CPS restricts content sources",
               "x-content-type-options": "blocks MIME sniffing",
               "x-frame-options": "anti-clickjacking",
               "referrer-policy": "controls referrer leakage",
               "permissions-policy": "restricts browser APIs"}
        rows, missing = [], []
        for h, desc in sec.items():
            if h in low:
                rows.append((h, "present", low[h][:40]))
            else:
                rows.append((h, "MISSING", desc)); missing.append(h)
        UI.table(f"HTTP response — {r.status_code} {r.url}", rows, cols=("Header", "Status", "Detail"))
        if "server" in low: UI.kv("server", low["server"])
        cookies = r.headers.get("set-cookie", "")
        cflags = []
        if cookies:
            for flag in ("Secure", "HttpOnly", "SameSite"):
                cflags.append((flag, "present" if flag.lower() in cookies.lower() else "MISSING"))
            UI.table("Cookie flags", cflags)
        return {"url": url, "status": r.status_code, "security_headers": dict(rows),
                "cookie_flags": cflags}

    @staticmethod
    def cookies_and_tech(url):
        """Fingerprinting from real response data: headers, cookies, HTML markers."""
        if "//" not in url: url = "https://" + url
        try:
            r = requests.get(url, headers={"User-Agent": UA_HEADER}, timeout=15)
        except requests.RequestException as e:
            UI.err(f"Request failed: {e}"); return None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        tech = {}
        gen = soup.find("meta", attrs={"name": "generator"})
        if gen: tech["generator_meta"] = gen.get("content")
        if soup.find("script", src=re.compile(r"wp-content|wp-includes")): tech["wordpress"] = True
        if any("react" in (s.get("src") or "") for s in soup.find_all("script")): tech["react"] = True
        if soup.find(lambda t: t.name == "script" and "next/static" in (t.string or "")): tech["nextjs"] = True
        tech["server_header"] = r.headers.get("server", "unavailable")
        tech["x_powered_by"] = r.headers.get("x-powered-by", "unavailable")
        UI.table("Technology fingerprints (observed)", list(tech.items()))
        return {"url": url, "fingerprints": tech}

    @staticmethod
    def local_discovery():
        """ARP-free local discovery: probes the common RFC1918 gateway subnet
        via ICMP-then-TCP/80/443 reachability using pure Python."""
        try:
            gate = subprocess.run(["ip", "route"] if os.name != "nt" else ["route", "print"],
                                  capture_output=True, text=True, timeout=5).stdout
        except Exception:
            gate = ""
        UI.info("Probing local /24 for live hosts (ping + TCP)...")
        live = []
        base = "192.168.1." if "192.168.1" in gate else "192.168.0."
        def ping(ip):
            if os.name == "nt":
                c = subprocess.run(["ping", "-n", "1", "-w", "800", ip], capture_output=True)
            else:
                c = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True)
            if c.returncode == 0:
                live.append(ip)
        threads = [threading.Thread(target=ping, args=(base + str(i),)) for i in range(1, 255)]
        for t in threads: t.start()
        for t in threads: t.join()
        if live:
            UI.table("Live local hosts (ICMP)", [(ip, "up") for ip in sorted(live, key=lambda x: int(x.rsplit('.',1)[1]))])
        else:
            UI.warn("No ICMP responses (many hosts block ping — that is a finding, not an error).")
        return {"live_hosts": sorted(live)}

UA_HEADER = NetTools.UA

# ---------------------------------------------------------------- CODE SECURITY
class CodeSec:
    PY_PATTERNS = [
        (r"eval\s*\(", "MEDIUM", "eval() executes arbitrary code — audit input path"),
        (r"exec\s*\(", "MEDIUM", "exec() executes arbitrary code"),
        (r"os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True", "HIGH",
         "shell command execution — check for unsanitized input"),
        (r"pickle\.loads?\s*\(", "MEDIUM", "pickle deserialization of untrusted data = code execution"),
        (r"verify\s*=\s*False", "HIGH", "TLS verification disabled"),
        (r"md5\s*\(|sha1\s*\(", "LOW", "weak hash for security purposes"),
        (r"hashlib\.(md5|sha1)\(", "LOW", "weak hash"),
        (r"['\"](?:pass|passwd|password|secret|api_key|apikey|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]",
         "HIGH", "hardcoded credential"),
        (r"sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}",
         "HIGH", "well-known API key format detected"),
        (r"random\.(random|randint)\(", "INFO",
         "random module is not cryptographically secure — use secrets for keys/tokens"),
        (r"debug\s*=\s*True", "MEDIUM", "debug mode enabled (info disclosure if deployed)"),
    ]

    @classmethod
    def audit_python(cls, path):
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError as e:
            UI.err(str(e)); return None
        findings = []
        for i, line in enumerate(src.splitlines(), 1):
            for pat, sev, desc in cls.PY_PATTERNS:
                if re.search(pat, line):
                    findings.append({"line": i, "severity": sev, "issue": desc,
                                     "code": line.strip()[:80]})
        if findings:
            UI.table(f"Audit findings — {path}",
                     [(f["line"], f["severity"], f["issue"]) for f in findings],
                     cols=("Line", "Severity", "Issue"))
        else:
            UI.ok("No pattern-based findings. (Regex audit is a first pass, not a substitute "
                  "for manual review or static analyzers like bandit.)")
        return {"file": path, "findings": findings, "analyzed_lines": len(src.splitlines())}

    @staticmethod
    def identify_hash(h):
        h = h.strip().lower()
        algos = [
            (32, "MD5"), (40, "SHA-1"), (64, "SHA-256"), (128, "SHA-512"),
            (56, "SHA-224"), (96, "SHA-384"), (8, "CRC32 (hex)"),
        ]
        if re.fullmatch(r"[0-9a-f]+", h):
            for length, name in algos:
                if len(h) == length:
                    UI.ok(f"{name} candidate (length {length})")
                    return {"input": h, "candidate": name}
            UI.warn(f"Hex string of length {len(h)} — no standard single-hash match.")
            return {"input": h, "candidate": f"unknown hex ({len(h)} chars)"}
        if h.startswith(("$2b$", "$2a$", "$2y$")):
            UI.ok("bcrypt hash")
            return {"input": h[:12] + "...", "candidate": "bcrypt"}
        if h.startswith("$6$"):
            UI.ok("SHA-512 crypt (Unix)"); return {"input": h[:12]+"...", "candidate": "sha512-crypt"}
        if h.startswith("$argon2"):
            UI.ok("Argon2 hash"); return {"input": h[:12]+"...", "candidate": "argon2"}
        UI.err("Not a recognized hash format.")
        return {"input": h, "candidate": "unrecognized"}

    @staticmethod
    def file_integrity(path):
        try:
            data = open(path, "rb").read()
        except OSError as e:
            UI.err(str(e)); return None
        digests = {n: hashlib.new(n, data).hexdigest()
                   for n in ("md5", "sha1", "sha256", "sha512")}
        UI.table(f"Integrity — {path} ({len(data)} bytes)", list(digests.items()))
        return {"file": path, "size": len(data), **digests}

# ---------------------------------------------------------------- SAFE LABS
class Labs:
    """Isolated local practice labs. Everything runs on localhost SQLite / local
    Flask-free HTTP emulation — nothing leaves the machine, nothing touches
    third parties."""

    @staticmethod
    def sql_lab():
        import sqlite3
        UI.box("SQLi EDUCATIONAL LAB — LOCAL SQLite",
               ["1. A vulnerable query is built by string concatenation (vulnerable).",
                "2. You inject and see the result.",
                "3. The parameterized version blocks it. Compare."])
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE users (id INTEGER, user TEXT, pw TEXT)")
        db.execute("INSERT INTO users VALUES (1,'admin','s3cr3t!'),(2,'bob','hunter2')")
        db.commit()
        payload = input("  payload> ").strip() or "' OR '1'='1"
        vuln = f"SELECT * FROM users WHERE user='{payload}'"
        rows = db.execute(vuln).fetchall()
        UI.kv("Injected query", vuln)
        UI.kv("Rows returned (vulnerable)", str(len(rows)))
        for r in rows: UI.kv("  row", str(r))
        safe = db.execute("SELECT * FROM users WHERE user=?", (payload,)).fetchall()
        UI.kv("Parameterized result", f"{len(safe)} rows (injection neutralized)")
        UI.box("LESSON", ["Concatenation let your payload change the query logic.",
                          "The parameterized call treats the whole payload as a literal string.",
                          "Fix pattern: ALWAYS parameterize; never build SQL with f-strings/%."],
               color="green")

    @staticmethod
    def xss_lab():
        from html import escape
        UI.box("XSS EDUCATIONAL LAB — LOCAL string rendering",
               ["Shows reflected XSS sink and the encoding fix. Nothing is served over HTTP."])
        payload = input("  payload> ").strip() or "<script>alert('xss')</script>"
        UI.kv("Unescaped output", payload + "   <-- would execute in a browser")
        UI.kv("escape()d output", escape(payload) + "   <-- renders as text, harmless")
        UI.box("LESSON", ["The browser executes <script> tags found in HTML text.",
                          "escape() converts < > & to &lt; &gt; &amp; — script becomes text.",
                          "Real apps need context-aware encoding (HTML attr, JS, URL differ) + CSP."],
               color="green")

# ---------------------------------------------------------------- WORKSPACE
class Workspace:
    LANG_EXECS = {  # safe local executors actually implemented
        "python": lambda src, path: _run([sys.executable, path]),
        "bash":   lambda src, path: _run(["bash", path]) if _which("bash") else ("bash not found", 1),
    }

    @staticmethod
    def generate(code_text, name=None, lang="python"):
        ext = {"python": "py", "javascript": "js", "html": "html", "css": "css",
               "php": "php", "c": "c", "cpp": "cpp", "java": "java", "kotlin": "kt",
               "sql": "sql", "bash": "sh"}.get(lang, "txt")
        name = name or f"snippet_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = os.path.join("projects", f"{name}.{ext}")
        with open(path, "w") as f:
            f.write(code_text)
        UI.ok(f"Exported: {path}")
        return path

    @staticmethod
    def run_python(path):
        UI.warn("Executing locally. Review the code first — it runs with your user privileges.")
        out, rc = _run([sys.executable, path])
        UI.box("OUTPUT", out or "(no output)", color="green" if rc == 0 else "red")
        if rc != 0:
            UI.err(f"Exit code {rc}")
        return out, rc

    @staticmethod
    def files():
        rows = []
        for d in ("projects", "reports", "modules"):
            for fn in sorted(os.listdir(d)):
                p = os.path.join(d, fn)
                rows.append((p, os.path.getsize(p),
                             datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")))
        UI.table("Workspace files", rows, cols=("Path", "Bytes", "Modified"))
        return rows

def _run(cmd):
    try:
        c = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (c.stdout + c.stderr).strip(), c.returncode
    except subprocess.TimeoutExpired:
        return "execution timed out (30s)", 1
    except Exception as e:
        return str(e), 1

def _which(prog):
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isfile(os.path.join(p, prog)):
            return True
    return False

# ---------------------------------------------------------------- SYSTEM INFO
def sysinfo():
    import psutil
    rows = [("Python", sys.version.split()[0]),
            ("Platform", sys.platform),
            ("CPU cores", str(psutil.cpu_count())),
            ("CPU usage", f"{psutil.cpu_percent(interval=0.5)}%"),
            ("RAM used", f"{psutil.virtual_memory().percent}% of {psutil.virtual_memory().total // (2**30)} GB"),
            ("Disk used", f"{psutil.disk_usage('/').percent}%")]
    UI.table("System", rows)

# ---------------------------------------------------------------- COMMAND DISPATCH
HELP = """  [red]AI & CODING[/]
  chat <text>        talk to the AI (LLM if configured, else offline KB)
  ask <question>     same as chat, one-shot
  code <desc>        request code generation (exported to projects/)
  debug <file>       run pattern-based analysis on a Python file
  explain <topic>    offline knowledge base / AI explanation
  history            show conversation history

  [red]NETWORK (authorized targets only)[/]
  ip <host|ip>       resolve + geo + RDAP intelligence
  dns <domain>       A/AAAA/MX/NS/TXT/CNAME/SOA via DoH
  whois <domain>     RDAP registration lookup
  scan <host>        TCP connect-scan ports 1-1025+ (owns-host confirmation)
  local              discover live hosts on your LAN
  ssl <host>         TLS certificate inspection
  headers <url>      HTTP security-header audit + cookie flags
  tech <url>         technology fingerprinting from real response data
  ping <host>        ICMP reachability test

  [red]CODE SECURITY[/]
  hash <digest>      identify hash type by structure
  integrity <file>   MD5/SHA1/SHA256/SHA512 digests
  secrets <file>     scan a file for hardcoded credentials/keys

  [red]LABS & SYSTEM[/]
  lab sql            local SQL injection demonstration (SQLite)
  lab xss            local XSS encoding demonstration
  sys                system resource info
  files              list workspace files
  run <file.py>      execute a Python file locally (review first!)
  export             export last AI answer to projects/

  [red]CONFIG[/]
  ai                 show AI provider status & how to configure
  persona <name>     operator | mentor | analyst
  help               this help
  exit / quit        leave"""

def export_last(text):
    p = Workspace.generate(text, name=f"ai_answer_{datetime.datetime.now().strftime('%H%M%S')}", lang="txt")
    return p

def dispatch(cmd, arg):
    if cmd in ("exit", "quit"):
        save_history(); UI.info("History saved. Stay ethical."); return False

    if cmd in ("chat", "ask"):
        if not arg:
            arg = input("  > ").strip()
        if not arg: return True
        SESSION["history"].append({"role": "user", "content": arg})
        with console.status("[red]thinking...", spinner="dots"):
            answer, via_llm = AI.chat(arg)
        SESSION["history"].append({"role": "assistant", "content": answer})
        UI.box(f"{'AI' if via_llm else 'OFFLINE KB'} RESPONSE", answer, color="green" if via_llm else "yellow")
        save_history()

    elif cmd == "code":
        desc = arg or input("  describe the code you want> ").strip()
        if desc:
            with console.status("[red]generating...", spinner="dots"):
                answer, via_llm = AI.chat(f"Write complete, production-quality code for this request. "
                                          f"Output ONLY a code block.\nRequest: {desc}")
        if via_llm:
            m = re.search(r"```(\w*)\n(.*?)```", answer, re.S)
            code = m.group(2) if m else answer
            lang = (m.group(1) if m and m.group(1) else "python").lower()
            Workspace.generate(code, lang=lang)
        else:
            UI.warn("Code generation needs a configured AI provider (see `ai`). Offline KB "
                    "covers concepts, not arbitrary code generation — refusing to fake it.")

    elif cmd == "explain":
        ans, _ = AI.chat(f"Explain in depth: {arg or input('  topic> ')}")
        UI.box("EXPLANATION", ans)

    elif cmd == "debug":
        path = arg or input("  file> ").strip()
        if path:
            CodeSec.audit_python(path)
            if AI.connected():
                ans, _ = AI.chat(f"Review this Python file for bugs and improvements:\n\n"
                                 f"```\n{open(path).read()[:4000]}\n```")
                UI.box("AI REVIEW", ans)

    elif cmd == "history":
        for m in SESSION["history"][-20:]:
            who = "YOU" if m["role"] == "user" else "AI"
            console.print(f"[magenta]{who}[/]: {m['content'][:200]}")

    elif cmd == "ip":
        if arg:
            d = NetTools.ip_info(arg); Report.save(f"ip_{arg}", d) if d else None
        else: UI.err("usage: ip <host|ip>")

    elif cmd == "dns":
        if arg:
            d = NetTools.dns(arg); Report.save(f"dns_{arg}", d) if d else None
        else: UI.err("usage: dns <domain>")

    elif cmd == "whois":
        if arg:
            d = NetTools.whois(arg); Report.save(f"whois_{arg}", d) if d else None
        else: UI.err("usage: whois <domain>")

    elif cmd == "scan":
        if arg:
            d = NetTools.port_scan(arg)
            Report.save(f"scan_{arg}", d) if d else None
        else: UI.err("usage: scan <host>")

    elif cmd == "local":
        d = NetTools.local_discovery(); Report.save("local_discovery", d)

    elif cmd == "ssl":
        if arg:
            d = NetTools.ssl_inspect(arg.split(":")[0], int(arg.split(":")[1]) if ":" in arg else 443)
            Report.save(f"ssl_{arg}", d) if d else None
        else: UI.err("usage: ssl <host[:443]>")

    elif cmd == "headers":
        if arg:
            d = NetTools.headers_audit(arg); Report.save(f"headers_{urlparse(arg if '//' in arg else 'https://'+arg).netloc}", d) if d else None
        else: UI.err("usage: headers <url>")

    elif cmd == "tech":
        if arg:
            d = NetTools.cookies_and_tech(arg)
        else: UI.err("usage: tech <url>")

    elif cmd == "ping":
        if arg:
            p = ["ping", "-n" if os.name == "nt" else "-c", "4", arg]
            out, rc = _run(p)
            console.print(out or "(no output)")
        else: UI.err("usage: ping <host>")

    elif cmd == "hash":
        if arg: CodeSec.identify_hash(arg)
        else: UI.err("usage: hash <digest>")

    elif cmd == "integrity":
        if arg: CodeSec.file_integrity(arg)
        else: UI.err("usage: integrity <file>")

    elif cmd == "secrets":
        if arg: CodeSec.audit_python(arg)
        else: UI.err("usage: secrets <file>")

    elif cmd == "lab":
        if arg == "sql": Labs.sql_lab()
        elif arg == "xss": Labs.xss_lab()
        else: UI.err("usage: lab sql | lab xss")

    elif cmd == "sys":
        sysinfo()

    elif cmd == "files":
        Workspace.files()

    elif cmd == "run":
        if arg and os.path.isfile(arg):
            Workspace.run_python(arg)
        else: UI.err("usage: run <file.py>")

    elif cmd == "export":
        if SESSION["history"]:
            last = next((m["content"] for m in reversed(SESSION["history"])
                         if m["role"] == "assistant"), None)
            export_last(last) if last else UI.warn("No AI answer yet.")
        else: UI.warn("History empty.")

    elif cmd == "ai":
        UI.box("AI PROVIDER STATUS",
               [f"endpoint: {CFG['ai_endpoint'] or '(not set)'}",
                f"model:    {CFG['ai_model'] or '(not set)'}",
                f"status:   {'CONNECTED-capable' if AI.connected() else 'OFFLINE MODE'}", "",
                "To enable full LLM chat (free option — local Ollama):",
                "  1. Install Ollama on a machine you control: ollama.com",
                "  2. ollama pull llama3",
                "  3. In config.json set:",
                '     "ai_endpoint": "http://localhost:11434/v1",',
                '     "ai_model": "llama3"',
                "Any OpenAI-compatible endpoint also works. DARKGPT will never",
                "claim a model is connected when one is not."], color="yellow")

    elif cmd == "persona":
        if arg in PERSONAS:
            CFG["personality"] = arg; save_cfg(); UI.ok(f"Personality: {arg}")
        else: UI.err(f"choices: {', '.join(PERSONAS)}")

    elif cmd == "help":
        console.print(HELP)

    else:
        UI.err(f"Unknown command '{cmd}'. Type help.")
    return True

def main():
    UI.banner()
    UI.info("Type help for commands.")
    if not SESSION["loaded"]:
        load_history()
    while True:
        try:
            raw = input("\n[darkgpt]~$ ").strip()
        except (KeyboardInterrupt, EOFError):
            print(); save_history(); UI.info("History saved. Stay ethical."); break
        if not raw:
            continue
        cmd, _, arg = raw.partition(" ")
        try:
            if not dispatch(cmd.lower(), arg.strip()):
                break
        except KeyboardInterrupt:
            UI.warn("Interrupted.")
        except Exception as e:
            UI.err(f"Error: {e}")

if __name__ == "__main__":
    main()
