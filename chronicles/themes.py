"""Modern glassmorphic HUD themes and cohesive color palettes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeSpec:
    """Complete color tokens for both the HUD overlay and Command Center."""

    name: str
    description: str
    # Surfaces (hex or #RRGGBB; alpha applied cleanly in painters)
    bg_primary: str
    bg_elevated: str
    card_bg: str
    card_hover: str
    # Borders & highlights
    border_subtle: str
    border_locked: str
    specular_top: str
    # Typography
    text_primary: str
    text_secondary: str
    text_muted: str
    # Brand & Accents
    accent_primary: str
    accent_secondary: str
    # Semantic phase badges
    normal_fg: str
    normal_bg: str
    hard_fg: str
    hard_bg: str
    live_normal_fg: str
    live_normal_bg: str
    live_hard_fg: str
    live_hard_bg: str
    warning_fg: str


THEMES: dict[str, ThemeSpec] = {
    "Obsidian Gold": ThemeSpec(
        name="Obsidian Gold",
        description="Tactical carbon glass with forged gold & cyan telemetry",
        bg_primary="#0B0E14",
        bg_elevated="#121722",
        card_bg="#151B27",
        card_hover="#1B2333",
        border_subtle="#2A3447",
        border_locked="#22D3EE",
        specular_top="#F5C451",
        text_primary="#F8FAFC",
        text_secondary="#CBD5E1",
        text_muted="#7C8BA1",
        accent_primary="#F5C451",
        accent_secondary="#22D3EE",
        normal_fg="#38BDF8",
        normal_bg="#0F2942",
        hard_fg="#FB7185",
        hard_bg="#3A1220",
        live_normal_fg="#34D399",
        live_normal_bg="#093628",
        live_hard_fg="#FF5C77",
        live_hard_bg="#49111E",
        warning_fg="#FBBF24",
    ),
    "Cyber Neon": ThemeSpec(
        name="Cyber Neon",
        description="Synthwave midnight indigo with electric cyan & magenta",
        bg_primary="#090714",
        bg_elevated="#120E24",
        card_bg="#17122E",
        card_hover="#201940",
        border_subtle="#372963",
        border_locked="#00F5D4",
        specular_top="#FF2A85",
        text_primary="#F9F7FF",
        text_secondary="#D8CEF6",
        text_muted="#8C7EB8",
        accent_primary="#00F5D4",
        accent_secondary="#FF2A85",
        normal_fg="#00F5D4",
        normal_bg="#09363B",
        hard_fg="#FF4D9D",
        hard_bg="#470F30",
        live_normal_fg="#4ADE80",
        live_normal_bg="#0B3B24",
        live_hard_fg="#FF2A85",
        live_hard_bg="#540A29",
        warning_fg="#FDE047",
    ),
    "Crimson Eclipse": ThemeSpec(
        name="Crimson Eclipse",
        description="Volcanic dark slate with blood-moon crimson & ember highlights",
        bg_primary="#11090B",
        bg_elevated="#1B0E12",
        card_bg="#211217",
        card_hover="#2B171E",
        border_subtle="#4A212B",
        border_locked="#FF4757",
        specular_top="#FF4757",
        text_primary="#FFF1F2",
        text_secondary="#FECDD3",
        text_muted="#B67B84",
        accent_primary="#FF4757",
        accent_secondary="#FB923C",
        normal_fg="#FDBA74",
        normal_bg="#3B1D0F",
        hard_fg="#FF6B81",
        hard_bg="#4D111C",
        live_normal_fg="#FBBF24",
        live_normal_bg="#3F2B09",
        live_hard_fg="#FF3B53",
        live_hard_bg="#5E0F1D",
        warning_fg="#FDBA74",
    ),
    "Abyssal Frost": ThemeSpec(
        name="Abyssal Frost",
        description="Deep oceanic midnight with glacier cyan & sapphire light",
        bg_primary="#06101C",
        bg_elevated="#0B192B",
        card_bg="#0E2036",
        card_hover="#142B47",
        border_subtle="#1E3F63",
        border_locked="#38BDF8",
        specular_top="#38BDF8",
        text_primary="#F0F9FF",
        text_secondary="#BAE6FD",
        text_muted="#6994B8",
        accent_primary="#38BDF8",
        accent_secondary="#2DD4BF",
        normal_fg="#7DD3FC",
        normal_bg="#0D3154",
        hard_fg="#F472B6",
        hard_bg="#3F1635",
        live_normal_fg="#2DD4BF",
        live_normal_bg="#093B38",
        live_hard_fg="#FB7185",
        live_hard_bg="#4B1423",
        warning_fg="#FACC15",
    ),
    "Emerald Nexus": ThemeSpec(
        name="Emerald Nexus",
        description="Obsidian jade backdrop with luminous emerald & mint accents",
        bg_primary="#07120D",
        bg_elevated="#0C1C15",
        card_bg="#10241B",
        card_hover="#163125",
        border_subtle="#214B38",
        border_locked="#10B981",
        specular_top="#34D399",
        text_primary="#ECFDF5",
        text_secondary="#A7F3D0",
        text_muted="#689E84",
        accent_primary="#34D399",
        accent_secondary="#A3E635",
        normal_fg="#6EE7B7",
        normal_bg="#0D3B2A",
        hard_fg="#FB923C",
        hard_bg="#3F210D",
        live_normal_fg="#A3E635",
        live_normal_bg="#243B0B",
        live_hard_fg="#F87171",
        live_hard_bg="#481418",
        warning_fg="#FDE047",
    ),
    "Monochrome Frosted": ThemeSpec(
        name="Monochrome Frosted",
        description="Minimalist smoked glass with crisp titanium white & steel",
        bg_primary="#111317",
        bg_elevated="#191C22",
        card_bg="#1F242C",
        card_hover="#272D37",
        border_subtle="#363E4B",
        border_locked="#E2E8F0",
        specular_top="#FFFFFF",
        text_primary="#FFFFFF",
        text_secondary="#CBD5E1",
        text_muted="#8A94A6",
        accent_primary="#F1F5F9",
        accent_secondary="#94A3B8",
        normal_fg="#E2E8F0",
        normal_bg="#2A313D",
        hard_fg="#FCA5A5",
        hard_bg="#3D1C22",
        live_normal_fg="#6EE7B7",
        live_normal_bg="#11382A",
        live_hard_fg="#FF6B7B",
        live_hard_bg="#4A151E",
        warning_fg="#FDE047",
    ),
}


def get_theme(name: str) -> ThemeSpec:
    """Resolve theme by name, falling back to Obsidian Gold."""
    return THEMES.get(name, THEMES["Obsidian Gold"])
