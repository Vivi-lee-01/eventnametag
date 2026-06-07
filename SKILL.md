---
name: eventnametag
description: 행사 전날, 명단만 넣으면 탐사 A4 8칸 라벨지(99×67.5mm)에 바로 인쇄 가능한 네임택을 만드는 AI 에이전트 스킬. 사용자가 '네임택', '명찰', 'eventnametag', 'BI 네임택', '행사 네임택', '밋업 네임택', '채용행사 네임택' 등을 요청하면 활성화한다. 기본 UX는 사용자가 Bash를 직접 실행하는 것이 아니라 에이전트가 행사명·브랜드 단서·명단을 받아 demo/quick/print 흐름을 대신 실행하고, 시안 미리보기·출력 파일·인쇄 체크리스트까지 안내하는 것이다.
---

# eventnametag — 행사 BI 네임택 생성/인쇄 스킬

## 무엇

`eventnametag`는 행사 운영자가 명단과 브랜드 단서만 주면 회사·커뮤니티 BI가 반영된 네임택을 만들고, 탐사 A4 8칸 라벨지(99×67.5mm)에 정확히 출력하도록 돕는 스킬이다.

### 최상위 불변식 — A4 8칸 99×67.5mm 라벨 좌표 🔒

이 프로젝트의 가치는 **사용 중인 Coupang A4 8칸(99mm × 67.5mm) 실물 라벨지에 정확히 맞는 인쇄 좌표**에 있다. 디자인이 아무리 좋아도 좌표가 틀리면 출력물이 폐기되므로 실패다.

- 페이지: A4, `@page margin: 0`
- 시트: `210mm × 297mm`
- 검증 좌표: 상단 `13mm` / 좌우 `5mm` / 하단 `14mm`
- 셀: `99mm × 67.5mm` (사용 제품: Coupang 상품 `8151170152`, item `24893867174`)
- 그리드: 2열 × 4행, `column-gap: 2mm`, `row-gap: 0`
- 금지: “A4에 8칸이면 대충 맞음”, 임의 여백 재계산, 셀 간격 0 처리, PDF 직접 인쇄, 실물 라벨 경계를 따라가는 외곽 테두리 출력
- 변경 원칙: 좌표 변경은 새 디자인 작업이 아니라 **실물 테스트+캘리브레이션+`tests/test_print_coordinates.py` 갱신이 필요한 제품 변경**이다.
- 기본 시각 보정: 프린터/라벨지 밀림을 고려해 셀 외곽 테두리는 두지 않는다. 라벨 경계 확인이 필요할 때만 디버그용 crop/border guide를 별도 파일로 만든다.
- 기본 이미지 보정: 사진/누끼/일러스트 같은 주요 비주얼은 라벨 절단·시선 중심을 고려해 계산상 위치보다 기본 `3mm` 위로 배치한다.

### 최상위 불변식 — 실제 인쇄용 디자인 안전성 🔒

이 프로젝트의 기본 산출물은 화면용 포스터가 아니라 **라벨지에 대량 인쇄될 네임택**이다. 원본 이미지의 무드는 살리되, 인쇄 실패·잉크 과다·가독성 저하를 만드는 요소는 제거한다.

- 금지: 그라데이션, 사진 풀블리드, 진한 대면적 배경, 과한 그림자/블러, 작은 저대비 텍스트, 장식이 이름 영역을 침범하는 구성
- 허용/권장: 단색 또는 2~3도 별색, 선화/실루엣 일러스트, 저잉크 패턴, 넓은 흰 여백, 이름 우선 정보 위계
- 원본 레퍼런스가 사진/포스터일 때: 핵심 무드·상징·색·인물 포즈를 **벡터/플랫 일러스트로 번역**하고, 사진적 명암·그라데이션·장소/시간 상세정보는 기본 제거
- 이름 영역: 실제 행사 참가자 이름이 2~4m 거리에서도 보이도록 가장 큰 정보 블록으로 확보한다.


### 최상위 불변식 — 셀 내부 2mm 인쇄 안전 영역 🔒

피지컬 인쇄에서는 프린터·급지·라벨지 재단 때문에 1–2mm 오차가 자주 발생한다. 라벨 외곽 99mm × 67.5mm와 A4 배치는 고정하되, 실제 디자인 요소는 각 셀 안쪽으로 `2mm`씩 줄인 안전 영역 안에 배치한다.

- 셀 외곽: `99mm × 67.5mm` 그대로 유지 — 라벨지 물리 크기이므로 줄이지 않는다.
- 디자인 안전 영역: 좌/우/상/하 각 `2mm` inset, 즉 실사용 디자인 박스는 대략 `95mm × 63.5mm`.
- 모든 텍스트·이미지·장식·이름 작성 박스는 이 안전 영역 안에 둔다. 단, 디버그용 crop mark나 보정 가이드는 별도 파일에서만 허용한다.
- 목적: 1–2mm 인쇄 밀림이 있어도 이미지가 라벨 밖으로 잘리거나 이웃 라벨을 침범하지 않게 한다.


### 최상위 불변식 — 참가자 식별 영역 우선 🔒

