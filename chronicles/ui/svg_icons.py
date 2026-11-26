"""Crisp scalable vector SVG emblems and dynamic icon rendering."""

from __future__ import annotations

import os

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from chronicles.config import get_app_root, get_resource_root

SVG_TEMPLATES: dict[str, str] = {
    "theme_gem": """
    <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="{color}"/>
          <stop offset="100%" stop-color="{secondary}"/>
        </linearGradient>
      </defs>
      <polygon points="32,4 56,16 56,42 32,60 8,42 8,16" fill="#0E131D" stroke="url(#g1)" stroke-width="3.5"/>
      <polygon points="32,12 46,20 32,31 18,20" fill="{color}" fill-opacity="0.9"/>
      <polygon points="32,52 46,44 32,33 18,44" fill="{secondary}" fill-opacity="0.9"/>
      <line x1="32" y1="9" x2="32" y2="55" stroke="#FFFFFF" stroke-width="2" stroke-opacity="0.75"/>
      <circle cx="32" cy="32" r="4.2" fill="#FFFFFF"/>
    </svg>""",
    "crest": """
    <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
      <polygon points="32,4 57,14 57,37 32,60 7,37 7,14" fill="#10131A" stroke="#F5C451" stroke-width="3.2"/>
      <polygon points="32,9 51,17 51,35 32,53 13,35 13,17" fill="none" stroke="#E11D48" stroke-width="2.2"/>
      <polygon points="18,22 46,22 46,40 18,40" fill="#07090D" stroke="#475569" stroke-width="1.5"/>
      <polygon points="21,23 26,23 23.5,32" fill="#F8FAFC"/>
      <polygon points="38,23 43,23 40.5,32" fill="#F8FAFC"/>
      <polygon points="22,39 25,39 23.5,33" fill="#F8FAFC"/>
      <polygon points="39,39 42,39 40.5,33" fill="#F8FAFC"/>
    </svg>""",
    "rift": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L19 9L15 13L18 22L12 17L6 22L9 13L5 9L12 2Z" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M12 5.5L13.5 11.5L12 15L10.5 11.5L12 5.5Z" fill="{color}"/>
    </svg>""",
    "nightmare": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 5C5.5 8 7 9.5 8 10.2C7.4 11.6 7 13.1 7 14.5C7 17.5 9.2 20 12 20C14.8 20 17 17.5 17 14.5C17 13.1 16.6 11.6 16 10.2C17 9.5 18.5 8 20 5C17.5 6.3 15.8 7 14.4 7.3C13.6 7.1 12.8 7 12 7C11.2 7 10.4 7.1 9.6 7.3C8.2 7 6.5 6.3 4 5Z" fill="{color}" fill-opacity="0.24" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <circle cx="9.8" cy="13.2" r="1.3" fill="{color}"/>
      <circle cx="14.2" cy="13.2" r="1.3" fill="{color}"/>
      <path d="M10.5 16.8H13.5" stroke="{color}" stroke-width="1.6" stroke-linecap="round"/>
    </svg>""",
    "dragon": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 16C5 10 9 5 14 4L12.5 8L19 6.5L15.5 11L21 12.5L14 15.5L16.5 20L10.5 17.5L7 20.5L8 15.5L3 16Z" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="1.7" stroke-linejoin="round"/>
    </svg>""",
    "sword": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M19.5 3.5L13 5L6.5 11.5L12.5 17.5L19 11L19.5 3.5Z" fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M5 13L11 19M4.5 19.5L8 16" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
    </svg>""",
    "compass": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="9" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="1.8"/>
      <polygon points="15.8,8.2 13.4,13.4 8.2,15.8 10.6,10.6" fill="{color}"/>
    </svg>""",
    "stopwatch": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="13.5" r="7.5" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="1.8"/>
      <path d="M9.5 3H14.5M12 3V6M12 13.5L15.2 10.5" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
    </svg>""",
    "lock": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect x="5" y="11" width="14" height="10" rx="2.5" fill="{color}" fill-opacity="0.2" stroke="{color}" stroke-width="1.9"/>
      <path d="M8 11V7.5C8 5.3 9.8 3.5 12 3.5C14.2 3.5 16 5.3 16 7.5V11" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
    </svg>""",
    "unlock": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect x="5" y="11" width="14" height="10" rx="2.5" fill="none" stroke="{color}" stroke-width="1.9"/>
      <path d="M8 11V7.5C8 5.3 9.8 3.5 12 3.5C13.8 3.5 15.3 4.7 15.8 6.3" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
    </svg>""",
    "settings": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 7H14M18 7H20M4 12H7M11 12H20M4 17H12M16 17H20" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
      <circle cx="16" cy="7" r="2.2" fill="{color}"/>
      <circle cx="9" cy="12" r="2.2" fill="{color}"/>
      <circle cx="14" cy="17" r="2.2" fill="{color}"/>
    </svg>""",
    "timeline": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="4" width="18" height="16" rx="2.5" fill="none" stroke="{color}" stroke-width="1.8"/>
      <path d="M3 9H21M7 13H13M11 16.5H17" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
    </svg>""",
    "compact": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="6" width="16" height="4" rx="1.5" fill="{color}"/>
      <rect x="4" y="14" width="16" height="4" rx="1.5" fill="{color}" fill-opacity="0.55"/>
    </svg>""",
    "expand": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect x="4" y="5" width="16" height="14" rx="2.5" fill="none" stroke="{color}" stroke-width="1.8"/>
      <path d="M7 9H17M7 13H13" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
    </svg>""",
    "volume_on": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <polygon points="4,9 8.5,9 13.5,5 13.5,19 8.5,15 4,15" fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M16.5 9C17.6 10.3 17.6 13.7 16.5 15M19 6.8C21 9.5 21 14.5 19 17.2" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
    </svg>""",
    "volume_off": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <polygon points="4,9 8.5,9 13.5,5 13.5,19 8.5,15 4,15" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M16.5 9.5L21 14.5M21 9.5L16.5 14.5" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
    </svg>""",
    "tray": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M5 17H19" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
    </svg>""",
    "close": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M6.5 6.5L17.5 17.5M17.5 6.5L6.5 17.5" stroke="{color}" stroke-width="2.1" stroke-linecap="round"/>
    </svg>""",
    "plus": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 5V19M5 12H19" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
    </svg>""",
    "trash": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M5 7H19M9 7V4.5H15V7M7.5 7L8.5 19.5H15.5L16.5 7" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",
    "edit": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 20H8.5L18.5 10L14 5.5L4 15.5V20Z" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
    </svg>""",
    "refresh": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M19 8A7.5 7.5 0 1 0 19.5 14" fill="none" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
      <polygon points="19.5,3.5 20.5,8.8 15.2,7.8" fill="{color}"/>
    </svg>""",
    "snooze": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M18 8C18 4.9 15.3 3 12 3C8.7 3 6 4.9 6 8V14L4 17H20L18 14V8Z" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M10 19.5C10.5 20.4 11.2 21 12 21C12.8 21 13.5 20.4 14 19.5" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
      <path d="M4 4L20 20" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>
    </svg>""",
    "bell": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M18 8.5C18 5.3 15.3 3 12 3C8.7 3 6 5.3 6 8.5V14.5L4 17.5H20L18 14.5V8.5Z" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
      <path d="M10 19.5C10.5 20.4 11.2 21 12 21C12.8 21 13.5 20.4 14 19.5" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
    </svg>""",
    "mic": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="1.8"/>
      <path d="M6 11.5C6 14.8 8.7 17.5 12 17.5C15.3 17.5 18 14.8 18 11.5M12 17.5V21" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
    </svg>""",
    "arrow_up": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M7 14L12 9L17 14" fill="none" stroke="{color}" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",
    "arrow_down": """
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M7 10L12 15L17 10" fill="none" stroke="{color}" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",
}


def _find_crest_png() -> str | None:
    for root in (get_resource_root(), get_app_root()):
        candidate = os.path.join(root, "assets", "icons", "app_icon.png")
        if os.path.exists(candidate):
            return candidate
    return None


def render_svg_pixmap(
    key: str,
    size: int = 20,
    color: str = "#F8FAFC",
    secondary: str = "#22D3EE",
    dpr: float = 2.0,
) -> QPixmap:
    """Render a crisp high-DPI QPixmap from the PNG crest or a named SVG template."""
    px_size = max(8, int(round(size * dpr)))
    if key == "crest":
        png_path = _find_crest_png()
        if png_path:
            src = QPixmap(png_path)
            if not src.isNull():
                scaled = src.scaled(
                    px_size,
                    px_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                scaled.setDevicePixelRatio(dpr)
                return scaled

    template = SVG_TEMPLATES.get(key, SVG_TEMPLATES["sword"])
    svg_str = template.format(color=color, secondary=secondary)
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(px_size, px_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def render_svg_icon(
    key: str,
    size: int = 20,
    color: str = "#F8FAFC",
    secondary: str = "#22D3EE",
) -> QIcon:
    """Render a QIcon from an SVG template."""
    return QIcon(render_svg_pixmap(key, size=size, color=color, secondary=secondary))
