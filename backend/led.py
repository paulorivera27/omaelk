#!/usr/bin/env python3
"""
CLI for ELK-BLE* LED controllers (run it through the `led` wrapper).

All commands go through a small persistent daemon (started on demand) that
holds one BLE connection, so changes are instant and never collide.

  led setup                    find the controller and remember its address
  led on | off
  led color RRGGBB             e.g. led color ff8800
  led bright 0-100
  led mode <name|id> [--speed 0-100]
  led speed 0-100
  led music [--source NAME] [-v]     audio-reactive (Ctrl-C or music-stop)
  led music-stop | music-status
  led status                   daemon / controller state
  led scan-modes               step through the effect ids
  led menu-snippet             print the omarchy menu entries (JSONC)
  led daemon | stop-daemon
"""

import argparse
import asyncio
import os
import signal
import sys

import elk
import ledclient

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


# ---- music process bookkeeping -------------------------------------------

def music_pid():
    """PID of a running `led music`, or None. The cmdline check guards against
    a recycled PID."""
    try:
        with open(elk.MUSIC_PID) as f:
            pid = int(f.read())
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            if b"led.py" in f.read():
                return pid
    except (OSError, ValueError):
        pass
    return None


def stop_music():
    pid = music_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False
        return True
    return False


# ---- setup ---------------------------------------------------------------

async def setup(preferred):
    from bleak import BleakScanner     # heavy import: only needed here
    print(f"Scanning for {elk.NAME_PREFIX}* controllers (8s)...")
    found = await BleakScanner.discover(timeout=8.0)
    devs = [d for d in found if d.name and d.name.startswith(elk.NAME_PREFIX)]
    if not devs:
        print("No controller found. Is it powered (USB plugged in) and nearby?\n"
              "If it looks stuck: bluetoothctl disconnect <address>", file=sys.stderr)
        return 1
    for d in devs:
        print(f"  {d.name}  {d.address}")
    pick = next((d for d in devs if d.address == preferred), devs[0])
    elk.save_address(pick.address)
    print(f"Saved {pick.address} to {elk.CONFIG}")
    return 0


# ---- omarchy menu --------------------------------------------------------

def menu_snippet():
    """JSONC entries for ~/.config/omarchy/extensions/omarchy-menu.jsonc,
    with this checkout's real paths."""
    import json
    led = os.path.join(ROOT, "led")
    sc = os.path.join(ROOT, "scripts")
    rows = {}

    def add(key, label, icon, action=None, **extra):
        row = {"icon": icon, "label": label}
        if action:
            row["action"] = action
        row.update(extra)
        rows[key] = row

    G = {  # Nerd Font glyphs
        "bulb": "\U000f0335", "on": "\U000f0521", "off": "\U000f0904",
        "palette": "\U000f03d8", "pick": "\U000f020a", "music": "\U000f075a",
        "dot": "\U000f03e0", "bright": "\U000f00e0", "speed": "\U000f04c5",
        "fx": "\U000f140b",
    }
    add("led", "LED Lights", G["bulb"])
    add("led.on", "On", G["on"], f"{led} on")
    add("led.off", "Off", G["off"], f"{led} off")
    add("led.music", "Music reactive (toggle)", G["music"],
        f"{sc}/led-music-toggle.sh", checked=f"{led} music-status")
    add("led.pick", "Pick a colour…", G["palette"], f"{sc}/led-pick.sh")
    add("led.eyedropper", "Pick from screen…", G["pick"], f"{sc}/led-eyedropper.sh")
    add("led.theme", "Match current theme", G["palette"], f"{sc}/theme-sync.sh")

    add("led.c", "Colours", G["palette"])
    for name, hexv in [("Warm white", "ffb060"), ("Red", "ff0000"),
                       ("Orange", "ff6600"), ("Yellow", "ffd000"),
                       ("Green", "00ff00"), ("Cyan", "00e5ff"),
                       ("Blue", "0040ff"), ("Purple", "8000ff"),
                       ("Pink", "ff2d95")]:
        add(f"led.c.{name.lower().replace(' ', '-')}", name, G["dot"],
            f"{led} color {hexv}")

    add("led.effects", "Effects", G["fx"])
    groups = {"jump": "Jump", "fade": "Fade", "strobe": "Strobe"}
    for gid, gname in groups.items():
        add(f"led.effects.{gid}", gname, G["fx"])
    for name in elk.NAMED_MODES:
        gid, rest = name.split("-", 1)
        if rest in ("3color", "7color"):
            label = rest[0] + " colours"
        else:
            label = " → ".join(p.capitalize() for p in rest.split("-"))
        add(f"led.effects.{gid}.{rest}", label, G["dot"], f"{led} mode {name}")

    add("led.speed", "Effect speed", G["speed"])
    for label, v in [("Slow", 15), ("Medium", 50), ("Fast", 80), ("Max", 100)]:
        add(f"led.speed.{v}", label, G["dot"], f"{led} speed {v}")
    add("led.brightness", "Brightness", G["bright"])
    for v in (10, 25, 50, 75, 100):
        add(f"led.brightness.{v}", f"{v}%", G["dot"], f"{led} bright {v}")

    lines = [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in rows.items()]
    return ",\n".join(lines) + ","


