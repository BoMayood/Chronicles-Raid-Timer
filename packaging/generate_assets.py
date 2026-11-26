"""Generate curated sound cues and ensure multi-resolution app icons exist."""

from __future__ import annotations

import os
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PIL import Image
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QFont, QFontDatabase, QFontMetrics, QGuiApplication, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from chronicles.audio_engine import ensure_builtin_sounds
from chronicles.ui.svg_icons import SVG_TEMPLATES
from version import APP_VERSION

_BADGE_LEFT_BG = "#2D333B"

_ICON_VERSION = (
    '<path d="M7 0.6L8.8 5.1L13.4 7L8.8 8.9L7 13.4L5.2 8.9L0.6 7L5.2 5.1Z" fill="#F5C451"/>'
)

_ICON_WINDOWS = (
    '<path d="M0.6 2.1L6.3 1.3V6.6H0.6V2.1ZM7.2 1.2L13.4 0.3V6.6H7.2V1.2Z'
    'M0.6 7.4H6.3V12.7L0.6 11.9V7.4ZM7.2 7.4H13.4V13.7L7.2 12.8V7.4Z" fill="#38BDF8"/>'
)

_ICON_PYTHON = (
    '<path d="M6.8 0.5C3.7 0.5 3.9 1.8 3.9 1.8V3.2H6.9V3.7H2.5C2.5 3.7 0.5 3.5 0.5 6.8'
    'C0.5 9.9 2.2 9.8 2.2 9.8H3.2V8.2C3.2 8.2 3.1 6.5 4.9 6.5H8.0C8.0 6.5 9.6 6.5 9.6 4.9V2.0'
    'C9.6 2.0 9.8 0.5 6.8 0.5ZM5.1 1.4A0.55 0.55 0 1 1 5.1 2.5A0.55 0.55 0 1 1 5.1 1.4Z" fill="#60A5FA"/>'
    '<path d="M7.2 13.5C10.3 13.5 10.1 12.2 10.1 12.2V10.8H7.1V10.3H11.5C11.5 10.3 13.5 10.5 13.5 7.2'
    'C13.5 4.1 11.8 4.2 11.8 4.2H10.8V5.8C10.8 5.8 10.9 7.5 9.1 7.5H6.0C6.0 7.5 4.4 7.5 4.4 9.1V12.0'
    'C4.4 12.0 4.2 13.5 7.2 13.5ZM8.9 11.5A0.55 0.55 0 1 1 8.9 12.6A0.55 0.55 0 1 1 8.9 11.5Z" fill="#FACC15"/>'
)

_ICON_UI = (
    '<path d="M7 1L13.2 4.3L7 7.6L0.8 4.3Z" fill="#4ADE80"/>'
    '<path d="M0.8 7.2L7 10.5L13.2 7.2" fill="none" stroke="#86EFAC" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M0.8 10.1L7 13.3L13.2 10.1" fill="none" stroke="#4ADE80" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
)

_ICON_DISCORD = (
    '<path d="M11.6 2.1A10.9 10.9 0 0 0 8.9 1.2L8.6 1.8A10.1 10.1 0 0 0 5.4 1.8L5.1 1.2'
    'A10.9 10.9 0 0 0 2.4 2.1C0.7 4.7 0.2 7.2 0.4 9.7A11.1 11.1 0 0 0 3.7 11.4L4.4 10.3'
    'A7.1 7.1 0 0 1 3.3 9.7L3.6 9.5C5.7 10.5 8.3 10.5 10.4 9.5L10.7 9.7'
    'A7.1 7.1 0 0 1 9.6 10.3L10.3 11.4A11.1 11.1 0 0 0 13.6 9.7C13.9 6.8 13.1 4.3 11.6 2.1Z" fill="#818CF8"/>'
    '<circle cx="4.8" cy="6.8" r="1.15" fill="#2D333B"/>'
    '<circle cx="9.2" cy="6.8" r="1.15" fill="#2D333B"/>'
)

_ICON_LICENSE = (
    '<path d="M7 0.8L12.4 2.9V6.8C12.4 10.1 10.1 12.6 7 13.6C3.9 12.6 1.6 10.1 1.6 6.8V2.9L7 0.8Z" '
    'fill="none" stroke="#22D3EE" stroke-width="1.5" stroke-linejoin="round"/>'
    '<path d="M4.6 7.0L6.3 8.7L9.7 5.2" fill="none" stroke="#22D3EE" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
)


def _load_badge_fonts() -> None:
    fonts_dir = r"C:\Windows\Fonts"
    for fname in ("verdana.ttf", "verdanab.ttf", "segoeui.ttf", "segoeuib.ttf"):
        fpath = os.path.join(fonts_dir, fname)
        if os.path.exists(fpath):
            QFontDatabase.addApplicationFont(fpath)


