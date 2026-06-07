#!/usr/bin/env python3
"""
eventnametag — BI 인터뷰 모듈.

generate.py --register-brand 시 모드(2번 인터뷰)에서 호출되는 모듈.
회사명/slug/colors/wordmark/signature/preferred_skeletons 순서로 질문하고,
각 입력을 검증한 뒤 ~/.config/eventnametag/brands/<slug>.yaml로 저장.

저장 직전 schema/brand.schema.json으로 한 번 더 검증해서 실패 시 재질문 루프.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    print("✗ PyYAML 미설치. `pip install -r requirements.txt`", file=sys.stderr)
    sys.exit(2)

try:
    import jsonschema  # type: ignore
except ImportError:
    jsonschema = None

# 공유 유틸 (sys.path: 직접 실행·다른 스크립트가 import할 때 모두 동작)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _brand_util import suggest_slug  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = SKILL_DIR / "schema" / "brand.schema.json"
USER_DIR = Path.home() / ".config" / "eventnametag"
USER_BRANDS_DIR = USER_DIR / "brands"

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
SIGNATURE_TYPES = {"gradient_orb", "icon_url", "none"}
SKELETON_IDS = {"r1", "r2", "r3", "r4"}


def _ask(prompt: str, *, default: str | None = None, allow_empty: bool = False) -> str:
    """입력 받기. default 있으면 빈 입력 시 default 반환."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            ans = input(f"  {prompt}{suffix} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n인터뷰 취소.", file=sys.stderr)
            sys.exit(130)
        if ans:
            return ans
        if default is not None:
            return default
        if allow_empty:
            return ""
        print("    값을 입력해 주세요.", file=sys.stderr)


def _ask_hex(prompt: str, *, default: str | None = None, optional: bool = False) -> str:
    """hex 색상 검증 입력."""
    while True:
        ans = _ask(prompt, default=default, allow_empty=optional)
        if not ans and optional:
            return ""
        if HEX_RE.match(ans):
            # 3자리 → 6자리로 정규화하지 않음 (yaml 그대로 보존)
            return ans
        print(f"    ✗ hex 색상 형식이 아닙니다 (예: #1a1a2e 또는 #abc).", file=sys.stderr)


def _ask_slug(prompt: str, *, default: str | None = None) -> str:
    while True:
        ans = _ask(prompt, default=default).lower()
        if SLUG_RE.match(ans):
            return ans
        print(
            "    ✗ slug는 소문자 영문/숫자/하이픈만, 3-32자, 영문 시작 + 영숫자 끝.",
            file=sys.stderr,
        )


def _ask_choice(prompt: str, choices: list[str], *, default: str | None = None) -> str:
    """제한된 보기 중 선택."""
    options = "/".join(choices)
    while True:
        ans = _ask(f"{prompt} ({options})", default=default).lower()
        if ans in choices:
            return ans
        print(f"    ✗ {options} 중 하나를 입력해 주세요.", file=sys.stderr)


def _ask_skeletons() -> list[str]:
    """preferred_skeletons. 빈 입력 = 4개 모두."""
    while True:
        ans = _ask(
            "선호 skeleton (r1/r2/r3/r4 쉼표로, 비우면 모두)",
            allow_empty=True,
        )
        if not ans:
            return []
        items = [s.strip().lower() for s in ans.split(",") if s.strip()]
        invalid = [s for s in items if s not in SKELETON_IDS]
        if invalid:
            print(f"    ✗ 알 수 없는 skeleton: {invalid}. r1/r2/r3/r4만 가능.", file=sys.stderr)
            continue
        # 중복 제거 + 입력 순서 보존
        seen = set()
        out: list[str] = []
        for s in items:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out


