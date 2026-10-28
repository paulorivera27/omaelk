import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// The OmaElk popup: colour swatches and pickers, built-in effects,
// brightness and speed, and the music-reactive toggle.
//
// Everything here shells out to the plugin's own `omaelk` CLI. BarWidget.qml owns
// the bar icon and hands this panel the button to anchor against.
Panel {
  id: root
  moduleName: "paulorivera27.omaelk"
  ipcTarget: "paulorivera27.omaelk"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  // Paths are resolved from this file, so the plugin works wherever it is
  // installed.
  readonly property string pluginDir: decodeURIComponent(
    String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
  readonly property string led: pluginDir + "/omaelk"
  readonly property string scripts: pluginDir + "/scripts"

  property bool lit: hostWidget ? hostWidget.lit : true
  property bool musicOn: false
  // Last colour / effect picked *in this popup*. Not read back from the lights
  // (only power and music have a source of truth), so one set from the menu or
  // CLI isn't highlighted; the sliders likewise only send, they don't report.
  property string activeColor: ""
  property string activeEffect: ""

  // Slider positions. PanelSlider snaps back to its `value` binding on release,
  // so they must be stored here or they would jump back every time. They live
  // as long as the shell does and start at the controller's defaults.
  property int brightness: 100
  property int effectSpeed: 50

  // Music start/stop in flight: the state we are waiting for the pidfile to
  // show, and how many polls are left before giving up and showing the truth.
  property bool musicTarget: false
  property int settleTicks: 0

  // Same for power: the state we expect the daemon to report once the command
  // we just sent has gone through (a cold Bluetooth connect can take a while).
  property bool powerTarget: true
  property int powerTicks: 0

  readonly property var swatches: [
    { name: "Warm white", hex: "ffb060" }, { name: "Red", hex: "ff0000" },
    { name: "Orange", hex: "ff6600" },     { name: "Yellow", hex: "ffd000" },
    { name: "Green", hex: "00ff00" },      { name: "Cyan", hex: "00e5ff" },
    { name: "Blue", hex: "0040ff" },       { name: "Purple", hex: "8000ff" },
    { name: "Pink", hex: "ff2d95" }
  ]

  // Effect ids are the names `led mode` understands.
  readonly property var effectGroups: [
    { title: "JUMP", items: [
      { l: "3 colours", n: "jump-3color" }, { l: "7 colours", n: "jump-7color" } ] },
    { title: "FADE", items: [
      { l: "3 colours", n: "fade-3color" }, { l: "7 colours", n: "fade-7color" },
      { l: "Red", n: "fade-red" }, { l: "Green", n: "fade-green" },
      { l: "Blue", n: "fade-blue" }, { l: "Yellow", n: "fade-yellow" },
      { l: "Cyan", n: "fade-cyan" }, { l: "Magenta", n: "fade-magenta" },
      { l: "White", n: "fade-white" }, { l: "R→G", n: "fade-red-green" },
      { l: "R→B", n: "fade-red-blue" }, { l: "G→B", n: "fade-green-blue" } ] },
    { title: "STROBE", items: [
      { l: "7 colours", n: "strobe-7color" }, { l: "Red", n: "strobe-red" },
      { l: "Green", n: "strobe-green" }, { l: "Blue", n: "strobe-blue" },
      { l: "Yellow", n: "strobe-yellow" }, { l: "Cyan", n: "strobe-cyan" },
      { l: "Magenta", n: "strobe-magenta" }, { l: "White", n: "strobe-white" } ] }
  ]

  function run(args) { Quickshell.execDetached([root.led].concat(args)) }

  // Power and music both show optimistically for instant feedback and are then
  // corrected by a probe (see below), so the icon can't stay wrong.
  function setPower(on) {
    run([on ? "on" : "off"])
    if (!on) musicStopping()      // `omaelk off` ends the visualiser too
    setLit(on)
  }

  function setColor(hex) {
    activeColor = hex
    activeEffect = ""
    musicStopping()               // a manual colour takes over from the visualiser
    run(["color", hex])
    setLit(true)
  }

  function setEffect(name) {
    activeEffect = name
    activeColor = ""
    musicStopping()
    run(["mode", name])
    setLit(true)
  }

  // The CLI stops music on colour/mode/off. Show that now, then let the probe
  // confirm once the process has actually gone.
  function musicStopping() {
    if (!musicOn) return
    musicOn = false
    startSettle(false)
  }

  function setLit(on) {
    applyLit(on)
    powerTarget = on
    powerTicks = 30               // x 1.5 s: gives up after 45 s and shows the truth
    powerSettle.restart()
  }

  function applyLit(on) {
    if (!hostWidget) return
    hostWidget.lit = on
    hostWidget.litKnown = true
  }

  // The toggle script starts music detached, and the pidfile only appears once
  // the CLI has spawned (and, on first run, built its virtualenv), so a click
  // can't know the outcome. Don't guess: leave the icon alone, run the toggle,
  // and poll the pidfile until it shows the state we asked for.
  function toggleMusic() {
    if (settle.running) return    // the toggle script flips whatever is there now;
                                  // the button reads "Starting…"/"Stopping…" meanwhile
    Quickshell.execDetached([root.scripts + "/music-toggle.sh"])
    startSettle(!musicOn)
  }

  function startSettle(target) {
    musicTarget = target
    settleTicks = 20              // x 400 ms: gives up after 8 s and shows the truth
    settle.restart()
  }

  function refreshMusic() { statusProc.running = true }
  function refreshPower() { powerProc.running = true }
  function refresh() { refreshMusic(); refreshPower() }

  // Music runs as its own process (menu, CLI or this panel can start it), so
  // ask the system rather than trusting our last click. This is the only thing
  // that sets musicOn from reality. Same check as the CLI's music_pid() (the
  // PID is alive and is `.../backend/cli.py music`, not a recycled PID), but
  // without starting Python.
  Process {
    id: statusProc
    command: ["sh", "-c",
      "pid=$(cat \"${XDG_RUNTIME_DIR:-/tmp}/omaelk-music.pid\" 2>/dev/null) && " +
      "tr '\\0' ' ' < \"/proc/$pid/cmdline\" 2>/dev/null | grep -q '/backend/cli.py music'"]
    onExited: function(exitCode) {
      var alive = exitCode === 0
      // We just asked for it to stop and it hasn't exited yet: don't flash back
      // to "playing" or wipe the colour that was just picked. If it never goes
      // away, the settle timeout lets the truth through.
      if (alive && settle.running && !root.musicTarget) return
      root.musicOn = alive
      if (alive) {
        // The visualiser owns the colour now, so a highlighted swatch or
        // effect would be a lie, and the lights are evidently on.
        root.activeColor = ""
        root.activeEffect = ""
        root.applyLit(true)
      }
      if (settle.running && alive === root.musicTarget) settle.stop()
    }
  }

  // The lights' power can't be read from the controller, so the daemon keeps
  // the last commanded state ("connected on"). "unknown" (fresh daemon) and a
  // missing daemon leave the icon as it is rather than guessing "off".
  Process {
    id: powerProc
    command: [root.led, "status"]
    stdout: StdioCollector {
      onStreamFinished: {
        var power = text.trim().split(/\s+/)[1]
        if (power !== "on" && power !== "off") return
        var on = power === "on"
        if (powerSettle.running) {
          // A command is still in flight: the daemon only reports it once the
          // write succeeds, so the old value isn't news. Wait for ours.
          if (on !== root.powerTarget) return
          powerSettle.stop()
        }
        root.applyLit(on)
      }
    }
  }

  // Bounded wait for the daemon to report the power we just commanded.
  Timer {
    id: powerSettle
    interval: 1500
    repeat: true
    onTriggered: {
      if (--root.powerTicks <= 0) stop()
      root.refreshPower()       // after the last tick this is plain truth
    }
  }

  // Bounded convergence after a music toggle.
  Timer {
    id: settle
    interval: 400
    repeat: true
    onTriggered: {
      if (--root.settleTicks <= 0) stop()
      root.refreshMusic()
    }
  }

  // Poll only while it can matter: the popup is open, or music is on (to notice
  // it being stopped from the CLI or the menu). Otherwise nothing runs. Power is
  // only probed with the popup open (music implies on, and the probe starts the
  // CLI); the music check is a one-line shell command.
  Timer {
    interval: 4000
    repeat: true
    running: root.opened || root.musicOn
    onTriggered: {
      root.refreshMusic()
      if (root.opened) root.refreshPower()
    }
  }

  // Opening the popup is the cue that a command is coming: have the daemon
  // connect now (a cold Bluetooth connect can take ~10 s) rather than on the
  // first click. A no-op if it is already running.
  onOpenedChanged: if (opened) { run(["daemon"]); refresh() }
  Component.onCompleted: refresh()

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(340))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: column
          width: scroll.width
          spacing: Style.space(8)

          // ---- Title + power
          Item {
            width: parent.width
            height: Style.space(30)

            Text {
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: "OMAELK"
              textFormat: Text.PlainText
              color: Commons.Color.accent
              font.family: Style.font.family
              font.pixelSize: Style.font.subtitle
              font.bold: true
              font.letterSpacing: 2
            }

            Row {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(6)

              PixelButton {
                text: "ON"
                active: root.lit
                onClicked: root.setPower(true)
              }
              PixelButton {
                text: "OFF"
                active: !root.lit
                tint: Commons.Color.urgent
                onClicked: root.setPower(false)
              }
            }
          }

          PanelSeparator {}

          // ---- Colour
          PanelSectionHeader { text: "COLOUR" }

          Flow {
            width: parent.width
            spacing: Style.space(6)

            Repeater {
              model: root.swatches
              PixelButton {
                required property var modelData
                swatch: true
                tint: "#" + modelData.hex
                active: root.activeColor === modelData.hex
                onClicked: root.setColor(modelData.hex)
              }
            }
          }

          Flow {
            width: parent.width
            spacing: Style.space(6)

            PixelButton {
              text: "Pick…"
              onClicked: Quickshell.execDetached([root.scripts + "/pick-color.sh"])
            }
            PixelButton {
              text: "From screen"
              onClicked: Quickshell.execDetached([root.scripts + "/eyedropper.sh"])
            }
            PixelButton {
              text: "Match theme"
              onClicked: Quickshell.execDetached([root.scripts + "/theme-sync.sh"])
            }
          }

          PanelSeparator {}

          // ---- Music
          PanelSectionHeader { text: "MUSIC" }

          PixelButton {
            text: settle.running ? (root.musicTarget ? "♪ Starting…" : "♪ Stopping…")
                  : root.musicOn ? "♪ Reacting to audio — click to stop" : "♪ React to what's playing"
            active: root.musicOn
            onClicked: root.toggleMusic()
          }

          PanelSeparator {}

          // ---- Effects
          Repeater {
            model: root.effectGroups

            Column {
              required property var modelData
              width: column.width
              spacing: Style.space(6)

              PanelSectionHeader { text: modelData.title }

              Flow {
                width: parent.width
                spacing: Style.space(6)

                Repeater {
                  model: modelData.items
                  PixelButton {
                    required property var modelData
                    text: modelData.l
                    active: root.activeEffect === modelData.n
                    onClicked: root.setEffect(modelData.n)
                  }
                }
              }
            }
          }

          PanelSeparator {}

          // ---- Brightness / speed
          PanelSectionHeader { text: "BRIGHTNESS" }

          PanelSlider {
            width: parent.width
            bar: root.bar
            minimum: 0
            maximum: 100
            step: 5
            integer: true
            value: root.brightness
            onReleased: function(v) {
              root.brightness = Math.round(v)
              root.run(["bright", String(root.brightness)])
            }
          }

          PanelSectionHeader { text: "EFFECT SPEED" }

          PanelSlider {
            width: parent.width
            bar: root.bar
            minimum: 0
            maximum: 100
            step: 5
            integer: true
            value: root.effectSpeed
            onReleased: function(v) {
              root.effectSpeed = Math.round(v)
              root.run(["speed", String(root.effectSpeed)])
            }
          }
        }
      }
    }
  }
}
