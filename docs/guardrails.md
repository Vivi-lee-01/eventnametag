# 가드레일

현재 차단하는 silent failure:

| ID | 가드 | 강행 옵션 |
|---|---|---|
| G1 | yaml schema 검증 (jsonschema) | (필수, 강행 X) |
| G2 | 컬러 대비 (WCAG AA 4.5) | `--no-contrast-check` |
| G3 | 잉크 커버리지 raster 분석 | `--ignore-ink` |
| G4 | skeleton ID 검증 + custom 파일 존재 | (필수) |
| G5 | Chrome / sips 의존성 검사 | `--html-only`로 우회 |
| G6 | 명단 파싱 안전망 | (자동 fallback) |
| G7 | state.json 손상 시 백업 후 재생성 | (자동) |
| G8 | `~/.config/eventnametag/` 자동 생성 | (자동) |
| G9 | AI 템플릿 textzone 대비/공백 영역 검사 | 안전 floor fallback |
| G10 | AI 템플릿 sanitize: 외부 URL·script·handler·예약 셀렉터 차단 | 안전 floor fallback |
| G11 | 작성 공백 가이드라인 금지: 점선·밑줄·칸 구분선 차단 | 안전 floor fallback |
| G12 | 포스터성 장소 정보 차단: 장소명·주소·층수 제거 | 안전 floor fallback |
| G13 | 주최사/호스트명 필수 슬롯 검사 | 안전 floor fallback |

원칙: **"인쇄가 망가지면 사용자가 인쇄 후에 알게 하지 말 것."**

## 내부 안전 fallback

일반 사용자는 내부 레이아웃을 직접 고를 필요가 없습니다. 내부 레이아웃은 AI 템플릿이 인쇄 안전 기준을 통과하지 못할 때만 쓰는 실패 방지용 내부 구현입니다.
