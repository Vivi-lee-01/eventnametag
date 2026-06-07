# 고급 CLI 사용법

## Quick Start / CLI

AI 에이전트 안에서 사용할 때는 아래 명령을 사용자가 직접 칠 필요가 없습니다. Agent가 라벨지 준비, 행사 정보, 브랜드 방식, 명단 입력 방식을 `askuser`/선택형 질문으로 확인한 뒤 대신 실행하는 것이 기본 UX입니다.

터미널에서 직접 사용할 때만 아래 CLI 흐름을 따르면 됩니다.

### 1. 의존성 설치

```bash
# 시스템 의존성
#   - macOS Preview (기본 제공)
#   - Google Chrome (https://google.com/chrome)
#   - sips (macOS 기본 제공)

# Python 의존성
cd ~/projects/eventnametag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 첫 확인 — doctor

```bash
$ bin/eventnametag doctor
✓ PyYAML
✓ jsonschema
✓ Pillow(PIL)
✓ Google Chrome
✓ sips
✓ Preview open
상태: 바로 demo/quick 실행 가능
```

### 3. 샘플 preview — demo

```bash
$ bin/eventnametag demo --html-only
탐사 A4 8칸 라벨지 준비 상태를 확인할게요.

  1. 쿠팡에서 주문할게요
  2. 이미 가지고 있어요
  3. 라벨지는 나중에 준비하고, 행사 정보부터 입력할게요
> 3
✓ 샘플 네임택 preview 생성
  미리보기: ~/.claude/tmp/eventnametag/demo-preview-....html
```

핵심은 구매를 강요하는 것이 아니라, 물리 라벨지가 없으면 내일 인쇄 일정이 막히므로 첫 실행에서 준비 여부를 먼저 확인하는 것입니다.
1번을 선택하면 Chrome에서 기본 탐사 A4 8칸 라벨지 구매 링크가 바로 열립니다.

### 4. 5분 안에 내 행사 네임택 만들기 — quick

```bash
$ bin/eventnametag quick
행사명을 입력하세요:
> AI Meetup Seoul #3
브랜드/단체 이름이나 URL이 있나요? (없으면 Enter):
> DemoOrg
참석자 명단을 붙여넣으세요. Ctrl+D로 종료합니다.
예: 김지원<Tab>DemoOrg<Tab>HR Lead<Tab>채용과 조직문화를 만듭니다
> 김지원	DemoOrg	HR Lead	채용과 조직문화를 만듭니다
> 박서연	Acme Lab	PM	AI 제품을 기획합니다
> [Ctrl+D]

✓ 명단 2명 파싱
✓ 인쇄용 네임택 생성
📄 PDF → 300dpi PNG → Preview 자동 오픈
```

`quick`은 “바로 만들어줘” 경로이므로 별도 preview 탭을 열지 않습니다. 디자인 비교가 필요할 때만 `showcase`/`demo`를 명시적으로 사용합니다.

파이프/자동화 입력도 가능합니다.

```bash
bin/eventnametag quick --event "AI Meetup" --names "김지원,박서연,이도윤"
```

### 5. BI 등록 (인터뷰 모드)

```bash
$ python3 scripts/generate.py --register-brand
어떻게 BI를 등록하시겠어요?
  1. 직접 yaml 편집  /  2. AI 에이전트 인터뷰  /  3. URL 자동 추출
> 2

🎙️ BI 인터뷰
  회사명? > Acme Lab
  slug? > acme-lab
  주요 색 1 (다크/강조)? > #1a1a2e
  주요 색 2 (배경/라이트)? > #ffffff
  액센트? > #ff6b35
  워드마크? > Acme Lab
  시그니처? (gradient_orb / icon_url / none) > none

✅ 저장: ~/.config/eventnametag/brands/acme-lab.yaml
```

또는 동봉된 examples 따라쓰기:

```bash
cp brands/examples/minimal-mono.yaml ~/.config/eventnametag/brands/my-brand.yaml
$EDITOR ~/.config/eventnametag/brands/my-brand.yaml
```

### 6. 등록한 BI로 행사 네임택 만들기

```bash
$ python3 scripts/generate.py --brand acme-lab --event "올핸즈 2026 Q2"
명단 붙여넣기 (Ctrl+D 종료):
> 김지원	Acme Lab	HR Lead	채용 담당
> 박서연	Acme Lab	PM	제품 기획
> [Ctrl+D]

✓ 명단 2명 파싱
✓ 행사 무드와 BI 기반 네임택 생성
📄 PDF → 300dpi PNG → Preview 자동 오픈
   Cmd+P → 크기 조절 100% → 탐사 A4 8칸 라벨지 인쇄
