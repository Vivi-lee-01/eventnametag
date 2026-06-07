"""eventnametag — interview / extract_brand 공유 유틸. 내부 모듈."""
from __future__ import annotations

import re


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _normalize_hex(s: str) -> str:
    """3자리 hex → 6자리. 항상 소문자."""
    s = s.lower()
    if len(s) == 4:  # #abc → #aabbcc
        return "#" + "".join(c * 2 for c in s[1:])
    return s


def _luminance(hex_color: str) -> float:
    """대략 luminance(0~1). 3자리·불량 hex는 0.5로 안전 처리."""
    h = _normalize_hex(hex_color).lstrip("#")
    if len(h) != 6:
        return 0.5
    try:
        r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return 0.5
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def suggest_slug(name: str) -> str:
    """회사·단체명 → slug 후보. 영숫자/하이픈만 남기고 32자로 자름.

    - 빈 이름 → 'my-brand'
    - 첫 문자가 영문이 아니면 'brand-' prefix
    - 끝에 하이픈 잔존 시 제거, 결과가 비면 'my-brand'
    """
    s = name.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    if not s:
        return "my-brand"
    if not s[0].isalpha():
        s = "brand-" + s
    return s[:32].rstrip("-") or "my-brand"
