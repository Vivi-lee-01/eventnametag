#!/usr/bin/env python3
"""
eventnametag — 메인 entry. BI yaml 로드 + skeleton 선택 + 시안 미리보기 + 인쇄.

인쇄 파이프라인: HTML → Chrome PDF → sips 300dpi PNG → Preview.
BI 토큰 시스템 + 4 skeleton 풀(R1-R4) + 가드레일 G1-G9.

Usage:
  generate.py --brand <slug> --event <name>     # 메인 — 명단 → 시안 → 인쇄
  generate.py --calibrate                       # 정렬 테스트 시트
  generate.py --order-paper                     # 쿠팡 라벨지 재구매
  generate.py --register-brand                  # BI 등록 (v0.1: 직접 편집 안내)
  generate.py --validate <yaml>                 # BI yaml schema 검증

자세한 옵션은 README.md 참조.
"""
from __future__ import annotations

import argparse
import csv
import html as html_mod
import io
import json
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# yaml, jsonschema는 optional import — help/doctor/demo UX가 막히지 않도록 지연 안내
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

try:
    import jsonschema  # type: ignore
except ImportError:
    jsonschema = None  # G1는 jsonschema 없으면 skip + 경고

try:
    from PIL import Image  # type: ignore
except ImportError:
    Image = None  # G3 잉크 커버리지는 PIL 없으면 skip + 경고

# ─── 경로 ───
SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
EXAMPLES_DIR = SKILL_DIR / "brands" / "examples"
SCHEMA_FILE = SKILL_DIR / "schema" / "brand.schema.json"

USER_DIR = Path.home() / ".config" / "eventnametag"
USER_BRANDS_DIR = USER_DIR / "brands"
STATE_FILE = USER_DIR / "state.json"
CALIBRATION_FILE = USER_DIR / "calibration.yaml"  # v0.2: 사용자별 프린터 정렬 보정값
OUTPUT_DIR = Path.home() / ".claude" / "tmp" / "eventnametag"

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
COUPANG_STANDARD_URL = "https://link.coupang.com/a/eGNFOI"
COUPANG_URL = COUPANG_STANDARD_URL

# 사용자는 skeleton ID보다 “행사 분위기”를 먼저 이해한다. Style pack은
# BI 토큰을 덮어쓰되 워드마크/회사명은 유지해서, 묻기 전에 바로 보여줄 수
# 있는 디자인 브리프 역할을 한다.
STYLE_PACKS = {
    "name-first": {
        "label": "이름 가독성 최우선형",
        "description": "멀리서도 이름이 먼저 읽히는 기본 행사 카드",
        "best_for": "세미나, 일반 네트워킹, 사내 행사, 등록대에서 빠르게 이름 확인이 필요한 행사",
        "emphasis": "이름을 가장 크게, 소속/역할은 보조 정보로 정리",
        "fields": ["name", "company", "role"],
        "internal_layout": "상단 브랜드 바 + 대형 이름 영역",
        "print_risk": "낮음 — 흰 여백이 많고 기본 라벨지에서 안정적",
        "user_explanation": "참석자 이름을 가장 크게 보여줘 현장에서 서로를 빨리 알아보게 합니다.",
        "colors": {
            "primary_dark": "#172033",
            "primary_light": "#FFFFFF",
            "accent_1": "#2563EB",
            "accent_2": "#D9E7FF",
            "surface_subtle": "#E5E7EB",
        },
        "preferred_skeletons": ["r1", "r2"],
        "layout_variant": "name_hero",
        "visual_motif": {"type": "quiet_rule"},
        "paper": "standard",
    },
    "networking-intro": {
        "label": "네트워킹·한줄소개형",
        "description": "이름 아래 한줄소개와 관심사를 배치해 첫 대화를 쉽게 여는 카드",
        "best_for": "커뮤니티 밋업, 네트워킹 파티, 멤버 교류 행사, 소규모 컨퍼런스",
        "emphasis": "한줄소개, 관심사, 대화 시작 단서",
        "fields": ["name", "company", "role", "intro", "interests"],
        "internal_layout": "좌측 컬러 띠 + 넓은 소개 텍스트 영역",
        "print_risk": "보통 — 소개가 길면 글자가 작아지므로 35자 안팎 권장",
        "user_explanation": "처음 만난 사람이 바로 말을 걸 수 있도록 이름보다 소개 문장의 역할을 키웁니다.",
        "colors": {
            "primary_dark": "#4338CA",
            "primary_light": "#FFF7ED",
            "accent_1": "#FB7185",
            "accent_2": "#FBBF24",
            "surface_subtle": "#FED7AA",
        },
        "preferred_skeletons": ["r2", "r1"],
        "layout_variant": "intro_hero",
        "visual_motif": {"type": "confetti"},
        "paper": "glossy_laser",
    },
    "recruiting": {
        "label": "채용행사·직무 강조형",
        "description": "지원자·리크루터·면접관을 구분하고 직무/관심 포지션을 잘 보이게 하는 카드",
        "best_for": "채용박람회, 캠퍼스 리크루팅, 후보자 밋업, 인터뷰 데이",
        "emphasis": "직무, 관심 포지션, 후보자/리크루터 구분",
        "fields": ["name", "company", "role", "group", "intro"],
        "internal_layout": "역할 배지 + 직무 정보가 긴 경우를 위한 세로형 정보 구조",
        "print_risk": "낮음 — 컬러 면적이 작아 대량 출력에 유리",
        "user_explanation": "채용 현장에서 누구와 어떤 대화를 해야 하는지 한눈에 보이게 합니다.",
        "colors": {
            "primary_dark": "#102A43",
            "primary_light": "#F7FBFF",
            "accent_1": "#0EA5E9",
            "accent_2": "#A7F3D0",
            "surface_subtle": "#D7ECFF",
        },
        "preferred_skeletons": ["r2", "r1"],
        "layout_variant": "badge_first",
        "visual_motif": {"type": "recruiting_flow"},
        "paper": "standard",
    },
    "speaker-staff-vip": {
        "label": "스피커·스태프·VIP 구분형",
        "description": "현장 운영자가 역할과 접근 권한을 빠르게 구분하는 운영 카드",
        "best_for": "컨퍼런스 운영, 초청행사, 스피커/VIP 동선 구분, 스태프 체크인",
        "emphasis": "Staff/Speaker/VIP 역할, 그룹, 트랙, 동선 구분",
        "fields": ["name", "company", "role", "group", "track"],
        "internal_layout": "강한 역할 배지 + 그룹/트랙 보조 영역",
        "print_risk": "낮음 — 운영 배지는 선명하지만 배경 잉크 사용량은 제한",
        "user_explanation": "참석자 이름보다 현장 역할 구분이 중요한 행사에 맞춰 배지를 크게 보여줍니다.",
        "colors": {
            "primary_dark": "#0F172A",
            "primary_light": "#F8FAFC",
            "accent_1": "#F97316",
            "accent_2": "#14B8A6",
            "surface_subtle": "#CBD5E1",
        },
        "preferred_skeletons": ["r2", "r1"],
        "layout_variant": "badge_first",
        "visual_motif": {"type": "role_badge"},
        "paper": "standard",
    },
    "ai-hackathon": {
        "label": "AI·해커톤 에너지형",
        "description": "네온 그리드와 강한 컬러로 사진에 잘 보이는 개발자 행사 카드",
        "best_for": "AI 밋업, 데모데이, 해커톤, 개발자 컨퍼런스, 팀 빌딩 행사",
        "emphasis": "팀, 트랙, 프로젝트/데모 키워드, 기술 관심사",
        "fields": ["name", "company", "role", "track", "interests"],
        "internal_layout": "풀 컬러 임팩트 + 트랙/팀 정보 영역",
        "print_risk": "높음 — 진한 배경과 그라디언트 때문에 대량 인쇄 전 테스트 권장",
        "user_explanation": "행사 사진과 데모 부스에서 눈에 띄는 에너지 있는 네임택이 필요할 때 씁니다.",
        "colors": {
            "primary_dark": "#080B2A",
            "primary_light": "#F8FAFF",
            "accent_1": "#7C3AED",
            "accent_2": "#22D3EE",
            "surface_subtle": "#D8D7FF",
        },
        "preferred_skeletons": ["r3", "r1"],
        "layout_variant": "diagonal",
        "visual_motif": {"type": "neon_grid"},
        "paper": "glossy_laser",
    },
    "premium-salon": {
        "label": "프리미엄 살롱형",
        "description": "여백과 절제된 금색 포인트로 고급 초청행사 분위기를 만드는 카드",
        "best_for": "프리미엄 살롱, 리더십 모임, VIP 초청, 투자자/파트너 라운드테이블",
        "emphasis": "이름, 소속, 초청 행사명, 과하지 않은 브랜드 무드",
        "fields": ["name", "company", "role"],
        "internal_layout": "넓은 여백 + 작은 프리미엄 포인트",
        "print_risk": "낮음 — 잉크 사용량이 적고 기본 라벨지에서도 무난",
        "user_explanation": "화려한 장식보다 여백과 정돈감을 통해 초대받은 느낌을 줍니다.",
        "colors": {
            "primary_dark": "#111111",
            "primary_light": "#FBF7EF",
            "accent_1": "#B0894F",
            "accent_2": "#E8D8B8",
            "surface_subtle": "#E7DEC9",
        },
        "preferred_skeletons": ["r4", "r1"],
        "layout_variant": "name_hero",
        "visual_motif": {"type": "gold_corner"},
        "paper": "standard",
    },
    "workshop-learning": {
        "label": "교육·워크숍 캐주얼형",
        "description": "밝은 색과 작은 스티커 장식으로 참여 부담을 낮추는 학습 행사 카드",
        "best_for": "교육, 워크숍, 커뮤니티 온보딩, 사내 러닝데이, 청소년/대학생 프로그램",
        "emphasis": "이름, 소속/학교, 참여 그룹, 한줄소개",
        "fields": ["name", "company", "group", "intro"],
        "internal_layout": "캐주얼 장식 + 소개/그룹 정보 영역",
        "print_risk": "보통 — 밝은 장식은 안전하지만 색감 확인용 테스트 권장",
        "user_explanation": "딱딱한 행사보다 편하게 말을 걸 수 있는 학습/워크숍 분위기를 만듭니다.",
        "colors": {
            "primary_dark": "#4338CA",
            "primary_light": "#FFF7ED",
            "accent_1": "#FB7185",
            "accent_2": "#FBBF24",
            "surface_subtle": "#FED7AA",
        },
        "preferred_skeletons": ["r2", "r1"],
        "layout_variant": "intro_hero",
        "visual_motif": {"type": "sticker_scene"},
        "paper": "glossy_laser",
    },
    "qr-connect": {
        "label": "QR·LinkedIn 연결형",
        "description": "네임택을 보고 바로 프로필·LinkedIn·개인 페이지로 이어지게 하는 연결 카드",
        "best_for": "네트워킹 행사, 채용 행사, 글로벌 컨퍼런스, 크리에이터/창업자 밋업",
        "emphasis": "이름, 소속, QR/LinkedIn URL, 짧은 연결 문구",
        "fields": ["name", "company", "role", "qr_url", "intro"],
        "internal_layout": "이름 영역 + 우측 하단 QR 연결 영역",
        "print_risk": "보통 — QR은 너무 작으면 인식률이 떨어져 사전 스캔 테스트 필요",
        "user_explanation": "명함 교환 없이도 네임택에서 바로 온라인 프로필로 연결되게 합니다.",
        "colors": {
            "primary_dark": "#0F172A",
            "primary_light": "#F8FAFC",
            "accent_1": "#10B981",
            "accent_2": "#BAE6FD",
            "surface_subtle": "#D1FAE5",
        },
        "preferred_skeletons": ["r1", "r2"],
        "layout_variant": "name_hero",
        "visual_motif": {"type": "qr_corner"},
        "paper": "standard",
    },
}

def require_yaml(context: str = "이 작업"):
    """PyYAML이 필요한 시점에만 친절하게 실패한다.

    --help/--doctor처럼 YAML이 없어도 동작해야 하는 첫 경험 명령을 막지 않기 위해
    모듈 import 시점에는 종료하지 않고, 실제 yaml 로드 직전에만 안내한다.
    """
    if yaml is None:
        print(f"✗ {context}에는 PyYAML이 필요합니다.", file=sys.stderr)
        print("  설치: python3 -m pip install -r requirements.txt", file=sys.stderr)
        sys.exit(2)
    return yaml


def print_label_paper_guidance() -> None:
    """출력물을 만든 뒤 자연스럽게 라벨지 준비물을 안내한다."""
    print(file=sys.stderr)
    print("📦 실제 인쇄 준비물", file=sys.stderr)
    print("  - 라벨지: 탐사 A4 8칸 라벨지 / 99×67.5mm", file=sys.stderr)
    print(f"  - 구매 링크: {COUPANG_STANDARD_URL}", file=sys.stderr)
    print("  - Preview에 열린 300dpi PNG를 인쇄 (PDF·lpr 직접 인쇄 금지)", file=sys.stderr)
    print("  - Cmd+P → 용지 크기 A4", file=sys.stderr)
    print("  - '크기 조절' 선택 후 100% 입력", file=sys.stderr)
    print("  - '용지에 맞게 크기 조절/Scale to Fit/자동 맞춤'은 반드시 OFF", file=sys.stderr)
    print("  - 자동 회전 OFF", file=sys.stderr)
    print("  - 첫 장은 일반 A4로 테스트 후 라벨지에 겹쳐 정렬을 확인하세요", file=sys.stderr)
    print("  - 프린터마다 라벨지 급지 방향이 다를 수 있습니다.", file=sys.stderr)
    print("    일반 A4 용지에 펜으로 앞/위 방향을 표시한 뒤 간단히 테스트 인쇄해서", file=sys.stderr)
    print("    라벨지의 상하·앞뒤 출력 방향을 맞춘 후 본 인쇄를 진행하세요! :)", file=sys.stderr)
    print("    이 링크는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.", file=sys.stderr)


