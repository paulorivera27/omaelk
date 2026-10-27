#!/bin/bash
# Pick a colour from anywhere on screen and send it to the LED.
LED="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)/omaelk"

command -v hyprpicker >/dev/null || { notify-send -a "OmaElk" "Install hyprpicker for the eyedropper"; exit 1; }
hex=$(hyprpicker -f hex -n 2>/dev/null) || exit 0
hex=${hex#\#}
[ -n "$hex" ] && exec "$LED" color "${hex:0:6}"