네임택의 1차 목적은 장식이나 행사 홍보가 아니라 **참가자의 소속과 이름을 멀리서 식별 가능하게 하는 것**이다. 대부분의 밋업/네트워킹 행사에서는 참가자가 소속(회사·팀·학교 등)과 이름을 함께 적으므로, 실제 인쇄용 네임택은 소속명과 이름을 모두 크게 쓸 수 있는 넓은 작성 영역을 최우선으로 확보한다.

- 기본 작성 영역은 셀 하단에 넓게 둔다. 권장 높이는 셀 내부 safe area의 약 40% 이상, 최소 `24mm` 이상이다.
- 적어도 소속명과 이름을 크게 쓸 수 있는 빈 공간이어야 한다. 유도선 2개를 넣는 방식은 기본 금지한다.
- `NAME / 이름` 같은 안내 문구는 필수 요소가 아니다. 공간을 잡아먹으면 제거한다.
- 칸을 “소속/이름”으로 억지 분리하지 않는다. 참가자가 자유롭게 크게 쓸 수 있는 빈 박스로 둔다.
- 작성 영역은 행사 정보보다 우선순위가 높다. 디자인이 밀리면 장식·파트너 정보·부제부터 줄이고, 작성 영역을 먼저 지킨다.

### 프린터별 실측 보정

상품 가이드 좌표는 source of truth로 유지하되, 실제 프린터/급지 특성 때문에 균일하게 밀리면 출력물별 보정값을 적용한다.

- 현재 행사 출력물 보정: 전체 라벨 그리드를 `2mm` 아래로 이동 (`padding-top 13mm → 15mm`, `padding-bottom 14mm → 12mm`).
- 이런 보정은 상품 규격 변경이 아니라 **프린터 프로파일/실측 보정**이다.
- 좌우가 다르게 밀리면 단순 y 이동이 아니라 프린터 스큐 가능성이 있으므로 일반 A4 테스트 출력 후 라벨지와 겹쳐 확인한다.

핵심은 “디자인 파일 생성”이 아니라 다음 3가지를 한 번에 해결하는 것이다.

1. 행사/브랜드 분위기에 맞는 네임택 시안 생성
2. CSV/TSV/붙여넣기 명단을 A4 8칸 라벨지에 배치
3. HTML → Chrome PDF → 300dpi PNG → Preview 인쇄 흐름으로 한글/프린터 실패를 줄임

## 언제 활성화할까

사용자가 아래와 비슷하게 말하면 이 스킬을 사용한다.

- “네임택 만들어줘”
- “행사 명찰 뽑아야 해”
- “AI 밋업 참가자 네임택 필요해”
- “채용 행사에서 쓸 이름표 만들어줘”
- “eventnametag로 이 명단 인쇄하고 싶어”
- “우리 회사 BI 넣어서 네임택 만들고 싶어”

## 중요한 UX 원칙

사용자에게 Bash 명령을 직접 실행하라고 넘기지 않는다. 사용자가 대화로 요청하면 에이전트가 필요한 파일 확인, 명단 정리, 브랜드 설정, 명령 실행, 결과 검증을 최대한 대신한다.

### 하지 말 것

- 처음부터 `python3 scripts/generate.py ...` 명령만 던지고 끝내지 말 것
- 첫 실행 라벨지 확인을 단순 광고/마찰로 보고 제거하지 말 것
- 라벨지 구매를 강요하거나, preview-only 사용자를 막지 말 것
- YAML, skeleton, calibration 같은 내부 용어를 초반에 노출하지 말 것
- `--brand`가 없다고 막지 말고 demo/예시/quick path로 이어줄 것
- 사용자가 “어떻게 실행해?”라고 묻기 전까지 CLI 플래그 전체를 나열하지 말 것

### 할 것

1. 먼저 사용자가 만들려는 행사를 한 문장으로 재진술한다.
2. 정보가 부족하면 preview를 먼저 강요하지 말고, 행사명·원하는 무드·BI/레퍼런스·명단을 자유 입력으로 받는다.
3. 필요한 입력을 3개 이하로만 확인한다.
4. 첫 실행 라벨지 확인은 유지하되 “오늘 주문→내일 수령→바로 인쇄” 이유를 명확히 말하고, 주문/보유/행사 정보 입력 3갈래를 제공한다.
5. 명단/브랜드가 부족하면 자유 입력을 먼저 받고, 사용자가 “샘플/분위기 먼저”를 원할 때만 showcase preview를 제안한다.
6. 가능한 경우 에이전트가 직접 repo에서 스크립트를 실행한다.
7. 결과물 경로와 인쇄 체크리스트를 짧게 알려준다. quick 경로에서는 별도 preview HTML을 열거나 제공하지 않는다.
8. 작업이 완료되면 사용자가 바로 인쇄할 수 있도록 최종 300dpi PNG를 Preview/기본 이미지 앱으로 열어준다.
9. 출력 파일 생성 후에도 탐사 A4 8칸 라벨지와 인쇄 체크리스트를 자연스럽게 안내한다.

## 기본 대화형 프로토콜

이 스킬에는 두 UX 레이어가 있다.

1. **Agent 대화형 flow**: 사용자가 Hermes/Codex/Claude Code 같은 AI 에이전트에게 “네임택 만들어줘”라고 요청했을 때의 기본값. `askuser`/`clarify` 같은 선택형 질문으로 분기하고, 에이전트가 필요한 명령을 대신 실행한다.
2. **CLI fallback flow**: 사용자가 터미널에서 `bin/eventnametag ...`를 직접 실행할 때의 보조 경로. 이때만 `input()` 기반 wizard를 사용한다.

