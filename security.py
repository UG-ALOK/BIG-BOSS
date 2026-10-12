
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import socket
import secrets
import threading
import ipaddress
import html
from datetime import datetime
from urllib.parse import urlsplit

import requests
from flask import Flask, request, jsonify, render_template_string

APP_NAME = "MANIFEST SECURITY CONSOLE"
DEVELOPER = "UG ALOK"
DEFAULT_PORT = 5000

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

LOCK = threading.Lock()
GENERAL_CREATED = False
LOCATION_CREATED = False

# -------------------- STORAGE --------------------

def setup_report_dir():
    candidates = [
        os.path.expanduser("~/storage/downloads"),
        "/sdcard/Download",
        os.path.expanduser("~/manifest-reports"),
    ]

    for folder in candidates:
        try:
            os.makedirs(folder, exist_ok=True)
            test = os.path.join(folder, ".manifest_test")
            with open(test, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test)
            return folder
        except OSError:
            continue

    folder = os.path.expanduser("~/manifest-reports")
    os.makedirs(folder, exist_ok=True)
    return folder


REPORT_DIR = setup_report_dir()
GENERAL_FILE = os.path.join(REPORT_DIR, "manifest.html")
LOCATION_FILE = os.path.join(REPORT_DIR, "location.html")


def timestamp():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def display_path(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home) else path


