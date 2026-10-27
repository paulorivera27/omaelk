<p align="center">
  <img src="assets/icon.svg" width="128" alt="pixel-art light bulb">
</p>

<h1 align="center">ledble</h1>

<p align="center">
  Control cheap <b>ELK-BLEDOB / ELK-BLE</b> Bluetooth LED lights from Linux —<br>
  colours, effects, brightness and a <b>music-reactive mode</b> — from the shell or an<br>
  <a href="https://omarchy.org">Omarchy</a> bar widget with a pixel-art popup.
</p>

These controllers (the little box on a USB-powered RGB strip, advertising as
`ELK-BLEDOB`) are powered over USB but **controlled over Bluetooth LE**, so they
never show up in `lsusb`. `ledble` talks to them directly; no phone app needed.

## Features

- **Bar widget** — a pixel-art bulb that takes its colour from your Omarchy
  theme. Click for a popup with swatches, effects, brightness and speed.
  Right-click toggles music mode, middle-click matches the current theme.
- **22 built-in effects** — jump, fade (single colours and cross-fades), strobe.
- **Music-reactive mode** — follows whatever you are playing. Hue tracks the
  spectrum (bass → red, treble → violet), brightness tracks loudness, with a
  punch on the beat.
- **Colour pickers** — a colour dialog and a screen eyedropper.
- **Theme sync** — match the lights to your Omarchy theme's accent colour,
  on demand or automatically on every theme change.
