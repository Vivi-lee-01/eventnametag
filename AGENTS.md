# AGENTS.md — eventnametag (Codex / 비-Claude 에이전트 진입 문서)

이 문서는 Codex 같은 비-Claude 에이전트가 **AskUser 카드 없이 CLI 플래그만으로**
eventnametag를 Claude와 동일하게 실행하기 위한 진입점이다. 전체 UX 원칙·대화형
프로토콜·디자인 선택 기준은 **`SKILL.md`를 참조**한다. 여기서는 핵심만 미러한다.

전제: **macOS** (Chrome + `sips` + Preview 필요). Linux/클라우드는 비범위.

## 1. 무엇 / 언제

- 무엇: 명단 + 브랜드 단서 → 탐사 A4 8칸 라벨지(99×67.5mm)에 바로 인쇄 가능한
  네임택을 만든다. HTML → Chrome PDF → 300dpi PNG → Preview 인쇄.
- 최상위 불변식: A4 8칸 99×67.5mm 검증 좌표를 절대 임의 재계산하지 않는다.
  `@page A4 margin 0`, `.a4-sheet 210×297mm`, padding `13mm 5mm 14mm`,
  셀 `99×67.5mm`, 2열×4행, `column-gap:2mm`, `row-gap:0`이 source of truth다.
  “A4 8칸”만 보고 좌우/상하를 균등분배하거나 gap 0으로 만들면 프로젝트 가치가 0이 된다.
  피지컬 인쇄 오차 대응을 위해 실제 디자인 요소는 각 셀 외곽에서 상하좌우 2mm 안쪽 안전 영역에 배치한다.
  네임택의 1차 목적은 참가자 식별이다. 밋업/네트워킹 네임택은 소속명+이름을 자유롭게 크게 쓸 수 있도록 셀 내부 safe area의 약 40% 이상(최소 24mm) 빈 작성 박스를 기본 확보한다. NAME 안내 문구/소속·이름 분리선/유도선보다 실제 자유 작성 공간이 우선이다.
- 언제: "네임택", "명찰", "행사 이름표", "밋업/채용행사 네임택" 요청 시.

## 2. 의도 분류 (4종)

| 의도 | 사용자 발화 | 실행 |
|---|---|---|
| demo | "샘플로 보여줘", "분위기 먼저" | `bin/eventnametag demo --html-only` (샘플 브랜드+명단 preview) |
| quick | "이 행사 네임택 만들어줘" | `bin/eventnametag quick --event "..." --brand <slug> --file guests.csv` — preview 없이 바로 PNG 출력 |
| print | "이 파일로 인쇄해줘" | `python3 scripts/generate.py --brand <slug> --event "..." --file guests.csv` |
| fix | "정렬이 밀렸어" | `~/.config/eventnametag/calibration.yaml`에 `x`/`y`(mm) 저장 → 재실행 |

`showcase`(행사 목적별 8개 제품 카드)도 있다: `bin/eventnametag showcase --event "..." --brand-hint "LiveClass"`.

## 3. 실행 명령

```bash
# 짧은 입구
bin/eventnametag demo --html-only          # 즉시 샘플 preview
bin/eventnametag doctor                     # Chrome/sips/PyYAML/Preview 진단
bin/eventnametag showcase --event "AI Meetup" --brand-hint "LiveClass"
bin/eventnametag quick --event "AI Meetup" --names "김지원,박서연,이도윤"
bin/eventnametag calibrate                  # 정렬 테스트 시트 1회 출력

# 직접 호출
python3 scripts/generate.py --brand <slug> --event "행사명" --file guests.csv
python3 scripts/generate.py --brand <slug> --event "행사명" --names "이름1,이름2"
python3 scripts/generate.py --validate brands/examples/<slug>.yaml
```

등록된 예시 브랜드 slug: `corporate-blue`, `minimal-mono`, `delta-society`
(`brands/examples/*.yaml`). 사용자 브랜드는 `~/.config/eventnametag/brands/<slug>.yaml`.

명단 입력 형식: CSV/TSV(헤더 자동 인식, Luma 호환) 또는 `--names`로 이름만 쉼표 구분,
또는 stdin 파이프. 기본 4필드: `name`(필수) / `company` / `role` / `intro`.
**P1-A부터 확장 필드 `track`·`interests`·`group`도 CSV 헤더로 인식·보존**되어
`intro_hero`/`badge_first` 레이아웃에서 렌더된다(헤더 있을 때만 채워짐, 4필드 base 호환 유지).
(`qr_url`은 아직 비범위.)

## 4. PNG-only 인쇄 체크리스트 🔒

**인쇄물은 반드시 PNG.** PDF는 중간 산출물일 뿐 인쇄 경로가 아니다. PDF 직접 인쇄나
`lpr` 자동 제출은 **금지** — 한글 CID 폰트가 PostScript 프린터(Sindoh D452 등)에서
`rangecheck`로 실패하고, 같은 PNG도 `lpr`에서는 silent fail한다. 검증된 경로는
Preview에서 사람이 직접 Cmd+P 하는 것뿐이다.

