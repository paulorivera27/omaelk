#!/bin/bash
# Push the active omarchy theme's accent colour to the LED.
#
# Run it by hand, from the menu ("Match current theme"), or install it as a
# theme-set hook so it runs on every theme change:
#   omarchy hook install theme-set /path/to/omaelk/scripts/theme-sync.sh
LED="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)/omaelk"
COLORS="$HOME/.local/state/omarchy/current/theme/colors.toml"

[ -r "$COLORS" ] || exit 0

# First `accent = "#RRGGBB"` line -> bare 6-hex-digit colour.
HEX=$(grep -E '^[[:space:]]*accent' "$COLORS" | head -1 | grep -oiE '[0-9a-f]{6}' | head -1)
[ -n "$HEX" ] || exit 0

# Detached and time-capped so a theme switch never waits on Bluetooth.
setsid timeout 35 "$LED" color "$HEX" >/dev/null 2>&1 &
exit 0