def _build_brand(seed: dict | None = None) -> dict:
    """인터뷰로 BI dict 빌드. seed가 있으면 재질문 시 기본값 채움."""
    seed = seed or {}
    seed_colors = seed.get("colors", {}) or {}
    seed_wm = seed.get("wordmark", {}) or {}
    seed_sig = seed.get("signature", {}) or {}
    seed_grad = seed_sig.get("gradient", {}) or {}

    print("\n🎙️  BI 인터뷰 — 비우면 기본값 또는 생략됩니다.\n", file=sys.stderr)

    name = _ask("회사·단체명", default=seed.get("name"))
    default_slug = seed.get("slug") or suggest_slug(name)
    slug = _ask_slug("slug (파일명·CLI 호출명, 소문자 hyphen)", default=default_slug)

    print("\n  ─── 컬러 토큰 ───", file=sys.stderr)
    primary_dark = _ask_hex("primary_dark (다크/강조 색)", default=seed_colors.get("primary_dark"))
    primary_light = _ask_hex(
        "primary_light (배경/라이트 색)",
        default=seed_colors.get("primary_light", "#ffffff"),
    )
    accent_1 = _ask_hex(
        "accent_1 (악센트 1, 비울 수 있음)",
        default=seed_colors.get("accent_1"),
        optional=True,
    )
    accent_2 = _ask_hex(
        "accent_2 (악센트 2, 비울 수 있음)",
        default=seed_colors.get("accent_2"),
        optional=True,
    )

    print("\n  ─── 워드마크 ───", file=sys.stderr)
    wm_text = _ask("워드마크 텍스트", default=seed_wm.get("text") or name)
    wm_case = _ask_choice(
        "워드마크 표기",
        ["title", "upper", "lower"],
        default=seed_wm.get("case", "title"),
    )

    print("\n  ─── 시그니처 ───", file=sys.stderr)
    sig_type = _ask_choice(
        "시그니처 타입",
        list(SIGNATURE_TYPES),
        default=seed_sig.get("type", "none"),
    )
    signature: dict[str, Any] | None
    if sig_type == "none":
        signature = {"type": "none"}
    elif sig_type == "gradient_orb":
        inner = _ask_hex("gradient inner color", default=seed_grad.get("inner") or accent_1 or primary_dark)
        outer = _ask_hex("gradient outer color", default=seed_grad.get("outer") or accent_2 or primary_dark)
        size_mm = _ask("크기 (mm)", default=str(seed_sig.get("size_mm", "3.5")))
        position = _ask_choice(
            "위치",
            ["left_of_wordmark", "right_of_wordmark", "replace_dot"],
            default=seed_sig.get("position", "left_of_wordmark"),
        )
        signature = {
            "type": "gradient_orb",
            "gradient": {"inner": inner, "outer": outer},
            "size_mm": _to_number(size_mm, default=3.5),
            "position": position,
        }
    else:  # icon_url
        url = _ask("아이콘 URL", default=seed_sig.get("icon_url"))
        size_mm = _ask("크기 (mm)", default=str(seed_sig.get("size_mm", "3.5")))
        position = _ask_choice(
            "위치",
            ["left_of_wordmark", "right_of_wordmark", "replace_dot"],
            default=seed_sig.get("position", "left_of_wordmark"),
        )
        signature = {
            "type": "icon_url",
            "icon_url": url,
            "size_mm": _to_number(size_mm, default=3.5),
            "position": position,
        }

    print("\n  ─── Skeleton 매칭 ───", file=sys.stderr)
    preferred = _ask_skeletons()

    brand: dict[str, Any] = {
        "schema_version": "1",
        "name": name,
        "slug": slug,
        "colors": {
            "primary_dark": primary_dark,
            "primary_light": primary_light,
        },
        "wordmark": {
            "text": wm_text,
            "case": wm_case,
        },
        "signature": signature,
    }
    if accent_1:
        brand["colors"]["accent_1"] = accent_1
    if accent_2:
        brand["colors"]["accent_2"] = accent_2
    if preferred:
        brand["preferred_skeletons"] = preferred

    return brand


def _to_number(val: str, *, default: float) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _validate(brand: dict) -> tuple[bool, str]:
    """schema 검증. (ok, error_message)."""
    if jsonschema is None:
        return True, "jsonschema 미설치 — 검증 skip"
    if not SCHEMA_FILE.exists():
        return True, "schema 파일 없음 — 검증 skip"
    try:
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        jsonschema.validate(brand, schema)
        return True, ""
    except jsonschema.ValidationError as e:  # type: ignore[union-attr]
        return False, e.message


def run_interview(*, target_dir: Path | None = None) -> Path:
    """인터뷰 실행 후 yaml 저장. 저장된 경로 반환."""
    target = target_dir or USER_BRANDS_DIR
    target.mkdir(parents=True, exist_ok=True)

    seed: dict | None = None
    while True:
        brand = _build_brand(seed=seed)
        ok, err = _validate(brand)
        if ok:
            break
        print(f"\n✗ schema 검증 실패: {err}", file=sys.stderr)
        print("  값을 다시 입력해 주세요. 이전 입력은 기본값으로 채워집니다.\n", file=sys.stderr)
        seed = brand  # 재시작 시 기본값으로 사용

    out = target / f"{brand['slug']}.yaml"
    if out.exists():
        ans = _ask_choice(
            f"이미 {out.name} 존재합니다. 덮어쓸까요?",
            ["y", "n"],
            default="n",
        )
        if ans != "y":
            print("✗ 취소됨. 다른 slug로 다시 실행해 주세요.", file=sys.stderr)
            sys.exit(1)

    yaml_text = yaml.safe_dump(
        brand,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    out.write_text(yaml_text, encoding="utf-8")
    print(f"\n✅ 저장: {out}", file=sys.stderr)
    print(f"   첫 사용: python3 scripts/generate.py --brand {brand['slug']} --event '...'", file=sys.stderr)
    return out


def main():
    """단독 실행 시 인터뷰 후 종료."""
    run_interview()


if __name__ == "__main__":
    main()
