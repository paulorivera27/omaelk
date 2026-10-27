"""
Audio-reactive visualiser.

Captures what you are playing (the PipeWire/PulseAudio sink monitor, via
`parec`; nothing is recorded or stored, each frame is analysed and discarded),
runs an FFT, and maps it to colour:

  - spectral centroid -> hue   (bassy = red/orange ... bright = blue/violet)
  - loudness          -> brightness
  - bass transient    -> a short brightness punch on the beat

The controller tops out around 10-20 BLE writes/sec, so colour is pushed at a
fixed rate, smoothed in HSV, and only when it actually changed.
"""

import asyncio
import colorsys
import os

# A 2048-point FFT does not need numpy's BLAS thread pool; left alone it spawns
# one thread per core. Must be set before numpy is imported.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np  # noqa: E402

RATE = 48000           # PipeWire's native rate: no resampling in the capture
CHUNK = 2048            # samples per analysis frame (~43 ms)
PUSH_HZ = 15            # max BLE writes per second
SMOOTH = 0.35           # EMA factor for hue/brightness (lower = smoother)
NOISE_FLOOR = 1e-4

_FREQS = np.fft.rfftfreq(CHUNK, 1.0 / RATE)
_WINDOW = np.hanning(CHUNK).astype(np.float32)
_BASS = (_FREQS >= 20) & (_FREQS < 250)
_MID = (_FREQS >= 250) & (_FREQS < 2000)
_TREBLE = (_FREQS >= 2000) & (_FREQS < 16000)
_LOG_LO, _LOG_HI = np.log2(150.0), np.log2(5000.0)


async def default_monitor():
    """Monitor source of the current default sink."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pactl", "get-default-sink",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await proc.communicate()
        sink = out.decode().strip()
        if sink:
            return sink + ".monitor"
    except OSError:
        pass
    return "@DEFAULT_MONITOR@"


async def run(stream, source=None, verbose=False):
    """Stream colour into `stream` (a connected ledclient.Stream) until
    cancelled or the audio capture ends."""
    source = source or await default_monitor()
    proc = await asyncio.create_subprocess_exec(
        "parec", "--format=s16le", f"--rate={RATE}", "--channels=1",
        "--latency-msec=30", "-d", source,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    if verbose:
        print(f"Capturing from: {source}")
        print("Play some music. Ctrl-C to stop.")

    nbytes = CHUNK * 2
    hue_s = val_s = bass_env = 0.0
    last_rgb = None
    last_push = 0.0
    loop = asyncio.get_running_loop()
    interval = 1.0 / PUSH_HZ

    try:
        while True:
            try:
                raw = await proc.stdout.readexactly(nbytes)
            except asyncio.IncompleteReadError:
                if verbose:
                    print("audio capture ended")
                return
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            mag = np.abs(np.fft.rfft(samples * _WINDOW)) / CHUNK

            bass = mag[_BASS].mean()
            total = bass + mag[_MID].mean() + mag[_TREBLE].mean() + NOISE_FLOOR

            # Hue from where the energy sits, so it moves with the music
            # (a bass-weighted mean would pin near red).
            msum = mag.sum()
            centroid = float((_FREQS * mag).sum() / msum) if msum > 1e-9 else 150.0
            cnorm = (np.log2(max(centroid, 1.0)) - _LOG_LO) / (_LOG_HI - _LOG_LO)
            hue = min(1.0, max(0.0, cnorm)) * 0.78      # red .. violet

            energy = min(1.0, (total * 14.0) ** 0.5)
            bass_env = max(bass, bass_env * 0.90)
            punch = 1.0 if bass > bass_env * 0.98 and bass > 0.02 else 0.0
            value = min(1.0, energy * (1.0 + 0.5 * punch))

            # Smooth in HSV: RGB smoothing greys the colour out.
            hue_s += (hue - hue_s) * SMOOTH
            val_s += (value - val_s) * SMOOTH

            now = loop.time()
            if now - last_push < interval:
                continue
            r, g, b = colorsys.hsv_to_rgb(hue_s % 1.0, 1.0, val_s)
            rgb = (int(r * 255), int(g * 255), int(b * 255))
            if rgb == last_rgb:         # silence or steady tone: nothing to send
                continue
            last_push = now
            last_rgb = rgb
            try:
                await stream.send("color %02x%02x%02x" % rgb)
            except ConnectionError as e:    # daemon gone: nothing left to drive
                if verbose:
                    print("stopped:", e)
                return
            except asyncio.TimeoutError:    # one slow write: skip the frame
                pass
    finally:
        if proc.returncode is None:
            proc.terminate()
        await proc.wait()