# ---- main ----------------------------------------------------------------

async def run_music(addr, source, verbose):
    import music                        # pulls in numpy: only for this command
    if music_pid():
        print("music is already running", file=sys.stderr)
        return 1
    with open(elk.MUSIC_PID, "w") as f:
        f.write(str(os.getpid()))
    try:
        check(await ledclient.send("on", addr))
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, stop.set)
        async with ledclient.Stream(addr) as st:
            task = asyncio.create_task(music.run(st, source=source, verbose=verbose))
            task.add_done_callback(lambda _: stop.set())   # capture died: exit too
            await stop.wait()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        try:
            os.unlink(elk.MUSIC_PID)
        except OSError:
            pass
    return 0


def check(reply):
    if reply != "ok":
        print(reply or "no reply from daemon", file=sys.stderr)
        sys.exit(1)


async def main():
    ap = argparse.ArgumentParser(prog="led", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--addr", default=None,
                    help="controller BLE address (default: saved by `led setup`)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("setup", "on", "off", "status", "daemon", "stop-daemon",
                 "music-stop", "music-status", "menu-snippet"):
        sub.add_parser(name)
    c = sub.add_parser("color"); c.add_argument("hex")
    b = sub.add_parser("bright"); b.add_argument("pct", type=int)
    sp = sub.add_parser("speed"); sp.add_argument("pct", type=int)
    md = sub.add_parser("mode")
    md.add_argument("effect", help=f"{', '.join(elk.NAMED_MODES)} or an id")
    md.add_argument("--speed", type=int, default=None)
    sm = sub.add_parser("scan-modes")
    sm.add_argument("--from", dest="lo", default="0x87")
    sm.add_argument("--to", dest="hi", default="0x9c")
    sm.add_argument("--hold", type=float, default=3.0)
    m = sub.add_parser("music")
    m.add_argument("--source", default=None, help="PipeWire monitor source")
    m.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    addr = args.addr or elk.load_address()
    cmd = args.cmd

    if cmd == "setup":
        return await setup(addr)
    if cmd == "menu-snippet":
        print(menu_snippet()); return 0
    if cmd == "music-status":
        return 0 if music_pid() else 1
    if cmd == "music-stop":
        return 0 if stop_music() else 1
    if cmd == "music":
        return await run_music(addr, args.source, args.verbose)
    if cmd == "daemon":
        await ledclient.ensure_daemon(addr); print("daemon running"); return 0
    if cmd == "stop-daemon":
        if not await ledclient._ping():
            print("daemon not running")
            return 0
        print(await ledclient.send("quit", addr))
        await ledclient.wait_stopped()      # until it has really let go
        return 0
    if cmd == "status":
        try:
            print((await ledclient.send("status", addr))[3:] or "ok")
        except (OSError, RuntimeError):
            print("daemon not running"); return 1
        return 0

    # Anything that sets colour/mode takes over from the visualiser, which
    # would otherwise keep overwriting it 15 times a second.
    if cmd in ("color", "mode", "off", "speed"):
        stop_music()

    if cmd == "on":
        check(await ledclient.send("on", addr))
    elif cmd == "off":
        check(await ledclient.send("off", addr))
    elif cmd == "color":
        h = args.hex.lstrip("#")
        if len(h) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in h):
            print("colour must be RRGGBB hex, e.g. ff8800", file=sys.stderr)
            return 1
        check(await ledclient.send(f"color {h}", addr))
    elif cmd == "bright":
        check(await ledclient.send(f"bright {args.pct}", addr))
    elif cmd == "speed":
        check(await ledclient.send(f"speed {args.pct}", addr))
    elif cmd == "mode":
        mid = elk.NAMED_MODES.get(args.effect)
        if mid is None:
            try:
                mid = int(args.effect, 0)
            except ValueError:
                print(f"unknown effect {args.effect!r}; see `led mode --help`",
                      file=sys.stderr)
                return 1
        line = f"mode {mid}" + (f" {args.speed}" if args.speed is not None else "")
        check(await ledclient.send(line, addr))
    elif cmd == "scan-modes":
        lo, hi = int(args.lo, 0), int(args.hi, 0)
        print(f"Stepping effect ids 0x{lo:02x}..0x{hi:02x}, {args.hold}s each. "
              "Watch the lights; Ctrl-C to stop.")
        async with ledclient.Stream(addr) as st:
            for mid in range(lo, hi + 1):
                print(f"  id 0x{mid:02x} ({mid})")
                await st.send(f"mode {mid}")
                await asyncio.sleep(args.hold)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()) or 0)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}".rstrip(": "), file=sys.stderr)
        sys.exit(1)
