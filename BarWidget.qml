import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// LED Lights: a pixel-art bulb in the bar and the host for the control popup.
//
// Left click opens the popup, right click toggles music-reactive mode, middle
// click matches the lights to the current theme.
BarWidget {
  id: root
  moduleName: "paulorivera27.ledble"

  // Whether the lights are believed to be on. The popup flips this when you
  // press ON/OFF; the icon dims when they are off.
  property bool lit: true
  readonly property bool musicOn: panelLoader.item ? panelLoader.item.musicOn === true : false

  // ---- Popup shape contract for shell.summon/hide/toggle routing:
  //      Bar.findPanelWidget requires open/close/opened on the root.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function togglePanel() { if (panelLoader.item) panelLoader.item.toggle() }

  readonly property real openPanelIndicatorWidth: icon.width
  readonly property real openPanelIndicatorHeight: icon.height
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  IpcHandler {
    target: "paulorivera27.ledble"

    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    labelVisible: false
    hasVisualContent: true
    tooltipText: root.musicOn ? "LED lights — music mode" : "LED lights"
    fixedWidth: root.vertical ? -1 : icon.width + Style.space(16)
    dimmed: !root.lit

    onPressed: function(b) {
      if (b === Qt.RightButton) {
        if (panelLoader.item) panelLoader.item.toggleMusic()
      } else if (b === Qt.MiddleButton) {
        Quickshell.execDetached([root.pluginScript("theme-sync.sh")])
      } else {
        root.togglePanel()
      }
    }

    // ---- The bulb. 16x16 pixel art, drawn rect by rect so it stays hard-edged
    //      at any integer scale and takes its colours from the live theme.
    //   #  body (theme accent)     +  highlight      =  screw base
    //   *  rays (accent; blink in music mode)
    Canvas {
      id: icon
      anchors.centerIn: parent

      readonly property var grid: [
        ".......**.......",
        ".....######.....",
        ".*.##########.*.",
        "..###+########..",
        "..##+#########..",
        "..############..",
        "*.############.*",
        "..############..",
        "...##########...",
        "..*.########.*..",
        ".....######.....",
        "......####......",
        "......====......",
        ".....======.....",
        "......====......",
        "................"
      ]

      // Whole-pixel scale: the largest that fits the bar slot, at least 1.
      readonly property int px: Math.max(1, Math.floor((root.barSize - Style.space(8)) / 16))
      readonly property color body: Commons.Color.accent
      readonly property color base: button.foreground
      property bool rayPhase: true

      width: 16 * px
      height: 16 * px
      renderTarget: Canvas.Image
      antialiasing: false

      onPxChanged: requestPaint()
      onBodyChanged: requestPaint()
      onBaseChanged: requestPaint()
      onRayPhaseChanged: requestPaint()
      Component.onCompleted: requestPaint()

      onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        for (var y = 0; y < 16; y++) {
          var row = grid[y]
          for (var x = 0; x < 16; x++) {
            var c = row.charAt(x)
            if (c === ".") continue
            if (c === "#") ctx.fillStyle = Qt.rgba(body.r, body.g, body.b, 1)
            else if (c === "+") ctx.fillStyle = Qt.rgba(Math.min(1, body.r + 0.35), Math.min(1, body.g + 0.35), Math.min(1, body.b + 0.35), 1)
            else if (c === "=") ctx.fillStyle = Qt.rgba(base.r, base.g, base.b, 0.6)
            else if (c === "*") {
              // Rays only while the lights are on; in music mode they blink.
              if (!root.lit || (root.musicOn && !rayPhase)) continue
              ctx.fillStyle = Qt.rgba(body.r, body.g, body.b, 0.85)
            }
            ctx.fillRect(x * px, y * px, px, px)
          }
        }
      }

      Connections {
        target: root
        function onLitChanged() { icon.requestPaint() }
        function onMusicOnChanged() { icon.requestPaint() }
      }

      Timer {
        interval: 420
        repeat: true
        running: root.musicOn
        onTriggered: icon.rayPhase = !icon.rayPhase
      }
    }
  }

  // Path of a script shipped next to this file.
  function pluginScript(name) {
    var dir = decodeURIComponent(String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "")).replace(/\/$/, "")
    return dir + "/scripts/" + name
  }
}
