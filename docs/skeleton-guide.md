# 사용자 정의 Skeleton 가이드

eventnametag는 4개 검증된 skeleton(R1·R2·R3·R4)을 기본으로 제공하지만, 사용자가 자기 BI 시그니처에 맞는 새 skeleton을 추가할 수 있습니다.

## 언제 사용자 정의 skeleton이 필요한가

기본 4종이 BI 시그니처를 충분히 표현하지 못할 때:

- 회사 시그니처가 **사선 컬러블록** (R1-R4 모두 직사각형)
- **로고 마크가 본문 정중앙에 큰 워터마크**로 들어가야 함
- 행사 컨셉 (할로윈, 신년, 컨퍼런스 series) 별로 시즌 변형이 필요함

## 추가 절차

### 1. 파일 생성

```bash
mkdir -p ~/.config/eventnametag/templates/custom
$EDITOR ~/.config/eventnametag/templates/custom/<your-skeleton>.html
```

또는 스킬 내부에 추가하려면 `templates/custom/<your-skeleton>.html` (PR 환영).

### 2. 기존 skeleton 베이스로 시작

가장 가까운 R1-R4 한 개를 복사:

```bash
cp templates/r1-topbar.html templates/custom/diagonal.html
$EDITOR templates/custom/diagonal.html
```

### 3. 필수 요건

- **`@page` 블록**: `size: A4; margin: 0;` 그대로
- **`.a4-sheet`** grid: `padding: 16.1mm 4.5mm 10.1mm; grid-template-columns: 1fr 1fr; column-gap: 3.3mm;` (탐사 A4 8칸 라벨지 grid)
- **`.cell`**: `width: 99.1mm; height: 67.7mm;` 정확
- **BI 토큰 placeholder**: `:root` 안에 다음 9개 변수를 `{{}}` placeholder로 두기. generate.py가 yaml에서 읽어 inject:
  ```css
  :root {
    --brand-dark: {{BRAND_DARK}};
    --brand-light: {{BRAND_LIGHT}};
    --brand-accent-1: {{BRAND_ACCENT_1}};
    --brand-accent-2: {{BRAND_ACCENT_2}};
    --brand-surface-subtle: {{BRAND_SURFACE_SUBTLE}};
    --brand-font-body: {{BRAND_FONT_BODY}};
    --brand-font-mono: {{BRAND_FONT_MONO}};
    --signature-inner: {{SIGNATURE_INNER}};
    --signature-outer: {{SIGNATURE_OUTER}};
  }
  ```
- **`<!-- CELLS_HERE -->`** placeholder를 `<body>` 안에 둘 것 (generate.py가 8칸 cell HTML 채움)
- **공통 cell 마크업**: `.tag` > (`.topbar` 또는 사용자 변형) > `.body` > `.name`/`.company`/`.role`/`.intro`. generate.py의 `build_cell()`이 이 구조를 가정.

### 4. BI yaml에서 참조

```yaml
preferred_skeletons: [r1, custom-diagonal]
```

`custom-` 접두어 필수. 스킬 검색 순서: `templates/custom/<name>.html` → 사용자 외부 디렉토리 (env override).

### 5. 검증

```bash
python3 scripts/generate.py --calibrate     # 탐사 A4 8칸 라벨지 정렬 시트로 종이 정렬 확인
python3 scripts/generate.py --brand <slug> --event "테스트"  # 시안 미리보기
```

**첫 인쇄 권장**: 일반 A4 종이로 먼저 출력 → 라벨지에 겹쳐 정렬 확인 → 잉크 커버리지 G3 경고 봤으면 RGB 비중 조정.

## 인쇄 안전성 체크

- **잉크 커버리지** ≤ 25% (저가 레이저 권장). 풀블리드는 35%까지 OK 단, calibrate 검증 후
- **WCAG 대비** ≥ 4.5 (이름·회사가 배경 위에서 가독)
- **한글 CID 폰트 + CSS 그라디언트** 조합 시 PostScript `rangecheck` 회피는 자동 (Chrome → sips raster 경로)

## v0.2 로드맵

- AI skeleton 자동 생성 (BI yaml 보고 새 HTML 작성, 사용자 검증 워크플로우)
- 사용자 정의 skeleton의 정렬 자동 검증 (calibrate에 매칭 비교)
- 시즌 변형 (event tag 기반 skeleton 자동 선택)
