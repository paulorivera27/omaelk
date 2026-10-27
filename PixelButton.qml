import QtQuick
import qs.Commons
import qs.Commons as Commons

// Chunky pixel-art button: hard square edges, a 2px offset drop shadow, and a
// press that shoves the face down into the shadow. As a swatch it is a solid
// block of colour; otherwise a labelled chip that lights up in `tint` when
// `active`.
Item {
  id: root

  property string text: ""
  property color tint: Commons.Color.accent
  property color foreground: Commons.Color.foreground
  property bool active: false
  property bool swatch: false
  property string fontFamily: Style.font.family
  property real fontSize: Style.font.caption

  signal clicked()

  readonly property int edge: 2
  readonly property bool hot: mouse.containsMouse

  implicitWidth: swatch ? Style.space(26) : label.implicitWidth + Style.space(16)
  implicitHeight: swatch ? Style.space(26) : label.implicitHeight + Style.space(10)

  Rectangle {
    x: root.edge
    y: root.edge
    width: face.width
    height: face.height
    color: Qt.rgba(0, 0, 0, 0.45)
    visible: !mouse.pressed
  }

  Rectangle {
    id: face
    x: mouse.pressed ? root.edge : 0
    y: mouse.pressed ? root.edge : 0
    width: root.width - root.edge
    height: root.height - root.edge
    radius: 0
    border.width: 2
    border.color: root.active || root.hot
      ? (root.swatch ? root.foreground : root.tint)
      : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.35)
    color: root.swatch
      ? root.tint
      : (root.active
          ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.30)
          : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, root.hot ? 0.14 : 0.06))

    // One-pixel highlight along the top-left edge: the bevel that makes a
    // flat block read as a pixel-art button.
    Rectangle {
      visible: root.swatch
      x: 2
      y: 2
      width: parent.width - 4
      height: 2
      color: Qt.rgba(1, 1, 1, 0.35)
    }

    Text {
      id: label
      visible: !root.swatch
      anchors.centerIn: parent
      text: root.text
      textFormat: Text.PlainText
      color: root.active ? root.tint : root.foreground
      font.family: root.fontFamily
      font.pixelSize: root.fontSize
      font.bold: root.active
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.clicked()
  }
}
