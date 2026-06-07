#!/usr/bin/env python3
"""
eventnametag — URL 자동 추출 모듈.

URL을 입력받아 fetch → DOM/CSS에서 컬러 5개 빈도 추출 + <title>·og:site_name에서
워드마크 텍스트 추출 → 사용자 미리보기 → [Y/n/edit].

stdlib만으로 동작 (urllib.request + html.parser + 정규식). BeautifulSoup 미사용.
실패 시 친절한 에러와 함께 interview.py로 fallback 안내.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml  # type: ignore
except ImportError:
    print("✗ PyYAML 미설치. `pip install -r requirements.txt`", file=sys.stderr)
    sys.exit(2)

# 공유 유틸 (sys.path: 직접 실행·다른 스크립트가 import할 때 모두 동작)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _brand_util import _luminance, _normalize_hex, _rgb_to_hex, suggest_slug  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
USER_DIR = Path.home() / ".config" / "eventnametag"
USER_BRANDS_DIR = USER_DIR / "brands"

# CSS 컬러 인식: hex (3·6자리), rgb(r,g,b), rgba(...)
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)")
USER_AGENT = "eventnametag/0.1"
FETCH_TIMEOUT = 10


class _MetaCollector(HTMLParser):
    """<title>, og:site_name, og:title, theme-color, <link href> 수집."""

    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title = ""
        self.og_site_name = ""
        self.og_title = ""
        self.theme_color = ""
        self.style_blocks: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self.in_title = True
            return
        if tag == "style":
            self._in_style = True
            return
        if tag == "meta":
            prop = (d.get("property") or "").lower()
            name = (d.get("name") or "").lower()
            content = d.get("content") or ""
            if prop == "og:site_name":
                self.og_site_name = content.strip()
            elif prop == "og:title":
                self.og_title = content.strip()
            elif name == "theme-color" and content:
                self.theme_color = content.strip()

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self._in_style:
            self.style_blocks.append(data)


def _fetch(url: str) -> str:
    """URL fetch. 에러 시 RuntimeError raise."""
    if not url.startswith(("http://", "https://")):
        raise RuntimeError(f"URL은 http:// 또는 https://로 시작해야 합니다: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            data = resp.read()
        return data.decode(charset, errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL fetch 실패 ({url}): {e}") from e
    except TimeoutError as e:
        raise RuntimeError(f"URL fetch 타임아웃 ({FETCH_TIMEOUT}초): {url}") from e


def _extract_colors(html_text: str, style_blocks: list[str]) -> list[str]:
    """HTML과 inline/style 블록에서 컬러 추출. 빈도순 상위 5개."""
    colors: list[str] = []
    for source in [html_text] + style_blocks:
        for match in HEX_RE.finditer(source):
            colors.append(_normalize_hex(match.group(0)))
        for r, g, b in RGB_RE.findall(source):
            try:
                colors.append(_rgb_to_hex(int(r), int(g), int(b)))
            except ValueError:
                continue

    if not colors:
        return []

    # 너무 흔한 흑·백·완전 회색은 빈도가 높아도 noise일 수 있으니 따로 둠.
    NOISE = {"#ffffff", "#000000", "#fff", "#000"}
    counter = Counter(colors)
    ranked = [c for c, _ in counter.most_common() if c not in NOISE]
    # noise 색도 포함 (이후 사용자가 거부할 수 있음)
    noise_present = [c for c in counter if c in NOISE]
    return (ranked[:4] + noise_present[:1])[:5]


def _extract_wordmark(meta: _MetaCollector, url: str) -> str:
    """og:site_name → <title> → URL 호스트 순으로 fallback."""
    candidates = [meta.og_site_name, meta.title, meta.og_title]
    for c in candidates:
        c = (c or "").strip()
        if c:
            # title이 "Foo - Subpage" 형태면 첫 토큰만
            for sep in [" | ", " — ", " - ", " · "]:
                if sep in c:
                    c = c.split(sep)[0].strip()
                    break
            if c:
                return c
    host = urlparse(url).netloc
    if host.startswith("www."):
        host = host[4:]
    return host or "Unknown Brand"


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"  {prompt}{suffix} > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n취소됨.", file=sys.stderr)
        sys.exit(130)
    return ans or (default or "")


def run_extract() -> None:
    """URL 입력 → 추출 → 미리보기 → [Y/n/edit] 분기."""
    print("\n🌐 웹사이트 URL 자동 추출", file=sys.stderr)
    url = _ask("URL")
    if not url:
        print("✗ URL이 비어 있습니다.", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"  fetching... ({url})", file=sys.stderr)
        html_text = _fetch(url)
    except RuntimeError as e:
        print(f"\n✗ {e}", file=sys.stderr)
        print("  추출 실패 — 인터뷰 모드로 진행하시겠습니까?", file=sys.stderr)
        ans = _ask("인터뷰로 fallback (y/n)", default="y").lower()
        if ans == "y":
            _fallback_to_interview()
        else:
            sys.exit(1)
        return

    parser = _MetaCollector()
    try:
        parser.feed(html_text)
    except Exception as e:  # HTML 파싱은 실패해도 raw text로 색상은 잡힘
        print(f"⚠️  HTML 구조 파싱 일부 실패 ({e}). 컬러는 raw text에서 추출.", file=sys.stderr)

    wordmark = _extract_wordmark(parser, url)
    colors = _extract_colors(html_text, parser.style_blocks)
    if parser.theme_color and parser.theme_color not in colors:
        # theme-color는 브랜드 의도 색이므로 우선
        colors.insert(0, _normalize_hex(parser.theme_color))
        colors = colors[:5]

    print("\n🔎 추출 결과:", file=sys.stderr)
    print(f"   워드마크: {wordmark}", file=sys.stderr)
    print(f"   컬러 후보: {', '.join(colors) if colors else '(추출 실패)'}", file=sys.stderr)

    if not colors:
        print("\n⚠️  컬러를 1개도 추출하지 못했습니다. 인터뷰로 진행을 권장합니다.", file=sys.stderr)
        ans = _ask("인터뷰로 fallback (y/n)", default="y").lower()
        if ans == "y":
            _fallback_to_interview(seed_name=wordmark)
        return

    print("\n  Y. 이 결과로 진행", file=sys.stderr)
    print("  e. 인터뷰로 보정", file=sys.stderr)
    print("  n. 취소", file=sys.stderr)
    while True:
        ans = _ask("선택", default="Y").lower()
        if ans in ("y", ""):
            _save_extracted(wordmark, colors)
            return
        if ans == "e":
            _fallback_to_interview(seed_name=wordmark, seed_colors=colors)
            return
        if ans == "n":
            print("취소됨.", file=sys.stderr)
            return
        print("  Y / e / n 중 입력해 주세요.", file=sys.stderr)


def build_brand_from_logo(colors: list[str], wordmark: str) -> dict:
    """로고에서 뽑은 색 + 워드마크로 brand dict 구성.

    색은 ingest_logo가 분류(결정론). `_labels`(symbol/mood)는 에이전트 vision이
    채울 스텁. `design` 슬롯은 비워 두고 에이전트가 yaml에 조판한다.
    vision에 hex를 묻지 않는다 — 색은 위 픽셀/정규식 결과만."""
    import ingest_logo  # noqa: PLC0415

    classified = ingest_logo.logo_to_brand_colors(colors)
    return {
        "schema_version": "1",
        "name": wordmark,
        "slug": suggest_slug(wordmark),
        "colors": classified,
        "wordmark": {"text": wordmark, "case": "title"},
        "signature": {"type": "none"},
        "design": {  # 에이전트가 vision 라벨을 보고 채움(Task 7 계약)
            "layout_variant": "name_hero",
            "illustration_svg_inline": "",
            "logo_svg_inline": "",
        },
        "_labels": {  # 에이전트 vision 보조 라벨(색 아님). yaml 저장 시 주석으로만.
            "symbol": "",
            "mood": "",
        },
    }


def _save_extracted(wordmark: str, colors: list[str]) -> None:
    """추출 결과를 yaml로 직접 저장."""
    slug = suggest_slug(wordmark)
    primary_dark = next((c for c in colors if _is_dark(c)), colors[0])
    primary_light = next(
        (c for c in colors if c not in {primary_dark} and _is_light(c)),
        "#ffffff",
    )
    accents = [c for c in colors if c not in {primary_dark, primary_light}][:2]

    brand: dict = {
        "schema_version": "1",
        "name": wordmark,
        "slug": slug,
        "colors": {
            "primary_dark": primary_dark,
            "primary_light": primary_light,
        },
        "wordmark": {"text": wordmark, "case": "title"},
        "signature": {"type": "none"},
    }
    if accents:
        brand["colors"]["accent_1"] = accents[0]
    if len(accents) > 1:
        brand["colors"]["accent_2"] = accents[1]

    USER_BRANDS_DIR.mkdir(parents=True, exist_ok=True)
    out = USER_BRANDS_DIR / f"{slug}.yaml"
    if out.exists():
        ans = _ask(f"{out.name} 존재합니다. 덮어쓸까요? (y/n)", default="n").lower()
        if ans != "y":
            print("✗ 취소됨.", file=sys.stderr)
            return
    yaml_text = yaml.safe_dump(brand, allow_unicode=True, sort_keys=False)
    out.write_text(yaml_text, encoding="utf-8")
    print(f"\n✅ 저장: {out}", file=sys.stderr)
    print(f"   첫 사용: python3 scripts/generate.py --brand {slug} --event '...'", file=sys.stderr)


def _fallback_to_interview(*, seed_name: str = "", seed_colors: list[str] | None = None) -> None:
    """인터뷰로 진입. URL 추출 결과를 seed로 전달."""
    try:
        from interview import run_interview  # type: ignore
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from interview import run_interview  # type: ignore
    # 현재 run_interview는 seed dict를 외부에서 받는 인터페이스가 없으므로 안내만.
    if seed_name or seed_colors:
        print("\n📌 추출 정보 참고:", file=sys.stderr)
        if seed_name:
            print(f"   회사명 후보: {seed_name}", file=sys.stderr)
        if seed_colors:
            print(f"   컬러 후보: {', '.join(seed_colors)}", file=sys.stderr)
        print("", file=sys.stderr)
    run_interview()


def _is_dark(hex_color: str) -> bool:
    """대략 luminance < 0.5."""
    return _luminance(hex_color) < 0.5


def _is_light(hex_color: str) -> bool:
    return _luminance(hex_color) >= 0.5


def main():
    run_extract()


if __name__ == "__main__":
    main()