- **Fast and light** — one background process holds the Bluetooth link; commands
  are instant. See [Performance](#performance).
- **`led` CLI** — scriptable, with a menu generator for the Omarchy launcher.

## Install

### As an Omarchy plugin

```bash
omarchy plugin add https://github.com/paulorivera27/ledble.git --enable
```

Then add **LED Lights** to your bar. The first time you use it, the `led`
wrapper creates a Python virtualenv in `~/.local/share/ledble/venv` and installs
`bleak` and `numpy` (needs `python3` with `venv`, and network access once).

Find your controller and remember its address:

```bash
~/.config/omarchy/plugins/paulorivera27.ledble/led setup
```

### Standalone (CLI only)

```bash
git clone https://github.com/paulorivera27/ledble.git
cd ledble
./led setup                     # finds the controller, saves its address
ln -s "$PWD/led" ~/.local/bin/led   # optional: use it as `led` anywhere
```

### Requirements

| | |
|---|---|
| Linux with BlueZ | Bluetooth LE adapter |
| `python3` + `venv` | everything else is installed for you |
| `pipewire-pulse` / `pulseaudio-utils` | `parec`, for music mode |
| `zenity`, `hyprpicker` | optional: colour dialog / eyedropper |

Tested with an `ELK-BLEDOB` controller on Omarchy (Arch, Hyprland, PipeWire).
Other `ELK-BLE*` controllers that speak the same protocol should work; see
[Compatibility](#compatibility).

## Usage

```bash
led setup                       # discover the controller (once)
led on / led off
led color ff8800                # any RRGGBB hex
led bright 60                   # 0-100
led mode fade-7color            # built-in effect, see below
led mode strobe-red --speed 80
led speed 40                    # effect speed 0 (slow) .. 100 (fast)
led music                       # react to what's playing; Ctrl-C to stop
led music-stop / led music-status
led status                      # daemon + controller state
led scan-modes                  # step through every effect to see them
led menu-snippet                # entries for the Omarchy launcher menu
```

Setting a colour or effect while music mode is running stops music mode, so the
change sticks.

### Effects

| | |
|---|---|
| `jump-3color` `jump-7color` | hard jumps between colours |
| `fade-3color` `fade-7color` | smooth cross-fade |
| `fade-red` `fade-green` `fade-blue` `fade-yellow` `fade-cyan` `fade-magenta` `fade-white` | pulse one colour |
| `fade-red-green` `fade-red-blue` `fade-green-blue` | cross-fade two colours |
| `strobe-7color` `strobe-red` `strobe-green` `strobe-blue` `strobe-yellow` `strobe-cyan` `strobe-magenta` `strobe-white` | strobe |

### Omarchy launcher menu

```bash
led menu-snippet
```

prints JSONC rows (with this checkout's real paths) to paste into
`~/.config/omarchy/extensions/omarchy-menu.jsonc`, giving you an **LED Lights**
submenu with colours, grouped effects, speed and brightness. Bind it to a key in
`~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + L", "LED Lights", "omarchy-menu summon led")
```

### Match the theme automatically

`scripts/theme-sync.sh` pushes the active theme's accent colour to the lights.
To run it on every theme change:

```bash
omarchy hook install theme-set /path/to/ledble/scripts/theme-sync.sh
```

## Music mode and privacy

Music mode listens to the **monitor of your default audio output** (a copy of
what you are already playing) using `parec`. It is not your microphone. Each
~43 ms frame is analysed with an FFT and then discarded: **nothing is recorded,
saved or sent anywhere**. The only thing that ever reaches the light is three
colour bytes. `led music --source NAME` picks a different monitor; list them
with `pactl list short sources | grep monitor`.

## Configuration

| | |
|---|---|
| `led setup` | saves the controller address to `~/.config/ledble/config.json` |
| `LEDBLE_ADDR` | override the controller address |
| `LEDBLE_VENV` | override the virtualenv location |
| `--addr AA:BB:..` | per-command address override |

With no address configured, the daemon scans for the first `ELK-BLE*` device
and remembers it.

## How it works

```
 led CLI / bar widget / menu ──►  Unix socket  ──►  led-daemon  ══ BLE ══►  controller
   (instant, stateless)       $XDG_RUNTIME_DIR     (one connection,
                               /ledble.sock         single instance)
```

Scanning and connecting over BlueZ takes seconds, and a controller that is
already connected stops advertising — so doing it per command made rapid changes
hang or get dropped. Instead a small daemon owns the single connection and every
command is a one-line write to its socket. The daemon:

- starts on demand and is guarded by a lock, so simultaneous clients can never
  spawn two daemons that fight over the link;
- opens its socket before connecting, so a missing controller never makes the
  CLI hang — it fails fast with a clear error and backs off;
- recovers a stuck BlueZ link (`bluetoothctl disconnect`, then rescan) on its own.

### Protocol

GATT service `0xfff0`, write characteristic `0xfff3` (write-without-response).
Commands are 9-byte frames `7E <7 bytes> EF`:

| Action | Frame |
|---|---|
| Power on / off | `7E 07 04 FF 00 01 02 01 EF` / `7E 07 04 00 00 00 02 01 EF` |
| Colour | `7E 07 05 03 RR GG BB 10 EF` |
| Brightness | `7E 04 01 PP 01 FF 02 01 EF` (PP = 0–100) |
| Effect | `7E 07 03 <id> 03 FF FF 00 EF` (id `0x87`–`0x9C`) |
| Effect speed | `7E 07 02 <0–100> FF FF FF 00 EF` |

The controller accepts roughly 10–20 writes per second, which is why music mode
is capped at 15 and only sends when the colour actually changes.

## Performance

Measured on a 16-core machine while music mode was driven by a synthetic
bass-and-sweep track:

| | CPU (of one core) | Memory |
|---|---|---|
| `led music` (capture + FFT + colour) | ~1.4 % | 37 MB |
| daemon, streaming colour | ~0.4 % | 28 MB |
| daemon, idle | 0.00 % | 28 MB, 1 thread |
| a plain `led color …` call | ~67 ms wall | — |

That is about 0.1 % of the whole machine. Nothing polls in the background: the
daemon idles at zero, the CLI does not import NumPy unless you start music mode,
NumPy's thread pool is capped to one thread, and the bar widget only checks
whether music is running while its popup is open or music mode is on.

## Compatibility

Written against `ELK-BLEDOB`. The related `ELK-BLEDOM` family uses a slightly
different frame layout and is **not** covered; see the projects in
[Credits](#credits) for those. If your controller advertises as `ELK-BLE…` and
the colour command does nothing, it is probably a variant — open an issue with
the output of `led setup`.

## Troubleshooting

- **"controller not found"** — is the USB power plugged in and the controller
  nearby? Close the phone app (a connected controller stops advertising).
- **Stuck connection** — `bluetoothctl disconnect <address>`, then retry. The
  daemon also does this on its own after a failed scan.
- **Restart the daemon** — `led stop-daemon` (the next command starts it again).
- **Music mode does nothing** — check `led status`, and that audio is playing on
  the *default* output. `pactl get-default-sink` shows which.

## Development

```
manifest.json  BarWidget.qml  Panel.qml  PixelButton.qml   Omarchy plugin (QML)
assets/icon.svg                                            pixel-art icon
led                                                        wrapper (venv bootstrap)
backend/       elk.py  led-daemon.py  ledclient.py  led.py  music.py
scripts/       theme-sync.sh  led-pick.sh  led-eyedropper.sh  led-music-toggle.sh
tests/         test_protocol.py
```

```bash
python3 -m unittest discover -s tests -v   # protocol + packaging checks
omarchy plugin validate .                  # Omarchy's own plugin validator
```

The icon is a 16×16 bitmap drawn in `BarWidget.qml`; `assets/icon.svg` is the
same grid. The bar draws it in your theme's accent colour.

## Credits

This project stands on other people's reverse-engineering work. Thank you:

- **[8none1/elk-bledob](https://github.com/8none1/elk-bledob)** by **Will Cooke**
  (MIT) — the ELK-BLEDOB protocol this project implements: command frames and
  the full effect table. See [THIRD_PARTY.md](THIRD_PARTY.md).
- **[dave-code-ruiz/elkbledom](https://github.com/dave-code-ruiz/elkbledom)**
  (MIT) — the Home Assistant integration for the wider ELK-BLE* family; a
  reference for device discovery and how these controllers behave.
- **[FergusInLondon/ELK-BLEDOM](https://github.com/FergusInLondon/ELK-BLEDOM)**
  — protocol documentation for the ELK-BLEDOM controllers, used to understand the
  frame layout. (No code from it is used.)
- **[bleak](https://github.com/hbldh/bleak)** by Henrik Blidh — Bluetooth LE for
  Python.
- **[NumPy](https://numpy.org)** — the FFT behind music mode.
- **[Omarchy](https://omarchy.org)** by DHH — the desktop this plugin is built
  for — and **[Quickshell](https://quickshell.org)**, which powers its shell.
- **BlueZ**, **PipeWire**, **zenity** and **hyprpicker**.

## License

[MIT](LICENSE) © 2026 Paulo Rivera. Third-party notices are in
[THIRD_PARTY.md](THIRD_PARTY.md).
