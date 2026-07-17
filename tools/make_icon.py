"""Generate the app icon (assets/icon.png + icon.ico).

Bitwig-dark tile with an orange eighth note (Liszt) beside checklist lines
and a check (list/to-do). Colors echo Bitwig's dark-gray UI + orange brand.

Run: python make_icon.py
"""
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath,
    QPen,
)

ASSETS = Path(__file__).parent.parent / "assets"


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # Tile: Bitwig-style dark gray gradient with a near-black border
    tile = QRectF(s * 0.02, s * 0.02, s * 0.96, s * 0.96)
    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor("#4d4d4d"))
    grad.setColorAt(1.0, QColor("#2c2c2c"))
    p.setBrush(grad)
    p.setPen(QPen(QColor("#1a1a1a"), max(1.0, s * 0.02)))
    p.drawRoundedRect(tile, s * 0.14, s * 0.14)

    # Eighth note in Bitwig orange, left side
    orange = QColor("#f46b1a")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(orange)
    # Head: slightly rotated ellipse
    p.save()
    p.translate(s * 0.30, s * 0.70)
    p.rotate(-20)
    p.drawEllipse(QPointF(0, 0), s * 0.115, s * 0.085)
    p.restore()
    # Stem
    stem_w = s * 0.045
    p.drawRect(QRectF(s * 0.385, s * 0.20, stem_w, s * 0.50))
    # Flag: curved sweep off the stem top
    flag = QPainterPath(QPointF(s * 0.385 + stem_w, s * 0.20))
    flag.cubicTo(
        QPointF(s * 0.56, s * 0.26), QPointF(s * 0.60, s * 0.36),
        QPointF(s * 0.54, s * 0.48),
    )
    flag.cubicTo(
        QPointF(s * 0.58, s * 0.34), QPointF(s * 0.52, s * 0.28),
        QPointF(s * 0.385 + stem_w, s * 0.28),
    )
    flag.closeSubpath()
    p.drawPath(flag)

    # Checklist rows, right side: two light lines, then an orange check
    line_pen = QPen(QColor("#d9d9d9"), s * 0.06, Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap)
    p.setPen(line_pen)
    p.drawLine(QPointF(s * 0.62, s * 0.28), QPointF(s * 0.86, s * 0.28))
    p.drawLine(QPointF(s * 0.62, s * 0.46), QPointF(s * 0.86, s * 0.46))

    check_pen = QPen(orange, s * 0.075, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(check_pen)
    check = QPainterPath(QPointF(s * 0.60, s * 0.66))
    check.lineTo(QPointF(s * 0.70, s * 0.76))
    check.lineTo(QPointF(s * 0.88, s * 0.56))
    p.drawPath(check)

    p.end()
    return img


def main():
    QGuiApplication(sys.argv)  # QPainter on QImage needs a Gui application
    ASSETS.mkdir(exist_ok=True)
    render(256).save(str(ASSETS / "icon.png"))
    render(48).save(str(ASSETS / "icon.ico"))
    print(f"Wrote {ASSETS / 'icon.png'} and {ASSETS / 'icon.ico'}")


if __name__ == "__main__":
    main()