따라서 Agent 안에서는 터미널 입력을 기다리는 UX를 만들지 말고, 의사결정 지점마다 선택형 질문을 사용한다. 단순 안내/체크리스트는 질문으로 만들지 않는다.

터미널 Hermes의 선택형 질문 박스는 긴 한글 문장/전각 문자 폭 계산이 깨질 수 있다. `clarify`/askuser 질문 본문은 한 줄짜리 짧은 문장으로 제한하고, 긴 설명은 질문 박스 안에 넣지 않는다.

### Agent askuser/clarify 질문 지점

| 단계 | 질문 방식 | 선택지/입력 | 원칙 |
|---|---|---|---|
| 라벨지 준비 | 선택형 질문 | 쿠팡에서 주문 / 이미 보유 / 행사 정보 입력 | 첫 실행에서 반드시 확인하되 구매 강요 금지 |
| 라벨지 상품 | 안내 | 기본 탐사 A4 8칸 라벨지 구매 링크 | 사용자가 주문을 선택하면 추가 상품 선택 없이 Chrome에서 바로 열기 |
| 의도 확인 | 선택형 질문 | 샘플 보기 / 내 행사로 만들기 / 기존 파일로 인쇄 / 정렬 보정 | 사용자가 이미 명확히 말했으면 생략 |
| 브랜드 방식 | 선택형 질문 | 단체명만 사용 / URL 자동 추출 / 기존 예시 / 등록 브랜드 | YAML·skeleton 같은 내부 용어 금지 |
| 명단 방식 | 선택형 질문 | 대화에 붙여넣기 / CSV 경로 / 이름만 빠르게 / 샘플 명단 | 가장 낮은 마찰의 입력 경로 선택 |
| 디자인 선택 | 선택형 질문 | 깔끔한 세미나 / 프리미엄 / AI·해커톤 / 일러스트 / 채용·리크루팅 / 스태프·스피커·VIP | showcase 생성 후 사용자 언어로 선택 |

예시 질문:

```text
탐사 A4 8칸 라벨지 준비 상태를 확인할게요.

1. 쿠팡에서 주문할게요
2. 이미 가지고 있어요
3. 라벨지는 나중에 준비하고, 행사 정보부터 입력할게요
```

라벨지 안내가 필요하면 질문 밖에서 짧게 말한다: “행사 전날이면 라벨지를 먼저 확인하는 게 안전합니다. 오늘 주문하면 내일 받아 출력할 수 있어요.”

이 질문 뒤에는 별도 preview 선택지를 기본으로 묻지 말고, 다음 자유 입력 질문으로 이어간다.

```text
행사명, 원하는 무드, BI/브랜드 단서를 자유롭게 입력해 주세요.
이미지, 웹사이트 URL, 로고 파일, 디자인 가이드 md, 참고 문서도 괜찮아요.
```

선택 후 에이전트가 해야 할 일:

- `1`이면 기본 라벨지(`https://link.coupang.com/a/eGNFOI`) 구매 링크를 안내하고, 쿠팡 파트너스 문구를 함께 보여준 뒤 Chrome에서 바로 연다.
- `2`이면 이후 라벨지 첫 질문을 반복하지 않는 방향으로 진행한다.
- `3`이면 자유 입력 질문으로 이어가고, 출력 단계에서 다시 라벨지를 안내한다.
- 행사명/브랜드/명단이 충분하면 추가 질문 없이 바로 `bin/eventnametag quick ...` 또는 적절한 생성 명령을 실행한다.

### 1단계: 의도 파악

사용자 요청을 아래 4개 중 하나로 분류한다.

| 의도 | 사용자가 하는 말 | 에이전트 행동 |
|---|---|---|
| demo/showcase | “한번 보여줘”, “샘플로 해봐”, “분위기 먼저 보고 싶어” | `showcase`로 8개 행사 목적별 제품 카드 HTML preview 생성 |
| quick | “이 행사 네임택 만들어줘” | 행사명·브랜드 단서·명단만 받아 preview 없이 바로 PNG 생성 |
| print | “이 파일로 인쇄해줘” | 기존 BI/명단 파일을 사용해 출력 파일 생성 |
| fix | “정렬이 밀렸어”, “디자인이 별로야” | 보정값 저장 또는 행사 무드/톤 재선택. skeleton 선택은 고급 디버그일 때만 노출 |

### 2단계: 최소 질문

정보가 부족하면 다음 중 부족한 것만 묻는다.

1. 행사명은 무엇인가요?
2. 브랜드/행사 스타일 단서가 있나요? (회사명, 웹사이트 URL, 로고/컬러, 원하는 분위기)
3. 참석자 명단은 붙여넣을까요, CSV/XLSX 파일이 있나요?

preview/showcase는 사용자가 “샘플 먼저”, “분위기 먼저”, “한번 보여줘”라고 말했을 때만 기본으로 쓴다. 일반 요청에서는 자유 입력을 받은 뒤 바로 quick/print 흐름으로 간다.

### 3단계: 실행 경로 선택

