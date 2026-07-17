from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory

from app.theme_defs import DEFAULT_THEME, PALETTE_THEMES


def theme_names() -> list[str]:
    return [DEFAULT_THEME, *PALETTE_THEMES]


def apply_theme(app: QApplication, name: str):
    colors = PALETTE_THEMES.get(name)
    if colors is None:
        # Native windowsvista style ignores palette changes; reset to stock
        app.setStyle(QStyleFactory.create("windowsvista"))
        app.setPalette(app.style().standardPalette())
        return
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_build_palette(colors))


def _build_palette(c: dict) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(c["window"]))
    p.setColor(role.WindowText, QColor(c["text"]))
    p.setColor(role.Base, QColor(c["base"]))
    p.setColor(role.AlternateBase, QColor(c["alternate_base"]))
    p.setColor(role.Text, QColor(c["text"]))
    p.setColor(role.Button, QColor(c["button"]))
    p.setColor(role.ButtonText, QColor(c["text"]))
    p.setColor(role.BrightText, QColor(c["bright_text"]))
    p.setColor(role.Highlight, QColor(c["accent"]))
    p.setColor(role.HighlightedText, QColor(c["highlighted_text"]))
    p.setColor(role.Link, QColor(c["link"]))
    p.setColor(role.ToolTipBase, QColor(c["base"]))
    p.setColor(role.ToolTipText, QColor(c["text"]))
    p.setColor(role.PlaceholderText, QColor(c["placeholder"]))
    p.setColor(role.Mid, QColor(c["border"]))
    p.setColor(role.Midlight, QColor(c["hover"]))
    p.setColor(role.Dark, QColor(c["muted"]))
    for r in (role.Text, role.WindowText, role.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, r, QColor(c["disabled"]))
    return p
