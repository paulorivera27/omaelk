# Changelog

## 0.3.0

- **Power state is real.** The daemon remembers the lights' last-commanded power
  and `omaelk status` reports it (`connected on` / `connected off` /
  `connected unknown`). The bar bulb and the ON/OFF buttons follow it, so changes
  made from the CLI or the menu show up, and a restarted shell no longer assumes
  "on". Brightness and speed don't change the reported power.
- **Music icon is real.** Clicking music no longer guesses the outcome: the
  widget waits for the music process to actually start or stop (button reads
  "Starting…" / "Stopping…"). A stale pidfile with a recycled PID can't pin it on.
- `omaelk status` never starts the daemon.
- Setting a colour or turning the lights off waits for the music process to exit
  first, so a last visualiser frame can't overwrite it.
- **Slow connects:** the daemon waits up to 25 s for the controller to connect
  (was 10 s), and clients wait up to 90 s for a reply. Controllers that took
  ~12 s to connect made every command time out.
- Brightness and speed sliders stay where you set them (they used to snap back
  on release).
- Opening the popup starts the daemon connecting, so the first click doesn't
  wait for a cold Bluetooth connect.
- In music mode three pixel-art music notes come off the bulb (they replace the
  rays and pulse), instead of the rays blinking.
- The bar checks every 4 s whether music mode is running (a one-line shell
  command), so starting or stopping it from the menu or the CLI shows on the icon
  even with the popup closed.
- Tooltip shows lights on/off once known.
- README: any Bluetooth LE adapter that can reach the controller works; notes on
  multiple adapters, what the widget shows and its known limitations; popup,
  music-mode and bar screenshots.
