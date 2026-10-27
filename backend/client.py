"""
Client side: send commands to the LED daemon over its Unix socket, starting the
daemon on demand. The per-command path is a local socket write, so colour and
mode changes are instant and never collide.
"""

import asyncio
import os
import subprocess
import sys

import elk

HERE = os.path.dirname(os.path.realpath(__file__))
_VENV_PY = os.path.join(elk.VENV, "bin", "python")
PY = _VENV_PY if os.path.exists(_VENV_PY) else sys.executable

REPLY_TIMEOUT = 30.0    # covers a cold connect inside the daemon


async def _ping():
    try:
        r, w = await asyncio.open_unix_connection(elk.SOCK)
    except OSError:
        return False
    try:
        w.write(b"ping\n")
        await w.drain()
        line = await asyncio.wait_for(r.readline(), 5)
        return line.strip() == b"ok"
    except (OSError, asyncio.TimeoutError):
        return False
    finally:
        w.close()


async def ensure_daemon(addr=None, timeout=10.0):
    """Start the daemon if it is not answering. Safe to call concurrently: a
    second daemon exits on the single-instance lock, and every caller then
    waits for the one socket."""
    if await _ping():
        return
    cmd = [PY, os.path.join(HERE, "daemon.py")]
    if addr:
        cmd.append(addr)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    next_spawn = 0.0
    while loop.time() < deadline:
        # (Re)spawn while nothing answers: a daemon that was still shutting
        # down holds the lock, and the one we just started then exits at once.
        if loop.time() >= next_spawn:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            next_spawn = loop.time() + 2.0
        await asyncio.sleep(0.2)
        if await _ping():
            return
    raise RuntimeError("LED daemon did not start")


async def wait_stopped(timeout=10.0):
    """Block until a quitting daemon has released the single-instance lock."""
    import fcntl
    fd = os.open(elk.LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                await asyncio.sleep(0.2)
        return False
    finally:
        os.close(fd)        # closing also drops our lock


async def send(line, addr=None):
    """Send one command, return the daemon's reply string."""
    await ensure_daemon(addr)
    r, w = await asyncio.open_unix_connection(elk.SOCK)
    try:
        w.write((line.strip() + "\n").encode())
        await w.drain()
        reply = await asyncio.wait_for(r.readline(), REPLY_TIMEOUT)
    finally:
        w.close()
    return reply.decode().strip()


class Stream:
    """A held-open connection for streaming many commands (music / scan)."""

    def __init__(self, addr=None):
        self.addr = addr
        self.r = self.w = None

    async def __aenter__(self):
        await ensure_daemon(self.addr)
        self.r, self.w = await asyncio.open_unix_connection(elk.SOCK)
        return self

    async def send(self, line):
        self.w.write((line.strip() + "\n").encode())
        await self.w.drain()
        # Consuming the reply paces us to the BLE write and keeps the socket
        # from backing up. EOF means the daemon went away.
        if not await asyncio.wait_for(self.r.readline(), 5):
            raise ConnectionError("LED daemon closed the connection")

    async def __aexit__(self, *exc):
        self.w.close()
