from flask import Flask, jsonify, render_template, request, session, redirect, url_for
import socket
import sqlite3
import subprocess
import platform
import json
import logging
import os
import sys
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

# ── Logging structuré ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Force UTF-8 sur la sortie console (évite UnicodeEncodeError sous Windows/cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "netwatch-dev-key-changez-moi-en-prod")

# ── Authentification ──────────────────────────────────────────────────────────
AUTH_USER = os.getenv("NETWATCH_USER", "admin")
AUTH_PASS = os.getenv("NETWATCH_PASSWORD", "netwatch")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ── Base de données SQLite ────────────────────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), "netwatch.db")

def init_db():
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                host_name   TEXT    NOT NULL,
                host        TEXT    NOT NULL,
                status      TEXT    NOT NULL,
                latency     REAL,
                checked_at  TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_host ON scan_history(host_name, id DESC)")
        conn.commit()
    logger.info("Base de données initialisée : %s", _DB_PATH)


def save_scan_results(results):
    with sqlite3.connect(_DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO scan_history (host_name, host, status, latency, checked_at) VALUES (?,?,?,?,?)",
            [(r["name"], r["host"], r["status"], r["latency"], r["checked_at"]) for r in results],
        )
        # Garder max 200 scans par hôte
        conn.execute("""
            DELETE FROM scan_history
            WHERE id NOT IN (
                SELECT id FROM scan_history
                ORDER BY id DESC LIMIT 10000
            )
        """)
        conn.commit()


# ── Alertes ───────────────────────────────────────────────────────────────────
_last_status: dict = {}


def check_and_alert(results):
    for r in results:
        name = r["name"]
        new_status = r["status"]
        old_status = _last_status.get(name)
        if old_status is not None and old_status != new_status:
            direction = "RÉTABLI ↑" if new_status == "up" else "HORS LIGNE ↓"
            logger.warning("ALERTE [%s] %s  (%s → %s)", direction, name, old_status, new_status)
            _send_alert_email(name, old_status, new_status)
        _last_status[name] = new_status


def _send_alert_email(name: str, old_status: str, new_status: str):
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        return  # Email non configuré — log suffisant
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")
        alert_to  = os.getenv("ALERT_TO", smtp_user)
        direction = "RÉTABLI" if new_status == "up" else "HORS LIGNE"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        body = (
            f"Hôte   : {name}\n"
            f"Statut : {old_status} → {new_status}\n"
            f"Heure  : {now}\n"
        )
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[NetWatch] {name} est {direction}"
        msg["From"]    = smtp_user
        msg["To"]      = alert_to
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [alert_to], msg.as_string())
        logger.info("Email d'alerte envoyé pour %s → %s", name, alert_to)
    except Exception as e:
        logger.error("Échec envoi email pour %s : %s", name, e)


# ── Chargement des cibles ─────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "targets.json")


def load_targets():
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            targets = json.load(f)
        logger.info("targets.json chargé : %d cibles", len(targets))
        return targets
    except FileNotFoundError:
        logger.error("targets.json introuvable — utilisation de la liste par défaut")
        return [
            {"name": "Google DNS",     "host": "8.8.8.8", "ports": [53],  "type": "dns"},
            {"name": "Cloudflare DNS", "host": "1.1.1.1", "ports": [53],  "type": "dns"},
        ]
    except json.JSONDecodeError as e:
        logger.error("targets.json invalide : %s", e)
        return []


def save_targets():
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(TARGETS, f, ensure_ascii=False, indent=2)
    logger.info("targets.json sauvegardé : %d cibles", len(TARGETS))


TARGETS = load_targets()

# ── Fonctions de vérification ─────────────────────────────────────────────────

def ping_host(host, count=2):
    try:
        is_windows = platform.system().lower() == "windows"
        param = "-n" if is_windows else "-c"
        timeout_flag = ["-w", "2000"] if is_windows else ["-W", "2"]
        cmd = ["ping", param, str(count), *timeout_flag, host]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if result.returncode == 0:
            out = result.stdout.decode()
            for line in out.split("\n"):
                if "avg" in line or "moyenne" in line:
                    parts = line.split("/")
                    if len(parts) >= 5:
                        try:
                            return True, round(float(parts[4]), 1)
                        except (ValueError, IndexError):
                            pass
                if "time=" in line.lower():
                    try:
                        t = line.lower().split("time=")[1].split()[0].replace("ms", "")
                        return True, round(float(t), 1)
                    except (ValueError, IndexError):
                        pass
            return True, None
        return False, None
    except Exception as e:
        logger.debug("ping_host(%s) : %s", host, e)
        return False, None