| 상황 | 기본 경로 |
|---|---|
| 아무 입력도 없음 | 자유 입력 요청: 행사명·원하는 무드·BI/브랜드 단서·명단/파일/이미지/URL/md를 받음 |
| 행사명만 있음 | 무드·BI/레퍼런스·명단 중 부족한 것만 물어 preview 없이 quick 생성 |
| 브랜드 URL 있음 | URL 추출 → 브랜드 스타일 카드 → preview |
| CSV/TSV 있음 | 명단 파싱 → 필드 확인 → preview |
| 기존 brand slug 있음 | 바로 print flow |
| 정렬 문제 | calibration 값을 자연어로 받아 yaml 저장 |

### 4단계: 결과 안내

결과는 다음 형식으로 안내한다.

```text
완료했습니다.
- 행사: <행사명>
- 사용한 스타일: <행사 무드/브랜드 톤>
- 출력 파일: <png 경로>

최종 300dpi PNG는 Preview/기본 이미지 앱으로 열어둡니다. PDF/HTML/lpr 직접 인쇄보다 Preview에 열린 PNG를 인쇄하는 쪽이 안전합니다.

인쇄 전 체크:
1. 파일: Preview에 열린 최종 300dpi PNG
2. 용지 크기: A4
3. 배율: “크기 조절” 선택 후 100%
4. 해제: “용지에 맞게 크기 조절 / Scale to Fit / 자동 맞춤” OFF
5. 해제: 자동 회전 OFF
6. 테스트: 첫 장은 일반 A4로 출력 → 탐사 A4 8칸 라벨지 위에 겹쳐 8칸 정렬 확인
7. 급지 방향: 프린터마다 라벨지 인쇄 방향이 다를 수 있으므로 일반 A4에 펜으로 앞/위 방향을 표시해 테스트 인쇄하고, 라벨지의 상하·앞뒤 출력 방향을 맞춘 뒤 본 인쇄
8. 본 인쇄: 정렬과 방향이 맞으면 탐사 A4 8칸 라벨지에 인쇄
```

## 현재 로컬 사용 경로

현재 repo 기준 핵심 스크립트는 다음이다.

```bash
bin/eventnametag showcase --event "AI Meetup" --brand-hint "LiveClass"
bin/eventnametag demo --html-only
bin/eventnametag doctor
bin/eventnametag quick
bin/eventnametag order-paper
bin/eventnametag calibrate
python3 scripts/generate.py --brand <slug> --event "행사명"
python3 scripts/generate.py --brand <slug> --event "행사명" --layout-variant badge_first
python3 scripts/generate.py --brand <slug> --event "행사명" --pattern dot-grid --accent-shape triangle --motif geo-corner
python3 scripts/generate.py --validate <yaml>
```

P1 디자인 다양성:
- 레이아웃(A): `--layout-variant {name_hero,intro_hero,badge_first}` (미지정 시 brand `design.layout_variant` > 자동 name_hero).
- 벡터 장식(B): `--pattern {dot-grid,stripe,wave,mesh-corner}` 배경 패턴, `--accent-shape {triangle,blob}` 코너 도형 (저잉크 CSS 벡터).
- 일러스트(C): `--motif <ID>` 내장 모티프(geo-corner/wave-band/dot-cluster/arc-rings/cross-hatch), 또는 brand yaml `design.illustration_svg_inline`로 직접 SVG. 우선순위: 인라인 > motif_id > 없음.
- 인라인 SVG 로고는 brand yaml `design.logo_svg_inline`로 넣는다. CLI 플래그는 brand `design.*`를 오버라이드한다.
**벡터-only**: 디자인 자산은 인라인 SVG/CSS만 — 래스터·외부 URL·`<script>`·`<foreignObject>`는 새니타이즈로 제거되고, 적용 결과는 잉크 게이트(풀블리드 35% 상한)를 통과해야 한다.

단, 사용자에게는 이 명령을 직접 실행하라고 하지 말고 에이전트가 대신 실행하거나, 필요한 경우에만 "고급 사용자용 명령"으로 보여준다.

## LLM 장식 생성 모드 (v0.5)

BI 로고/URL에서 색을 결정론적으로 추출한 뒤, **에이전트가 brand yaml의 `design:` 블록을 직접 조판**한다.
런타임 API 호출 없음 — 에이전트가 SVG를 쓰고, generate.py가 오프라인으로 렌더한다.

### BI 인제스트 (색 추출 → brand 조립)

색은 vision/추측이 아니라 **로고 픽셀·SVG 정규식에서 결정론적으로** 뽑는다. 에이전트는 다음 경로를 따른다.

1. 로고 → 대표색: PNG/JPG는 `ingest_logo.extract_colors_from_raster(path)`, SVG는 `ingest_logo.extract_colors_from_svg(svg_text)`.
2. 대표색 → brand colors 분류: `ingest_logo.logo_to_brand_colors(colors)` (휘도 기준 primary_dark / primary_light / accent).
3. brand dict 조립: `extract_brand.build_brand_from_logo(colors, wordmark)` — colors·wordmark·빈 `design` 슬롯·`_labels`(symbol/mood vision 스텁) 포함.
4. 에이전트가 vision으로 `_labels`를 채우고, 아래 규칙대로 `design:` 블록(장식 SVG)을 조판한다.

```python
import ingest_logo, extract_brand
colors = ingest_logo.extract_colors_from_raster("logo.png")   # SVG면 extract_colors_from_svg(text)
brand = extract_brand.build_brand_from_logo(colors, wordmark="Acme")
# → brand["colors"]는 결정론. 에이전트는 brand["design"] + brand["_labels"]만 채운다.
```

