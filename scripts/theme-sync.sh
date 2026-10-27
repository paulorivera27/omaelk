#!/bin/bash
# Push the active omarchy theme's accent colour to the LED.
#
# Run it by hand, from the menu ("Match current theme"), or install it as a
# theme-set hook so it runs on every theme change:
#   omarchy hook install theme-set ~/.config/omarchy/plugins/paulorivera27.omaelk/scripts/theme-sync.sh
#
# `omarchy hook install` COPIES this file into ~/.config/omarchy/hooks/, so it
# cannot assume it sits inside the plugin. Find omaelk in this order:
#   1. $OMAELK_HOME        explicit override
#   2. next to this script (running in place, e.g. from the menu)
#   3. the standard plugin install location (running as an installed hook)
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
OMAELK=""
for dir in "${OMAELK_HOME:-}" "$HERE/.." "$HOME/.config/omarchy/plugins/paulorivera27.omaelk"; do
    if [ -n "$dir" ] && [ -x "$dir/omaelk" ]; then
        OMAELK="$(cd "$dir" && pwd)/omaelk"
        break
    fi
done
[ -n "$OMAELK" ] || exit 0

COLORS="$HOME/.local/state/omarchy/current/theme/colors.toml"
[ -r "$COLORS" ] || exit 0

# First `accent = "#RRGGBB"` line -> bare 6-hex-digit colour.
HEX=$(grep -E '^[[:space:]]*accent' "$COLORS" | head -1 | grep -oiE '[0-9a-f]{6}' | head -1)
[ -n "$HEX" ] || exit 0

# Detached and time-capped so a theme switch never waits on Bluetooth.
setsid timeout 35 "$OMAELK" color "$HEX" >/dev/null 2>&1 &
exit 0