def open_url_in_chrome(url: str) -> None:
    """구매 링크는 macOS Chrome에서 바로 연다. 실패하면 기본 브라우저로 fallback."""
    try:
        subprocess.run(["open", "-a", "Google Chrome", url], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        webbrowser.open(url)


def apply_style_pack(brand: dict, style_id: str) -> dict:
    """행사 무드 style pack을 BI 위에 얹는다.

    회사명/워드마크는 유지하고 색상·시그니처·추천 skeleton·라벨지 추천만
    style pack 값으로 바꾼다. 사용자가 BI를 등록하지 않아도 먼저 매력적인
    시안을 보여주기 위한 경로다.
    """
    pack = STYLE_PACKS.get(style_id)
    if pack is None:
        raise ValueError(f"unknown style pack: {style_id}")

    themed = dict(brand)
    themed["colors"] = dict(pack["colors"])
    themed["preferred_skeletons"] = list(pack["preferred_skeletons"])
    themed["visual_motif"] = dict(pack["visual_motif"])
    design = dict(themed.get("design") or {})
    # showcase/quick에서 모든 카드가 diagonal 기본값으로 떨어지면 실제 미리보기가
    # 거의 같아 보인다. 제품 카드별 정보 구조를 즉시 체감할 수 있게 pack이
    # 의도한 layout variant를 brand design에 주입한다. 사용자가 명시한 cell_template은
    # 보존하되, style pack 미리보기에서는 layout만 pack 기준으로 덮어쓴다.
    design["layout_variant"] = pack["layout_variant"]
    themed["design"] = design
    themed["style_pack"] = {
        "id": style_id,
        "label": pack["label"],
        "description": pack["description"],
        "best_for": pack["best_for"],
        "emphasis": pack["emphasis"],
        "fields": list(pack["fields"]),
        "internal_layout": pack["internal_layout"],
        "print_risk": pack["print_risk"],
        "user_explanation": pack["user_explanation"],
        "layout_variant": pack["layout_variant"],
    }
    themed["print"] = dict(themed.get("print") or {})
    themed["print"]["recommended_paper"] = pack["paper"]
    if style_id in ("premium-salon", "ai-hackathon", "workshop-learning"):
        themed["signature"] = {
            "type": "gradient_orb",
            "gradient": {
                "inner": pack["colors"]["accent_2"],
                "outer": pack["colors"]["accent_1"],
            },
            "size_mm": 3.8,
            "position": "left_of_wordmark",
        }
    return themed


def _pattern_css(brand: dict) -> str:
    """design.pattern 값에 맞는 저잉크 벡터 배경 CSS를 반환한다 (P1-B).

    셀 루트의 .pattern-{id} 클래스에 걸리는 저강도 CSS 그라디언트 패턴.
    잉크 게이트(§6)를 통과하도록 opacity를 낮게 유지한다. 색은 brand
    accent 토큰(var)을 쓰며, 미설정 시 빈 문자열(현행 렌더 불변).
    """
    pattern = (brand.get("design") or {}).get("pattern")
    if not pattern:
        return ""
    colors = brand.get("colors", {})
    accent_1 = colors.get("accent_1", colors.get("primary_dark", "#111111"))
    accent_2 = colors.get("accent_2", accent_1)
    # 공통: 패턴 레이어는 셀 본문 뒤에 깔리며 텍스트 가독성을 해치지 않게 저강도
    # P1 가림 수정: 패턴을 .tag에 걸어 ::before가 .tag 불투명 배경 '위'(z-index:0)에 깔리고
    # 텍스트(.topbar/.body, z-index:1)는 그 위로 뜨게 한다. (이전엔 .cell에 걸려 .tag가 전부 가림)
    blocks = {
        "dot-grid": f"""
  .tag.pattern-dot-grid {{ position: relative; }}
  .tag.pattern-dot-grid::before {{ content: ""; position: absolute; inset: 0; z-index: 0; pointer-events: none;
    opacity: 0.10; background-image: radial-gradient(var(--brand-accent-1, {accent_1}) 0.5mm, transparent 0.6mm);
    background-size: 5mm 5mm; }}""",
        "stripe": f"""
  .tag.pattern-stripe {{ position: relative; }}
  .tag.pattern-stripe::before {{ content: ""; position: absolute; inset: 0; z-index: 0; pointer-events: none;
    opacity: 0.08; background-image: repeating-linear-gradient(45deg,
      var(--brand-accent-1, {accent_1}) 0 0.6mm, transparent 0.6mm 4mm); }}""",
        "wave": f"""
  .tag.pattern-wave {{ position: relative; }}
  .tag.pattern-wave::before {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 14mm; z-index: 0;
    pointer-events: none; opacity: 0.12; background-image: radial-gradient(circle at 50% 120%,
      var(--brand-accent-2, {accent_2}) 0 8mm, transparent 8.4mm); background-size: 16mm 14mm;
    background-repeat: repeat-x; }}""",
        "mesh-corner": f"""
  .tag.pattern-mesh-corner {{ position: relative; }}
  .tag.pattern-mesh-corner::before {{ content: ""; position: absolute; right: -8mm; bottom: -8mm; width: 34mm; height: 34mm;
    z-index: 0; pointer-events: none; opacity: 0.14; background: radial-gradient(circle,
      var(--brand-accent-2, {accent_2}), transparent 64%); }}""",
    }
    block = blocks.get(pattern)
    if not block:
        return ""
    # 클래스명에 pattern id를 노출해 _motif_css 호출부 테스트가 식별 가능하게 한다
    return f"\n<style id=\"eventnametag-pattern\">{block}\n</style>"


def _accent_shape_css(brand: dict) -> str:
    """design.accent_shape 코너 강조 벡터 도형 CSS (P1-B). 미설정 시 빈 문자열."""
    shape = (brand.get("design") or {}).get("accent_shape")
    if not shape:
        return ""
    colors = brand.get("colors", {})
    accent_1 = colors.get("accent_1", colors.get("primary_dark", "#111111"))
    accent_2 = colors.get("accent_2", accent_1)
    # P1 가림 수정: 액센트 도형을 .tag 내부(배경 위 · 텍스트 아래, z-index:0)에 깐다
    if shape == "triangle":
        return f"""
<style id="eventnametag-accent-shape">
  .tag .accent-triangle {{ position: absolute; right: 0; top: 0; width: 0; height: 0; z-index: 0;
    border-top: 12mm solid var(--brand-accent-1, {accent_1}); border-left: 12mm solid transparent; opacity: 0.85; }}
</style>"""
    if shape == "blob":
        return f"""
<style id="eventnametag-accent-shape">
  .tag .accent-blob {{ position: absolute; right: 3mm; bottom: 3mm; width: 13mm; height: 13mm; z-index: 0;
    border-radius: 42% 58% 53% 47%; background: var(--brand-accent-2, {accent_2}); opacity: 0.55; }}
</style>"""
    return ""


def _motif_css(brand: dict) -> str:
    """visual_motif에 맞는 인쇄 안전 CSS 장식을 반환한다.

    P1-B: design.pattern / accent_shape 가 있으면 저잉크 벡터 장식 CSS를 덧붙인다.
    기존 visual_motif 분기와 충돌하지 않게 결과를 누적해 반환한다.
    """
    base = _motif_css_base(brand)
    return base + _pattern_css(brand) + _accent_shape_css(brand)


def _motif_css_base(brand: dict) -> str:
    """기존 visual_motif(STYLE_PACK) 기반 장식 CSS (P1 이전 동작)."""
    motif = (brand.get("visual_motif") or {}).get("type", "")
    colors = brand.get("colors", {})
    accent_1 = colors.get("accent_1", colors.get("primary_dark", "#111111"))
    accent_2 = colors.get("accent_2", accent_1)
    dark = colors.get("primary_dark", "#111111")
    if motif == "neon_grid":
        return f"""
<style>
.tag::before {{ content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .20;
  background-image: linear-gradient(90deg, {accent_2} 1px, transparent 1px), linear-gradient(0deg, {accent_1} 1px, transparent 1px);
  background-size: 8mm 8mm; mix-blend-mode: multiply; }}
.tag::after {{ content: ""; position: absolute; right: -10mm; bottom: -14mm; width: 38mm; height: 38mm;
  background: radial-gradient(circle, {accent_2}, transparent 62%); opacity: .40; }}
</style>"""
    if motif in ("confetti", "sticker_scene"):
        extra = ""
        if motif == "sticker_scene":
            extra = f"""
.tag .body::after {{ content: ""; position: absolute; right: 5mm; bottom: 4mm; width: 12mm; height: 12mm;
  border-radius: 42% 58% 53% 47%; background: {accent_2}; opacity: .92; transform: rotate(-8deg); box-shadow: inset 0 0 0 .45mm {dark}; }}
.tag .body::before {{ content: "✦"; position: absolute; right: 8.7mm; bottom: 7.4mm; z-index: 1; color: {dark};
  font: 900 5mm system-ui; }}
.mood-sticker, .sticker-face {{ display: none; }}
.body {{ position: relative; }}"""
        return f"""
<style>
.tag::before {{ content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .28;
  background-image: radial-gradient(circle at 12% 18%, {accent_1} 0 1.2mm, transparent 1.3mm),
    radial-gradient(circle at 86% 22%, {accent_2} 0 1.4mm, transparent 1.5mm),
    radial-gradient(circle at 74% 78%, {accent_1} 0 1mm, transparent 1.1mm),
    radial-gradient(circle at 18% 84%, {accent_2} 0 1.1mm, transparent 1.2mm); }}
.name {{ letter-spacing: -0.06em; }}
{extra}
</style>"""
    if motif == "recruiting_flow":
        return f"""
<style>
.tag::before {{ content: ""; position: absolute; left: 26mm; top: 8mm; right: 8mm; height: 1mm;
  background: linear-gradient(90deg, {accent_1}, {accent_2}); border-radius: 999px; opacity: .75; }}
.tag::after {{ content: "OPEN ROLE"; position: absolute; right: 5mm; bottom: 5mm; padding: 1mm 2mm;
  border-radius: 999px; background: {accent_2}; color: {dark}; font: 800 2.4mm ui-monospace, monospace; letter-spacing: .08em; }}
.role {{ color: {accent_1}; font-weight: 800; }}
</style>"""
    if motif == "gold_corner":
        return f"""
<style>
.tag::before {{ content: ""; position: absolute; right: 4mm; top: 4mm; width: 18mm; height: 18mm;
  border-top: 1.4mm solid {accent_1}; border-right: 1.4mm solid {accent_1}; opacity: .75; }}
.tag {{ box-shadow: inset 0 0 0 .35mm {accent_2}; }}
</style>"""
    if motif == "role_badge":
        return f"""
<style>
.role {{ display: inline-block; padding: 1.1mm 2.2mm; border-radius: 999px; background: {accent_1}; color: white; font-weight: 800; }}
.company {{ color: {dark}; }}
</style>"""
    if motif == "quiet_rule":
        return f"""
<style>
.body::before {{ content: ""; display: block; width: 18mm; height: .8mm; border-radius: 999px; background: {accent_1}; margin-bottom: 3mm; }}
</style>"""
    if motif == "qr_corner":
        return f"""
<style>
.tag::after {{ content: "LINK"; position: absolute; right: 5mm; bottom: 5mm; width: 13mm; height: 13mm;
  display: grid; place-items: center; border-radius: 2mm; border: .7mm solid {dark}; color: {dark};
  background: repeating-linear-gradient(45deg, white 0 1.2mm, {accent_2} 1.2mm 2.4mm); font: 900 2.3mm ui-monospace, monospace; }}
.intro {{ max-width: 58mm; }}
</style>"""
    return ""

# ─── 헤더 매핑 (Luma 호환) ───
HEADER_MAP = {
    "이름": "name", "name": "name", "성함": "name", "full name": "name",
    "회사": "company", "company": "company", "소속": "company",
    "organization": "company", "org": "company",
    "company name": "company", "affiliation": "company",
    "직무": "role", "role": "role", "직함": "role", "title": "role",
    "position": "role", "job title": "role",
    "소개": "intro", "intro": "intro", "bio": "intro",
    "한줄소개": "intro", "한 줄 소개": "intro",
    "about you": "intro", "about me": "intro",
    # P1: 버려지던 확장 필드 (track/interests/group) 별칭 — 헤더 있을 때만 채워짐
    "track": "track", "트랙": "track", "세션": "track",
    "interests": "interests", "관심사": "interests", "관심": "interests",
    "group": "group", "그룹": "group", "팀": "group",
}
HEADER_KEYWORDS = set(HEADER_MAP.keys())
HEADER_LOOKUP = {k.replace(" ", ""): v for k, v in HEADER_MAP.items()}

# ─── Skeleton 매핑 ───
SKELETON_FILES = {
    "r1": "r1-topbar.html",
    "r2": "r2-sidestrip.html",
    "r3": "r3-fullbleed.html",
    "r4": "r4-minimal.html",
}
ALL_SKELETONS = ["r1", "r2", "r3", "r4"]

# ─── 기본 토큰 fallback ───
DEFAULT_FONT_BODY = '"Inter", system-ui, -apple-system, sans-serif'
DEFAULT_FONT_MONO = 'ui-monospace, "SF Mono", Menlo, monospace'
DEFAULT_SIGNATURE_INNER = "#999999"
DEFAULT_SIGNATURE_OUTER = "#666666"


# ─────────────────────── State (라벨지 분기) ───────────────────────

def choose_label_paper_url() -> tuple[str, str]:
    """주문 CTA는 기본 탐사 A4 8칸 라벨지 하나만 제공한다."""
    return ("기본 탐사 A4 8칸 라벨지", COUPANG_STANDARD_URL)

def load_state() -> dict:
    """state.json 로드. 손상이면 백업 후 빈 dict (G7)."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = STATE_FILE.with_suffix(f".bak.{ts}.json")
        try:
            STATE_FILE.rename(backup)
            print(f"⚠️  state.json 손상 → {backup.name} 백업 (G7)", file=sys.stderr)
        except OSError:
            pass
        return {}


def save_state(state: dict) -> None:
    """state.json 저장. 디렉토리 자동 생성 (G8)."""
    USER_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────── Calibration profile (v0.2) ───────────────────────

def load_calibration() -> dict | None:
    """calibration.yaml 로드. 없거나 0,0이면 None (보정 단계 스킵).

    yaml 형식 예:
        x: 1.0  # 오른쪽 +, 왼쪽 -
        y: 2.0  # 아래쪽 +, 위쪽 -
    """
    if not CALIBRATION_FILE.exists():
        return None
    yaml_mod = require_yaml("calibration.yaml 읽기")
    try:
        data = yaml_mod.safe_load(CALIBRATION_FILE.read_text(encoding="utf-8")) or {}
    except (yaml_mod.YAMLError, OSError) as e:
        print(f"⚠️  calibration.yaml 읽기 실패: {e}", file=sys.stderr)
        return None
    try:
        x = float(data.get("x", 0))
        y = float(data.get("y", 0))
    except (TypeError, ValueError):
        return None
    if x == 0 and y == 0:
        return None
    return {"x": x, "y": y}


def ask_label_paper_once() -> None:
    """첫 실행 시 라벨지 준비를 먼저 확인한다.

    탐사 A4 8칸 라벨지는 물리 소모품이라, 오늘 주문하면 내일 받아 바로 인쇄할 수
    있다는 전제가 UX의 핵심이다. 다만 자동 실행/파이프 입력에서는 멈추지 않고
    진행한다.
    """
    if not sys.stdin.isatty():
        return

    state = load_state()
    if state.get("label_paper", {}).get("status") in ("ordered", "owned"):
        return  # 이미 답함

    print("\n잠깐! 이 스킬을 통해 행사용 네임택을 인쇄하려면 탐사 A4 8칸 라벨지 (99mm x 67.5mm)가 필요해요.", file=sys.stderr)
    print("오늘 주문하면 내일 받아 바로 출력할 수 있어요. 어떻게 진행할까요?", file=sys.stderr)
    print(file=sys.stderr)
    print("  1. 쿠팡에서 주문할게요", file=sys.stderr)
    print("  2. 라벨지를 이미 가지고 있어요", file=sys.stderr)
    print("  3. 라벨지는 나중에 준비하고, 행사 정보부터 입력할게요", file=sys.stderr)
    while True:
        try:
            ans = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n라벨지 확인을 건너뛰고 계속합니다.", file=sys.stderr)
            return
        if ans == "1":
            product_name, product_url = choose_label_paper_url()
            state.setdefault("label_paper", {})
            state["label_paper"]["status"] = "ordered"
            state["label_paper"]["product"] = product_name
            state["label_paper"]["answered_at"] = datetime.now().isoformat(timespec="seconds")
            save_state(state)
            print(f"\n🛒 Chrome에서 기본 탐사 A4 8칸 라벨지 구매 페이지를 엽니다.", file=sys.stderr)
            print(f"   {product_url}", file=sys.stderr)
            print("   이 링크는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.", file=sys.stderr)
            print("   라벨지 도착 후 다시 호출해 주세요. 다시 묻지 않습니다.", file=sys.stderr)
            open_url_in_chrome(product_url)
            sys.exit(0)
        elif ans == "2":
            state.setdefault("label_paper", {})
            state["label_paper"]["status"] = "owned"
            state["label_paper"]["answered_at"] = datetime.now().isoformat(timespec="seconds")
            save_state(state)
            print("\n✅ 라벨지 보유 확인. 이제 BI를 등록하시거나 행사 네임택을 만드실 수 있습니다.", file=sys.stderr)
            return
        elif ans == "3":
            print("\n좋습니다. 행사명, 원하는 무드, BI/브랜드 단서를 자유롭게 입력해 주세요.", file=sys.stderr)
            print("이미지, 웹사이트 URL, 로고 파일, 디자인 가이드 md, 참고 문서도 괜찮습니다.", file=sys.stderr)
            return
        else:
            print("1, 2, 또는 3을 입력해 주세요.", file=sys.stderr)


def order_paper() -> None:
    """쿠팡 라벨지 페이지 자동 오픈 + state 갱신."""
    product_name, product_url = choose_label_paper_url()
    state = load_state()
    state.setdefault("label_paper", {})
    state["label_paper"]["status"] = "ordered"
    state["label_paper"]["product"] = product_name
    state["label_paper"]["last_order_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    print(f"🛒 Chrome에서 기본 탐사 A4 8칸 라벨지 구매 페이지를 엽니다.", file=sys.stderr)
    print(f"   {product_url}", file=sys.stderr)
    print("   이 링크는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.", file=sys.stderr)
    open_url_in_chrome(product_url)


# ─────────────────────── BI yaml 로드 ───────────────────────

def find_brand_yaml(slug: str) -> Path | None:
    """slug로 BI yaml 검색. 사용자 외부 디렉토리 → examples 순."""
    candidates = [
        USER_BRANDS_DIR / f"{slug}.yaml",
        USER_BRANDS_DIR / f"{slug}.yml",
        EXAMPLES_DIR / f"{slug}.yaml",
        EXAMPLES_DIR / f"{slug}.yml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def list_available_brands() -> dict[str, list[str]]:
    """사용 가능한 BI 목록을 examples / user 분리해서 반환."""
    result: dict[str, list[str]] = {"examples": [], "user": []}
    if EXAMPLES_DIR.exists():
        result["examples"] = sorted(p.stem for p in EXAMPLES_DIR.glob("*.yaml"))
    if USER_BRANDS_DIR.exists():
        result["user"] = sorted(p.stem for p in USER_BRANDS_DIR.glob("*.yaml"))
    return result


def load_brand(slug: str) -> dict:
    """slug로 BI yaml 로드 + schema 검증 (G1)."""
    yaml_mod = require_yaml("BI yaml 로드")
    path = find_brand_yaml(slug)
    if path is None:
        avail = list_available_brands()
        msg = [f"✗ BI '{slug}' 찾을 수 없음."]
        if avail["examples"]:
            msg.append(f"   examples: {', '.join(avail['examples'])}")
        if avail["user"]:
            msg.append(f"   user:     {', '.join(avail['user'])}")
        else:
            msg.append(f"   user:     (없음 — ~/.config/eventnametag/brands/ 비어 있음)")
        msg.append(f"   풀 예시 → {EXAMPLES_DIR}/delta-society.yaml")
        print("\n".join(msg), file=sys.stderr)
        sys.exit(1)

    try:
        data = yaml_mod.safe_load(path.read_text(encoding="utf-8"))
    except yaml_mod.YAMLError as e:
        print(f"✗ yaml 파싱 실패 ({path}): {e}", file=sys.stderr)
        sys.exit(1)

    # G1: schema 검증
    if jsonschema is not None and SCHEMA_FILE.exists():
        try:
            schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            print(f"✗ BI yaml schema 검증 실패 ({path}):", file=sys.stderr)
            print(f"   {e.message}", file=sys.stderr)
            print(f"   풀 예시 → {EXAMPLES_DIR}/delta-society.yaml", file=sys.stderr)
            sys.exit(1)
    else:
        print("⚠️  jsonschema 미설치 — BI 검증 skip. `pip install jsonschema` 권장.", file=sys.stderr)

    return data


def validate_brand_only(yaml_path: str) -> None:
    """--validate 모드: yaml schema 검증만 수행."""
    yaml_mod = require_yaml("BI yaml 검증")
    path = Path(yaml_path)
    if not path.exists():
        print(f"✗ 파일 없음: {path}", file=sys.stderr)
        sys.exit(1)
    if jsonschema is None:
        print("✗ jsonschema 미설치 — `pip install jsonschema`", file=sys.stderr)
        sys.exit(2)
    try:
        data = yaml_mod.safe_load(path.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        jsonschema.validate(data, schema)
    except (yaml_mod.YAMLError, jsonschema.ValidationError) as e:
        print(f"✗ 검증 실패: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"✓ {path.name} schema 검증 통과", file=sys.stderr)


# ─────────────────────── 명단 파싱 ───────────────────────

def _looks_mojibake(text: str) -> bool:
    """인코딩 깨짐(BOM·euc-kr/cp1252 오해석) 휴리스틱.

    UTF-8 한글을 cp1252/latin-1로 잘못 해석하면 Latin-1 보충·확장 영역 문자가
    **2자 이상 연속**으로 나타난다(예: '안녕' → 'ì•ˆë…•'). 반면 정상 악센트 라틴
    이름(Zoë, Renée, Müller)은 해당 문자가 단독으로만 쓰이므로, 연속 run 길이로
    오탐을 피한다. U+FFFD(대체문자)·BOM은 고신뢰 신호라 단독이어도 의심한다.
    """
    if not text:
        return False
    if "﻿" in text or "�" in text:
        return True
    # cp1252/latin-1 오해석 시 한글은 Latin-1 보충/확장-A(U+0080–U+024F)와
    # cp1252 punctuation 문자가 2자 이상 연속으로 나타난다. 정상 악센트 라틴
    # 이름(Zoë 등)은 단독이므로 연속 run >= 2 일 때만 인코딩 의심으로 본다.
    _cp1252_punct = (
        "ˆ˜–—‘’‚“”„†"
        "‡•…‰‹›€™ŒœŠ"
        "šŽžŸ"
    )
    run = 0
    for ch in text:
        if 0x80 <= ord(ch) <= 0x24F or ch in _cp1252_punct:
            run += 1
            if run >= 2:
                return True
        else:
            run = 0
    return False


def parse_attendees(text: str) -> tuple[list[dict], dict]:
    """TSV/CSV/이름만 모두 자동 감지.

    반환값은 (kept, dropped) 튜플.
    - kept: 이름이 있는 정상 참석자 레코드 리스트
    - dropped: 제외 사유별 카운트 dict (P0-B 명단 무결성 보고용)
      키: empty_name(빈 이름) / few_columns(컬럼 부족) /
          encoding(인코딩 의심) / header_skip(헤더로 추정되어 skip)
    """
    dropped = {"empty_name": 0, "few_columns": 0, "encoding": 0,
               "header_skip": 0, "encoding_warn": 0}
    text = text.strip()
    if not text:
        return [], dropped

    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return [], dropped

    first = lines[0]
    if "\t" in first:
        delim = "\t"
    elif "," in first:
        delim = ","
    else:
        # 이름만 모드: 줄 전체가 이름이므로 절대 drop하지 않는다(사람을 잃지 않음).
        # 인코딩 의심이어도 유지하고, drop이 아닌 경고(encoding_warn)로만 보고한다.
        result = []
        for l in lines:
            name = l.strip()
            result.append({"name": name, "company": "", "role": "", "intro": ""})
            if _looks_mojibake(name):
                dropped["encoding_warn"] += 1
        return result, dropped

    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return [], dropped

    first_row_normalized = {c.strip().lower().replace(" ", "") for c in rows[0]}
    normalized_keywords = {k.replace(" ", "") for k in HEADER_KEYWORDS}
    has_header = bool(first_row_normalized & normalized_keywords)

    if has_header:
        headers_raw = [c.strip().lower().replace(" ", "") for c in rows[0]]
        mapped_cols = [HEADER_LOOKUP.get(h) for h in headers_raw]
        data_rows = rows[1:]
        dropped["header_skip"] += 1  # 첫 행을 헤더로 추정하여 제외
    else:
        mapped_cols = ["name", "company", "role", "intro"]
        data_rows = rows

    # name 컬럼이 매핑된 인덱스 (컬럼 부족 판별용)
    name_idx = mapped_cols.index("name") if "name" in mapped_cols else 0

    result = []
    for row in data_rows:
        # P1: 확장 필드(track/interests/group)도 보존 — 헤더로 매핑될 때만 채워짐
        rec = {"name": "", "company": "", "role": "", "intro": "",
               "track": "", "interests": "", "group": ""}
        for i, col in enumerate(mapped_cols):
            if col and i < len(row) and col in rec:
                rec[col] = row[i].strip()
        if rec["name"]:
            result.append(rec)
            continue
        # 이름이 비어 사유 분류: 인코딩 의심 → 컬럼 부족 → 빈 이름 순
        joined = " ".join(c for c in row)
        if _looks_mojibake(joined):
            dropped["encoding"] += 1
        elif len(row) <= name_idx:
            dropped["few_columns"] += 1
        else:
            dropped["empty_name"] += 1
    return result, dropped


def format_parse_summary(kept_count: int, dropped: dict) -> str:
    """명단 파싱 결과 한 줄 요약 문자열.

    제외가 0이면 `✓ 명단 N명 파싱`만, 제외가 있으면
    `✓ 명단 N명 파싱 (⚠ M행 제외: 빈 이름 a / 컬럼 부족 b / 인코딩 의심 c / 헤더 추정 d)`.
    P0-B: 기존 출력 라인을 확장해 입력 대비 제외된 행수·사유를 함께 보고한다.
    """
    base = f"✓ 명단 {kept_count}명 파싱"
    enc_warn = dropped.get("encoding_warn", 0)
    # encoding_warn은 '유지된' 행이므로 제외 합계에서 분리한다.
    drop_only = {k: v for k, v in dropped.items() if k != "encoding_warn"}
    total_dropped = sum(drop_only.values())
    suffix = ""
    if total_dropped:
        parts = []
        if drop_only.get("empty_name"):
            parts.append(f"빈 이름 {drop_only['empty_name']}")
        if drop_only.get("few_columns"):
            parts.append(f"컬럼 부족 {drop_only['few_columns']}")
        if drop_only.get("encoding"):
            parts.append(f"인코딩 의심 {drop_only['encoding']}")
        if drop_only.get("header_skip"):
            parts.append(f"헤더 추정 {drop_only['header_skip']}")
        suffix += f" (⚠ {total_dropped}행 제외: {' / '.join(parts)})"
    if enc_warn:
        suffix += f" (⚠ 인코딩 의심 {enc_warn}명 — 유지됨, 원본 인코딩 확인 권장)"
    return base + suffix


def name_font_size(name: str) -> str:
    n = len(name)
    if n <= 5:
        return "14mm"
    elif n <= 7:
        return "11mm"
    elif n <= 9:
        return "9mm"
    else:
        return "7mm"


def company_font_size(company: str) -> str:
    n = len(company)
    if n <= 8:
        return "5.5mm"
    elif n <= 12:
        return "4.5mm"
    else:
        return "3.6mm"


def apply_case(text: str, case: str) -> str:
    """워드마크 case 적용."""
    if case == "upper":
        return text.upper()
    elif case == "lower":
        return text.lower()
    return text  # title


# ─────────────────────── BI 토큰 → CSS 변수 inject ───────────────────────

def inject_brand_tokens(template_html: str, brand: dict) -> str:
    """template HTML의 {{BRAND_*}} placeholder를 BI yaml 값으로 치환."""
    colors = brand["colors"]
    fonts = brand.get("fonts") or {}
    body_font = fonts.get("body") or {}
    mono_font = fonts.get("mono") or {}
    signature = brand.get("signature") or {"type": "none"}
    sig_grad = signature.get("gradient") or {}

    body_family = body_font.get("family", "")
    body_fallback = body_font.get("fallback", DEFAULT_FONT_BODY)
    if body_family:
        body_full = f'"{body_family}", {body_fallback}'
    else:
        body_full = body_fallback

    mono_family = mono_font.get("family", "")
    mono_fallback = mono_font.get("fallback", DEFAULT_FONT_MONO)
    if mono_family:
        mono_full = f'"{mono_family}", {mono_fallback}'
    else:
        mono_full = mono_fallback

    replacements = {
        "{{BRAND_DARK}}": colors["primary_dark"],
        "{{BRAND_LIGHT}}": colors["primary_light"],
        "{{BRAND_ACCENT_1}}": colors.get("accent_1", colors["primary_dark"]),
        "{{BRAND_ACCENT_2}}": colors.get("accent_2", colors["primary_dark"]),
        "{{BRAND_SURFACE_SUBTLE}}": colors.get("surface_subtle", colors["primary_dark"]),
        "{{BRAND_FONT_BODY}}": body_full,
        "{{BRAND_FONT_MONO}}": mono_full,
        "{{SIGNATURE_INNER}}": sig_grad.get("inner", DEFAULT_SIGNATURE_INNER),
        "{{SIGNATURE_OUTER}}": sig_grad.get("outer", DEFAULT_SIGNATURE_OUTER),
    }
    for placeholder, value in replacements.items():
        template_html = template_html.replace(placeholder, value)
    return template_html


# ─────────────────────── Cell 빌드 ───────────────────────

# ─────────────────────── v0.6: AI 셀 템플릿 (검증·치환) ───────────────────────
# AI(호출 에이전트)가 brand design.cell_template에 셀 한 칸 전체를 조판한다.
# 코드는 검증(슬롯·textzone·sanitize·예약셀렉터)→실제폰트 텍스트 치환→렌더의 결정론적 소비자.

# 텍스트존 메타: 이름 텍스트가 놓이는 영역을 셀 기준 분수 좌표로 선언. G9 대비검사 영역.
_TEXTZONE_RE = re.compile(
    r"<!--\s*textzone:\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*-->",
    re.IGNORECASE,
)
# 셀 템플릿 토큰: 코드가 실제 텍스트로 치환하는 슬롯.
_TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z_]+)\s*\}\}")
_ALLOWED_TEMPLATE_TOKENS = {
    "name", "company", "role", "intro", "track", "group", "event",
    "name_size", "company_size",
}
# <svg>…</svg> 블록 (sanitize_svg 적용 단위).
_SVG_BLOCK_RE = re.compile(r"<svg\b.*?</svg\s*>", re.IGNORECASE | re.DOTALL)
_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.IGNORECASE | re.DOTALL)
# 현장 수기용 공백은 진짜 공백이어야 한다. 밑줄/점선/가이드라인은 밤티처럼 보이고,
# 실제 네임펜 필기 방향·크기 선택도 방해하므로 AI 템플릿 단계에서 막는다.
_WRITING_GUIDE_RE = re.compile(
    r"border-(?:bottom|top)\s*:|text-decoration\s*:\s*underline|\b(?:dashed|dotted)\b|점선|밑줄",
    re.IGNORECASE,
)
# 네임택은 포스터/초대장이 아니다. 장소·주소·층수는 칸을 잡아먹으므로 기본 금지.
_VENUE_COPY_RE = re.compile(r"\b(?:venue|location|place|address)\b|장소|주소|오피스|office|층\b|\d+F\b|\d+층", re.IGNORECASE)
# SVG 제거 후 잔여 텍스트에서 거부할 위험 패턴 (외부 리소스/스크립트/핸들러).
# 내부 SVG 조각 참조 url(#id)는 svg 블록 안이라 이미 제거됨 → 잔여 url(은 외부만 의심.
_OUTER_DANGER_RE = re.compile(
    r"(<script\b|<iframe\b|<foreignobject\b|<object\b|<embed\b|<link\b"
    r"|javascript:|@import|data:image/|on\w+\s*=|https?://"
    r"|position\s*:\s*fixed"
    r"|url\s*\(\s*['\"]?\s*(?:https?:|//|data:))",
    re.IGNORECASE,
)
# <style> 안에서 침범 금지 예약 셀렉터 (셀 경계 불변식 1 보호).
# (?![-\w]): \b는 .cell 뒤 하이픈(비단어문자) 앞에서 발동해 .cell-name 같은 BEM 클래스를
# 오탐 거부한다. 음수 lookahead로 .cell/.a4-sheet 정확매치만 잡고 .cell-name/.cellophane은 통과.
_RESERVED_SELECTOR_RE = re.compile(
    r"(?:^|[\s,{}>])(?:html|body|@page|\.a4-sheet|\.cell)(?![-\w])",
    re.IGNORECASE,
)


def _parse_textzone(template: str) -> tuple[float, float, float, float] | None:
    """템플릿에서 textzone 메타를 파싱한다. (x0,y0,x1,y1) 분수 또는 None(없음/무효)."""
    m = _TEXTZONE_RE.search(template)
    if not m:
        return None
    try:
        x0, y0, x1, y1 = (float(g) for g in m.groups())
    except ValueError:
        return None
    coords = (x0, y0, x1, y1)
    if any(c < 0.0 or c > 1.0 for c in coords):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return coords


def _all_template_svgs_clean(template: str) -> bool:
    """템플릿 안 모든 <svg> 블록이 sanitize_svg를 비지 않게 통과하는지.
    lenient: sanitize가 ''(wholesale 거부)일 때만 False. 내부 script 등은 sanitize가
    스트립하므로 통과하되 fill_template이 렌더 시 동일 sanitize로 정화한다.
    중첩 <svg>는 비지원(AI 출력에서 비정상 패턴) — non-greedy 매치라 바깥 닫힘태그가
    잔여에 남지만 무해하고, fill이 렌더 시 재정화한다."""
    import _svg_safe  # 지연 import
    for m in _SVG_BLOCK_RE.finditer(template):
        if not _svg_safe.sanitize_svg(m.group(0)):
            return False
    return True


def validate_cell_template(template: str, brand: dict | None = None) -> tuple[bool, tuple | None, str]:
    """AI 셀 템플릿을 검증한다. 반환: (ok, textzone, reason).

    규칙(불변식 보호): {{name}} 필수 · 허용 토큰만 · textzone 유효 ·
    모든 SVG sanitize 통과 · 외부 리소스/스크립트/핸들러 없음 ·
    <style>이 셀 경계(html/body/.cell/.a4-sheet/@page) 침범 안 함.
    brand: 향후 per-brand 토큰 허용목록/대비 검증용 (현재 미사용 — 호출부 시그니처 안정성)."""
    if not template or not template.strip():
        return (False, None, "빈 템플릿")
    tokens = set(_TEMPLATE_TOKEN_RE.findall(template))
    if "name" not in tokens:
        return (False, None, "{{name}} 슬롯 없음")
    unknown = tokens - _ALLOWED_TEMPLATE_TOKENS
    if unknown:
        return (False, None, f"허용되지 않은 토큰: {sorted(unknown)}")
    tz = _parse_textzone(template)
    if tz is None:
        return (False, None, "textzone 메타 없음/무효")
    x0, y0, x1, y1 = tz
    if (x1 - x0) * (y1 - y0) < 0.60 or (y1 - y0) < 0.58:
        return (False, None, "이름/소속 작성 공백이 전체 셀의 2/3 기준에 못 미침")
    if _WRITING_GUIDE_RE.search(template):
        return (False, None, "작성 공백에 밑줄/점선/가이드라인 사용 금지")
    if _VENUE_COPY_RE.search(template):
        return (False, None, "네임택에는 장소명/주소/층수 문구를 넣지 않음")
    if not _all_template_svgs_clean(template):
        return (False, None, "위험한 SVG (sanitize 거부)")
    # SVG 블록을 제거한 잔여에서 외부 위험 + 예약 셀렉터를 검사한다. svg 내부의 <style>·url은
    # sanitize_svg 영역이므로 잔여 스캔에서 제외해 오탐(예: svg clip-path .cell)을 피한다.
    remainder = _SVG_BLOCK_RE.sub(" ", template)
    if _OUTER_DANGER_RE.search(remainder):
        return (False, None, "외부 리소스/스크립트/이벤트 핸들러 포함")
    for style_body in _STYLE_BLOCK_RE.findall(remainder):
        if _RESERVED_SELECTOR_RE.search(style_body):
            return (False, None, "예약 셀렉터(html/body/.cell/.a4-sheet/@page) 침범")
    return (True, tz, "ok")


def _sanitize_template_svgs(template: str) -> str:
    """템플릿 안 모든 <svg> 블록을 sanitize_svg 결과로 치환한다(빈 결과는 제거).
    검증 후 호출되므로 정상 템플릿은 모두 비지 않은 결과를 받는다."""
    import _svg_safe  # 지연 import
    return _SVG_BLOCK_RE.sub(lambda m: _svg_safe.sanitize_svg(m.group(0)) or "", template)


def fill_template(template: str, att: dict, brand: dict, event: str) -> str:
    """검증된 AI 셀 템플릿의 토큰을 실제 폰트 텍스트로 치환한다.

    SVG는 sanitize 결과로 치환 후, 텍스트 토큰을 html.escape된 값으로 채운다.
    글자 내용은 코드가 박으므로 오타·흐림 없음(불변식 2). 사이즈 토큰은 기존
    name_font_size/company_font_size 램프를 재사용해 긴 이름 셀 침범을 막는다.
    호출 전제: validate_cell_template를 통과한 템플릿만 전달한다(미검증 토큰은 ''로 조용히 드롭 — 렌더 중단 방지). brand 인자는 미사용(build_cell 호출부 시그니처 통일용)."""
    out = _sanitize_template_svgs(template)
    name = att.get("name", "")
    company = att.get("company", "")
    values = {
        "name": html_mod.escape(name),
        "company": html_mod.escape(company),
        "role": html_mod.escape(att.get("role", "")),
        "intro": html_mod.escape(att.get("intro", "")),
        "track": html_mod.escape(att.get("track", "")),
        "group": html_mod.escape(att.get("group", "")),
        "event": html_mod.escape(event),
        "name_size": name_font_size(name),
        "company_size": company_font_size(company),
    }
    return _TEMPLATE_TOKEN_RE.sub(lambda m: values.get(m.group(1), ""), out)


def _brand_without_cell_template(brand: dict) -> dict:
    """cell_template만 제거한 brand 얕은 복제본 (명시 floor override·강도하향용).
    원본 brand는 변형하지 않는다. design 외 키는 공유 참조 유지."""
    out = dict(brand)
    design = dict(out.get("design") or {})
    design.pop("cell_template", None)
    out["design"] = design
    return out


def build_signature_html(brand: dict) -> str:
    """yaml signature 정의에 따라 cell 안 시그니처 HTML 조각 반환. none이면 빈 문자열."""
    sig = brand.get("signature") or {"type": "none"}
    sig_type = sig.get("type", "none")
    if sig_type == "none":
        return ""
    if sig_type == "gradient_orb":
        size = sig.get("size_mm", 3.5)
        return f'<span class="signature-orb" style="width: {size}mm; height: {size}mm;"></span>'
    if sig_type == "icon_url":
        url = html_mod.escape(sig.get("icon_url", ""))
        size = sig.get("size_mm", 3.5)
        return f'<img class="signature-icon" src="{url}" alt="" style="width: {size}mm; height: {size}mm;">'
    return ""


LAYOUT_VARIANTS = ("diagonal", "name_hero", "intro_hero", "badge_first")
# P1-B: 벡터 장식 선택지 (schema design enum과 동일하게 유지)
PATTERN_IDS = ("dot-grid", "stripe", "wave", "mesh-corner")
ACCENT_SHAPE_IDS = ("triangle", "blob")


def _available_motif_ids() -> list[str]:
    """내장 모티프 ID 목록 (argparse choices용). _motifs 미존재 시 빈 목록."""
    try:
        import _motifs
        return _motifs.list_motifs()
    except Exception:
        return []


def apply_design_overrides(brand: dict, *, pattern: str | None = None,
                           accent_shape: str | None = None, motif_id: str | None = None) -> dict:
    """CLI 플래그로 brand.design 필드를 오버라이드한다 (Codex parity).

    우선순위: CLI 플래그 > brand.design.* > 없음. None 인자는 무시(brand 값 유지).
    원본 brand를 변형하지 않고 design 섹션만 얕은 복제해 갱신한 dict를 반환한다.
    """
    if pattern is None and accent_shape is None and motif_id is None:
        return brand
    out = dict(brand)
    design = dict(out.get("design") or {})
    if pattern is not None:
        design["pattern"] = pattern
    if accent_shape is not None:
        design["accent_shape"] = accent_shape
    if motif_id is not None:
        design["motif_id"] = motif_id
    out["design"] = design
    return out


def _minimal_brand_for_test() -> dict:
    """테스트용 최소 brand dict (PyYAML 비의존). build_cell 호출에 필요한 키만."""
    return {
        "name": "테스트브랜드",
        "colors": {"primary_dark": "#0a0a0b", "primary_light": "#ffffff",
                   "accent_1": "#2563eb", "accent_2": "#22d3ee"},
        "wordmark": {"text": "TESTBRAND", "case": "upper"},
        "signature": {"type": "none"},
    }


def _wordmark_html(brand: dict) -> str:
    """워드마크 슬롯 HTML.

    design.logo_svg_inline가 있으면 새니타이즈 후 인라인 SVG 로고로 워드마크 텍스트를
    대체한다. 없거나 새니타이즈 결과가 비면 기존 signature + 워드마크 텍스트로 fallback.
    """
    logo_raw = (brand.get("design") or {}).get("logo_svg_inline") or ""
    if logo_raw:
        import _svg_safe  # 지연 import (테스트·CLI 양쪽에서 동작)
        clean = _svg_safe.sanitize_svg(logo_raw)
        if clean:
            return f'<div class="brand-wrap"><span class="brand-logo">{clean}</span></div>'
    sig_html = build_signature_html(brand)
    wordmark = brand.get("wordmark", {})
    wm_text = html_mod.escape(apply_case(wordmark.get("text", ""), wordmark.get("case", "title")))
    return f'<div class="brand-wrap">{sig_html}<span>{wm_text}</span></div>'


def _illustration_html(brand: dict) -> str:
    """일러스트 슬롯 HTML (P1-C). 우선순위:
    sanitize_svg(design.illustration_svg_inline) > sanitize_svg(_motifs.get_motif(motif_id)) > 없음.

    셀 레이아웃을 침범하지 않게 .illustration-slot 장식 레이어(절대배치)로 감싼다.
    새니타이즈 결과가 비면 미표시(빈 문자열).
    """
    design = brand.get("design") or {}
    inline_raw = design.get("illustration_svg_inline") or ""
    motif_id = design.get("motif_id") or ""
    if not inline_raw and not motif_id:
        return ""

    import _svg_safe  # 지연 import
    # 1) 인라인 일러스트 우선
    if inline_raw:
        clean = _svg_safe.sanitize_svg(inline_raw)
        if clean:
            return f'<span class="illustration-slot">{clean}</span>'
    # 2) 내장 모티프 라이브러리 fallback
    if motif_id:
        import _motifs  # 지연 import
        clean = _svg_safe.sanitize_svg(_motifs.get_motif(motif_id))
        if clean:
            return f'<span class="illustration-slot">{clean}</span>'
    return ""


def _body_parts_for_variant(att: dict, layout_variant: str) -> list[str]:
    """variant별 .body 내부 요소를 조립해 반환. base 좌표(셀 크기·grid)는 불변,
    셀 안쪽 강조 순서/배지만 달라진다."""
    name = html_mod.escape(att.get("name", ""))
    company = html_mod.escape(att.get("company", ""))
    role = html_mod.escape(att.get("role", ""))
    intro = html_mod.escape(att.get("intro", ""))
    interests = html_mod.escape(att.get("interests", ""))
    track = html_mod.escape(att.get("track", ""))
    group = html_mod.escape(att.get("group", ""))

    name_block = f'      <div class="name" style="font-size: {name_font_size(att.get("name", ""))}">{name}</div>'
    company_block = (f'      <div class="company" style="font-size: {company_font_size(att.get("company", ""))}">{company}</div>'
                     if company else "")
    role_block = f'      <div class="role">{role}</div>' if role else ""
    intro_block = f'      <div class="intro">{intro}</div>' if intro else ""

    parts: list[str] = []
    if layout_variant == "intro_hero":
        # 소개·관심사를 이름 아래 강조 블록으로 상단 배치 (네트워킹·커뮤니티)
        parts.append(name_block)
        hero_lines = [t for t in (intro, interests) if t]
        if hero_lines:
            inner = "".join(f'<span class="intro-hero-line">{t}</span>' for t in hero_lines)
            parts.append(f'      <div class="intro-hero">{inner}</div>')
        if company_block:
            parts.append(company_block)
        if role_block:
            parts.append(role_block)
    elif layout_variant == "badge_first":
        # 역할/트랙 배지를 셀 상단에 먼저 강조 (채용·스피커·스태프)
        badges = [t for t in (track, group) if t]
        if badges:
            inner = "".join(f'<span class="badge">{t}</span>' for t in badges)
            parts.append(f'      <div class="badge-row">{inner}</div>')
        parts.append(name_block)
        if company_block:
            parts.append(company_block)
        if role_block:
            parts.append(role_block)
        if intro_block:
            parts.append(intro_block)
    else:
        # name_hero (기본·현행) — 이름 최대 → 회사 → 직무 → 소개
        parts.append(name_block)
        if company_block:
            parts.append(company_block)
        if role_block:
            parts.append(role_block)
        if intro_block:
            parts.append(intro_block)
    return parts


def _diagonal_cell_inner(att: dict, brand: dict, event: str) -> str:
    """diagonal 변형의 셀 내부(.dcell) HTML을 조립한다 (검증된 대각 컬러블록 시안).

    좌상단 네이비 대각 블록 + 우하단 액센트 삼각 위에, 어두운 블록 위 헤더와
    중앙 본문을 얹는다. 하드코딩색은 모두 브랜드 토큰(var(--brand-*))으로 들어가
    어떤 브랜드든 대비가 보장된다. 셀 크기·grid 등 base 좌표는 건드리지 않는다.
    """
    event_upper = html_mod.escape(event).upper()
    brand_wrap = _wordmark_html(brand)  # 로고/워드마크 조립 재사용 (logo_svg_inline·orb 동작)

    name = html_mod.escape(att.get("name", ""))
    company = html_mod.escape(att.get("company", ""))
    role = html_mod.escape(att.get("role", ""))
    intro = html_mod.escape(att.get("intro", ""))
    # 배지는 track > group 순으로 있을 때만 노출 (없으면 미표시)
    badge_val = att.get("track") or att.get("group") or ""
    badge = html_mod.escape(badge_val)

    parts = [
        '  <div class="dcell">',
        '    <div class="diag-top"></div>',      # 좌상단 네이비 대각 블록
        '    <div class="diag-corner"></div>',   # 우하단 액센트 대각 삼각
        '    <div class="dhead">',
        f'      {brand_wrap}',
    ]
    if event_upper:
        parts.append(f'      <span class="devent">{event_upper}</span>')
    parts.append('    </div>')
    parts.append('    <div class="dbody">')
    if badge:
        parts.append(f'      <span class="dbadge">{badge}</span>')
    # 긴 이름·회사명은 기존 폰트 크기 로직으로 축소해 셀 침범 방지
    parts.append(f'      <span class="dname" style="font-size: {name_font_size(att.get("name", ""))}">{name}</span>')
    if company:
        parts.append(f'      <span class="dcompany" style="font-size: {company_font_size(att.get("company", ""))}">{company}</span>')
    if role:
        parts.append(f'      <span class="drole">{role}</span>')
    if intro:
        parts.append(f'      <span class="dintro">{intro}</span>')
    parts.append('    </div>')
    parts.append('  </div>')
    return "\n".join(parts)


def build_cell(att: dict | None, brand: dict, event: str, layout_variant: str = "diagonal") -> str:
    """한 셀 HTML. attendee=None이면 빈 셀, 있으면 BI 워드마크 + signature + 본문.

    layout_variant: diagonal(기본·검증된 대각 컬러블록) / name_hero(이름 강조) /
    intro_hero(소개·관심사 강조) / badge_first(역할·트랙 배지 상단 강조). 셀 크기·grid
    등 base 좌표는 불변이고 셀 안쪽 DOM 구성/강조만 바뀐다.
    """
    if not att:
        return '<div class="cell empty"></div>'

    # v0.6: AI 셀 템플릿 우선. 유효하면 셀 전체를 AI 디자인으로, 무효면 스켈레톤 floor로 통과.
    cell_template = (brand.get("design") or {}).get("cell_template")
    if cell_template:
        ok, _tz, _reason = validate_cell_template(cell_template, brand)
        if ok:
            filled = fill_template(cell_template, att, brand, event)
            return f'<div class="cell variant-ai">\n{filled}\n</div>'

    if layout_variant not in LAYOUT_VARIANTS:
        layout_variant = "diagonal"

    # diagonal은 topbar/body 대신 독립 .dcell 구조를 쓴다 (검증된 시안 재현)
    if layout_variant == "diagonal":
        inner = _diagonal_cell_inner(att, brand, event)
        return f'<div class="cell variant-diagonal">\n{inner}\n</div>'

    event_upper = html_mod.escape(event).upper()
    brand_wrap = _wordmark_html(brand)

    design = brand.get("design") or {}
    # P1-B: 셀 루트 클래스에 패턴 id를 실어 _pattern_css의 .pattern-* 선택자와 맞춘다
    pattern = design.get("pattern")
    pattern_cls = f" pattern-{pattern}" if pattern else ""
    accent_shape = design.get("accent_shape")

    parts = [
        f'<div class="cell variant-{layout_variant}">',
        # P1 가림 수정: pattern 클래스를 .tag에 부여해 ::before 장식이 .tag 불투명 배경
        # '위'에 깔리게 한다. (이전엔 .cell에 붙어 .tag가 전부 가렸음)
        f'  <div class="tag{pattern_cls}">',
    ]
    # P1-B: 코너 강조 벡터 도형 — .tag 첫 자식(배경 위 · 텍스트 아래)으로 깐다
    if accent_shape in ("triangle", "blob"):
        parts.append(f'    <span class="accent-{accent_shape}"></span>')
    # P1-C: 일러스트 슬롯 — .tag 내부 장식 레이어(배경 위 · 텍스트 아래)
    illustration = _illustration_html(brand)
    if illustration:
        parts.append(f'    {illustration}')
    parts.extend([
        '    <div class="topbar">',
        f'      {brand_wrap}',
    ])
    if event_upper:
        parts.append(f'      <div class="event">{event_upper}</div>')
    parts.append('    </div>')
    parts.append('    <div class="body">')
    parts.extend(_body_parts_for_variant(att, layout_variant))
    parts.append('    </div>')
    parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


def build_blank_cell(brand: dict, event: str) -> str:
    """현장 수기용 빈 네임택 — 워드마크만 + 2/3 이상 백지 본문. 장소/행사 세부문구 금지."""
    wordmark = brand.get("wordmark", {})
    wm_text = html_mod.escape(apply_case(wordmark.get("text", ""), wordmark.get("case", "title")))
    sig_html = build_signature_html(brand)

    parts = [
        '<div class="cell blank-cell">',
        '  <div class="tag blank-tag">',
        '    <div class="topbar blank-topbar">',
        f'      <div class="brand-wrap">{sig_html}<span>{wm_text}</span></div>',
    ]
    parts.append('    </div>')
    parts.append('    <div class="body blank-body"></div>')
    parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


def resolve_layout_variant(brand: dict, override: str | None = None) -> str:
    """적용할 layout_variant 결정. 우선순위: CLI override > brand.design.layout_variant > diagonal(기본)."""
    if override in LAYOUT_VARIANTS:
        return override
    design_variant = (brand.get("design") or {}).get("layout_variant")
    if design_variant in LAYOUT_VARIANTS:
        return design_variant
    return "diagonal"


def build_pages(attendees: list[dict], brand: dict, event: str, fill_blanks: bool = False,
                layout_variant: str | None = None) -> str:
    """8명씩 페이지 분할."""
    if not attendees:
        return ""
    variant = resolve_layout_variant(brand, layout_variant)
    # v0.6: --layout-variant 명시 = floor 강제 → AI 셀 템플릿 건너뜀(스켈레톤 디버그/보수 모드).
    cell_brand = brand
    if layout_variant is not None and (brand.get("design") or {}).get("cell_template"):
        cell_brand = _brand_without_cell_template(brand)
    pages = []
    for i in range(0, len(attendees), 8):
        batch = attendees[i:i + 8]
        padded = batch + [None] * (8 - len(batch))
        cell_htmls = []
        for a in padded:
            if a is not None:
                cell_htmls.append(build_cell(a, cell_brand, event, layout_variant=variant))
            elif fill_blanks:
                cell_htmls.append(build_blank_cell(cell_brand, ""))
            else:
                cell_htmls.append('<div class="cell empty"></div>')
        cells = "\n".join(cell_htmls)
        pages.append(f'<div class="a4-sheet">\n{cells}\n</div>')
    return "\n".join(pages)


def build_blank_pages(count: int, brand: dict, event: str) -> str:
    """빈 네임택을 8칸 단위 시트로."""
    if count <= 0:
        return ""
    pages = []
    for i in range(0, count, 8):
        batch_size = min(8, count - i)
        cells = [build_blank_cell(brand, event) for _ in range(batch_size)]
        cells += ['<div class="cell empty"></div>' for _ in range(8 - batch_size)]
        pages.append('<div class="a4-sheet">\n' + "\n".join(cells) + '\n</div>')
    return "\n".join(pages)


# ─────────────────────── 시안 미리보기 (skeleton 선택) ───────────────────────

def get_candidate_skeletons(brand: dict) -> list[str]:
    """yaml.preferred_skeletons에 따라 시안 후보 목록 반환. 비우면 4개 모두."""
    pref = brand.get("preferred_skeletons") or []
    if not pref:
        return list(ALL_SKELETONS)
    valid = []
    for s in pref:
        if s.startswith("custom-"):
            custom_path = TEMPLATES_DIR / "custom" / f"{s[7:]}.html"
            if custom_path.exists():
                valid.append(s)
            else:
                print(f"⚠️  custom skeleton '{s}' 파일 없음 → skip", file=sys.stderr)
        elif s in SKELETON_FILES:
            valid.append(s)
        else:
            print(f"⚠️  알 수 없는 skeleton ID '{s}' → skip", file=sys.stderr)
    if not valid:
        print(f"✗ preferred_skeletons에 유효한 ID 없음. r1-r4 또는 custom-*", file=sys.stderr)
        sys.exit(1)
    return valid


def load_skeleton_template(skeleton_id: str) -> str:
    """skeleton ID로 template HTML 파일 로드."""
    if skeleton_id.startswith("custom-"):
        path = TEMPLATES_DIR / "custom" / f"{skeleton_id[7:]}.html"
    else:
        path = TEMPLATES_DIR / SKELETON_FILES[skeleton_id]
    if not path.exists():
        print(f"✗ skeleton template 없음: {path}", file=sys.stderr)
        print(f"   유효한 ID: r1, r2, r3, r4 또는 templates/custom/<name>.html 존재해야 함", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def _inject_motif_css(template_html: str, brand: dict) -> str:
    """template HTML의 </head> 직전에 style pack 장식 CSS를 추가한다."""
    css = _motif_css(brand)
    if not css:
        return template_html
    if "</head>" in template_html:
        return template_html.replace("</head>", f"{css}\n</head>", 1)
    return css + template_html


_VARIANT_CSS = """
<style id="eventnametag-variant">
  /* 인라인 SVG 로고 슬롯 — 워드마크 텍스트 대체 시 topbar 높이에 맞춘다 */
  .brand-logo { display: inline-flex; align-items: center; }
  .brand-logo svg { height: 4mm; width: auto; max-width: 40mm; }

  /* P1-C: 일러스트 슬롯 — .tag 내부 우하단 장식 레이어(배경 위 · 텍스트 아래, 저강도) */
  .tag .illustration-slot { position: absolute; right: 3mm; bottom: 3mm; width: 16mm; height: 16mm;
    z-index: 0; pointer-events: none; opacity: 0.85; color: var(--brand-accent-1, #2563eb); }
  .tag .illustration-slot svg { width: 100%; height: 100%; display: block; }

  /* P1 가림 수정: .tag 내부 장식(::before·accent·illustration, z-index:0)이 불투명 배경 위에
     깔리므로, 실제 텍스트(topbar/body)는 그보다 위(z-index:1)로 띄워 항상 보이게 한다.
     장식이 없는 셀은 stacking에 영향 없음 → 회귀 0. */
  .tag .topbar, .tag .body { position: relative; z-index: 1; }

  /* badge_first — 역할/트랙 배지를 본문 상단에 강조 */
  .variant-badge_first .badge-row {
    display: flex; flex-wrap: wrap; justify-content: center; gap: 1.6mm; margin-bottom: 2.4mm;
  }
  .variant-badge_first .badge {
    display: inline-block; padding: 0.9mm 2.4mm; border-radius: 999px;
    background: var(--brand-accent-1, #2563eb); color: #ffffff;
    font: 800 2.8mm var(--brand-font-mono, ui-monospace, monospace);
    letter-spacing: 0.04em; text-transform: uppercase;
  }

  /* intro_hero — 소개·관심사를 이름 아래 강조 블록으로 */
  .variant-intro_hero .intro-hero {
    display: flex; flex-direction: column; gap: 1mm; margin-top: 2.6mm;
    padding-top: 2mm; border-top: 0.3mm solid var(--brand-accent-1, #2563eb); max-width: 88%;
  }
  .variant-intro_hero .intro-hero-line {
    font-size: 3.6mm; line-height: 1.25; color: var(--brand-dark, #0a0a0b); font-weight: 600;
  }
  /* intro_hero에서는 하단 .intro 중복 표시 방지 (소개를 hero 블록이 이미 담당) */
  .variant-intro_hero .body > .intro { display: none; }

  /* ─── diagonal (기본) — 검증된 대각 컬러블록 시안. 하드코딩색은 브랜드 토큰으로 치환 ─── */
  /* .dcell은 .cell 안을 가득 채우는 독립 캔버스 (topbar/body 미사용) */
  .variant-diagonal .dcell { position: relative; width: 100%; height: 100%;
    background: var(--brand-light); overflow: hidden; }
  /* 좌상단 네이비 대각 블록 (어두운 면) */
  .variant-diagonal .diag-top { position: absolute; top: 0; left: 0; right: 0; height: 30mm;
    background: var(--brand-dark); z-index: 0; clip-path: polygon(0 0, 100% 0, 100% 58%, 0 100%); }
  /* 우하단 액센트 대각 삼각 (accent_1 미정의 brand는 dark로 fallback해 대비 유지) */
  .variant-diagonal .diag-corner { position: absolute; right: 0; bottom: 0; width: 26mm; height: 26mm;
    background: var(--brand-accent-1, var(--brand-dark)); z-index: 0; clip-path: polygon(100% 0, 100% 100%, 0 100%); }
  /* 헤더 — 어두운 대각 블록 위라 로고·텍스트는 항상 밝게(var(--brand-light)) */
  .variant-diagonal .dhead { position: absolute; top: 0; left: 0; right: 0; height: 18mm; z-index: 2;
    display: flex; align-items: center; justify-content: space-between; padding: 0 6mm; }
  .variant-diagonal .dhead .brand-wrap,
  .variant-diagonal .dhead .brand-logo,
  .variant-diagonal .dhead .brand-logo svg { color: var(--brand-light); fill: var(--brand-light); }
  .variant-diagonal .devent { color: var(--brand-light); opacity: .78;
    font-family: var(--brand-font-mono); font-size: 2.8mm; letter-spacing: .12em; }
  /* 본문 — 밝은 면 중앙 정렬 */
  .variant-diagonal .dbody { position: absolute; top: 22mm; left: 0; right: 0; bottom: 0; z-index: 1;
    display: flex; flex-direction: column; align-items: center; text-align: center; gap: .6mm; padding: 0 6mm; }
  .variant-diagonal .dbadge { background: var(--brand-accent-1, var(--brand-dark)); color: var(--brand-light);
    border-radius: 999px; padding: .7mm 3.4mm; font-size: 2.6mm; font-weight: 800; letter-spacing: .08em; margin-bottom: 1mm; }
  /* dname/dcompany font-size 기본값 — 긴 이름·회사명은 generate.py가 inline으로 축소 주입 */
  .variant-diagonal .dname { font-size: 14mm; font-weight: 800; color: var(--brand-dark); line-height: 1; letter-spacing: -.02em; }
  .variant-diagonal .dcompany { font-size: 5mm; font-weight: 700; color: var(--brand-dark); margin-top: 1.5mm; }
  .variant-diagonal .drole { font-size: 3.2mm; font-family: var(--brand-font-mono); letter-spacing: .1em;
    color: var(--brand-accent-1, var(--brand-dark)); margin-top: .5mm; }
  .variant-diagonal .dintro { font-size: 3mm; color: var(--brand-dark); opacity: .62; font-style: italic; margin-top: 1.2mm; }

  /* v0.6: AI 셀 템플릿 컨테이너 — 셀 경계 불변(overflow:hidden) + 자식 절대배치 기준 */
  .cell.variant-ai { position: relative; overflow: hidden; }
  .cell.variant-ai > * { width: 100%; height: 100%; }
</style>"""


def _inject_variant_css(template_html: str) -> str:
    """template HTML의 </head> 직전에 layout_variant CSS를 추가한다.
    셀 크기·grid·topbar 등 base 좌표는 건드리지 않고 .body 안쪽만 스타일링한다.
    brand 색은 inject 시점에 var(--brand-*)로 들어와 있으므로 var()로 참조한다."""
    if "</head>" in template_html:
        return template_html.replace("</head>", f"{_VARIANT_CSS}\n</head>", 1)
    return _VARIANT_CSS + template_html


def _inject_preview_fit_css(template_html: str) -> str:
    """스켈레톤 후보 iframe 안에서 내부 스크롤 없이 1개 라벨만 딱 맞게 보이도록 한다."""
    css = """
<style id="eventnametag-preview-fit">
  html, body { width: 99.1mm !important; height: 67.7mm !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; background: white !important; }
  .a4-sheet { width: 99.1mm !important; height: 67.7mm !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important; display: block !important; box-shadow: none !important; page-break-after: auto !important; overflow: hidden !important; }
  .cell { width: 99.1mm !important; height: 67.7mm !important; overflow: hidden !important; }
</style>"""
    if "</head>" in template_html:
        return template_html.replace("</head>", f"{css}\n</head>", 1)
    return css + template_html


def _render_single_preview(brand: dict, event: str, skeleton_id: str, attendee: dict | None) -> str:
    """한 명 샘플을 1칸 preview HTML로 렌더링한다."""
    tpl = load_skeleton_template(skeleton_id)
    tpl = inject_brand_tokens(tpl, brand)
    tpl = _inject_motif_css(tpl, brand)
    tpl = _inject_variant_css(tpl)
    tpl = _inject_preview_fit_css(tpl)
    variant = resolve_layout_variant(brand)
    sample_cell = build_cell(attendee, brand, event, layout_variant=variant)
    single_sheet = f'<div class="a4-sheet" style="grid-template-rows: 1fr; grid-template-columns: 1fr; height: 67.7mm;">\n{sample_cell}\n</div>'
    return tpl.replace("<!-- CELLS_HERE -->", single_sheet)


def build_preview_html(brand: dict, event: str, skeleton_ids: list[str], sample_attendees: list[dict]) -> str:
    """시안 미리보기 HTML. N개 skeleton을 가로 정렬로 보여줌. 각 카드 클릭 시 정보 표시."""
    cards = []
    for idx, sid in enumerate(skeleton_ids, 1):
        try:
            tpl = load_skeleton_template(sid)
        except SystemExit:
            continue  # 누락된 skeleton은 skip
        # iframe srcdoc으로 격리 렌더 — CSS 충돌 방지
        tpl_filled = _render_single_preview(brand, event, sid, sample_attendees[0] if sample_attendees else None)
        srcdoc = html_mod.escape(tpl_filled)
        cards.append(f"""
        <div class="card">
          <div class="card-label">시안 {idx} — {html_mod.escape(skeleton_choice_label(sid))}</div>
          <iframe srcdoc="{srcdoc}" scrolling="no" style="border:0; width: 99.1mm; height: 67.7mm; overflow: hidden; background: white; border-radius: 6px;"></iframe>
        </div>
        """)

    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>eventnametag — 시안 미리보기</title>
<style>
  body {{ margin: 0; padding: 30px; background: #1a1a1a; color: #fafafa;
         font-family: system-ui, sans-serif; }}
  h1 {{ font-size: 18px; font-weight: 600; margin: 0 0 8px; }}
  p.subtitle {{ color: #a1a1aa; font-size: 14px; margin: 0 0 24px; }}
  .cards {{ display: flex; gap: 24px; flex-wrap: wrap; }}
  .card {{ background: #27272a; border-radius: 8px; padding: 16px;
           border: 1px solid #3f3f46; }}
  .card-label {{ font-weight: 600; margin-bottom: 12px; color: #C0F0FB; }}
  .instruction {{ margin-top: 32px; padding: 16px; background: #18181b;
                  border-radius: 8px; border-left: 3px solid #FFEA00; }}
</style></head><body>
<h1>시안 미리보기 — {html_mod.escape(brand["name"])} · {html_mod.escape(event)}</h1>
<p class="subtitle">{len(skeleton_ids)}개 인쇄 레이아웃 후보입니다. 일반 사용자는 무드/목적을 고르면 되고, 이 화면은 고급 확인용입니다.</p>
<div class="cards">{cards_html}</div>
<div class="instruction">
  <strong>다음 단계</strong> — 터미널로 돌아가서 마음에 드는 시안 번호 (1~{len(skeleton_ids)})를 입력하세요.<br>
  선택 시 해당 레이아웃으로 8칸 페이지를 채워 인쇄용 PNG로 변환합니다.
</div>
</body></html>"""


def _paper_recommendation_label(brand: dict) -> str:
    return "기본 탐사 A4 8칸 라벨지 기준"


def build_showcase_html(brand: dict, event: str, sample_attendees: list[dict]) -> str:
    """질문 없이 바로 보여주는 행사 무드별 쇼케이스 HTML."""
    sample = sample_attendees[0] if sample_attendees else None
    cards = []
    for style_id, pack in STYLE_PACKS.items():
        themed = apply_style_pack(brand, style_id)
        skeleton_id = themed["preferred_skeletons"][0]
        preview = _render_single_preview(themed, event, skeleton_id, sample)
        srcdoc = html_mod.escape(preview)
        paper = _paper_recommendation_label(themed)
        fields = ", ".join(pack.get("fields", []))
        cards.append(f"""
        <section class="mood-card mood-{html_mod.escape(style_id)}">
          <div class="mood-copy">
            <div class="mood-kicker">{html_mod.escape(style_id)}</div>
            <h2>{html_mod.escape(pack["label"])}</h2>
            <p>{html_mod.escape(pack["description"])}</p>
            <dl class="mood-meta">
              <div><dt>적합한 행사</dt><dd>{html_mod.escape(pack["best_for"])}</dd></div>
              <div><dt>강조 정보</dt><dd>{html_mod.escape(pack["emphasis"])}</dd></div>
              <div><dt>필요 필드</dt><dd>{html_mod.escape(fields)}</dd></div>
              <div><dt>내부 구성</dt><dd>{html_mod.escape(pack["internal_layout"])}</dd></div>
              <div><dt>인쇄 리스크</dt><dd>{html_mod.escape(pack["print_risk"])}</dd></div>
            </dl>
            <p class="explain">{html_mod.escape(pack["user_explanation"])}</p>
            <div class="paper">{html_mod.escape(paper)}</div>
          </div>
          <iframe srcdoc="{srcdoc}" title="{html_mod.escape(pack['label'])}"></iframe>
        </section>
        """)

    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>eventnametag — mood showcase</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; padding: 34px; background: radial-gradient(circle at top left, #26345c, #101014 42%, #050505); color: #fafafa; font-family: system-ui, -apple-system, sans-serif; }}
  header {{ max-width: 1120px; margin: 0 auto 28px; }}
  h1 {{ font-size: 30px; line-height: 1.12; margin: 0 0 10px; letter-spacing: -0.04em; }}
  .lead {{ margin: 0; color: #c9cad3; font-size: 15px; }}
  .grid {{ max-width: 1120px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(430px, 1fr)); gap: 22px; }}
  .mood-card {{ background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.14); border-radius: 22px; padding: 18px; box-shadow: 0 22px 70px rgba(0,0,0,.30); overflow: hidden; }}
  .mood-copy {{ display: grid; gap: 5px; margin-bottom: 12px; }}
  .mood-kicker {{ color: #9CA3AF; text-transform: uppercase; font: 700 11px ui-monospace, monospace; letter-spacing: .14em; }}
  h2 {{ margin: 0; font-size: 20px; letter-spacing: -0.03em; }}
  p {{ margin: 0; color: #d4d4d8; font-size: 13px; line-height: 1.5; }}
  .mood-meta {{ display: grid; gap: 5px; margin: 4px 0 0; color: #cbd5e1; font-size: 12px; }}
  .mood-meta div {{ display: grid; grid-template-columns: 82px 1fr; gap: 8px; }}
  .mood-meta dt {{ color: #94a3b8; font-weight: 800; }}
  .mood-meta dd {{ margin: 0; }}
  .explain {{ margin-top: 8px; color: #f4f4f5; font-weight: 650; }}
  .paper {{ width: fit-content; margin-top: 7px; padding: 6px 9px; border-radius: 999px; background: rgba(255,255,255,.12); color: #FDE68A; font-size: 12px; font-weight: 800; }}
  iframe {{ border: 0; width: 105mm; height: 75mm; transform: scale(.98); transform-origin: 0 0; background: white; border-radius: 10px; }}
  footer {{ max-width: 1120px; margin: 26px auto 0; color: #a1a1aa; font-size: 13px; }}
</style></head><body>
<header>
  <h1>바로 고르는 네임택 무드 — {html_mod.escape(brand.get('name', 'Brand'))} · {html_mod.escape(event)}</h1>
  <p class="lead">BI를 길게 묻기 전에, 행사 목적별로 정보 구조가 다른 8개 제품 카드를 먼저 보여줍니다. 마음에 드는 방향을 고른 뒤 로고·컬러·명단만 보정하면 됩니다.</p>
</header>
<main class="grid">{cards_html}</main>
<footer>모든 시안은 기본 탐사 A4 8칸 라벨지 기준으로 생성합니다. 풀컬러·그라디언트·일러스트형은 대량 인쇄 전 일반 A4 테스트를 먼저 권장합니다.</footer>
</body></html>"""


# ─────────────────────── 인쇄 파이프라인 ───────────────────────

def render_pdf_and_png(html_path: Path, out_dir: Path) -> tuple[Path, Path]:
    """HTML → PDF (Chrome headless) → 300dpi PNG (sips). rangecheck 우회 raster 경로."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    pdf_out = out_dir / f"nametag-{ts}.pdf"
    png_out = out_dir / f"nametag-{ts}.png"

    subprocess.run(
        [
            CHROME_BIN,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--print-to-pdf={pdf_out}",
            "--print-to-pdf-no-header",
            f"file://{html_path}",
        ],
        check=True,
        capture_output=True,
    )
    if not pdf_out.exists():
        raise RuntimeError(f"PDF 생성 실패: {pdf_out}")

    subprocess.run(
        ["sips", "-s", "format", "png", "-Z", "3508", str(pdf_out), "--out", str(png_out)],
        check=True,
        capture_output=True,
    )
    if not png_out.exists():
        raise RuntimeError(f"PNG 생성 실패: {png_out}")

    subprocess.run(
        ["sips", "-s", "dpiHeight", "300", "-s", "dpiWidth", "300", str(png_out)],
        check=True,
        capture_output=True,
    )
    return pdf_out, png_out


# ─────────────────────── 가드레일 G2 — 컬러 대비 (WCAG AA) ───────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"invalid hex: {hex_color}")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def _relative_luminance(hex_color: str) -> float:
    """WCAG 2.x 상대 휘도."""
    r, g, b = _hex_to_rgb(hex_color)

    def _linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(c1: str, c2: str) -> float:
    """두 hex 색의 WCAG 대비비. 1:1 ~ 21:1."""
    l1 = _relative_luminance(c1)
    l2 = _relative_luminance(c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_color_contrast(brand: dict, *, no_check: bool = False, threshold: float = 4.5) -> None:
    """G2: primary_dark vs primary_light 대비 검사. WCAG AA = 4.5.
       no_check=True면 skip. 미달 시 경고만 출력 (사용자 강행 가능)."""
    if no_check:
        print("⚠️  G2 컬러 대비 검사 skip (--no-contrast-check)", file=sys.stderr)
        return
    colors = brand.get("colors", {})
    dark = colors.get("primary_dark")
    light = colors.get("primary_light")
    if not dark or not light:
        return
    try:
        ratio = contrast_ratio(dark, light)
    except ValueError as e:
        print(f"⚠️  G2 검사 실패: {e}", file=sys.stderr)
        return
    if ratio < threshold:
        print(
            f"⚠️  G2 컬러 대비 경고: primary_dark({dark}) vs primary_light({light}) "
            f"대비 {ratio:.2f} (WCAG AA 임계 {threshold})",
            file=sys.stderr,
        )
        print("    네임택 가독성이 떨어질 수 있습니다. --no-contrast-check로 강행 가능.", file=sys.stderr)


# ─────────────────────── 가드레일 G3 — 잉크 커버리지 ───────────────────────

def estimate_ink_coverage(png_path: Path) -> float | None:
    """PNG raster 분석으로 잉크 커버리지(%) 추정. PIL 없으면 None."""
    if Image is None:
        return None
    try:
        img = Image.open(png_path).convert("RGB")
    except Exception as e:
        print(f"⚠️  G3 PNG 열기 실패: {e}", file=sys.stderr)
        return None

    # 다운샘플링으로 속도 확보
    img.thumbnail((600, 600))
    pixels = list(img.getdata())
    if not pixels:
        return None

    # 잉크 = 1 - (R+G+B) / (255*3) 픽셀별 평균
    total = 0.0
    for r, g, b in pixels:
        total += 1.0 - ((r + g + b) / 765)
    return (total / len(pixels)) * 100


def check_ink_coverage(png_path: Path, brand: dict, *, ignore: bool = False) -> None:
    """G3: 잉크 커버리지 임계 검사. brand.print.ink_coverage_warning(%) 초과 시 경고.
       ignore=True면 skip. PIL 없으면 검사 skip + 안내."""
    if ignore:
        print("⚠️  G3 잉크 커버리지 검사 skip (--ignore-ink)", file=sys.stderr)
        return
    threshold = (brand.get("print") or {}).get("ink_coverage_warning")
    if threshold is None:
        return
    if Image is None:
        print("⚠️  G3 검사 skip — PIL 미설치. `pip install pillow` 권장.", file=sys.stderr)
        return
    coverage = estimate_ink_coverage(png_path)
    if coverage is None:
        return
    if coverage > threshold:
        print(
            f"⚠️  G3 잉크 커버리지 경고: 추정 {coverage:.1f}% (BI 임계 {threshold}%)",
            file=sys.stderr,
        )
        print("    R3 풀블리드는 잉크 사용량이 높습니다. R1/R4를 추천하거나 --ignore-ink로 강행.", file=sys.stderr)


# ─────────────────────── 인쇄안전 닫힌 루프 (P0 — render→verify→retry→fallback) ───────────────────────

# 닫힌 루프 게이트의 기본 잉크 임계(%). brand.print.ink_coverage_warning가 있으면 그 값을 쓰고,
# 없으면 아키텍처 문서(§4-3) 다이어그램 기준값 35%(풀블리드 floor)를 적용한다.
DEFAULT_INK_GATE_THRESHOLD = 35.0
# WCAG AA 대비 임계 (이름/회사 텍스트 vs 배경).
CONTRAST_GATE_THRESHOLD = 4.5
# 대비 fail 시 강제 적용하는 안전 다크 텍스트색 (거의 검정 — primary_light가 밝으면 항상 ≥4.5 보장).
SAFE_DARK_TEXT = "#0a0a0b"


def _ink_gate_threshold(brand: dict) -> float:
    """이 brand에 적용할 잉크 게이트 임계(%)를 결정한다.
    brand.print.ink_coverage_warning가 있으면 우선, 없으면 기본 게이트값."""
    threshold = (brand.get("print") or {}).get("ink_coverage_warning")
    if isinstance(threshold, (int, float)):
        return float(threshold)
    return DEFAULT_INK_GATE_THRESHOLD


def _verify_name_ocr(png_path: Path, attendees: list[dict]) -> list[dict]:
    """[확장 지점 · 미구현] 렌더된 PNG에서 이름 텍스트가 실재하는지 OCR로 확인.

    이번 P0 범위에서는 no-op(빈 목록)이다. 코드-디자인 파이프라인은 텍스트를 실제
    폰트 문자로 박으므로 이름이 누락/오타날 구조적 여지가 없다(이미지 생성과 다름).
    OCR은 가치가 낮고(항상 통과 예상) tesseract 등 무거운 외부 의존성을 끌어오므로
    '새 외부 의존성 추가 금지' 제약과 충돌한다. LLM이 raster 배경을 합성하는 미래
    경로가 생기면 여기에 OCR 검증을 붙인다."""
    return []


def _verify_overflow(png_path: Path, attendees: list[dict]) -> list[dict]:
    """[확장 지점 · 미구현] 텍스트 bbox가 셀 경계를 침범하는지 검사.

    이번 P0 범위에서는 no-op(빈 목록)이다. 셀 침범은 base 좌표 불변 + .tag/.cell의
    overflow:hidden + name_font_size/company_font_size 축소 로직으로 이미 원천 차단돼
    있어(test_print_coordinates lock) 런타임 bbox 측정이 불필요하다. raster 합성 배경
    같은 비결정 요소가 들어오면 여기에 bbox 검증을 붙인다."""
    return []


# ── G9: 텍스트영역 대비 게이트 ───────────────────────────
# 탐사 A4 8칸 라벨지 = 2열 × 4행 8칸. margin 0 근사로 페이지를 균등 분할.
# 이름 밴드 = 각 칸 높이 [0.32, 0.60] · 폭 [0.08, 0.92] (텍스트 영역 근사).
# 텍스트 기준색 = primary_dark(밝은 배경 위 어두운 이름이 기본 레이아웃).
NAME_BAND_Y = (0.32, 0.60)
NAME_BAND_X = (0.08, 0.92)
TEXT_REGION_CONTRAST_THRESHOLD = 4.5


def _rel_lum_rgb(r: int, g: int, b: int) -> float:
    def _lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast_from_lum(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _verify_text_region_contrast(png_path: Path, brand: dict,
                                 textzone: tuple | None = None) -> list[dict]:
    """[G9] 각 칸 이름 밴드의 배경 휘도가 텍스트색과 WCAG 4.5 대비를 유지하는지.

    장식 레이어가 이름 글자 뒤 대비를 깎으면 fail → _downgrade_design 트리거.
    배경 휘도는 밴드 픽셀 휘도의 상위 백분위(P90)로 추정한다. 종이(배경)는 밴드에서
    가장 밝은 영역이고 이름 글자는 어두운 소수 픽셀이므로, 상위 백분위는 글자가
    밴드의 50%를 넘게 덮는 hero 이름(1명 셀 등)에서도 종이 휘도를 안정적으로 잡는다.
    (중앙값은 글자 면적<50% 가정 — hero 단일 이름에서 글자 위에 떨어져 오탐.)
    첫 fail에서 즉시 반환(강도하향은 전역 적용이므로).

    v0.6: textzone=(x0,y0,x1,y1)이 주어지면 각 칸 내부의 그 분수 영역을, None이면 기존 이름밴드를 샘플한다(2×4 per-cell 루프 유지)."""
    if Image is None:
        return []
    colors = brand.get("colors") or {}
    text_hex = colors.get("primary_dark", "#0a0a0b").lstrip("#")
    tr, tg, tb = (int(text_hex[i: i + 2], 16) for i in (0, 2, 4))
    text_lum = _rel_lum_rgb(tr, tg, tb)
    try:
        img = Image.open(png_path).convert("RGB")
    except Exception:
        return []
    W, H = img.size
    cols, rows = 2, 4
    cw, ch = W / cols, H / rows
    # v0.6: textzone이 주어지면 AI 선언 영역(x0,y0,x1,y1)을, 없으면 기본 이름밴드를 샘플.
    # 분수는 각 칸 내부 좌표로 적용한다(AI는 한 칸의 이름 위치를 선언). 2×4 per-cell 루프 유지.
    bx0, by0, bx1, by1 = (NAME_BAND_X[0], NAME_BAND_Y[0], NAME_BAND_X[1], NAME_BAND_Y[1])
    if textzone is not None:  # 관용구: 옵션 튜플은 is not None으로 (빈 튜플 falsy 함정 회피)
        bx0, by0, bx1, by1 = textzone
    for cyi in range(rows):
        for cxi in range(cols):
            x0 = int(cxi * cw + bx0 * cw)
            x1 = int(cxi * cw + bx1 * cw)
            y0 = int(cyi * ch + by0 * ch)
            y1 = int(cyi * ch + by1 * ch)
            if x1 <= x0 or y1 <= y0:
                continue
            band = img.crop((x0, y0, x1, y1)).resize((16, 16))
            lums = sorted(_rel_lum_rgb(*px) for px in band.getdata())
            bg_lum = lums[min(int(len(lums) * 0.90), len(lums) - 1)]  # P90 = 종이(배경) 휘도
            ratio = _contrast_from_lum(text_lum, bg_lum)
            if ratio < TEXT_REGION_CONTRAST_THRESHOLD:
                return [{
                    "check": "text_region_contrast",
                    "cell": cyi * cols + cxi,
                    "value": round(ratio, 2),
                    "threshold": TEXT_REGION_CONTRAST_THRESHOLD,
                }]
    return []


def verify_print_safety(png_path: Path, brand: dict, *, attendees: list[dict] | None = None,
                        textzone: tuple | None = None) -> dict:
    """렌더된 PNG와 brand로 인쇄안전 검증을 실행한다 (닫힌 루프 게이트의 'verify' 단계).

    검사:
      ① 잉크 커버리지 — estimate_ink_coverage(png) > 게이트 임계(brand.print 또는 기본 35%)
      ② WCAG 대비 — contrast_ratio(이름/회사 텍스트색, 배경색) < 4.5
         (텍스트=primary_dark, 배경=primary_light. 기존 check_color_contrast와 동일한 쌍.)
    반환: {"ok": bool, "failures": [{"check","value","threshold"}, ...]}.
    PIL 미설치 등으로 잉크 추정이 불가하면 해당 검사는 skip(보수적으로 통과 처리)한다.
    """
    failures: list[dict] = []

    # ① 잉크 커버리지 — 기존 estimate_ink_coverage 재사용 (중복 로직 신설 안 함)
    ink_threshold = _ink_gate_threshold(brand)
    coverage = estimate_ink_coverage(png_path)
    if coverage is not None and coverage > ink_threshold:
        failures.append({"check": "ink_coverage", "value": round(coverage, 1), "threshold": ink_threshold})

    # ② WCAG 대비 — 기존 contrast_ratio 재사용. 텍스트(primary_dark) vs 배경(primary_light).
    colors = brand.get("colors") or {}
    dark = colors.get("primary_dark")
    light = colors.get("primary_light")
    if dark and light:
        try:
            ratio = contrast_ratio(dark, light)
            if ratio < CONTRAST_GATE_THRESHOLD:
                failures.append({"check": "contrast", "value": round(ratio, 2), "threshold": CONTRAST_GATE_THRESHOLD})
        except ValueError:
            pass  # 잘못된 hex는 G2와 동일하게 검사 skip

    # ③/④ OCR·셀 침범 — 확장 지점만(현재 no-op). 위 _verify_* docstring 참고.
    atts = attendees or []
    failures.extend(_verify_name_ocr(png_path, atts))
    failures.extend(_verify_overflow(png_path, atts))
    failures.extend(_verify_text_region_contrast(png_path, brand, textzone=textzone))  # ← G9 (v0.6: textzone 일반화)

    return {"ok": not failures, "failures": failures}


def _downgrade_design(brand: dict, *, fix_contrast: bool) -> dict:
    """강도하향: brand.design에서 잉크·장식 요소를 제거하고(패턴/모티프/일러스트/accent_shape),
    대비 fail이면 텍스트색(primary_dark)을 안전 다크값으로 강제한다.

    원본 brand를 변형하지 않고 얕은 복제본을 반환한다. 좌표·셀 크기는 건드리지 않는다."""
    out = dict(brand)
    design = dict(out.get("design") or {})
    # 잉크·장식 요인 제거 (배경 패턴·모티프·인라인 일러스트·코너 도형)
    # v0.6: cell_template도 장식 요인이므로 강도하향 시 제거 → 스켈레톤 floor로 떨어짐.
    for key in ("pattern", "motif_id", "illustration_svg_inline", "accent_shape", "cell_template"):
        design.pop(key, None)
    out["design"] = design
    if fix_contrast:
        colors = dict(out.get("colors") or {})
        light = colors.get("primary_light")
        # primary_light가 충분히 밝으면 안전 다크값이 ≥4.5 대비를 보장. 아니면 그대로 둠.
        if light:
            try:
                if contrast_ratio(SAFE_DARK_TEXT, light) >= CONTRAST_GATE_THRESHOLD:
                    colors["primary_dark"] = SAFE_DARK_TEXT
            except ValueError:
                pass
        out["colors"] = colors
    return out


def _safe_preset_brand(brand: dict) -> dict:
    """검증된 안전 프리셋 brand: 장식 0 + name_hero 레이아웃 + 대비 보장 텍스트색.
    닫힌 루프가 재시도로도 통과 못할 때의 최종 fallback 목적지."""
    out = _downgrade_design(brand, fix_contrast=True)
    design = dict(out.get("design") or {})
    design["layout_variant"] = "name_hero"  # 검증된 저잉크·이름 강조 레이아웃
    out["design"] = design
    return out


def _build_print_html(attendees: list[dict], brand: dict, event: str, *,
                      layout_variant: str | None = None, fill_blanks: bool = False,
                      skeleton: str | None = None) -> str:
    """명단 + brand로 최종 인쇄 HTML 문서를 조립한다 (메인 흐름과 동일한 파이프라인).

    skeleton: 사용할 skeleton ID. 미지정 시 brand 후보 중 첫 번째(단일 skeleton 브랜드는 동일,
    다중 skeleton 브랜드에서는 사용자 선택값이 전달돼야 preview 선택과 최종 출력이 일치한다).

    v0.2 calibration: load_calibration() 결과가 있으면 HTML 조립 직후 주입한다. 게이트 경로의
    강도하향·preset fallback 재빌드에도 동일하게 적용되므로 정렬 offset이 보존된다."""
    chosen = skeleton or get_candidate_skeletons(brand)[0]
    template = _inject_variant_css(_inject_motif_css(inject_brand_tokens(load_skeleton_template(chosen), brand), brand))
    filled_html = build_pages(attendees, brand, event, fill_blanks=fill_blanks, layout_variant=layout_variant)
    html = template.replace("<!-- CELLS_HERE -->", filled_html)
    # v0.2 calibration: 게이트 경로의 모든 재빌드(1차·재시도·fallback)에 보정 transform 주입
    cal = load_calibration()
    if cal is not None:
        html = apply_calibration_transform(html, cal)
    return html


def render_with_safety_loop(attendees: list[dict], brand: dict, event: str, out_dir: Path,
                            *, max_retries: int = 2,
                            layout_variant: str | None = None,
                            fill_blanks: bool = False,
                            skeleton: str | None = None) -> tuple[Path, dict]:
    """인쇄안전 닫힌 루프: 빌드 → render → verify → (fail 시) 강도하향 재시도 → preset fallback.

    1) 1차: 현재 design(기본 diagonal 등)으로 빌드·렌더·검증. ok면 그대로 반환.
    2) fail이면 강도하향(_downgrade_design) 후 max_retries회 재시도. 대비 fail이면 텍스트색도 강제.
    3) 그래도 fail이면 검증된 preset(name_hero·장식 없음)으로 재빌드·렌더 후 반환.

    skeleton: 사용자가 선택한 skeleton ID. 강도하향·preset fallback 재빌드에도 동일하게 쓰여
    preview 선택과 최종 출력이 일치한다. 미지정 시 brand 첫 번째 후보.
    calibration은 _build_print_html 내부에서 각 빌드마다 주입(수정1 참고).

    반환: (png_path, report). report = {retried:int, fallback_used:bool, final_failures:[...]}.
    기본 diagonal은 저잉크(7~8%)·고대비라 보통 1차 통과 → 재시도/fallback 0 (회귀 없음).
    """
    cur_brand = brand
    cur_variant = layout_variant

    # cur_variant는 루프 내에서 재할당하지 않는다 — closure capture 안전(여기서 한 번만 읽음).
    def _textzone_for(b: dict) -> tuple | None:
        # 🔒 cur_variant 가드는 필수·정확하다(제거 금지): build_pages는 명시 layout override 시
        # cell_template을 '복제본'에서만 strip하므로(원본 미변형) cur_brand는 cell_template을 그대로
        # 보유한다. cur_variant!=None이면 실제 렌더는 스켈레톤이지만 b엔 cell_template이 남아 있으므로,
        # cur_variant로 걸러 기본 밴드를 써야 G9 샘플 영역이 실렌더(스켈레톤)와 일치한다.
        if cur_variant is not None:
            return None
        ct = (b.get("design") or {}).get("cell_template")
        if not ct:
            return None
        ok, tz, _ = validate_cell_template(ct, b)
        return tz if ok else None

    def _render(b: dict, v: str | None, sk: str | None = skeleton) -> Path:
        html = _build_print_html(attendees, b, event, layout_variant=v, fill_blanks=fill_blanks,
                                 skeleton=sk)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        html_path = out_dir / f"_safety-{ts}.html"
        html_path.write_text(html, encoding="utf-8")
        _pdf, png = render_pdf_and_png(html_path, out_dir)
        return png

    # 1) 1차 렌더·검증
    png = _render(cur_brand, cur_variant)
    result = verify_print_safety(png, cur_brand, attendees=attendees,
                                 textzone=_textzone_for(cur_brand))
    if result["ok"]:
        return png, {"retried": 0, "fallback_used": False, "final_failures": []}

    # 2) 강도하향 재시도
    retried = 0
    last_failures = result["failures"]
    for _ in range(max(0, max_retries)):
        retried += 1
        fix_contrast = any(
            f["check"] in ("contrast", "text_region_contrast")  # ← G9 포함
            for f in last_failures
        )
        cur_brand = _downgrade_design(cur_brand, fix_contrast=fix_contrast)
        png = _render(cur_brand, cur_variant)
        result = verify_print_safety(png, cur_brand, attendees=attendees,
                                     textzone=_textzone_for(cur_brand))
        last_failures = result["failures"]
        if result["ok"]:
            print("⚠ 인쇄안전 게이트: 장식 강도하향으로 안전 기준을 통과했습니다.", file=sys.stderr)
            return png, {"retried": retried, "fallback_used": False, "final_failures": []}

    # 3) preset fallback (검증된 안전 레이아웃)
    preset_brand = _safe_preset_brand(cur_brand)
    png = _render(preset_brand, "name_hero")
    result = verify_print_safety(png, preset_brand, attendees=attendees,
                                 textzone=_textzone_for(preset_brand))
    if last_failures and any(f["check"] == "ink_coverage" for f in last_failures):
        print("⚠ 잉크 과다 → 안전 레이아웃으로 대체했습니다.", file=sys.stderr)
    else:
        print("⚠ 인쇄안전 기준 미달 → 검증된 안전 레이아웃으로 대체했습니다.", file=sys.stderr)
    return png, {"retried": retried, "fallback_used": True, "final_failures": result["failures"]}


def check_dependencies() -> None:
    """G5: Chrome / sips 의존성 검사. 첫 실행 1회."""
    if not Path(CHROME_BIN).exists():
        print(f"✗ Google Chrome 없음 ({CHROME_BIN}).", file=sys.stderr)
        print(f"  https://google.com/chrome 설치 후 재시도. 일단 HTML만 미리보려면 --html-only", file=sys.stderr)
        sys.exit(2)
    if subprocess.run(["which", "sips"], capture_output=True).returncode != 0:
        print(f"✗ sips 없음. macOS 외 OS는 v0.1 미지원.", file=sys.stderr)
        sys.exit(2)


def apply_calibration_transform(html: str, cal: dict) -> str:
    """calibration offset을 .a4-sheet에 CSS transform으로 inject (v0.2).

    base값(deltanametag 검증된 padding) 위에 사용자 보정값을 덧붙이는 모델.
    인쇄 후 라벨지 정렬 어긋남 보정용.
    """
    style = (
        f"<style>"
        f"/* v0.2 calibration profile */ "
        f".a4-sheet {{ transform: translate({cal['x']}mm, {cal['y']}mm); }}"
        f"</style>"
    )
    # </head> 직전에 inject (마지막 정의가 우선)
    if "</head>" in html:
        return html.replace("</head>", f"{style}\n</head>", 1)
    # </head> 없으면 그대로 (안전)
    return html


def finalize_output(
    html_path: Path,
    html_only: bool,
    *,
    brand: dict | None = None,
    ignore_ink: bool = False,
    no_contrast_check: bool = False,
    safety_loop: dict | None = None,
) -> None:
    """HTML → PNG 변환 후 Preview 자동 오픈. --html-only면 HTML 그대로 브라우저.
       brand가 주어지면 PNG 생성 후 G3 잉크 커버리지 검사.
       v0.2: calibration profile 있으면 인쇄 직전 보정 transform inject.

       P0 인쇄안전 닫힌 루프(기본 동작): safety_loop={"attendees", "event"}가 주어지고
       escape hatch(ignore_ink·no_contrast_check)가 모두 꺼져 있으면, 단순 1회 렌더 대신
       render_with_safety_loop(render→verify→retry→preset fallback)로 게이트를 집행한다.
       --ignore-ink/--no-contrast-check를 주면 게이트를 우회하고 기존 단순 렌더로 떨어진다."""
    # v0.2: calibration 적용 (있을 때만)
    cal = load_calibration()
    if cal is not None:
        html_text = html_path.read_text(encoding="utf-8")
        html_text = apply_calibration_transform(html_text, cal)
        html_path.write_text(html_text, encoding="utf-8")
        print(f"  📐 calibration 적용: x={cal['x']:+g}mm, y={cal['y']:+g}mm", file=sys.stderr)

    if html_only:
        print(f"  [HTML-only] 브라우저 Cmd+P → 크기 100% · 맞춤(Scale to Fit) OFF · 자동회전 해제 → 라벨지 인쇄", file=sys.stderr)
        webbrowser.open(f"file://{html_path}")
        print_label_paper_guidance()
        return

    check_dependencies()

    # P0: escape hatch가 꺼져 있고 safety_loop 컨텍스트가 있으면 닫힌 루프로 집행
    gate_enabled = (safety_loop is not None and brand is not None
                    and not ignore_ink and not no_contrast_check)
    if gate_enabled:
        print(f"  인쇄안전 게이트(render→verify→retry→fallback) 실행 중...", file=sys.stderr)
        png_path, report = render_with_safety_loop(
            safety_loop["attendees"], brand, safety_loop.get("event", ""), OUTPUT_DIR,
            layout_variant=safety_loop.get("layout_variant"),
            fill_blanks=safety_loop.get("fill_blanks", False),
            skeleton=safety_loop.get("skeleton"),  # 사용자 선택 skeleton 전달 (미지정 시 None→첫 번째)
        )
        print(f"✓ PNG 저장: {png_path} (재시도 {report['retried']}회, "
              f"fallback {'사용' if report['fallback_used'] else '미사용'})", file=sys.stderr)
    else:
        print(f"  PDF → 300dpi PNG 변환 중... (rangecheck 우회 raster 경로)", file=sys.stderr)
        pdf_path, png_path = render_pdf_and_png(html_path, OUTPUT_DIR)
        print(f"✓ PNG 저장: {png_path}", file=sys.stderr)

        # G3: 잉크 커버리지 검사 (게이트 우회 시 advisory)
        if brand is not None:
            check_ink_coverage(png_path, brand, ignore=ignore_ink)

    print(f"  Preview 자동 오픈 → Cmd+P → 크기 조절 100% · 자동회전 해제 → 인쇄", file=sys.stderr)
    subprocess.run(["open", "-a", "Preview", str(png_path)])

    # P0-A: PNG-only 인쇄 체크리스트 (Preview 인쇄 다이얼로그 기준)
    print(file=sys.stderr)
    print("🖨️  인쇄 체크리스트 (Preview Cmd+P)", file=sys.stderr)
    print("  1. 용지: A4 (Paper Size = A4)", file=sys.stderr)
    print("  2. 크기 조절(Scale): 100% — '맞춤(Scale to Fit/자동맞춤)'은 반드시 OFF", file=sys.stderr)
    print("  3. 자동회전(Auto Rotate): 해제 (세로 그대로)", file=sys.stderr)
    print("  4. 첫 장은 일반 A4 용지로 테스트 인쇄 → 라벨지에 겹쳐 칸 정렬 확인 후 라벨지 인쇄", file=sys.stderr)
    print("  5. 인쇄 대상은 Preview에 열린 이 PNG (PDF·lpr 직접 인쇄 금지)", file=sys.stderr)
    print("  6. 프린터마다 라벨지 급지 방향이 다를 수 있으니, 일반 A4에 펜으로 앞/위 방향을 표시한 뒤", file=sys.stderr)
    print("     간단한 테스트 인쇄로 라벨지의 상하·앞뒤 출력 방향을 맞춘 후 본 인쇄하세요! :)", file=sys.stderr)
    print("  ※ PNG에 300dpi 메타데이터가 박혀 있어 '맞춤' 없이도 실제 크기(A4)로 출력됩니다.", file=sys.stderr)

    # v0.2: 인쇄 후 정렬 어긋남 발견 시 사용자 안내
    print(file=sys.stderr)
    print(f"💡 라벨지와 정렬이 맞지 않으면 자로 측정하여 자연어로 말씀해주세요.", file=sys.stderr)
    print(f"   예: '아래쪽으로 2mm 이동', '오른쪽으로 1mm 이동'", file=sys.stderr)
    print(f"   Claude가 보정값을 {CALIBRATION_FILE}에 자동 저장하여 다음 인쇄에 적용합니다.", file=sys.stderr)
    print_label_paper_guidance()


# ─────────────────────── 정렬 시트 ───────────────────────

def run_calibrate() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    content = (TEMPLATES_DIR / "_calibrate.html").read_text(encoding="utf-8")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"calibrate-{ts}.html"
    out.write_text(content, encoding="utf-8")
    webbrowser.open(f"file://{out}")
    print(f"✓ 정렬 테스트 시트: {out}", file=sys.stderr)
    print(f"  Cmd+P → 크기 100% → 일반 A4 종이로 먼저 인쇄 → 라벨지에 겹쳐 정렬 확인", file=sys.stderr)


# ─────────────────────── 첫 경험 UX ───────────────────────

def run_doctor() -> None:
    """첫 실행 전 환경을 점검한다. 실패해도 복구 방법을 함께 보여준다."""
    checks = [
        ("PyYAML", yaml is not None, "python3 -m pip install -r requirements.txt"),
        ("jsonschema", jsonschema is not None, "python3 -m pip install -r requirements.txt"),
        ("Pillow(PIL)", Image is not None, "python3 -m pip install -r requirements.txt"),
        ("Google Chrome", Path(CHROME_BIN).exists(), "https://google.com/chrome 에서 Chrome 설치"),
        ("sips", shutil.which("sips") is not None, "macOS 기본 도구입니다. macOS에서 실행하세요."),
        ("Preview open", shutil.which("open") is not None, "macOS open 명령이 필요합니다."),
    ]
    failed = False
    print("eventnametag doctor", file=sys.stderr)
    for name, ok, fix in checks:
        mark = "✓" if ok else "✗"
        print(f"{mark} {name}", file=sys.stderr)
        if not ok:
            failed = True
            print(f"  해결: {fix}", file=sys.stderr)

    avail = list_available_brands()
    brand_count = len(avail.get("examples", [])) + len(avail.get("user", []))
    print(f"✓ 사용 가능한 브랜드 예시/설정: {brand_count}개", file=sys.stderr)
    if not avail.get("examples") and not avail.get("user"):
        failed = True
        print("  해결: brands/examples/*.yaml 또는 ~/.config/eventnametag/brands/*.yaml 필요", file=sys.stderr)

    if failed:
        print("\n상태: 일부 항목 보완 필요", file=sys.stderr)
        sys.exit(1)
    print("\n상태: 바로 demo/quick 실행 가능", file=sys.stderr)


def _default_demo_brand_slug() -> str:
    """첫 경험용 기본 브랜드 slug를 고른다."""
    avail = list_available_brands()
    if "minimal-mono" in avail.get("examples", []):
        return "minimal-mono"
    candidates = avail.get("examples", []) or avail.get("user", [])
    if not candidates:
        print("✗ demo/quick용 브랜드 yaml이 없습니다. brands/examples/*.yaml을 확인하세요.", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def _brand_label_from_hint(brand_hint: str) -> str:
    """회사명 또는 URL 힌트를 preview용 워드마크 텍스트로 정리한다."""
    hint = brand_hint.strip()
    if not hint:
        return ""
    if "://" in hint:
        parsed = urlparse(hint)
        host = (parsed.netloc or parsed.path).strip().lower()
        if host.startswith("www."):
            host = host[4:]
        return host[:48]
    return hint[:48]


def _apply_quick_brand_hint(brand: dict, brand_hint: str) -> dict:
    """quick 입력의 브랜드/단체명 또는 URL을 저장 없이 preview용 워드마크에 반영한다."""
    label = _brand_label_from_hint(brand_hint)
    if not label:
        return brand
    brand = dict(brand)
    brand["name"] = label
    wordmark = dict(brand.get("wordmark") or {})
    wordmark["text"] = label[:32]
    brand["wordmark"] = wordmark
    return brand


def _write_preview(brand: dict, event: str, skeleton_ids: list[str], attendees: list[dict], prefix: str, ts: str) -> Path:
    """시안 preview HTML을 저장하고 브라우저로 연다."""
    preview_html = build_preview_html(brand, event, skeleton_ids, attendees[:1])
    preview_path = OUTPUT_DIR / f"{prefix}-preview-{ts}.html"
    preview_path.write_text(preview_html, encoding="utf-8")
    webbrowser.open(f"file://{preview_path}")
    return preview_path


def skeleton_choice_label(skeleton_id: str) -> str:
    """CLI fallback에서도 내부 skeleton ID 대신 사용자용 스타일명만 보여준다."""
    descriptions = {
        "r1": "안정적인 기본형",
        "r2": "긴 이름/회사명에 유리",
        "r3": "강한 AI/해커톤 무드",
        "r4": "미니멀 프리미엄형",
    }
    return descriptions.get(skeleton_id.lower(), "브랜드 지정 스타일")


def _choose_skeleton(skeleton_ids: list[str]) -> str:
    """시안 후보 중 하나를 고른다. 비대화형에서는 첫 후보를 자동 선택한다."""
    if len(skeleton_ids) == 1:
        chosen = skeleton_ids[0]
        print(f"✓ 스타일 자동 선택: {skeleton_choice_label(chosen)}", file=sys.stderr)
        return chosen
    print("\n어떤 스타일로 출력할까요?", file=sys.stderr)
    for idx, sid in enumerate(skeleton_ids, 1):
        print(f"  {idx}. {skeleton_choice_label(sid)}", file=sys.stderr)
    if not sys.stdin.isatty():
        chosen = skeleton_ids[0]
        print(f"✓ 비대화형 입력이라 {skeleton_choice_label(chosen)} 자동 선택", file=sys.stderr)
        return chosen
    while True:
        try:
            ans = input("> ").strip()
            idx = int(ans)
            if 1 <= idx <= len(skeleton_ids):
                chosen = skeleton_ids[idx - 1]
                print(f"✓ {skeleton_choice_label(chosen)} 선택됨", file=sys.stderr)
                return chosen
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        print(f"1~{len(skeleton_ids)} 중 입력해 주세요.", file=sys.stderr)


def _write_output_html(attendees: list[dict], brand: dict, event: str, chosen: str, ts: str, *, fill_blanks: bool = True, prefix: str = "nametag") -> Path:
    """선택된 skeleton으로 최종 인쇄 HTML을 만든다."""
    template = _inject_variant_css(_inject_motif_css(inject_brand_tokens(load_skeleton_template(chosen), brand), brand))
    filled_html = build_pages(attendees, brand, event, fill_blanks=fill_blanks)
    out = OUTPUT_DIR / f"{prefix}-{ts}.html"
    out.write_text(template.replace("<!-- CELLS_HERE -->", filled_html), encoding="utf-8")
    return out


def _built_in_showcase_brand() -> dict:
    """PyYAML/브랜드 파일 없이도 showcase가 열리도록 하는 내장 fallback."""
    return {
        "schema_version": "1",
        "name": "Event Brand",
        "slug": "event-brand",
        "colors": {
            "primary_dark": "#171717",
            "primary_light": "#fafafa",
            "accent_1": "#71717a",
            "accent_2": "#a1a1aa",
            "surface_subtle": "#e4e4e7",
        },
        "wordmark": {"text": "Event Brand", "case": "title"},
        "signature": {"type": "none"},
    }


def run_showcase(args) -> None:
    """묻지 않고 행사 목적별 제품 카드 8개를 한 화면에 보여준다."""
    brand_slug = args.brand or "event-brand"
    if args.brand:
        brand = load_brand(args.brand)
    else:
        if yaml is None:
            brand = _built_in_showcase_brand()
        else:
            try:
                brand_slug = _default_demo_brand_slug()
                brand = load_brand(brand_slug)
            except SystemExit:
                brand = _built_in_showcase_brand()
    brand_hint = (args.brand_hint or "").strip()
    if brand_hint:
        brand = _apply_quick_brand_hint(brand, brand_hint)
    event = args.event.strip() or "AI Meetup Demo"
    text = read_input(args) if (args.file or args.names or not sys.stdin.isatty()) else ""
    attendees, _dropped = parse_attendees(text) if text else ([], {})
    if not attendees:
        attendees = [
            {"name": "김지원", "company": "LiveClass", "role": "HR Lead", "intro": "채용과 조직문화를 만듭니다"},
            {"name": "박서연", "company": "Acme Lab", "role": "Product Manager", "intro": "AI 제품을 기획합니다"},
        ]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"mood-showcase-{ts}.html"
    out.write_text(build_showcase_html(brand, event, attendees), encoding="utf-8")
    webbrowser.open(f"file://{out}")
    print("✓ 행사 목적별 네임택 제품 카드 쇼케이스 생성", file=sys.stderr)
    print(f"  브랜드: {brand.get('name', brand_slug)}", file=sys.stderr)
    print(f"  행사: {event}", file=sys.stderr)
    print(f"  미리보기: {out}", file=sys.stderr)
    print("  포함: 이름 가독성 / 네트워킹·한줄소개 / 채용행사 / 스피커·스태프·VIP / AI·해커톤 / 프리미엄 살롱 / 교육·워크숍 / QR·LinkedIn", file=sys.stderr)


def run_demo(html_only: bool = True) -> None:
    """아무 입력 없이 샘플 네임택 preview를 만든다."""
    brand_slug = _default_demo_brand_slug()
    brand = load_brand(brand_slug)
    event = "AI Meetup Demo"
    attendees = [
        {"name": "김지원", "company": "LiveClass", "role": "HR Lead", "intro": "채용과 조직문화를 만듭니다"},
        {"name": "박서연", "company": "Acme Lab", "role": "Product Manager", "intro": "AI 제품을 기획합니다"},
        {"name": "이도윤", "company": "Delta Society", "role": "Engineer", "intro": "자동화를 좋아합니다"},
    ]
    skeleton_ids = get_candidate_skeletons(brand)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    preview_path = _write_preview(brand, event, skeleton_ids, attendees, "demo", ts)
    print("✓ 샘플 네임택 preview 생성", file=sys.stderr)
    print(f"  브랜드: {brand_slug}", file=sys.stderr)
    print(f"  미리보기: {preview_path}", file=sys.stderr)

    if not html_only:
        chosen = skeleton_ids[0]
        out = _write_output_html(attendees, brand, event, chosen, ts, prefix="demo-nametag")
        print(f"  출력 HTML: {out}", file=sys.stderr)
        finalize_output(out, html_only=False, brand=brand, ignore_ink=True)
    else:
        print("  다음: eventnametag quick 으로 실제 행사명/명단을 붙여넣어 만드세요.", file=sys.stderr)
        print_label_paper_guidance()


def run_quick(args) -> None:
    """비개발자용 빠른 생성 wizard."""
    print("\neventnametag quick — 5분 안에 행사 네임택 만들기", file=sys.stderr)

    event = args.event.strip()
    if not event and sys.stdin.isatty():
        event = input("행사명을 입력하세요: ").strip()
    if not event:
        event = "Event"

    brand_slug = args.brand or _default_demo_brand_slug()
    brand = load_brand(brand_slug)
    brand_hint = (args.brand_hint or "").strip()
    if not brand_hint and not args.brand and sys.stdin.isatty():
        brand_hint = input("브랜드/단체 이름이나 URL이 있나요? (없으면 Enter): ").strip()
    brand = _apply_quick_brand_hint(brand, brand_hint)
    # P1-B/C: CLI 벡터 장식 플래그 오버라이드 (Codex parity)
    brand = apply_design_overrides(
        brand, pattern=getattr(args, "pattern", None),
        accent_shape=getattr(args, "accent_shape", None),
        motif_id=getattr(args, "motif", None))

    text = ""
    if args.file or args.names or not sys.stdin.isatty():
        text = read_input(args)
    else:
        print("\n참석자 명단을 붙여넣으세요. Ctrl+D로 종료합니다.", file=sys.stderr)
        print("예: 김지원<Tab>LiveClass<Tab>HR Lead<Tab>채용과 조직문화를 만듭니다", file=sys.stderr)
        text = sys.stdin.read()

    attendees, dropped = parse_attendees(text)
    if not attendees:
        print("✗ 참석자 명단이 비어있거나 파싱 실패", file=sys.stderr)
        print("  예: eventnametag quick --names '김지원,박서연,이도윤'", file=sys.stderr)
        sys.exit(1)

    skeleton_ids = get_candidate_skeletons(brand)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"\n{format_parse_summary(len(attendees), dropped)}", file=sys.stderr)

    # quick은 사용자가 “바로 만들어줘”라고 들어온 경로다.
    # 별도 preview 탭/스타일 선택을 만들지 않고, BI/명단 기준 첫 안전 스타일로 바로 출력한다.
    # 디자인 비교가 필요한 사용자는 showcase/demo를 명시적으로 호출한다.
    chosen = skeleton_ids[0]
    print(f"✓ 스타일 자동 선택: {skeleton_choice_label(chosen)}", file=sys.stderr)
    out = _write_output_html(attendees, brand, event, chosen, ts, fill_blanks=args.fill_blanks, prefix="quick-nametag")
    pages = (len(attendees) + 7) // 8
    print("✓ 인쇄용 네임택 생성", file=sys.stderr)
    print(f"  행사: {event}", file=sys.stderr)
    print(f"  인원/페이지: {len(attendees)}명 / {pages}페이지", file=sys.stderr)
    if args.html_only:
        print(f"  HTML-only 출력 파일: {out}", file=sys.stderr)
    # P0: 기본은 인쇄안전 닫힌 루프. escape hatch(--ignore-ink/--no-contrast-check)는 finalize_output에서 우회.
    # skeleton: quick에서 자동 선택한 chosen을 전달해 게이트 재빌드와 최종 출력이 일치하게 한다.
    finalize_output(
        out, args.html_only, brand=brand,
        ignore_ink=args.ignore_ink, no_contrast_check=getattr(args, "no_contrast_check", False),
        safety_loop={"attendees": attendees, "event": event, "fill_blanks": args.fill_blanks,
                     "skeleton": chosen},
    )


# ─────────────────────── BI 등록 (v0.1: 수동 안내) ───────────────────────

def register_brand() -> None:
    """BI 등록 — 3가지 입구 분기.
       1) 직접 yaml 편집  2) 인터뷰  3) URL 추출 (v0.1 정식, v0.2 자동 fallback 강화)."""
    print("\n📝 BI 등록 — 입구를 선택하세요.", file=sys.stderr)
    print("   1. 직접 yaml 편집 (개발자)", file=sys.stderr)
    print("   2. 인터뷰 (Claude가 질문)", file=sys.stderr)
    print("   3. 웹사이트 URL 자동 추출", file=sys.stderr)
    USER_BRANDS_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            ans = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n취소됨.", file=sys.stderr)
            return
        if ans in ("1", "2", "3"):
            break
        print("1, 2, 또는 3을 입력해 주세요.", file=sys.stderr)

    if ans == "1":
        _register_brand_manual()
    elif ans == "2":
        _register_brand_interview()
    else:
        _register_brand_extract()


def _register_brand_manual() -> None:
    """직접 yaml 편집 — examples 복사 + 검증 안내."""
    print(f"\n다음 절차로 BI를 등록하세요:", file=sys.stderr)
    print(f"  1. 가장 가까운 example을 복사:", file=sys.stderr)
    avail = list_available_brands()
    for ex in avail.get("examples", []):
        print(f"     cp {EXAMPLES_DIR}/{ex}.yaml {USER_BRANDS_DIR}/<your-slug>.yaml", file=sys.stderr)
    print(f"\n  2. 에디터로 열어서 컬러·워드마크·preferred_skeletons 수정:", file=sys.stderr)
    print(f"     $EDITOR {USER_BRANDS_DIR}/<your-slug>.yaml", file=sys.stderr)
    print(f"\n  3. 검증:", file=sys.stderr)
    print(f"     python3 {Path(__file__).name} --validate {USER_BRANDS_DIR}/<your-slug>.yaml", file=sys.stderr)
    print(f"\n  4. 첫 사용:", file=sys.stderr)
    print(f"     python3 {Path(__file__).name} --brand <your-slug> --event '...'", file=sys.stderr)


def _register_brand_interview() -> None:
    """인터뷰 모듈 호출."""
    try:
        from interview import run_interview  # type: ignore
    except ImportError:
        # 동일 디렉토리 import 보장
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from interview import run_interview  # type: ignore
    run_interview()


def _register_brand_extract() -> None:
    """URL 추출 모듈 호출. 추출 실패 시 인터뷰로 fallback."""
    try:
        from extract_brand import run_extract  # type: ignore
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from extract_brand import run_extract  # type: ignore
    run_extract()


# ─────────────────────── 명단 입력 ───────────────────────

def read_input(args) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.names:
        return "\n".join(n.strip() for n in args.names.split(",") if n.strip())
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("참석자 명단을 붙여넣으세요 (Ctrl+D로 종료):", file=sys.stderr)
    return sys.stdin.read()


# ─────────────────────── main ───────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서. main에서 분리해 테스트(Codex parity)에서도 직접 검증 가능하게 한다."""
    ap = argparse.ArgumentParser(
        description="eventnametag — 회사 BI 적용 행사 네임택 (탐사 A4 8칸 라벨지)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "command",
        nargs="?",
        choices=["demo", "doctor", "quick", "showcase", "order-paper", "calibrate", "register-brand"],
        help="짧은 실행 명령: demo / doctor / quick / showcase / order-paper / calibrate / register-brand",
    )
    ap.add_argument("--brand", "-b", help="사용할 BI yaml slug")
    ap.add_argument("--event", "-e", default="", help="행사명")
    ap.add_argument("--file", "-f", help="CSV 파일 경로")
    ap.add_argument("--names", "-n", help="이름만 쉼표로")
    ap.add_argument("--brand-hint", help="showcase/quick preview용 브랜드·단체명 힌트")

    ap.add_argument("--demo", action="store_true", help="샘플 브랜드+명단으로 즉시 preview 생성")
    ap.add_argument("--showcase", action="store_true", help="질문 없이 행사 목적별 8개 제품 카드 쇼케이스 생성")
    ap.add_argument("--quick", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--doctor", action="store_true", help="의존성/브랜드/인쇄 환경 점검")
    ap.add_argument("--register-brand", action="store_true", help="새 BI 등록")
    ap.add_argument("--order-paper", action="store_true", help="쿠팡 라벨지 재구매 페이지 오픈")
    ap.add_argument("--calibrate", action="store_true", help="정렬 테스트 시트")
    ap.add_argument("--validate", help="BI yaml schema 검증만 수행 후 종료")

    ap.add_argument("--blank", action="store_true", help="백지 네임택 8칸")
    ap.add_argument("--both", action="store_true", help="명단 + 예비지")
    ap.add_argument("--spares", type=int, default=8)
    ap.add_argument("--fill-blanks", action="store_true", help="남는 칸을 워드마크 blank로")

    # P1: 셀 레이아웃 변형 강제 (미지정 시 brand.design.layout_variant > 자동 diagonal)
    ap.add_argument("--layout-variant", choices=list(LAYOUT_VARIANTS),
                    help="셀 레이아웃 변형: diagonal(기본·대각 컬러블록) / name_hero(이름 강조) / intro_hero(소개·관심사 강조) / badge_first(역할·트랙 배지)")

    # P1-B/C: 벡터 장식 선택 (Codex parity — brand.design 필드를 CLI로 오버라이드)
    ap.add_argument("--pattern", choices=list(PATTERN_IDS),
                    help="배경 벡터 패턴: dot-grid / stripe / wave / mesh-corner")
    ap.add_argument("--accent-shape", choices=list(ACCENT_SHAPE_IDS),
                    help="코너 강조 벡터 도형: triangle / blob")
    ap.add_argument("--motif", choices=_available_motif_ids(),
                    help="내장 벡터 모티프 ID (일러스트 슬롯). brand.design.motif_id 오버라이드")

    ap.add_argument("--html-only", action="store_true", help="HTML만 생성 (디버그)")
    ap.add_argument("--no-contrast-check", action="store_true", help="G2 강행")
    ap.add_argument("--ignore-ink", action="store_true", help="G3 강행")
    return ap


def main():
    ap = _build_arg_parser()
    args = ap.parse_args()

    # 짧은 명령 alias: eventnametag demo/doctor/quick ...
    if args.command == "demo":
        args.demo = True
    elif args.command == "doctor":
        args.doctor = True
    elif args.command == "quick":
        args.quick = True
    elif args.command == "showcase":
        args.showcase = True
    elif args.command == "order-paper":
        args.order_paper = True
    elif args.command == "calibrate":
        args.calibrate = True
    elif args.command == "register-brand":
        args.register_brand = True

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 단순 명령들 (라벨지 분기 skip)
    if args.doctor:
        run_doctor()
        return
    if args.demo:
        ask_label_paper_once()
        run_demo(html_only=args.html_only)
        return
    if args.showcase:
        ask_label_paper_once()
        run_showcase(args)
        return
    if args.quick:
        ask_label_paper_once()
        run_quick(args)
        return
    if args.validate:
        validate_brand_only(args.validate)
        return
    if args.order_paper:
        order_paper()
        return
    if args.register_brand:
        register_brand()
        return
    if args.calibrate:
        run_calibrate()
        return

    # 메인 흐름 — 실제 인쇄에 필요한 라벨지를 먼저 확인한다.
    # 오늘 주문하면 내일 받아 바로 인쇄할 수 있다는 전제를 보존한다.
    ask_label_paper_once()

    # BI 미지정 시 안내
    if not args.brand:
        avail = list_available_brands()
        print("\n⚠️  --brand <slug> 지정 필요. 사용 가능한 BI:", file=sys.stderr)
        if avail["user"]:
            print(f"   user:     {', '.join(avail['user'])}", file=sys.stderr)
        if avail["examples"]:
            print(f"   examples: {', '.join(avail['examples'])}", file=sys.stderr)
        print(f"\n새 BI 등록: --register-brand", file=sys.stderr)
        sys.exit(1)

    brand = load_brand(args.brand)
    # P1-B/C: CLI 벡터 장식 플래그를 brand.design에 오버라이드 (Codex parity)
    brand = apply_design_overrides(
        brand, pattern=args.pattern, accent_shape=args.accent_shape,
        motif_id=getattr(args, "motif", None))

    # G2: 컬러 대비 검사 (BI 로드 직후, 시안 생성 전에 한 번)
    check_color_contrast(brand, no_check=args.no_contrast_check)

    # 시안 후보 skeleton
    skeleton_ids = get_candidate_skeletons(brand)

    event = args.event.strip()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    # blank 전용 모드
    if args.blank and not args.both:
        # blank 모드는 첫 후보 skeleton 사용 (사용자 미리보기 skip — blank는 비교 의미 적음)
        chosen = skeleton_ids[0]
        template = _inject_variant_css(_inject_motif_css(inject_brand_tokens(load_skeleton_template(chosen), brand), brand))
        sheet_html = build_blank_pages(args.spares if args.spares > 0 else 8, brand, event)
        output_html = template.replace("<!-- CELLS_HERE -->", sheet_html)
        out = OUTPUT_DIR / f"nametag-blank-{ts}.html"
        out.write_text(output_html, encoding="utf-8")
        print(f"✓ 빈 네임택 {args.spares}칸 ({skeleton_choice_label(chosen)}): {out}", file=sys.stderr)
        finalize_output(out, args.html_only, brand=brand, ignore_ink=args.ignore_ink)
        return

    # 명단 파싱
    text = read_input(args)
    attendees, dropped = parse_attendees(text)
    if not attendees:
        print("✗ 참석자 명단이 비어있거나 파싱 실패", file=sys.stderr)
        sys.exit(1)
    print(format_parse_summary(len(attendees), dropped), file=sys.stderr)

    # 시안 선택 (skeleton이 1개면 자동 선택, 2+개면 미리보기)
    if len(skeleton_ids) == 1:
        chosen = skeleton_ids[0]
        print(f"✓ 스타일 자동 선택: {skeleton_choice_label(chosen)} (BI에 1개만 지정됨)", file=sys.stderr)
    else:
        # 시안 미리보기 HTML 생성 + 자동 오픈
        preview_html = build_preview_html(brand, event, skeleton_ids, attendees[:1])
        preview_path = OUTPUT_DIR / f"preview-{ts}.html"
        preview_path.write_text(preview_html, encoding="utf-8")
        webbrowser.open(f"file://{preview_path}")
        print(f"\n🌐 시안 미리보기 자동 오픈 → 어떤 스타일로 인쇄할까요?", file=sys.stderr)
        for idx, sid in enumerate(skeleton_ids, 1):
            print(f"   {idx}. {skeleton_choice_label(sid)}", file=sys.stderr)
        while True:
            try:
                ans = input("> ").strip()
                idx = int(ans)
                if 1 <= idx <= len(skeleton_ids):
                    chosen = skeleton_ids[idx - 1]
                    break
            except ValueError:
                pass
            print(f"1~{len(skeleton_ids)} 중 입력해 주세요.", file=sys.stderr)
        print(f"✓ {skeleton_choice_label(chosen)} 선택됨", file=sys.stderr)

    # 선택된 skeleton + 명단 → 8칸 페이지
    template = _inject_variant_css(_inject_motif_css(inject_brand_tokens(load_skeleton_template(chosen), brand), brand))
    filled_html = build_pages(attendees, brand, event, fill_blanks=args.fill_blanks,
                              layout_variant=args.layout_variant)
    pages = (len(attendees) + 7) // 8

    if args.both:
        blank_html = build_blank_pages(args.spares, brand, event)
        combined = filled_html + "\n" + blank_html
        output_html = template.replace("<!-- CELLS_HERE -->", combined)
        out = OUTPUT_DIR / f"nametag-both-{ts}.html"
        blank_pages = (args.spares + 7) // 8
        print(f"✓ {len(attendees)}명({pages}p) + 예비 {args.spares}칸({blank_pages}p) [{skeleton_choice_label(chosen)}]: {out}", file=sys.stderr)
    else:
        output_html = template.replace("<!-- CELLS_HERE -->", filled_html)
        out = OUTPUT_DIR / f"nametag-{ts}.html"
        print(f"✓ {len(attendees)}명, {pages}페이지 [{skeleton_choice_label(chosen)}]: {out}", file=sys.stderr)

    out.write_text(output_html, encoding="utf-8")
    # P0: 기본은 인쇄안전 닫힌 루프(render→verify→retry→fallback). escape hatch는 finalize_output에서 우회.
    # --both는 명단+예비지 혼합 페이지라 루프 재빌드가 예비 칸을 누락시키므로 기존 단순 렌더 경로 유지.
    # skeleton: 사용자가 preview에서 고른 chosen을 전달해 게이트 재빌드와 최종 출력이 일치하게 한다.
    # --both는 명단+예비지 혼합 페이지라 루프 재빌드가 예비 칸을 누락시키므로 기존 단순 렌더 경로 유지.
    safety_loop = None if args.both else {
        "attendees": attendees, "event": event,
        "layout_variant": args.layout_variant, "fill_blanks": args.fill_blanks,
        "skeleton": chosen,
    }
    finalize_output(
        out, args.html_only, brand=brand,
        ignore_ink=args.ignore_ink, no_contrast_check=args.no_contrast_check,
        safety_loop=safety_loop,
    )


if __name__ == "__main__":
    main()
