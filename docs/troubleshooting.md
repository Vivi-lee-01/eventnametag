# FAQ / 트러블슈팅

### Chrome이 없다고 나옵니다
설치 후 재시도 (https://google.com/chrome). 또는 `--html-only`로 우회 (이 경우 사용자가 직접 브라우저에서 Cmd+P).

### 잉크 커버리지 경고가 떠요
강한 다크 무드나 장식이 많은 템플릿에서 자주 나옵니다. 여백이 많은 안전 레이아웃으로 fallback시키거나, 장식을 줄이는 것이 기본 대응입니다. `--ignore-ink` 강행은 테스트 인쇄를 감수할 때만 씁니다.

### `rangecheck` 에러
이 스킬은 raster PNG 경로로 자동 회피. 그래도 발생하면 프린터 PostScript 인터프리터가 PDF를 거부한 케이스이므로 다른 프린터로 시도.

### 명단 헤더가 자동 매핑 안 돼요
`scripts/generate.py`의 `HEADER_MAP` 딕셔너리에 헤더 추가:
```python
HEADER_MAP = {
    "이름": "name", "name": "name", ...
    "당신_컬럼명": "name",  # 추가
}
```

### Linux/Windows에서 안 됩니다
v0.1은 macOS 전용 (Preview·sips 의존). Linux는 v0.2 로드맵에 있습니다.
