#!/bin/bash
# Toggle the music-reactive visualiser (used by the menu and the bar widget).
LED="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)/led"

if "$LED" music-status; then
    "$LED" music-stop
    notify-send -a "LED lights" "Music mode off" 2>/dev/null
else
    setsid "$LED" music >/dev/null 2>&1 &
    notify-send -a "LED lights" "Music mode on" 2>/dev/null
fi