### 핵심 불변식 🔒

**텍스트(이름·회사·직무)는 절대 SVG에 넣지 않는다.**
텍스트는 항상 코드(generate.py)가 렌더하고, `design.illustration_svg_inline`·`design.logo_svg_inline`은
그 **뒤** 배경 레이어에만 존재한다. → 이름 100% 정확, OCR 불필요, 폰트 렌더 보장.

### 조판 규칙 (에이전트가 design 블록을 작성할 때 반드시 준수)

1. **색은 brand `colors`에서만** — SVG 안에 hex를 하드코딩하지 않는다. `fill="currentColor"` 또는 CSS 변수 사용.
2. **저잉크** — 큰 면적 요소는 `opacity` 0.06–0.15. 잉크 게이트(>35%)와 G9 대비 게이트가 초과분을 차단한다.
3. **셀 좌표 상대값만** — `viewBox` 기준 상대 좌표. 셀 밖을 넘어도 `overflow:hidden`이 자르므로 안전.
4. **이름 밴드(세로 32–60%)를 어둡게 만들지 말 것** — G9 텍스트영역 대비 게이트가 fail시키고 장식을 자동 제거한다.
5. **벡터만** — 래스터(`data:image/png` 등)·외부 URL·`<script>`·`<foreignObject>`는 새니타이즈로 제거된다.

### brand yaml `design:` 블록 스키마 및 예시

```yaml
design:
  layout_variant: "name_hero"         # 필수 선택: diagonal | name_hero | intro_hero | badge_first
  illustration_svg_inline: '<svg viewBox="0 0 100 100"><polygon points="0,100 100,100 100,40" fill="currentColor" opacity="0.12"/></svg>'
  logo_svg_inline: '<svg ...>...</svg>'  # 선택: 워드마크 대체 인라인 SVG
  pattern: "dot-grid"                  # 선택: dot-grid | stripe | wave | mesh-corner
  accent_shape: "triangle"             # 선택: triangle | blob
  motif_id: "geo-corner"               # 선택: geo-corner|wave-band|dot-cluster|arc-rings|cross-hatch (illustration_svg_inline 없을 때 사용)
```

### 게이트 루프 동작

- generate.py가 렌더 후 잉크·G9 대비·오버플로 게이트를 순서대로 검사한다.
- 게이트 fail → 장식(`illustration_svg_inline`·`pattern`·`motif_id`·`accent_shape`) 자동 제거 후 재시도.
- 재시도 후에도 fail → 검증된 preset으로 fallback.
- **장식이 인쇄를 막는 일은 없다** — 게이트가 항상 안전망을 보장한다.

## AI 셀 템플릿 자율 생성 모드 (v0.6)

v0.5는 "사람이 만든 스켈레톤 중 AI가 고르고 구석에 SVG만" 넣었다. v0.6은 **AI가 셀 한 칸 전체를 디자인**한다(배경·레이아웃·텍스트 위치/색/크기). 고정 스켈레톤은 메뉴가 아니라 **검증/게이트 실패 시 떨어지는 safety floor**다.

### 불변식 (협상 불가) 🔒
1. **셀 경계는 못 넘는다** — AI는 셀 *안*만 디자인. `<style>`이 `html`/`body`/`.cell`/`.a4-sheet`/`@page`를 건드리면 검증 거부. 셀 크기·페이지 격자는 스켈레톤 소유.
2. **글자 내용은 코드가 박는다** — AI는 이름/회사/직무가 *어디에·무슨 색·크기로* 놓일지만 디자인. 글자 자체는 `{{name}}` 등 토큰으로 두고 generate.py가 실제 폰트로 치환. AI가 텍스트를 SVG path/픽셀로 그리면 안 됨(오타·흐림 = 인쇄 사고).

### `design.cell_template` 작성 규칙
- **텍스트 슬롯(토큰)**: `{{name}}`(필수)·`{{company}}`·`{{role}}`·`{{intro}}`·`{{track}}`·`{{group}}`·`{{event}}`. 글자를 직접 쓰거나 SVG로 그리지 않는다. 허용 외 토큰(`{{BRAND_*}}` 등)은 검증 거부.
- **사이즈 토큰(권장)**: `{{name_size}}`·`{{company_size}}` — 코드가 긴 이름 축소 램프 값(예: `14mm`/`7mm`)으로 치환. 이름 요소에 `style="font-size: {{name_size}}"`로 바인딩하면 긴 이름 셀 침범을 막는다.
- **텍스트존 메타(필수)**: 템플릿 어딘가에 `<!-- textzone: x0,y0,x1,y1 -->`(셀 기준 분수, `x0<x1`·`y0<y1`, 0~1). 이름이 놓이는 영역 — G9 대비 게이트가 이 영역 배경을 검사한다. 없거나 무효면 floor로 fallback.
- **색/폰트**: 브랜드 토큰만 — `var(--brand-dark)`·`var(--brand-light)`·`var(--brand-accent-1)`·`var(--brand-font-body/mono)`. SVG는 `fill="currentColor"`. hex 하드코딩·외부 URL·`http(s)://`·`<script>`·이벤트 핸들러·`@import`·`data:image/`·외부 `url(...)`는 검증 거부.
- **셀 충전 + overflow**: 루트는 셀을 채우는 컨테이너. `.cell.variant-ai`가 `overflow:hidden`을 보장하므로 셀 밖은 잘린다.

