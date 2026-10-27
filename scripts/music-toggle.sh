#!/bin/bash
# Toggle the music-reactive visualiser (used by the menu and the bar widget).
OMAELK="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)/omaelk"
LOG="${XDG_RUNTIME_DIR:-/tmp}/omaelk-music.log"

if "$OMAELK" music-status; then
    "$OMAELK" music-stop
    notify-send -a "OmaElk" "Music mode off" 2>/dev/null
else
    # Keep the output: a visualiser that fails to start would otherwise do so
    # silently, which is exactly the kind of thing that is hard to diagnose.
    setsid "$OMAELK" music -v >"$LOG" 2>&1 &
    notify-send -a "OmaElk" "Music mode on" 2>/dev/null
fi
