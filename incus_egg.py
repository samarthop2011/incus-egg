#!/usr/bin/env python3
import os, re, sys, time, signal, logging
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s incus-egg: %(message)s")
log = logging.getLogger("incus-egg")

BASE = os.environ["INCUS_API_URL"].rstrip("/")
PROJECT = os.getenv("INCUS_PROJECT", "default")
CERT = os.getenv("INCUS_CLIENT_CERT", "/home/container/certs/client.crt")
KEY = os.getenv("INCUS_CLIENT_KEY", "/home/container/certs/client.key")
CA = os.getenv("INCUS_SERVER_CA", "").strip()
VERIFY = CA if CA else os.getenv("INCUS_TLS_VERIFY", "true").lower() not in ("0", "false", "no")
TIMEOUT = int(os.getenv("INCUS_HTTP_TIMEOUT", "30"))

for path, label in ((CERT, "client certificate"), (KEY, "client private key")):
    if not Path(path).is_file():
        raise RuntimeError(f"Missing {label}: {path}")
if isinstance(VERIFY, str) and not Path(VERIFY).is_file():
    raise RuntimeError(f"Missing server CA certificate: {VERIFY}")

S = requests.Session()
S.cert = (CERT, KEY)
S.verify = VERIFY
S.headers.update({"Content-Type": "application/json"})

def api(method, path, **kwargs):
    r = S.request(method, BASE + path, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    data = r.json()
    if data.get("type") == "error":
        raise RuntimeError(data.get("error", "Incus API error"))
    return data

def wait_op(data):
    op = data.get("operation")
    if data.get("type") == "async" and op:
        if not op.startswith("/"):
            op = "/" + op
        result = api("GET", op + "/wait?timeout=60")
        err = result.get("metadata", {}).get("err")
        if err:
            raise RuntimeError(err)

def safe_name(value):
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return re.sub(r"-+", "-", value)[:60] or "ptero-vps"

SERVER_ID = os.getenv("P_SERVER_UUID") or os.getenv("SERVER_UUID") or "ptero-server"
NAME = safe_name(os.getenv("INCUS_INSTANCE_NAME") or "ptero-" + SERVER_ID[:8])

def state():
    try:
        d = api("GET", f"/1.0/instances/{NAME}/state?project={PROJECT}")
        return d.get("metadata", {}).get("status", "Unknown")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return "Missing"
        raise

def action(verb):
    d = api("PUT", f"/1.0/instances/{NAME}/state?project={PROJECT}",
            json={"action": verb, "timeout": 60, "force": True})
    wait_op(d)

def create():
    image = os.getenv("INCUS_IMAGE", "images:debian/13")
    payload = {
        "name": NAME, "type": "container", "source": {"type": "image", "mode": "pull", "alias": image},
        "config": {"limits.cpu": os.getenv("INCUS_CPU", "2"),
                   "limits.memory": os.getenv("INCUS_RAM", "4GiB"),
                   "boot.autostart": "true"},
        "devices": {
            "root": {"type": "disk", "path": "/", "pool": os.getenv("INCUS_STORAGE_POOL", "default"),
                     "size": os.getenv("INCUS_DISK", "25GiB")},
            "eth0": {"type": "nic", "name": "eth0", "nictype": "bridged",
                     "parent": os.getenv("INCUS_BRIDGE", "incusbr0")}
        },
        "profiles": [], "ephemeral": False
    }
    if os.getenv("INCUS_NESTING", "false").lower() in ("true", "1", "yes"):
        payload["config"]["security.nesting"] = "true"
    log.info("Creating %s from %s", NAME, image)
    wait_op(api("POST", f"/1.0/instances?project={PROJECT}", json=payload))
    log.info("Starting %s", NAME)
    action("start")
    log.info("Incus VPS %s is running", NAME)

def stop(*_):
    try:
        if state() == "Running":
            log.info("Stopping Incus VPS %s", NAME)
            action("stop")
    except Exception:
        log.exception("Failed to stop Incus VPS")
    sys.exit(0)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

try:
    current = state()
    if current == "Missing":
        create()
    elif current != "Running":
        log.info("Existing instance state is %s; starting it", current)
        action("start")
    else:
        log.info("Incus VPS %s is already running", NAME)
    log.info("Lifecycle wrapper active for %s", NAME)
    while True:
        time.sleep(30)
        if state() == "Missing":
            raise RuntimeError("Managed Incus instance disappeared")
except Exception as exc:
    log.exception("Provisioning/lifecycle failure: %s", exc)
    sys.exit(1)