생성 후 안내할 체크리스트:

1. 용지: A4 (Paper Size = A4)
2. 크기 조절(Scale): **100%** — '맞춤(Scale to Fit/자동맞춤)'은 반드시 **OFF**
3. 자동회전(Auto Rotate): 해제 (세로 그대로)
4. 첫 장은 일반 A4로 테스트 인쇄 → 라벨지에 겹쳐 칸 정렬 확인 후 라벨지 인쇄
5. 인쇄 대상은 **Preview에 열린 PNG** (`open -a Preview <png>`)
6. 프린터마다 라벨지 인쇄 방향이 다를 수 있으므로 일반 A4에 펜으로 앞/위 방향을 표시해 테스트 인쇄하고, 라벨지의 상하·앞뒤 출력 방향을 확인
7. PNG에 300dpi 메타데이터가 박혀 있어 '맞춤' 없이도 실제 크기(A4 = 2480×3508px)로 출력됨

라벨지: 탐사 A4 8칸 라벨지 / 99×67.5mm. 정렬이 밀리면 자연어 보정값을 `calibration.yaml`의
`x`(오른쪽 +, 왼쪽 -) / `y`(아래쪽 +, 위쪽 -) mm로 저장한다.

## 5. CLI 플래그 parity (P0 범위)

P0의 모든 사용자 선택은 플래그/입력으로 노출되므로 AskUser 없이 재현 가능하다.

| 선택 | 플래그 | Codex 단독 가능 |
|---|---|---|
| 행사명 | `--event "..."` / `-e` | ✅ |
| 명단 | `--file <csv>` / `-f`, `--names "a,b"` / `-n`, stdin 파이프 | ✅ |
| 브랜드 | `--brand <slug>` / `-b` (+ preview 힌트는 `--brand-hint`) | ✅ |
| HTML만(디버그) | `--html-only` | ✅ |
| 정렬 시트 | `calibrate` 서브커맨드 또는 `--calibrate` | ✅ |

Track 1(본 P0)에는 신규 플래그가 없다. (프린터별 프로파일 `--printer-profile` 등은
Track 2 — 보류 상태, 본 범위 아님.)

### 5-1. P1 디자인 다양성 플래그 (Stage A/B/C)

| 선택 | 플래그 / 필드 | Codex 단독 가능 |
|---|---|---|
| 레이아웃 변형 | `--layout-variant {name_hero,intro_hero,badge_first}` (우선순위: 플래그 > brand `design.layout_variant` > 자동 name_hero) | ✅ |
| 인라인 SVG 로고 | brand yaml `design.logo_svg_inline` (워드마크 대체, 새니타이즈 후 inject) | ✅ |
| 배경 벡터 패턴 (B) | `--pattern {dot-grid,stripe,wave,mesh-corner}` (우선순위: 플래그 > brand `design.pattern`) | ✅ |
| 코너 강조 도형 (B) | `--accent-shape {triangle,blob}` (우선순위: 플래그 > brand `design.accent_shape`) | ✅ |
| 내장 모티프 일러스트 (C) | `--motif <ID>` (내장 라이브러리: geo-corner / wave-band / dot-cluster / arc-rings / cross-hatch). 우선순위: 플래그 > brand `design.motif_id` | ✅ |
| 인라인 SVG 일러스트 (C) | brand yaml `design.illustration_svg_inline` (새니타이즈 후 inject, 우선순위: 인라인 > motif_id > 없음) | ✅ |

**벡터-only 제약 🔒**: 디자인 자산(로고·일러스트·내장 모티프·패턴·코너 도형)은 인라인 SVG/CSS만
허용한다. 래스터(`data:image/png` 등)·외부 URL(`http(s)://`, 원격 `href`/`xlink:href`)·`<script>`·
`<foreignObject>`는 새니타이즈 단계에서 제거되며, 위험 참조가 남으면 해당 SVG는 통째로 무시되고
워드마크/장식 미표시로 fallback한다. 내장 모티프는 전부 `currentColor` 단색·저잉크 벡터다.
인쇄 잉크 검사(`check_ink_coverage`)는 brand `print.ink_coverage_warning` 설정 시 **경고만** 내는
advisory이며 출력을 차단하지 않는다(자체 브랜드 책임). 내장 모티프 라이브러리는 CI 테스트
(`tests/test_motifs`, 실측 ~6% / CI 가드 10% / 인쇄 상한 35%)로 회귀를 강제한다.

## 5-2. LLM 장식 생성 계약 (v0.5) — Codex parity

에이전트가 brand yaml의 `design:` 블록을 직접 조판할 때 적용한다.

**불변식 🔒 텍스트(이름·회사·직무)는 절대 SVG에 넣지 않는다.**
장식 SVG는 배경 레이어 전용. 텍스트는 항상 generate.py가 코드로 렌더한다.

