"""인라인 SVG 새니타이즈 — 로컬 Chrome 렌더 전 위험 요소 제거.

로컬 렌더(서버 미노출)라 XSS 노출은 낮지만, 신뢰 못 할 SVG가
Chrome에서 외부 fetch/스크립트를 돌리지 않도록 방어한다. 이 함수는
사용자 제공 SVG(로고/일러스트)의 **유일한 보안 경계**이므로 fail-closed로 둔다:
위험 요소를 제거한 뒤에도 위험 잔여가 남으면 SVG를 통째로 거부('' 반환)한다.
호출부는 ''를 받으면 워드마크 텍스트로 fallback한다.
"""
import re

# 제거 대상 태그 (SMIL 애니메이션 포함 — href를 javascript:로 변이 가능)
_TAG_BLOCKLIST = (
    "script", "style", "foreignobject", "iframe", "image", "use", "a",
    "set", "animate", "animatetransform", "animatemotion", "handler", "listener",
)
# 이벤트 핸들러·href 속성: 큰따옴표 / 작은따옴표 / 무인용 모두 매칭
# lookbehind(비소비)로 구분자를 소비하지 않아 인접 핸들러 쌍도 반복 제거 가능
_EVENT_ATTR_RE = re.compile(r"""(?<=[\s"'/>])on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.IGNORECASE)
_HREF_ATTR_RE = re.compile(r"""\s(?:xlink:href|href)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", re.IGNORECASE)
# SVG 표준 네임스페이스 xmlns 속성 — 무해하므로 fail-closed 스캔 전에 제거
# sub(" ", ...) 로 공백을 남겨 인접 토큰이 글루되지 않도록 함
_XMLNS_SVG_RE = re.compile(
    r"""\sxmlns(?::\w+)?\s*=\s*["']https?://www\.w3\.org/[^"']*["']""",
    re.IGNORECASE,
)
# fail-closed 재스캔용
_DANGER_RE = re.compile(r"(javascript:|data:image/(png|jpe?g|gif|webp|bmp)|https?:|//)", re.IGNORECASE)
# 경계 없음 — 스트립 후 on\w+= 가 어디에든 남으면 통째 거부 (whack-a-mole 종결)
_RESIDUAL_EVENT_RE = re.compile(r"on\w+\s*=", re.IGNORECASE)


def sanitize_svg(svg: str) -> str:
    """인라인 SVG를 새니타이즈한다. SVG가 아니거나 위험 잔여가 있으면 ''."""
    if not svg or "<svg" not in svg.lower():
        return ""
    out = svg
    # 1) 위험 태그 제거 — 중첩 회피 위해 변화 없을 때까지 반복(최대 5회)
    for _ in range(5):
        before = out
        for tag in _TAG_BLOCKLIST:
            # 여는~닫는 쌍 (본문 포함)
            out = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}\s*>", "", out, flags=re.IGNORECASE | re.DOTALL)
            # self-closing / 여는 단독
            out = re.sub(rf"<{tag}\b[^>]*/?>", "", out, flags=re.IGNORECASE)
            # 고아 닫는 태그
            out = re.sub(rf"</{tag}\s*>", "", out, flags=re.IGNORECASE)
        if out == before:
            break
    # 2) 이벤트 핸들러·href 속성 제거 (모든 인용 형태)
    # lookbehind 비소비 패턴이므로 인접 핸들러 쌍을 처리하려면 fixpoint까지 반복
    for _ in range(5):
        before = out
        out = _EVENT_ATTR_RE.sub("", out)
        if out == before:
            break
    out = _HREF_ATTR_RE.sub("", out)
    # 2b) SVG 표준 네임스페이스 xmlns 속성 제거 — http://www.w3.org/… 는 무해
    #     fail-closed _DANGER_RE 에서 https?:// 로 잘못 거부되는 것을 방지
    out = _XMLNS_SVG_RE.sub(" ", out)
    # 3) fail-closed 재스캔 — 위험 잔여가 조금이라도 있으면 통째로 거부
    low = out.lower()
    if any(f"<{tag}" in low for tag in _TAG_BLOCKLIST):
        return ""
    if _RESIDUAL_EVENT_RE.search(out):
        return ""
    if _DANGER_RE.search(out):
        return ""
    return out
