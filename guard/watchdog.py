"""Fail-closed risk watcher. Runs independently from Freqtrade's AI process.

Never authorises exchanges or deposits. Uses localhost Docker-network API.
Entry guards expire after 120 seconds; a dead sidecar cannot allow new buys.
"""
import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from risk_logic import risk_decision

LOG = logging.getLogger('risk-guard')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
ROOT = Path('/freqtrade/user_data')
CONFIG = ROOT / 'config.json'
STATE = ROOT / 'risk_guard_state.json'
HEARTBEAT = ROOT / 'risk_guard_heartbeat.json'
BASE = 'http://freqtrade:8080/api/v1'
POLL_SECONDS = 30


def write_atomic(path: Path, obj: dict):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def api_json(endpoint: str, method: str = 'GET', authorization: str = ''):
    req = urllib.request.Request(BASE + endpoint, data=b'' if method == 'POST' else None,
                                 method=method,
                                 headers={'Authorization': authorization} if authorization else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def auth():
    cfg = json.loads(CONFIG.read_text())
    api = cfg['api_server']
    creds = f"{api['username']}:{api['password']}".encode()
    basic = 'Basic ' + base64.b64encode(creds).decode()
    response = api_json('/token/login', 'POST', basic)
    return 'Bearer ' + response['access_token']


def check(token: str):
    api_json('/health', authorization=token)  # Request also proves auth and bot responds.
    balance = api_json('/balance', authorization=token)
    # Freqtrade's total_bot is marked-to-market equity denominated in stake currency.
    equity = float(balance['total_bot'])
    initial = float(balance['starting_capital'])
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    state = risk_decision(state, equity, initial)
    write_atomic(STATE, state)
    if state['locked']:
        return 'halt', state['reason']
    return 'ok', ''


def run_once():
    try:
        status, reason = check(auth())
    except Exception as exc:
        status, reason = 'halt', 'watchdog unavailable: ' + type(exc).__name__
    hb = {'timestamp': time.time(), 'status': status, 'reason': reason}
    write_atomic(HEARTBEAT, hb)
    LOG.info('status=%s reason=%s', status, reason)


if __name__ == '__main__':
    while True:
        run_once()
        time.sleep(POLL_SECONDS)