def check_port(host, port, timeout=1):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception as e:
        logger.debug("check_port(%s:%s) : %s", host, port, e)
        return False


def check_target(target):
    start = time.time()
    reachable, latency = ping_host(target["host"])
    ports_status = {}
    with ThreadPoolExecutor(max_workers=min(len(target["ports"]), 10)) as ex:
        futures = {ex.submit(check_port, target["host"], p): p for p in target["ports"]}
        for f in as_completed(futures):
            ports_status[futures[f]] = f.result()
    any_port_open = any(ports_status.values())
    elapsed = round((time.time() - start) * 1000, 1)
    status = "up" if (reachable or any_port_open) else "down"
    checked_at = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    logger.debug("%-20s  status=%-4s  latency=%s ms", target["name"], status, latency or elapsed)
    return {
        "name":      target["name"],
        "host":      target["host"],
        "type":      target["type"],
        "status":    status,
        "reachable": reachable,
        "latency":   latency if latency is not None else elapsed,
        "ports":     ports_status,
        "checked_at": checked_at,
    }

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        if request.form.get("username") == AUTH_USER and request.form.get("password") == AUTH_PASS:
            session["logged_in"] = True
            logger.info("Connexion réussie pour '%s'", request.form.get("username"))
            return redirect(url_for("dashboard"))
        error = "Identifiants incorrects."
        logger.warning("Tentative de connexion échouée")
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/status")
@login_required
def api_status():
    logger.info("Scan démarré (%d cibles)", len(TARGETS))
    results = [None] * len(TARGETS)
    with ThreadPoolExecutor(max_workers=min(len(TARGETS), 10)) as ex:
        futures = {ex.submit(check_target, t): i for i, t in enumerate(TARGETS)}
        for f in as_completed(futures):
            results[futures[f]] = f.result()
    up = sum(1 for r in results if r["status"] == "up")
    logger.info("Scan terminé — %d/%d en ligne", up, len(results))
    save_scan_results(results)
    check_and_alert(results)
    return jsonify({
        "hosts": results,
        "summary": {
            "total": len(results),
            "up": up,
            "down": len(results) - up,
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    })


@app.route("/api/history")
@login_required
def get_history():
    limit = min(int(request.args.get("limit", 20)), 100)
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT host_name, status, latency, checked_at
            FROM scan_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit * max(len(TARGETS), 1),)).fetchall()

    history: dict = {}
    for row in rows:
        name = row["host_name"]
        if name not in history:
            history[name] = []
        if len(history[name]) < limit:
            history[name].append({
                "status":     row["status"],
                "latency":    row["latency"],
                "checked_at": row["checked_at"],
            })

    result = {}
    for name, scans in history.items():
        up_count = sum(1 for s in scans if s["status"] == "up")
        result[name] = {
            "uptime_pct": round(up_count / len(scans) * 100, 1) if scans else 0,
            "scans": scans,
        }
    return jsonify(result)


@app.route("/api/targets", methods=["GET"])
@login_required
def get_targets():
    return jsonify(TARGETS)


@app.route("/api/targets", methods=["POST"])
@login_required
def add_target():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Corps JSON manquant"}), 400
    name = str(data.get("name", "")).strip()
    host = str(data.get("host", "")).strip()
    ports_raw = data.get("ports", [])
    target_type = str(data.get("type", "web")).strip()
    if not name or not host:
        return jsonify({"error": "Les champs 'name' et 'host' sont obligatoires"}), 400
    if any(t["name"] == name for t in TARGETS):
        return jsonify({"error": f"Un hôte nommé '{name}' existe déjà"}), 409
    try:
        ports = [int(p) for p in ports_raw if str(p).strip().isdigit()]
    except (ValueError, TypeError):
        return jsonify({"error": "Ports invalides"}), 400
    if not ports:
        ports = [80]
    new_target = {"name": name, "host": host, "ports": ports, "type": target_type}
    TARGETS.append(new_target)
    save_targets()
    logger.info("Hôte ajouté : %s (%s)", name, host)
    return jsonify(new_target), 201


@app.route("/api/targets/<path:name>", methods=["DELETE"])
@login_required
def delete_target(name):
    global TARGETS
    original_len = len(TARGETS)
    TARGETS = [t for t in TARGETS if t["name"] != name]
    if len(TARGETS) == original_len:
        return jsonify({"error": f"Hôte '{name}' introuvable"}), 404
    save_targets()
    logger.info("Hôte supprimé : %s", name)
    return jsonify({"deleted": name}), 200


# ── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("NetWatch démarré sur http://localhost:5000")
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