def save_html(path, title, rows):
    """One compact HTML report per event; overwrite the existing file."""
    safe_title = html.escape(str(title))
    items = []

    for label, value in rows:
        items.append(
            "<div class='row'>"
            f"<span class='label'>{html.escape(str(label))}</span>"
            f"<span class='value'>{html.escape(str(value))}</span>"
            "</div>"
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
body {{
  background:#07110b; color:#38e878; font:14px/1.5 monospace;
  padding:16px; margin:0; overflow-wrap:anywhere;
}}
main {{
  max-width:760px; margin:auto; padding:16px;
  border:1px solid #176b38; border-radius:10px;
  background:#0a170e;
}}
h2 {{ color:#38e878; font-size:19px; }}
.row {{ padding:8px 0; border-bottom:1px solid #153c25; }}
.label {{ display:block; color:#a2ffba; font-weight:bold; }}
.value {{ display:block; color:#38e878; white-space:pre-wrap; }}
</style>
</head>
<body><main>
<h2>{safe_title}</h2>
<div class="row"><span class="label">Generated</span>
<span class="value">{html.escape(timestamp())}</span></div>
{''.join(items)}
</main></body></html>"""

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(document)
        return True
    except OSError as exc:
        print(f"{RED}[SAVE ERROR] {exc}{RESET}", flush=True)
        return False


# -------------------- IP DETAILS --------------------

def client_ip():
    # Do not trust spoofable X-Forwarded-For headers.
    return request.remote_addr or "Unknown"


def ip_type(value):
    try:
        ip = ipaddress.ip_address(value)
        if ip.is_loopback:
            return "Localhost"
        if ip.is_private:
            return "Private/LAN"
        if ip.is_global:
            return "Public"
        return "Non-public"
    except ValueError:
        return "Unknown"


def phone_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "Unavailable"
    finally:
        sock.close()


def term_field(label, value, color=GREEN):
    print(
        f"  {YELLOW}{label:<16}{RESET} {color}{value}{RESET}",
        flush=True
    )


# -------------------- LIVE REQUEST LOGGING --------------------

@app.before_request
def live_request():
    request._start_time = time.perf_counter()

    print("\n" + CYAN + "─" * 56 + RESET, flush=True)
    print(
        f"{YELLOW}[ LIVE REQUEST ] {timestamp()}{RESET}",
        flush=True
    )
    term_field("CLIENT IP", client_ip())
    term_field("IP TYPE", ip_type(client_ip()))
    term_field("FULL URL", request.url, YELLOW)
    term_field("METHOD", request.method)
    term_field("USER-AGENT", request.headers.get("User-Agent", "Unknown"))
    term_field("LANGUAGE", request.headers.get("Accept-Language", "Unknown"))
    term_field("REFERRER", request.headers.get("Referer", "None"))


@app.after_request
def response_log(response):
    elapsed = round(
        (time.perf_counter() - request._start_time) * 1000, 2
    )

    status_color = GREEN if response.status_code < 400 else RED
    term_field("HTTP STATUS", response.status_code, status_color)
    term_field("RESPONSE TIME", f"{elapsed} ms")

    # Only the first successful homepage GET creates the general report.
    # Refreshes, favicon requests and API requests never create another one.
    global GENERAL_CREATED

    if request.path == "/" and request.method == "GET":
        reserved = False

        with LOCK:
            if not GENERAL_CREATED:
                GENERAL_CREATED = True
                reserved = True

        if reserved:
            rows = [
                ("Time", timestamp()),
                ("Full URL", request.url),
                ("Client IP", client_ip()),
                ("IP type", ip_type(client_ip())),
                ("Phone LAN IP", phone_lan_ip()),
                ("Browser", request.headers.get("User-Agent", "Unknown")),
                ("Language", request.headers.get("Accept-Language", "Unknown")),
                ("HTTP status", response.status_code),
                ("Response time", f"{elapsed} ms"),
            ]

            if save_html(
                GENERAL_FILE, "MANIFEST - VISIT REPORT", rows
            ):
                print(f"{GREEN}[+] First report saved{RESET}", flush=True)
                term_field("REPORT", display_path(GENERAL_FILE))
            else:
                print(
                    f"{RED}[!] Report could not be saved. "
                    f"Restart server to retry.{RESET}",
                    flush=True
                )
        else:
            print(
                f"{CYAN}[i] General report already exists; skipped.{RESET}",
                flush=True
            )

    print(CYAN + "─" * 56 + RESET, flush=True)
    return response


# -------------------- WEB UI --------------------

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Manifest Security Console</title>
<style>
* {box-sizing:border-box}
body {margin:0;background:#101318;color:#e7eaf0;font:15px/1.55 system-ui,sans-serif}
header {padding:22px;background:#181d25;border-bottom:1px solid #303744}
main {width:min(900px,94%);margin:24px auto}
h1 {font-size:21px;margin:0 0 5px}
h2 {font-size:18px}
.muted {color:#aab3c2}
nav {display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}
nav a,button {padding:10px 14px;border-radius:8px;border:1px solid #424b5a;background:#242b36;color:white;text-decoration:none;cursor:pointer}
.card {background:#181d25;border:1px solid #303744;padding:18px;border-radius:12px;margin:14px 0}
input[type=url] {width:100%;padding:12px;background:#0f1218;color:white;border:1px solid #465064;border-radius:8px;margin:8px 0 12px}
pre {white-space:pre-wrap;overflow-wrap:anywhere;background:#0c0f14;border:1px solid #303744;padding:12px;border-radius:8px}
.notice {color:#e5c36a}
</style>
</head>
<body>
<header>
<h1>MANIFEST SECURITY CONSOLE</h1>
<div class="muted">Developed by UG ALOK</div>
</header>
<main>
<nav>
<a href="/">Dashboard</a>
<a href="#checker">Website Checker</a>
<a href="#device">Browser Info</a>
<a href="#location">Optional Location</a>
</nav>

<section class="card">
<h2>Live Request Logging</h2>
<p>Requests are displayed in Termux. Only the first homepage visit
creates the general report.</p>
<p class="muted">Reports are compact and saved to the configured report folder.</p>
</section>

<section class="card" id="checker">
<h2>Website Checker</h2>
<form id="check-form">
<input id="url" type="url" placeholder="https://example.com" required>
<button type="submit">Check URL</button>
</form>
<pre id="check-result">Enter a public website URL.</pre>
</section>

<section class="card" id="device">
<h2>Browser Information</h2>
<pre id="browser-info"></pre>
</section>

<section class="card" id="location">
<h2>Optional Location Report</h2>
<p class="notice">Location is optional. Check consent and grant browser permission.
Geolocation normally requires HTTPS or localhost.</p>
<label><input type="checkbox" id="consent">
I consent to share my browser location.</label>
<button id="share" type="button">Share Location</button>
<pre id="location-result">No location requested.</pre>
</section>
</main>

<script>
const info = {
  Browser: navigator.userAgent,
  Language: navigator.language || "Unknown",
  Platform: navigator.platform || "Unknown",
  SecureContext: window.isSecureContext,
  PageURL: location.href
};
document.getElementById("browser-info").textContent =
  Object.entries(info).map(([k,v]) => k + ": " + v).join("\n");

document.getElementById("check-form").addEventListener("submit", async e => {
  e.preventDefault();
  const out = document.getElementById("check-result");
  out.textContent = "Checking…";
  try {
    const r = await fetch("/api/website-check", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({url:document.getElementById("url").value})
    });
    out.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (err) {
    out.textContent = "Request failed: " + err.message;
  }
});

document.getElementById("share").addEventListener("click", () => {
  const out = document.getElementById("location-result");

  if (!document.getElementById("consent").checked) {
    out.textContent = "Please check the consent box first.";
    return;
  }
  if (!window.isSecureContext || !navigator.geolocation) {
    out.textContent = "Geolocation requires browser support and HTTPS or localhost.";
    return;
  }

  out.textContent = "Waiting for location permission…";
  navigator.geolocation.getCurrentPosition(async pos => {
    try {
      const r = await fetch("/api/location", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          consent:true,
          latitude:pos.coords.latitude,
          longitude:pos.coords.longitude,
          accuracy:pos.coords.accuracy
        })
      });
      out.textContent = JSON.stringify(await r.json(), null, 2);
    } catch (err) {
      out.textContent = "Failed to send location: " + err.message;
    }
  }, err => {
    out.textContent = "Location error: " + err.message;
  }, {timeout:15000,maximumAge:30000});
});
</script>
</body>
</html>
"""


@app.get("/")
def dashboard():
    return render_template_string(PAGE)


# -------------------- WEBSITE CHECKER --------------------

def validate_public_url(raw):
    raw = (raw or "").strip()

    if not raw or len(raw) > 2048:
        raise ValueError("Enter a valid URL.")

    parsed = urlsplit(raw)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only valid HTTP/HTTPS URLs are supported.")

    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed.")

    if parsed.port not in (None, 80, 443):
        raise ValueError("Only standard HTTP/HTTPS ports are supported.")

    host = parsed.hostname.rstrip(".").lower()

    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local hostnames are not allowed.")

    try:
        addresses = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ValueError("Hostname lookup failed.")

    found = False
    for entry in addresses:
        try:
            addr = ipaddress.ip_address(entry[4][0])
        except ValueError:
            continue
        if not addr.is_global:
            raise ValueError("The URL resolves to a non-public IP.")
        found = True

    if not found:
        raise ValueError("No public IP address found.")

    return raw, host


@app.post("/api/website-check")
def website_check():
    data = request.get_json(silent=True) or {}

    try:
        url, host = validate_public_url(data.get("url", ""))
        start = time.perf_counter()

        r = requests.get(
            url,
            timeout=(5, 10),
            allow_redirects=False,
            stream=True,
            headers={"User-Agent": "ManifestSecurityConsole/1.0"}
        )
        elapsed = round((time.perf_counter() - start) * 1000, 2)

        result = {
            "url": url,
            "hostname": host,
            "https": urlsplit(url).scheme == "https",
            "status": r.status_code,
            "response_ms": elapsed,
            "content_type": r.headers.get("Content-Type", "Unknown"),
            "content_length": r.headers.get("Content-Length", "Unknown"),
            "server": r.headers.get("Server", "Not disclosed"),
            "redirect": r.headers.get("Location", "None")
        }
        r.close()

        print(f"\n{YELLOW}[ URL CHECK ]{RESET}", flush=True)
        term_field("FULL URL", url, YELLOW)
        term_field("HOSTNAME", host)
        term_field("HTTP STATUS", result["status"])
        term_field("RESPONSE", f"{elapsed} ms")
        term_field("CONTENT TYPE", result["content_type"])
        term_field("SERVER", result["server"])

        return jsonify(result)

    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except requests.RequestException:
        return jsonify({"ok": False, "error": "Request failed or timed out."}), 502


# -------------------- LOCATION REPORT --------------------

@app.post("/api/location")
def location_report():
    global LOCATION_CREATED

    data = request.get_json(silent=True) or {}

    if data.get("consent") is not True:
        return jsonify({"ok": False, "error": "Consent required."}), 403

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        accuracy = float(data.get("accuracy", 0))
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid coordinates."}), 400

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"ok": False, "error": "Coordinates out of range."}), 400

    # Reserve this one report event atomically.
    with LOCK:
        if LOCATION_CREATED:
            return jsonify({
                "ok": False,
                "error": "Location report already created."
            }), 409
        LOCATION_CREATED = True

    address = "Unavailable"
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format":"jsonv2", "lat":lat, "lon":lon},
            headers={"User-Agent":"ManifestSecurityConsole/1.0"},
            timeout=8
        )
        if r.ok:
            address = r.json().get("display_name", address)
        r.close()
    except requests.RequestException:
        pass

    address_parts = [x.strip() for x in address.split(",") if x.strip()]
    short_address = ", ".join(address_parts[:4]) if address_parts else "Unavailable"

    rows = [
        ("Time", timestamp()),
        ("Client IP", client_ip()),
        ("IP type", ip_type(client_ip())),
        ("Latitude", lat),
        ("Longitude", lon),
        ("Accuracy", f"{accuracy:.0f} metres"),
        ("Address", short_address),
    ]

    if not save_html(LOCATION_FILE, "MANIFEST - LOCATION REPORT", rows):
        with LOCK:
            LOCATION_CREATED = False
        return jsonify({"ok":False, "error":"Could not save location report."}), 500

    print(f"\n{YELLOW}[ LOCATION REPORT SAVED ]{RESET}", flush=True)
    term_field("CLIENT IP", client_ip())
    term_field("IP TYPE", ip_type(client_ip()))
    term_field("LATITUDE", lat)
    term_field("LONGITUDE", lon)
    term_field("ACCURACY", f"{accuracy:.0f} metres")
    term_field("ADDRESS", short_address)
    term_field("REPORT", display_path(LOCATION_FILE))

    return jsonify({
        "ok": True,
        "message": "Location report saved.",
        "report": display_path(LOCATION_FILE)
    })


# -------------------- MAIN MENU --------------------

def choose_port():
    answer = input(
        f"{YELLOW}Use custom port? (Y/N): {RESET}"
    ).strip().lower()

    if answer not in ("y", "yes"):
        return DEFAULT_PORT

    while True:
        value = input(f"{YELLOW}Port (1024-9999): {RESET}").strip()
        if value.isdigit() and 1024 <= int(value) <= 9999:
            return int(value)
        print(f"{RED}Invalid port.{RESET}")


def start_server():
    print(f"\n{YELLOW}1.{RESET} Localhost only")
    print(f"{YELLOW}2.{RESET} LAN access")
    mode = input(f"{YELLOW}Choose mode (1/2): {RESET}").strip()

    host = "0.0.0.0" if mode == "2" else "127.0.0.1"

    if host == "0.0.0.0":
        print(
            f"{RED}Warning: LAN mode exposes this app to your local network. "
            f"Do not expose it to the public internet.{RESET}"
        )

    port = choose_port()

    print(f"\n{GREEN}[+] Starting server{RESET}")
    print(f"{YELLOW}[+] Local URL: http://127.0.0.1:{port}/{RESET}")
    print(f"{GREEN}[+] Max report events: 2{RESET}")
    print(f"{GREEN}[+] Report folder: {display_path(REPORT_DIR)}{RESET}")
    print(f"{YELLOW}[+] Press CTRL+C to stop.{RESET}\n")

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    try:
        app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except OSError as exc:
        print(f"{RED}[SERVER ERROR] {exc}{RESET}")


def main():
    while True:
        os.system("clear")
        print(f"{YELLOW}{BOLD}")
        print("╔══════════════════════════════════════════════════╗")
        print("║          KIT CLONE              ║")
        print("║                UG ALOK                           ║")
        print("╚══════════════════════════════════════════════════╝")
        print(f"{RESET}")
        print(f"{GREEN}Report folder: {display_path(REPORT_DIR)}{RESET}")
        print()
        print(f"{YELLOW}1.{RESET} Start Tool")
        print(f"{YELLOW}2.{RESET} Show Report Paths")
        print(f"{YELLOW}3.{RESET} Exit")

        choice = input(f"\n{YELLOW}Select option: {RESET}").strip()

        if choice == "1":
            start_server()
            input(f"\n{YELLOW}Press Enter for main menu...{RESET}")

        elif choice == "2":
            print(f"\n{GREEN}General: {display_path(GENERAL_FILE)}{RESET}")
            print(f"{GREEN}Location: {display_path(LOCATION_FILE)}{RESET}")
            input(f"\n{YELLOW}Press Enter to return...{RESET}")

        elif choice == "3":
            print(f"{GREEN}Goodbye.{RESET}")
            break

        else:
            print(f"{RED}Invalid choice.{RESET}")
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped.{RESET}")
