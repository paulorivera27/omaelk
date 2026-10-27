#!/bin/bash
# Open a colour-picker dialog and send the chosen colour to the LED.
LED="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)/led"

command -v zenity >/dev/null || { notify-send -a "LED lights" "Install zenity for the colour picker"; exit 1; }
sel=$(zenity --color-selection --title="LED colour" 2>/dev/null) || exit 0
if [[ "$sel" == rgb* ]]; then
    read -r r g b _ < <(grep -oE '[0-9]+' <<<"$sel" | head -3 | tr '\n' ' ')
    hex=$(printf '%02x%02x%02x' "$r" "$g" "$b")
else
    hex=$(tr -d '#' <<<"$sel" | cut -c1-6)
fi

[ -n "$hex" ] && exec "$LED" color "$hex"
