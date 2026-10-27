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
  property string activeColor: ""
  property string activeEffect: ""

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

  function setPower(on) {
    run([on ? "on" : "off"])
    if (hostWidget) hostWidget.lit = on
  }

  function setColor(hex) {
    activeColor = hex
    activeEffect = ""
    musicOn = false          // a manual colour takes over from the visualiser
    run(["color", hex])
    if (hostWidget) hostWidget.lit = true
  }

  function setEffect(name) {
    activeEffect = name
    activeColor = ""
    musicOn = false
    run(["mode", name])
    if (hostWidget) hostWidget.lit = true
  }

  function toggleMusic() {
    musicOn = !musicOn
    Quickshell.execDetached([root.scripts + "/music-toggle.sh"])
    recheck.restart()
  }

  function refresh() { statusProc.running = true }

  // Music runs as its own process (menu, CLI or this panel can start it), so
  // ask the system rather than trusting our last click. A kill -0 on the
  // pidfile's PID is far cheaper than starting the CLI.
  Process {
    id: statusProc
    command: ["sh", "-c",
      "kill -0 \"$(cat \"${XDG_RUNTIME_DIR:-/tmp}/omaelk-music.pid\" 2>/dev/null)\" 2>/dev/null"]
    onExited: function(exitCode) { root.musicOn = exitCode === 0 }
  }

  Timer {
    id: recheck
    interval: 1800
    onTriggered: root.refresh()
  }

  // Poll only while it can matter: the popup is open, or music is on (to notice
  // it being stopped from the CLI or the menu). Otherwise nothing runs.
  Timer {
    interval: 4000
    repeat: true
    running: root.opened || root.musicOn
    onTriggered: root.refresh()
  }

  onOpenedChanged: if (opened) refresh()
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
            text: root.musicOn ? "♪ Reacting to audio — click to stop" : "♪ React to what's playing"
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
            value: 100
            onReleased: function(v) { root.run(["bright", String(Math.round(v))]) }
          }

          PanelSectionHeader { text: "EFFECT SPEED" }

          PanelSlider {
            width: parent.width
            bar: root.bar
            minimum: 0
            maximum: 100
            step: 5
            integer: true
            value: 50
            onReleased: function(v) { root.run(["speed", String(Math.round(v))]) }
          }
        }
      }
    }
  }
}
