"""내장 모티프 라이브러리 — repo-baked, print-safe 벡터 SVG.

어떤 에이전트(Codex 포함)든 외부 자산 0으로 장식을 선택할 수 있게 한다.
모든 모티프는 단색 path/도형만 사용(저잉크), 외부 fetch·래스터 없음.
색은 currentColor로 두어 셀의 brand 색을 그대로 따른다.
"""

# 모든 SVG는: 외부 href 없음 / data:image 래스터 없음 / script·foreignObject 없음 /
# 단색(currentColor) 저강도(opacity) — 잉크 게이트(§6) 통과를 전제로 큐레이션.
_MOTIFS = {
    # 좌하단→우상단 코너 삼각 — 채용·스피커 카드용 절제된 기하
    "geo-corner": '<svg viewBox="0 0 40 40"><path d="M0 40 L40 0 L40 40 Z" fill="currentColor" opacity="0.12"/></svg>',
    # 가로 물결 띠 — 네트워킹·커뮤니티 카드용 부드러운 라인
    "wave-band": '<svg viewBox="0 0 100 12"><path d="M0 6 Q25 0 50 6 T100 6" stroke="currentColor" fill="none" stroke-width="1.2" opacity="0.5"/></svg>',
    # 점 군집 — 캐주얼·밋업 카드용 가벼운 텍스처
    "dot-cluster": '<svg viewBox="0 0 24 24"><g fill="currentColor" opacity="0.18"><circle cx="4" cy="4" r="1.5"/><circle cx="12" cy="6" r="1.5"/><circle cx="8" cy="14" r="1.5"/><circle cx="18" cy="12" r="1.5"/></g></svg>',
    # 동심 호 — 세미나·발표 카드용 차분한 방사 모티프
    "arc-rings": '<svg viewBox="0 0 40 40"><g stroke="currentColor" fill="none" stroke-width="1" opacity="0.22"><path d="M40 40 A30 30 0 0 0 10 40"/><path d="M40 40 A20 20 0 0 0 20 40"/><path d="M40 40 A10 10 0 0 0 30 40"/></g></svg>',
    # 사선 격자 — 운영·스태프 카드용 미니멀 그리드
    "cross-hatch": '<svg viewBox="0 0 40 40"><g stroke="currentColor" stroke-width="0.8" opacity="0.16"><path d="M0 10 L40 10 M0 20 L40 20 M0 30 L40 30"/><path d="M10 0 L10 40 M20 0 L20 40 M30 0 L30 40"/></g></svg>',
}


def list_motifs() -> list[str]:
    """사용 가능한 내장 모티프 ID 목록(정렬)."""
    return sorted(_MOTIFS)


def get_motif(motif_id: str) -> str:
    """모티프 ID로 인라인 SVG 원문을 반환. 없으면 빈 문자열."""
    return _MOTIFS.get(motif_id, "")
