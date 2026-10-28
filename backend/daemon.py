#!/usr/bin/env python3
"""
Persistent BLE daemon for ELK-BLE* controllers.

Holds ONE connection to the controller and executes commands received over a
Unix socket, so every colour/mode change is a write on an already-open link
instead of a scan+connect. The daemon is the sole owner of the link, enforced
by an exclusive lock: a second instance exits immediately, so two clients that
start at the same moment can never leave an orphaned daemon holding the BLE
connection.

Socket: $XDG_RUNTIME_DIR/omaelk.sock (newline-delimited text, one reply line
per command: "ok", "ok <detail>" or "err <reason>").
Commands: ping | status | on | off | color RRGGBB | bright N |
          mode ID [SPEED] | speed N | quit
`status` replies "ok connected|disconnected on|off|unknown": the link state, then
the power the lights were last commanded to (the controller can't be asked).
A client may stream many command lines on one connection (music mode).
"""

import asyncio
import fcntl
import os
import sys
import time

from bleak import BleakClient, BleakScanner

import elk

SCAN_TIMEOUT = 6.0
CONNECT_TIMEOUT = 25.0
RETRY_BACKOFF = 5.0     # after a failed connect, fail fast for this long


class Controller:
    def __init__(self, addr):
        self.addr = addr
        self.client = None
        self.lock = asyncio.Lock()
        self.retry_after = 0.0
        # Last commanded power: None until the first command. The controller has
        # no readable power state, so this is the only truth there is; it
        # survives a dropped link because the command still describes intent.
        self.power = None

    @property
    def connected(self):
        return self.client is not None and self.client.is_connected

    async def _find(self):
        """Resolve the BLE device. BlueZ must discover a device by scanning
        before it can connect, so a direct connect-by-address is not possible."""
        if self.addr:
            return await BleakScanner.find_device_by_address(
                self.addr, timeout=SCAN_TIMEOUT)
        dev = await BleakScanner.find_device_by_filter(
            lambda d, _: bool(d.name) and d.name.startswith(elk.NAME_PREFIX),
            timeout=SCAN_TIMEOUT)
        if dev is not None:
            self.addr = dev.address
            elk.save_address(dev.address)   # remembered for next time
        return dev

    async def _release_stale_link(self):
        # A controller that BlueZ still believes is connected stops
        # advertising, so the scan can't see it. Dropping that link brings it
        # back. Async so the event loop (and other clients) keep running.
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "disconnect", self.addr,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        await asyncio.sleep(2)

    async def _connect(self):
        dev = await self._find()
        if dev is None and self.addr:
            await self._release_stale_link()
            dev = await self._find()
        if dev is None:
            raise RuntimeError("controller not found (powered and in range?)")
        client = BleakClient(dev, timeout=CONNECT_TIMEOUT)
        await client.connect()
        self.client = client

    async def _drop(self):
        client, self.client = self.client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def _ensure(self):
        if self.connected:
            return
        wait = self.retry_after - time.monotonic()
        if wait > 0:
            raise RuntimeError(f"controller unavailable, retrying in {wait:.0f}s")
        try:
            await self._connect()
        except Exception:
            self.retry_after = time.monotonic() + RETRY_BACKOFF
            raise

    async def write(self, data):
        async with self.lock:
            await self._ensure()        # raises with the real cause if it can't connect
            try:
                await self.client.write_gatt_char(elk.WRITE_UUID, data, response=False)
            except Exception:
                # The established link dropped under us: one reconnect + retry.
                await self._drop()
                await self._ensure()
                await self.client.write_gatt_char(elk.WRITE_UUID, data, response=False)

    async def warm_up(self):
        """Connect in the background so the first command is fast."""
        async with self.lock:
            try:
                await self._ensure()
            except Exception as e:
                print("daemon: initial connect failed:", e, file=sys.stderr, flush=True)


def _hex(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError("colour must be RRGGBB")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


async def dispatch(ctl, parts):
    c = parts[0].lower()
    if c == "ping":
        return "ok"
    if c == "status":
        link = "connected" if ctl.connected else "disconnected"
        power = "unknown" if ctl.power is None else ("on" if ctl.power else "off")
        return f"ok {link} {power}"
    # Power is recorded only after the write succeeded, so a failed command
    # never changes what status reports. Colour and mode light the strip, so
    # they imply "on"; brightness and speed only set a parameter and leave an
    # "off" strip dark, so they say nothing about power.
    if c == "on":
        await ctl.write(elk.cmd_power(True)); ctl.power = True; return "ok"
    if c == "off":
        await ctl.write(elk.cmd_power(False)); ctl.power = False; return "ok"
    if c == "color":
        await ctl.write(elk.cmd_color(*_hex(parts[1]))); ctl.power = True; return "ok"
    if c == "bright":
        await ctl.write(elk.cmd_brightness(int(parts[1]))); return "ok"
    if c == "mode":
        await ctl.write(elk.cmd_mode(int(parts[1], 0)))
        ctl.power = True
        if len(parts) > 2:
            await ctl.write(elk.cmd_speed(int(parts[2])))
        return "ok"
    if c == "speed":
        await ctl.write(elk.cmd_speed(int(parts[1]))); return "ok"
    if c == "quit":
        raise SystemExit
    return "err unknown command"


async def handle(reader, writer, ctl, stop):
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            parts = line.decode(errors="ignore").split()
            if not parts:
                continue
            quitting = False
            try:
                resp = await dispatch(ctl, parts)
            except SystemExit:
                resp, quitting = "ok", True
            except Exception as e:
                resp = f"err {type(e).__name__}: {e}".rstrip(": ")
            writer.write((resp + "\n").encode())
            await writer.drain()
            if quitting:
                stop.set()
                break
    except ConnectionError:
        pass
    finally:
        writer.close()


async def main():
    addr = sys.argv[1] if len(sys.argv) > 1 else elk.load_address()
    ctl = Controller(addr)
    stop = asyncio.Event()

    # Socket first, connect after: `ping` answers at once and a slow or absent
    # controller never delays the daemon coming up.
    if os.path.exists(elk.SOCK):
        os.unlink(elk.SOCK)
    server = await asyncio.start_unix_server(
        lambda r, w: handle(r, w, ctl, stop), path=elk.SOCK)
    os.chmod(elk.SOCK, 0o600)
    print(f"daemon: listening on {elk.SOCK}", flush=True)
    warm = asyncio.create_task(ctl.warm_up())

    async with server:
        await stop.wait()
    warm.cancel()
    if os.path.exists(elk.SOCK):
        os.unlink(elk.SOCK)
    await ctl._drop()


if __name__ == "__main__":
    # Single instance: the lock is held for the life of the process.
    lock_fd = os.open(elk.LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)     # another daemon already owns the controller
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