### 예시 (`brands/examples/<slug>.yaml`)
```yaml
design:
  cell_template: |
    <!-- textzone: 0.08,0.42,0.92,0.66 -->
    <div class="ai-root">
      <svg viewBox="0 0 100 68" style="position:absolute;inset:0">
        <polygon points="0,0 100,0 100,26 0,40" fill="var(--brand-dark)"/>
        <circle cx="86" cy="58" r="16" fill="var(--brand-accent-1)" opacity="0.14"/>
      </svg>
      <div class="ai-event" style="position:absolute;top:5mm;left:6mm;color:var(--brand-light);
        font:600 2.8mm var(--brand-font-mono);letter-spacing:.12em">{{event}}</div>
      <div class="ai-name" style="position:absolute;top:42%;left:6mm;font-weight:800;
        font-size:{{name_size}};color:var(--brand-dark)">{{name}}</div>
      <div class="ai-co" style="position:absolute;top:62%;left:6mm;font-size:{{company_size}};
        color:var(--brand-dark)">{{company}}</div>
    </div>
```

### 게이트 루프 동작 (v0.5 계승)
- 렌더 → 잉크·G9(textzone 대비)·sanitize 검사. fail → 강도하향(`cell_template` 포함 장식 제거) 재시도 → 그래도 fail이면 검증된 스켈레톤(name_hero) preset fallback. **AI 디자인이 인쇄를 막는 일은 없다.**
- `--layout-variant <floor>` 명시 = AI 생성 건너뛰고 그 스켈레톤 강제(디버그/보수 모드).
- 검증: `python3 scripts/generate.py --validate <yaml>`로 스키마 통과 확인.

## 브랜드/행사 스타일 설정

사용자 언어는 “BI YAML 등록”이 아니라 “행사/브랜드 스타일 설정”이다.

지원할 입력:

| 입력 | 설명 |
|---|---|
| 회사/커뮤니티명 | 워드마크 fallback |
| 웹사이트 URL | title, og:site_name, theme-color, 색상 후보 추출 |
| 주요 색상 | 모르면 에이전트가 후보 제안 |
| 행사 분위기 | clean / dark AI / premium / casual / corporate |
| 로고/워드마크 | 현재는 텍스트 중심, 로고 파일은 후순위 |
| 선호 디자인 | 이름 강조 / 대화 유도 / 스피커·스태프 / QR / 미니멀 |

내부적으로는 `~/.config/eventnametag/brands/<slug>.yaml` 또는 `brands/examples/*.yaml`을 사용한다.

## 디자인 선택 기준

지원 제품 카드는 8개다. 사용자는 skeleton ID가 아니라 행사 목적과 정보 구조로 고른다.

| 제품 카드 ID | 사용자용 이름 | 적합 상황 | 강조 정보 | 필요한 필드 | 추천 라벨지 | 인쇄 리스크 |
|---|---|---|---|---|---|---|
| name-first | 이름 가독성 최우선형 | 세미나, 일반 네트워킹, 사내 행사, 등록대에서 빠르게 이름 확인이 필요한 행사 | 이름을 가장 크게, 소속/역할은 보조 정보로 정리 | name, company, role | 기본 탐사 A4 8칸 라벨지 | 낮음 — 흰 여백이 많고 기본 라벨지에서 안정적 |
| networking-intro | 네트워킹·한줄소개형 | 커뮤니티 밋업, 네트워킹 파티, 멤버 교류 행사, 소규모 컨퍼런스 | 한줄소개, 관심사, 대화 시작 단서 | name, company, role, intro, interests | 기본 탐사 A4 8칸 라벨지 | 보통 — 소개가 길면 글자가 작아지므로 35자 안팎 권장 |
| recruiting | 채용행사·직무 강조형 | 채용박람회, 캠퍼스 리크루팅, 후보자 밋업, 인터뷰 데이 | 직무, 관심 포지션, 후보자/리크루터 구분 | name, company, role, group, intro | 기본 탐사 A4 8칸 라벨지 | 낮음 — 컬러 면적이 작아 대량 출력에 유리 |
| speaker-staff-vip | 스피커·스태프·VIP 구분형 | 컨퍼런스 운영, 초청행사, 스피커/VIP 동선 구분, 스태프 체크인 | Staff/Speaker/VIP 역할, 그룹, 트랙, 동선 구분 | name, company, role, group, track | 기본 탐사 A4 8칸 라벨지 | 낮음 — 운영 배지는 선명하지만 배경 잉크 사용량은 제한 |
| ai-hackathon | AI·해커톤 에너지형 | AI 밋업, 데모데이, 해커톤, 개발자 컨퍼런스, 팀 빌딩 행사 | 팀, 트랙, 프로젝트/데모 키워드, 기술 관심사 | name, company, role, track, interests | 기본 탐사 A4 8칸 라벨지 | 높음 — 진한 배경과 그라디언트 때문에 대량 인쇄 전 테스트 권장 |
| premium-salon | 프리미엄 살롱형 | 프리미엄 살롱, 리더십 모임, VIP 초청, 투자자/파트너 라운드테이블 | 이름, 소속, 초청 행사명, 과하지 않은 브랜드 무드 | name, company, role | 기본 탐사 A4 8칸 라벨지 | 낮음 — 잉크 사용량이 적고 기본 라벨지에서도 무난 |
| workshop-learning | 교육·워크숍 캐주얼형 | 교육, 워크숍, 커뮤니티 온보딩, 사내 러닝데이, 청소년/대학생 프로그램 | 이름, 소속/학교, 참여 그룹, 한줄소개 | name, company, group, intro | 기본 탐사 A4 8칸 라벨지 | 보통 — 밝은 장식은 안전하지만 색감 확인용 테스트 권장 |
| qr-connect | QR·LinkedIn 연결형 | 네트워킹 행사, 채용 행사, 글로벌 컨퍼런스, 크리에이터/창업자 밋업 | 이름, 소속, QR/LinkedIn URL, 짧은 연결 문구 | name, company, role, qr_url, intro | 기본 탐사 A4 8칸 라벨지 | 보통 — QR은 너무 작으면 인식률이 떨어져 사전 스캔 테스트 필요 |

