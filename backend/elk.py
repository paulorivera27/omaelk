"""
Protocol, paths and config for ELK-BLEDOB / "ELK-BLE*" Bluetooth RGB controllers.

Protocol: GATT service 0xfff0, write characteristic 0xfff3 (write-without-
response). Commands are 9-byte frames, 7E <7 payload bytes> EF. The frames and
the effect table follow the ELK-BLEDOB reference implementation
(github.com/8none1/elk-bledob, MIT) -- see the README credits.

The controller only reliably accepts ~10-20 writes/sec, so anything streaming
colour (the music visualiser) must rate-limit itself.
"""

import json
import os

WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NAME_PREFIX = "ELK-BLE"

# Everything the daemon and its clients share lives in the user's runtime dir.
RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
SOCK = os.path.join(RUNTIME_DIR, "ledble.sock")
LOCK = os.path.join(RUNTIME_DIR, "ledble.lock")
MUSIC_PID = os.path.join(RUNTIME_DIR, "ledble-music.pid")

CONFIG = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "ledble", "config.json")

# Same location the `led` wrapper creates its virtualenv in (outside the
# plugin folder, which omarchy requires to be symlink-free).
VENV = os.environ.get("LEDBLE_VENV") or os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
    "ledble", "venv")


def load_address():
    """Controller MAC: $LEDBLE_ADDR, else the saved config, else None."""
    addr = os.environ.get("LEDBLE_ADDR")
    if addr:
        return addr
    try:
        with open(CONFIG) as f:
            return json.load(f).get("address")
    except (OSError, ValueError):
        return None


def save_address(addr):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump({"address": addr}, f)


def _frame(payload):
    """Wrap 7 payload bytes in the 7E ... EF envelope."""
    assert len(payload) == 7
    return bytes([0x7E] + list(payload) + [0xEF])


def cmd_power(on):
    if on:
        return _frame([0x07, 0x04, 0xFF, 0x00, 0x01, 0x02, 0x01])
    return _frame([0x07, 0x04, 0x00, 0x00, 0x00, 0x02, 0x01])


def cmd_color(r, g, b):
    return _frame([0x07, 0x05, 0x03, r & 0xFF, g & 0xFF, b & 0xFF, 0x10])


def cmd_brightness(pct):
    pct = max(0, min(100, int(pct)))
    return _frame([0x04, 0x01, pct, 0x01, 0xFF, 0x02, 0x01])


def cmd_mode(mode):
    """Built-in dynamic effect; `mode` is an effect id (see NAMED_MODES)."""
    return _frame([0x07, 0x03, mode & 0xFF, 0x03, 0xFF, 0xFF, 0x00])


def cmd_speed(speed):
    """Effect speed, 0 (slow) .. 100 (fast)."""
    speed = max(0, min(100, int(speed)))
    return _frame([0x07, 0x02, speed, 0xFF, 0xFF, 0xFF, 0x00])


# Effect ids for ELK-BLEDOB (0x87-0x9c), from the reference EFFECT_MAP.
NAMED_MODES = {
    "jump-3color": 0x87,
    "jump-7color": 0x88,
    "fade-3color": 0x89,
    "fade-7color": 0x8A,
    "fade-red": 0x8B,
    "fade-green": 0x8C,
    "fade-blue": 0x8D,
    "fade-yellow": 0x8E,
    "fade-cyan": 0x8F,
    "fade-magenta": 0x90,
    "fade-white": 0x91,
    "fade-red-green": 0x92,
    "fade-red-blue": 0x93,
    "fade-green-blue": 0x94,
    "strobe-7color": 0x95,
    "strobe-red": 0x96,
    "strobe-green": 0x97,
    "strobe-blue": 0x98,
    "strobe-yellow": 0x99,
    "strobe-cyan": 0x9A,
    "strobe-magenta": 0x9B,
    "strobe-white": 0x9C,
}
