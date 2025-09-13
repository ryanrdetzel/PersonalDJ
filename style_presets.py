"""
Reusable voice/tone/dialect style presets for TTS instructions.

Each preset is a small dictionary that captures the desired vocal
character, dialect guidance, and delivery features. Use
`build_instructions` to convert a preset (plus optional per-spot
context) into an instructions string for TTS.
"""

from typing import Dict, List, Optional


# Named presets you can expand over time
STYLES: Dict[str, Dict] = {
    "morning_radio": {
        "description": "Live morning radio host with confident, upbeat energy.",
        "tone": "confident, lively, upbeat, playful",
        "dialect": "General American with natural radio cadence",
        "features": [
            "clear, punchy pronunciation",
            "snappy, fluid phrasing",
            "conversational feel-good vibe",
            "smile in the voice",
        ],
        # Optional default voice suggestion (may be overridden by caller)
        "default_voice": "shimmer",
    },
}


def list_styles() -> List[str]:
    return list(STYLES.keys())


def get_style(name: str) -> Dict:
    if name not in STYLES:
        raise KeyError(f"Unknown style preset: {name}")
    return STYLES[name]


def build_instructions(
    style: Dict,
    *,
    spot_type: Optional[str] = None,
    spot_tone: Optional[str] = None,
    extra_notes: Optional[str] = None,
) -> str:
    """
    Create a concise TTS instructions string from a style preset.

    - style: style dictionary from STYLES
    - spot_type: optional high level type (e.g., "morning_greeting")
    - spot_tone: optional per-spot tone (e.g., "warm and energetic")
    - extra_notes: optional additional guidance to append
    """
    tone = style.get("tone", "")
    dialect = style.get("dialect", "")
    features = "; ".join(style.get("features", []))

    parts: List[str] = []
    base = (
        f"Speak in a {tone} voice. Dialect: {dialect}. "
        f"Emphasize: {features}. Keep it conversational and avoid robotic cadence."
    )
    parts.append(base)

    if spot_type:
        parts.append(f"Match the delivery to a short '{spot_type}' DJ link.")
    if spot_tone:
        parts.append(f"For this spot, lean into: {spot_tone}.")
    if extra_notes:
        parts.append(extra_notes)

    return " ".join(parts)

