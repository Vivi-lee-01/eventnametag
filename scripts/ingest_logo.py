"""로고(raster/SVG)에서 대표색을 결정론적으로 추출한다.

vision에 hex를 묻지 않는다(환각). 색은 항상 픽셀/정규식에서만.
stdlib + Pillow(이미 requirements.txt)만 사용.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from PIL import Image  # type: ignore
except ImportError:  # 잉크 게이트와 동일한 optional import 정책
    Image = None

# 공유 유틸 (sys.path: 직접 실행·다른 스크립트가 import할 때 모두 동작)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _brand_util import _luminance, _normalize_hex, _rgb_to_hex  # noqa: E402


def extract_colors_from_raster(path: Path, max_colors: int = 5) -> list[str]:
    """PNG/JPG 등 raster 로고에서 빈도 상위 대표색 hex(소문자) 목록.

    투명·근사 중복은 병합. Pillow 필수(없으면 RuntimeError)."""
    if Image is None:
        raise RuntimeError("Pillow 필요 — raster 로고 색 추출 불가")
    img = Image.open(path).convert("RGBA")
    # 양자화로 대표색 후보 축소 (결정론: 동일 입력 → 동일 출력, MEDIANCUT 핀)
    quant = img.convert("RGB").quantize(
        colors=max(8, max_colors * 4), method=Image.Quantize.MEDIANCUT
    )
    palette = quant.getpalette()
    counts = quant.getcolors() or []  # [(count, palette_index), ...]
    counts.sort(key=lambda c: (-c[0], c[1]))
    seen: list[tuple[int, int, int]] = []
    out: list[str] = []
    for _count, idx in counts:
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        # 근사 중복 병합(맨해튼 거리 < 24)
        if any(abs(r - sr) + abs(g - sg) + abs(b - sb) < 24 for sr, sg, sb in seen):
            continue
        seen.append((r, g, b))
        out.append(_rgb_to_hex(r, g, b))
        if len(out) >= max_colors:
            break
    return out


# ── Task 2: SVG 색 추출 ──────────────────────────────────────────────────────

# stroke 의도적 포함 — 로고는 마크 윤곽선을 stroke로 칠하는 경우가 많음(분류에서 accent로 흡수).
_HEX_RE = re.compile(
    r"(?:fill|stop-color|stroke)\s*[:=]\s*[\"']?\s*(#[0-9a-fA-F]{3,6})",
    re.IGNORECASE,
)


def extract_colors_from_svg(svg_text: str) -> list[str]:
    """SVG 문자열에서 fill/stop-color/stroke hex를 출현 순서로 추출(중복 병합)."""
    out: list[str] = []
    for m in _HEX_RE.finditer(svg_text):
        hx = _normalize_hex(m.group(1))
        if len(hx) == 7 and hx not in out:
            out.append(hx)
    return out


# ── Task 3: 대표색 → brand colors 분류 ─────────────────────────────────────

def logo_to_brand_colors(colors: list[str]) -> dict[str, str]:
    """대표색 목록을 brand.schema colors 블록으로 분류.

    primary_dark = 최저 휘도, primary_light = 최고 휘도(밝은 색 없으면 #ffffff),
    나머지는 accent_1/accent_2."""
    if not colors:
        raise ValueError("색 목록이 비어 있음")
    ordered = sorted(colors, key=_luminance)
    primary_dark = ordered[0]
    light_candidates = [c for c in ordered if _luminance(c) >= 0.5]
    primary_light = light_candidates[-1] if light_candidates else "#ffffff"
    accents = [c for c in colors if c not in (primary_dark, primary_light)]
    out = {"primary_dark": primary_dark, "primary_light": primary_light}
    if accents:
        out["accent_1"] = accents[0]
    if len(accents) > 1:
        out["accent_2"] = accents[1]
    return out