def _render_badge_svg(
    label: str,
    value: str,
    right_bg: str,
    value_fg: str,
    icon_svg: str,
) -> str:
    label_u = label.upper()
    value_u = value.upper()

    fm_label = QFontMetrics(QFont("Verdana", 8, QFont.Weight.DemiBold))
    fm_value = QFontMetrics(QFont("Verdana", 8, QFont.Weight.Bold))

    # Measure cleanly with safe cross-platform margin for Verdana / DejaVu Sans.
    icon_block = 18
    pad_l = 10
    pad_r = 11
    label_text_w = max(18, fm_label.horizontalAdvance(label_u)) + max(4, int(len(label_u) * 0.8))
    value_text_w = max(20, fm_value.horizontalAdvance(value_u)) + max(4, int(len(value_u) * 0.9))

    left_w = pad_l + icon_block + label_text_w + 8
    right_w = pad_r + value_text_w + pad_r
    total_w = left_w + right_w

    label_x = pad_l + icon_block + (label_text_w / 2.0) + 1.0
    value_x = left_w + (right_w / 2.0)

    alt_text = escape(f"{label}: {value}")
    label_xml = escape(label_u)
    value_xml = escape(value_u)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="28" '
        f'viewBox="0 0 {total_w} 28" role="img" aria-label="{alt_text}">'
        f'<title>{alt_text}</title>'
        f'<defs><clipPath id="r"><rect width="{total_w}" height="28" rx="4" fill="#FFFFFF"/></clipPath></defs>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{left_w}" height="28" fill="{_BADGE_LEFT_BG}"/>'
        f'<rect x="{left_w}" width="{right_w}" height="28" fill="{right_bg}"/>'
        f'<rect width="{total_w}" height="1" fill="#FFFFFF" fill-opacity="0.10"/>'
        f'</g>'
        f'<g transform="translate(10, 7)">{icon_svg}</g>'
        f'<g fill="#F8FAFC" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="10" font-weight="600" letter-spacing="0.6">'
        f'<text x="{label_x:.1f}" y="17.5">{label_xml}</text>'
        f'</g>'
        f'<g fill="{value_fg}" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="10" font-weight="700" letter-spacing="0.7">'
        f'<text x="{value_x:.1f}" y="17.5">{value_xml}</text>'
        f'</g>'
        f'</svg>\n'
    )


def generate_readme_badges() -> str:
    """Write self-contained GitHub-safe SVG badges to docs/badges/."""
    _load_badge_fonts()
    badges_dir = os.path.join(ROOT, "docs", "badges")
    os.makedirs(badges_dir, exist_ok=True)
    specs = [
        ("version.svg", "Version", APP_VERSION, "#F5C451", "#111827", _ICON_VERSION),
        ("platform.svg", "Platform", "Windows 10 / 11", "#0078D6", "#FFFFFF", _ICON_WINDOWS),
        ("python.svg", "Python", "3.10+", "#3776AB", "#FFFFFF", _ICON_PYTHON),
        ("ui.svg", "UI", "PyQt6 Glassmorphic", "#2EA043", "#FFFFFF", _ICON_UI),
        ("discord.svg", "Discord", "Updates & Community", "#5865F2", "#FFFFFF", _ICON_DISCORD),
        ("license.svg", "License", "MIT", "#22D3EE", "#111827", _ICON_LICENSE),
    ]
    for fname, label, val, bg, fg, icon_svg in specs:
        svg = _render_badge_svg(label, val, bg, fg, icon_svg)
        with open(os.path.join(badges_dir, fname), "w", encoding="utf-8") as fh:
            fh.write(svg)
    return badges_dir


def generate_app_icons() -> tuple[str, str]:
    """Ensure app_icon.png and multi-size app_icon.ico exist without overwriting custom crest."""
    icons_dir = os.path.join(ROOT, "assets", "icons")
    os.makedirs(icons_dir, exist_ok=True)
    png_path = os.path.join(icons_dir, "app_icon.png")
    ico_path = os.path.join(icons_dir, "app_icon.ico")

    if not os.path.exists(png_path):
        svg_str = SVG_TEMPLATES["crest"].format(color="#F5C451", secondary="#22D3EE")
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        pixmap = QPixmap(256, 256)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
        painter.end()
        pixmap.save(png_path, "PNG")

    if not os.path.exists(ico_path) or os.path.getmtime(png_path) > os.path.getmtime(ico_path):
        img = Image.open(png_path).convert("RGBA")
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ico_path, format="ICO", sizes=sizes)
    return png_path, ico_path


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    sounds_dir = ensure_builtin_sounds(os.path.join(ROOT, "assets", "sounds"))
    png_path, ico_path = generate_app_icons()
    badges_dir = generate_readme_badges()
    print(f"Verified sounds in: {sounds_dir}")
    print(f"Verified icons: {png_path}, {ico_path}")
    print(f"Verified badges in: {badges_dir}")


if __name__ == "__main__":
    main()