기존 R1~R4 skeleton은 내부 구현/인쇄 안전 레이아웃이다. 일반 사용자나 AI 에이전트 사용자에게 “R1/R2/R3/R4 중 고르라”고 묻는 것은 기본 UX가 아니다. 에이전트는 행사 무드, 필드 길이, 잉크/라벨지 조건을 보고 내부 skeleton을 자동 선택하고, 사용자가 요청하거나 디버그가 필요할 때만 고급 옵션으로 보여준다.

| 현재 ID | 사용자용 설명 | 적합 상황 |
|---|---|---|
| R1 topbar | 안정적인 기본형 | 세미나, 일반 네트워킹 |
| R2 sidestrip | 긴 이름/회사명에 유리 | B2B, 채용행사, 직무 정보 많은 행사 |
| R3 fullbleed | 강한 AI/해커톤 무드 | AI 밋업, 데모데이, 해커톤 |
| R4 minimal | 절제된 프리미엄형 | 소규모 초청행사, 살롱, 리더십 행사 |

향후 M1~M8 행사 니즈 기반 skeleton으로 확장한다.

| 새 ID | 이름 | 용도 |
|---|---|---|
| M1 | Hero Name | 이름 가독성 최우선 |
| M2 | Conversation Starter | 한줄소개/관심사로 대화 유도 |
| M3 | Speaker / Staff | 스피커·스태프·VIP 구분 |
| M4 | Sponsor Clean | 스폰서/파트너 로고 영역 확보 |
| M5 | QR Connect | LinkedIn/X/개인 페이지 연결 |
| M6 | Minimal Premium | 고급스럽고 절제된 행사 |
| M7 | Hackathon Energy | 팀/트랙/데모데이 분위기 |
| M8 | Table Badge | 팀/좌석/체크인 번호 표시 |

## 명단 입력 기준

우선 지원 필드:

| 필드 | 필수 | 용도 |
|---|---:|---|
| name | 필수 | 가장 크게 노출 |
| company | 권장 | 소속/회사 |
| role | 권장 | 직무/역할 |
| intro | 선택 | 대화 유도형 |
| interests | 선택 | AI/커뮤니티 밋업 태그 |
| group | 선택 | Staff/Speaker/VIP/Track 구분 |
| qr_url | 선택 | QR Connect용 |
| track | 선택 | 해커톤/컨퍼런스 트랙 |

모든 디자인이 모든 필드를 쓰면 안 된다. skeleton별 정보 위계를 다르게 잡는다.

P1-A부터 `track`·`interests`·`group`은 CSV 헤더로 인식·보존되어 `intro_hero`/`badge_first` 레이아웃에서 렌더된다
(헤더 있을 때만 채워짐, 4필드 base 호환 유지). `qr_url`은 아직 비범위.

## 인쇄 정확도 원칙

인쇄 도구의 핵심은 “예쁜가”보다 “망하지 않는가”다.

반드시 안내할 체크리스트:

- 라벨지: 탐사 A4 8칸 라벨지 / 99×67.5mm
- 인쇄 배율: 100%
- 자동 맞춤/축소: 끄기
- 첫 장: 일반 A4로 테스트 인쇄 후 라벨지와 겹쳐보기
- 급지 방향: 일반 A4에 펜으로 앞/위 방향 표시 후 테스트 인쇄해 프린터별 라벨지 상하·앞뒤 방향 확인
- Preview로 열린 300dpi PNG를 인쇄
- 정렬이 밀리면 자연어로 보정 요청 받기

### 자연어 보정 약속어

| 사용자 발화 | 저장값 |
|---|---|
| “아래쪽으로 2mm 이동” | `y: 2` |
| “위쪽으로 2mm 이동” | `y: -2` |
| “오른쪽으로 1mm 이동” | `x: 1` |
| “왼쪽으로 1mm 이동” | `x: -1` |

저장 위치:

```text
~/.config/eventnametag/calibration.yaml
```

형식:

```yaml
x: 1.0  # 오른쪽 +, 왼쪽 -
y: 2.0  # 아래쪽 +, 위쪽 -
```

기존 보정값이 있으면 새 요청을 더해서 저장한다.

## 라벨지 구매 CTA

