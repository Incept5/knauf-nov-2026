"""Colour words (English + German) -> CSS colour.

`find_colours(text)` returns every colour mention in order, as (word, name, css).
German adjective endings (-e, -en, -er, -es, -em) are accepted, so "rote",
"blauen", "grünes" all match. "light"/"dark" and "hell"/"dunkel" shift the shade.
"""

from __future__ import annotations

import re

# canonical name -> CSS colour
PALETTE = {
    "red": "#e0201b", "orange": "#ff8a00", "yellow": "#ffd600", "green": "#1fae4b",
    "blue": "#1f5fff", "purple": "#7b2fbe", "violet": "#8f3fd9", "pink": "#ff5fa8",
    "black": "#000000", "white": "#ffffff", "grey": "#808080", "brown": "#7a4a22",
    "cyan": "#00d1e0", "magenta": "#e000a8", "turquoise": "#20c9b5", "gold": "#d4a514",
    "silver": "#b8bec6", "navy": "#0b1f5c", "teal": "#0f8080", "lime": "#9be22d",
    "maroon": "#7a0f1f", "indigo": "#3b1f9e", "lavender": "#b9a6f0", "beige": "#e8d9b5",
    "crimson": "#c4122f", "scarlet": "#ff2400",
}

LIGHT = {"light", "pale", "hell"}
DARK = {"dark", "deep", "dunkel"}

# spoken stem -> canonical name. English words are matched exactly; German stems
# take an optional adjective ending.
EN = {
    "red": "red", "orange": "orange", "yellow": "yellow", "green": "green", "blue": "blue",
    "purple": "purple", "violet": "violet", "pink": "pink", "black": "black", "white": "white",
    "grey": "grey", "gray": "grey", "brown": "brown", "cyan": "cyan", "magenta": "magenta",
    "turquoise": "turquoise", "gold": "gold", "golden": "gold", "silver": "silver",
    "navy": "navy", "teal": "teal", "lime": "lime", "maroon": "maroon", "indigo": "indigo",
    "lavender": "lavender", "beige": "beige", "crimson": "crimson", "scarlet": "scarlet",
}
DE = {
    "rot": "red", "gelb": "yellow", "grün": "green", "gruen": "green", "blau": "blue",
    "lila": "purple", "violett": "violet", "rosa": "pink", "schwarz": "black",
    "weiß": "white", "weiss": "white", "grau": "grey", "braun": "brown",
    "türkis": "turquoise", "tuerkis": "turquoise", "golden": "gold", "silbern": "silver",
    "silber": "silver", "orangen": "orange", "pink": "pink",
}
DE_ENDINGS = r"(?:e|en|er|es|em)?"

_alts = sorted(EN, key=len, reverse=True)
_de_alts = sorted(DE, key=len, reverse=True)
# Optional light/dark modifier, either as its own word ("dark blue") or fused in
# German compounds ("dunkelblau", "hellgrün").
_RX = re.compile(
    r"(?<![\w])"
    r"(?:(?P<mod>light|pale|dark|deep|hell|dunkel)[\s-]?)?"
    r"(?:(?P<en>" + "|".join(map(re.escape, _alts)) + r")"
    r"|(?P<de>" + "|".join(map(re.escape, _de_alts)) + r")" + DE_ENDINGS + r")"
    r"(?![\w])",
    re.IGNORECASE,
)


def _shade(hex_colour: str, factor: float) -> str:
    """factor > 0 lightens toward white, < 0 darkens toward black."""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    if factor > 0:
        r, g, b = (round(c + (255 - c) * factor) for c in (r, g, b))
    else:
        r, g, b = (round(c * (1 + factor)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def find_colours(text: str) -> list[tuple[str, str, str]]:
    out = []
    for m in _RX.finditer(text):
        stem = (m.group("en") or m.group("de")).lower()
        name = EN.get(stem) or DE.get(stem)
        if not name:
            continue
        css = PALETTE[name]
        mod = (m.group("mod") or "").lower()
        if mod in LIGHT:
            css, name = _shade(css, 0.55), f"light {name}"
        elif mod in DARK:
            css, name = _shade(css, -0.55), f"dark {name}"
        out.append((m.group(0), name, css))
    return out


if __name__ == "__main__":
    for s in ["Let's paint it blue, then dark green.", "Der Himmel ist dunkelblau, die Rose ist rot.",
              "ein grünes Auto und eine gelbe Banane", "Bluetooth is not a colour, nor is reddit.",
              "hellgrün und Weiß", "light pink please"]:
        print(s, "->", find_colours(s))