**조판 규칙:**
1. 색은 `fill="currentColor"` — SVG 안에 hex 하드코딩 금지.
2. 저잉크: 큰 면적은 `opacity` 0.06–0.15. 잉크 게이트 35% 상한.
3. `viewBox` 기준 상대 좌표만. `overflow:hidden`이 셀 밖을 자른다.
4. 이름 밴드(세로 32–60%) 뒤를 어둡게 만들지 말 것 — G9 게이트가 장식을 자동 제거함.
5. 벡터만 — 래스터·외부 URL·`<script>`·`<foreignObject>` 새니타이즈 제거.

**`design:` 블록 스키마:**

```yaml
design:
  layout_variant: "name_hero"         # diagonal | name_hero | intro_hero | badge_first
  illustration_svg_inline: '<svg viewBox="0 0 100 100"><polygon points="0,100 100,100 100,40" fill="currentColor" opacity="0.12"/></svg>'
  logo_svg_inline: '<svg ...>...</svg>'  # 선택
  pattern: "dot-grid"                  # 선택: dot-grid | stripe | wave | mesh-corner
  accent_shape: "triangle"             # 선택: triangle | blob
  motif_id: "geo-corner"               # 선택: geo-corner|wave-band|dot-cluster|arc-rings|cross-hatch
```

검증: `python3 scripts/generate.py --validate <yaml>` — 스키마 통과 확인 후 사용.
게이트 fail 시 generate.py가 장식 자동 제거 → 재시도 → preset fallback (인쇄 항상 안전).

## 5-3. AI 셀 템플릿 자율 생성 계약 (v0.6) — Codex parity

에이전트가 brand yaml `design.cell_template`에 **셀 한 칸 전체**(배경·레이아웃·텍스트 배치/색)를 조판한다. generate.py는 검증→실제폰트 텍스트 주입→렌더의 결정론적 소비자(런타임 API 0).

**불변식 🔒** (1) 셀 경계 못 넘음 — `<style>`이 html/body/.cell/.a4-sheet/@page 건드리면 거부. (2) 글자는 코드 주입 — `{{name}}` 등 토큰만, SVG/path로 글자 그리기 금지.

**cell_template 규칙:**
1. 토큰 — `{{name}}`(필수)·`{{organizer}}`/`{{host}}`(둘 중 하나 필수, 주최사/호스트명)·`{{company}}`·`{{role}}`·`{{intro}}`·`{{track}}`·`{{group}}`·`{{event}}`. 사이즈: `{{name_size}}`·`{{company_size}}`(긴 이름 축소 램프). 허용 외 토큰 거부.
2. 텍스트존 — `<!-- textzone: x0,y0,x1,y1 -->`(분수, x0<x1·y0<y1) 필수. 현장 수기/공백형 기준으로 전체 셀의 최소 2/3에 가까운 넓은 이름·소속 작성 공간이어야 한다. 없거나 작으면 floor.
3. 색/폰트 — `var(--brand-*)`만. SVG는 `fill="currentColor"`. 외부 URL·http(s)·`<script>`·핸들러·`@import`·`data:image/`는 거부(sanitize_svg + 잔여 스캔).
4. 셀 충전 컨테이너 + `overflow:hidden`(`.cell.variant-ai`).
5. 공백 작성란에는 점선/밑줄/칸 구분선/NAME 가이드 문구를 넣지 않는다. 장소명·주소·층수 등 포스터성 정보도 네임택 기본값에서 제외한다. 단, 주최사/호스트 이름은 반드시 남긴다.
6. 크리에이티브는 허용하되 인쇄 안전 안에서 한다. 매번 같은 상단 포스터+하단 박스 패턴으로 도망가지 말고, 저잉크 벡터 조형·여백 형태·코너/프레임 구성을 행사마다 다르게 설계한다.

**게이트:** 렌더→잉크·G9·sanitize fail → 강도하향(cell_template 포함 제거) 재시도 → preset(name_hero) fallback. `--layout-variant <floor>`는 AI 건너뛰고 스켈레톤 강제. 검증: `python3 scripts/generate.py --validate <yaml>`.

## 6. 완료 기준 형식

산출물 안내는 항상 **"무엇을 만들었고 / 파일은 어디 있고 / 다음 인쇄 행동은 무엇인지"**
로 끝낸다.

```text
완료했습니다.
- 행사: <행사명>
- 사용한 스타일: <행사 무드/브랜드 톤>
- 출력 파일: <png 경로>

인쇄 전 체크: 용지 A4 / 크기 100% / 맞춤(Scale to Fit) OFF / 자동회전 해제 /
첫 장은 일반 A4 테스트 / 펜 표시로 프린터별 급지 방향 확인 / Preview의 PNG 인쇄 / 탐사 A4 8칸 라벨지
```

> 전체 UX 원칙(대화형 흐름, 디자인 8종 선택 기준, 라벨지 CTA, 사업성 메모)은 `SKILL.md` 참조. quick 경로에서는 preview HTML을 사용자에게 제공하지 않는다.