탐사 A4 8칸 라벨지는 실제 인쇄에 필요한 물리 소모품이다. 첫 경험을 광고처럼 만들면 안 되지만, “오늘 주문해야 내일 인쇄 가능”이라는 납기 리스크는 첫 실행에서 알려야 한다.

원칙:

1. 첫 실행에서는 라벨지 보유/주문 여부를 먼저 확인한다.
2. 단, 이유는 “오늘 주문→내일 수령→바로 인쇄”로 설명하고, 선택지는 주문/보유/preview 먼저 보기 3갈래로 제공한다.
3. 사용자가 preview만 원하면 막지 않는다.
4. 실제 출력 파일 생성 후에도 탐사 A4 8칸 라벨지 준비물과 인쇄 체크리스트를 다시 안내한다.
5. 쿠팡 파트너스 문구는 README/랜딩/출력 전 안내에 명시한다.

문구:

```text
탐사 A4 8칸 라벨지가 필요합니다.
구매 링크: https://link.coupang.com/a/eGNFOI
이 링크는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.
```

## 사업성/GTM 메모

이 스킬은 유료 대행/SaaS로 조기 확장하지 않는다. 기본 전략은 **무료 배포 + 넓은 사용 + 탐사 A4 8칸 라벨지 affiliate**다.

### 하지 말 것

- 1회 제작 대행, 행사 운영 패키지, 건별 웹 생성 과금을 기본 수익 모델로 제안하지 말 것
- 소규모 행사 주최자가 전날 요청하면 제작자가 직접 인쇄·전달할 수 있다는 식으로 가정하지 말 것
- eventnametag를 억지로 큰 사업으로 포장하지 말 것

### 할 것

| 방향 | 설명 |
|---|---|
| 무료 배포 | GitHub/Hermes·Codex·Claude Code 등 AI 에이전트/커뮤니티에서 누구나 쓰게 한다 |
| 사용 장벽 최소화 | demo/quick/doctor로 첫 결과물을 빠르게 보여준다 |
| affiliate 집중 | 실제 출력 단계에서 필요한 탐사 A4 8칸 라벨지를 쿠팡 파트너스 링크로 안내한다 |
| 학습 목적 | 사용 과정에서 더 큰 수익성이 있는 다음 제품 기회를 발견한다 |

추천 사용자:

- AI 밋업/해커톤 운영자
- 스타트업 HR/채용행사 담당자
- 교육/워크숍 운영자
- 20~100명 규모 반복 행사 담당자

단, 이들에게 돈을 받는 것보다 무료로 많이 쓰이게 하는 것이 우선이다.

## 고도화 우선순위

### P0 — 첫 성공 경험

- `showcase`: 행사 목적별 8개 제품 카드 갤러리를 먼저 보여주고, 사용자가 디자인 언어가 아니라 행사 목적/정보 구조로 고르게 한다
- `demo`: 샘플 브랜드+샘플 명단으로 즉시 preview 생성
- `doctor`: PyYAML/Chrome/sips/Preview/권한 진단
- `quick`: 행사명/브랜드 단서/붙여넣기 명단만으로 preview와 출력 파일 생성
- `bin/eventnametag` 짧은 실행 입구 제공
- PyYAML 없어도 `--help`/`doctor`는 실패하지 않게 import 지연
- `--brand` 없이 실행하면 예시 보기/내 브랜드 설정/기존 브랜드 선택으로 연결
- 첫 실행 라벨지 확인은 유지하되 “오늘 주문→내일 수령→바로 인쇄” 이유를 명시하고, 행사 정보 자유 입력 선택지도 제공

### P1 — 디자인/출력 품질

- M1~M8 행사 니즈 기반 skeleton 정의
- tone preset: Clean Tech / Dark AI / Editorial / Festival / Corporate
- 명단 필드 기반 skeleton 추천
- 출력 전 체크리스트 UI 강화
- 긴 한글 이름/회사명 자동 축소·줄바꿈 QA

### P2 — 배포/학습

- 랜딩 CTA를 “무료로 샘플 네임택 만들기”로 변경
- 샘플 명단으로 즉시 결과를 보여주는 mini generator
- README/출력 단계에서 탐사 A4 8칸 라벨지 affiliate CTA를 자연스럽게 노출
- AI 밋업/커뮤니티/HR 네트워크에 무료 도구로 공유
- 사용 후기와 반복 pain을 관찰해 더 좋은 후속 제품 기회를 발굴

## 관련 문서

- `README.md`: 사용자 설치/사용 안내
- `AGENTS.md`: Codex/Hermes/Claude Code 등 AI 에이전트용 실행 규칙
- `docs/skeleton-guide.md`: 템플릿/skeleton 작성 가이드
- `docs/print/preview-print-settings.svg`: macOS Preview 인쇄 설정 안내 이미지
- `docs/showcase/`: README용 쇼케이스 예시 이미지/HTML

## 완료 기준

스킬이 잘 작동했다면 사용자는 다음 중 하나를 얻어야 한다.

- 샘플 네임택 preview
- 실제 행사 네임택 PDF/PNG
- 브랜드 스타일 yaml
- 인쇄 위치 보정 yaml
- 다음 인쇄 행동 체크리스트
- 무료 배포/affiliate CTA/사용 후기 수집 같은 다음 검증 액션

최종 답변은 항상 “무엇을 만들었고, 파일은 어디 있으며, 사용자는 다음에 무엇을 하면 되는지”로 끝낸다.