```

### 7. 첫 인쇄 전 정렬 테스트

```bash
$ bin/eventnametag calibrate
```

격자가 그려진 시트가 나오는데, 일반 A4 종이로 먼저 인쇄해서 라벨지에 겹쳐보고 정렬 확인.

### 8. 라벨지 떨어졌을 때

```bash
$ bin/eventnametag order-paper
🛒 쿠팡 라벨지 페이지 자동 오픈
```

## BI 등록 3가지 입구

| 모드 | 적합 사용자 | 진입 |
|---|---|---|
| **(1) yaml 직접 편집** | 개발자·디자인 안목 있는 사용자 | `brands/examples/`를 `~/.config/eventnametag/brands/`로 복사 후 $EDITOR |
| **(2) AI 에이전트 인터뷰** *(default)* | 색·폰트 정도만 알고 있는 사용자 | `--register-brand` → 2번 |
| **(3) URL 자동 추출** | "회사 사이트 주면 알아서" 사용자 | `--register-brand` → 3번 |

## 내부 안전 fallback

일반 사용자는 내부 레이아웃을 직접 고를 필요가 없습니다. 현재 핵심 기능은 **행사 무드와 BI를 반영한 AI 셀 템플릿 생성**이고, 내부 레이아웃은 AI 템플릿이 인쇄 안전 기준을 통과하지 못할 때만 쓰는 안전장치입니다.

AI 셀 템플릿은 아래 조건을 통과해야 렌더됩니다. 실패하면 도구가 조용히 안전 fallback으로 바꿔 인쇄 실패를 막습니다.

- `{{name}}` 필수
- `{{organizer}}` 또는 `{{host}}` 필수 — 주최사/호스트명
- 작성 공백은 전체 셀의 최소 2/3에 가까운 넓은 영역
- 공백 작성란에 점선/밑줄/칸 구분선 금지
- 장소명·주소·층수·상세 일시 같은 포스터성 정보 금지
- 그라데이션·사진·풀블리드·대면적 진한 배경 금지
- 색/폰트는 브랜드 토큰만 사용

즉, README에서 내부 레이아웃을 사용자가 선택해야 하는 기능처럼 설명하지 않습니다. 그것들은 제품 기능이 아니라 실패 방지용 내부 구현입니다.

## CLI 옵션

```
bin/eventnametag [COMMAND] [OPTIONS]
python3 scripts/generate.py [COMMAND] [OPTIONS]

예:
  bin/eventnametag quick --event "AI Meetup" --names "김지원,박서연,이도윤"
  bin/eventnametag showcase --event "AI Meetup" --brand-hint "DemoOrg"  # 선택: 샘플/디버그

짧은 명령:
  demo                   샘플 브랜드+명단으로 즉시 preview 생성
  doctor                 의존성/브랜드/인쇄 환경 점검
  quick                  행사명/브랜드/명단을 묻는 빠른 생성 wizard
  showcase              선택 기능: 행사 목적별 샘플/디버그 쇼케이스 생성
  order-paper            쿠팡 라벨지 재구매 페이지 자동 오픈
  calibrate              탐사 A4 8칸 라벨지 정렬 테스트 시트
  register-brand         새 BI 등록

옵션:
  --brand <slug>          사용할 BI yaml 지정. 없으면 quick/showcase/demo에서는 예시/brand-hint로 진행
  --event <name>          행사명 (예: "AI Meetup #3"). 장소/층수보다 무드 식별용으로만 최소 사용
  --file <csv>            CSV 파일 경로
  --names <a,b,c>         이름만 쉼표로 (빠른 모드)

  --demo                  샘플 브랜드+명단으로 즉시 preview 생성
  --doctor                의존성/브랜드/인쇄 환경 점검

  --register-brand        새 BI 등록 (인터뷰 / yaml / URL 추출 분기)
  --order-paper           쿠팡 라벨지 재구매 페이지 자동 오픈
  --calibrate             탐사 A4 8칸 라벨지 정렬 테스트 시트 (skeleton 무관)

  --blank                 백지 네임택 (현장 수기용) 8칸
  --both --spares N       명단 + 예비지 N칸 같이
  --fill-blanks           명단 페이지의 남는 칸을 워드마크만 있는 blank로

  --html-only             HTML만 생성 (디버그·빠른 반복용). 기본은 PDF→300dpi PNG
  --no-contrast-check     컬러 대비 가드(G2) 강행
  --ignore-ink            잉크 커버리지 가드(G3) 강행
  --validate <yaml>       BI yaml schema 검증만 수행 후 종료
```

## Non-goals

- ❌ DB 저장 (매번 휘발, CSV가 source of truth)
- ❌ 다른 라벨지 규격 (탐사 A4 8칸 라벨지 전용. 6580·6586 등은 grid 좌표가 다름)
- ❌ Linux/Windows (v0.2 검토)
- ❌ 자동 인쇄 (`lpr` 직접 제출은 드라이버 silent failure가 있음, Preview Cmd+P 위임)
- ❌ QR 이미지 자동 생성 (현재는 연결 문구/URL 텍스트까지만)
- ❌ 라벨지 밖으로 나가는 풀블리드/테두리 디자인
- ❌ 장소·주소·층수까지 넣는 행사 포스터형 네임택
- ❌ 공백 작성란의 점선/밑줄/칸 구분선

## 변경 이력

- **v0.6** — AI 셀 템플릿 자율 생성 + 안전 floor fallback. 작성 공백 2/3, 점선/밑줄 금지, 장소 정보 금지, 주최사/호스트명 필수 가드 추가.
- v0.5 — 저잉크 벡터 장식, 로고/BI 기반 색 추출, 잉크·대비 게이트 강화.
- v0.1 — 초기 출시. 4 skeleton 풀 + BI yaml + 인터뷰 + 한국어 README.

## 기여

Pull Request 환영. 작은 수정은 바로, 큰 변경은 issue 먼저.

```bash
git clone https://github.com/<user>/eventnametag
cd eventnametag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 기여하실 때
```

새 BI를 `brands/examples/`에 PR로 추가하실 때:
- yaml schema 통과 (필수)
- 컬러 대비 WCAG AA (가능하면)
- skeleton별 calibrate 1회 인쇄 검증 결과 (선택)

