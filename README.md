# eventnametag

> **행사 네임택을 디자인부터 인쇄 파일까지 한 번에 만드는 무료 AI 에이전트 스킬.**
> 행사명·브랜드 단서·레퍼런스만 있어도 현장 수기용 네임택을 만들고, 명단이 있으면 참가자별 네임택까지 탐사 A4 8칸 라벨지(99×67.5mm)에 맞춰 바로 출력합니다. Hermes, Codex, Claude Code 같은 AI 에이전트와 일반 터미널에서 사용할 수 있습니다.
>
> 인쇄에 필요한 라벨지는 여기서 바로 구입할 수 있습니다: **탐사 A4 8칸 라벨지** https://link.coupang.com/a/eGNFOI
>
> 이 링크는 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

## 인쇄 가이드

기본 경로는 **Preview로 자동 오픈되는 300dpi PNG → Cmd+P**입니다. 자동 맞춤이 켜지면 라벨 칸이 1–3mm씩 밀릴 수 있으니, 아래 설정을 그대로 확인하세요.

![macOS Preview 인쇄 설정 예시](docs/print/preview-print-settings.svg)

1. 최종 파일은 Preview에 열린 **300dpi PNG**를 사용합니다.
2. 인쇄 용지는 **A4**로 설정합니다.
3. 배율은 **크기 조절 100%**로 둡니다.
4. `용지에 맞게 크기 조절 / Scale to Fit / 자동 맞춤`은 끕니다.
5. 자동 회전은 끕니다.
6. 첫 장은 일반 A4에 테스트 인쇄한 뒤, 실제 라벨지와 겹쳐 8칸 정렬과 급지 방향을 확인합니다.

상세 설정과 정렬 보정은 [docs/print-guide.md](docs/print-guide.md)를 보세요.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Skill: AI Agent](https://img.shields.io/badge/AI%20Agent-skill-7c3aed.svg)](https://github.com/)

---

## 무엇을 할 수 있나요

- 행사명, 브랜드 단서, 참고 이미지/URL/md 같은 레퍼런스를 주면 행사 무드에 맞는 네임택을 만듭니다.
- 명단이 있으면 참가자별 네임택을 자동 배치하고, 명단이 없어도 현장 수기용 빈 네임택을 만들 수 있습니다.
- 출력은 탐사 A4 8칸 라벨지(99×67.5mm)에 맞춘 HTML/PDF/300dpi PNG입니다.
- 기본 인쇄 경로는 **Preview에 열린 PNG → Cmd+P → A4 100%**입니다.
- 내부 레이아웃은 일반 사용자가 직접 고를 필요가 없습니다. AI 템플릿 실패 시 인쇄를 망치지 않기 위한 실패 방지용 내부 구현입니다.

## AI 에이전트에서 쓰기

Hermes, Codex, Claude Code 같은 AI 에이전트에게 이렇게 말하면 됩니다.

```text
우리 행사 네임택 만들어줘. 행사명은 AI Meetup Seoul이고, 브랜드는 DemoOrg 느낌으로. 현장 수기용으로 8칸 뽑고 싶어.
```

```text
이 명단으로 참가자별 네임택 만들어줘. 탐사 A4 8칸 라벨지에 바로 인쇄할 수 있게 PNG까지 열어줘.
```

```text
이 로고/웹사이트 분위기 참고해서 채용행사용 네임택 만들어줘. 이름이 멀리서 잘 보이게 해줘.
```

에이전트는 행사명, 브랜드 단서, 명단/파일 여부만 확인한 뒤 필요한 명령을 대신 실행하는 흐름이 기본입니다. 사용자가 “샘플 먼저”라고 하지 않는 한, 별도 쇼케이스 화면을 먼저 띄우지 않습니다.

## 터미널 Quick Start

```bash
cd ~/projects/eventnametag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

bin/eventnametag doctor
bin/eventnametag quick --event "AI Meetup" --names "김지원,박서연,이도윤"
```

샘플을 보고 싶을 때만:

```bash
bin/eventnametag demo --html-only
bin/eventnametag showcase --event "AI Meetup" --brand-hint "DemoOrg"
```

## 입력 방식

| 입력 | 가능 여부 | 설명 |
|---|---:|---|
| 행사명 | 권장 | 네임택 상단/무드 식별에 사용 |
| 브랜드/단체명 | 권장 | 워드마크와 기본 톤에 사용 |
| 웹사이트 URL | 가능 | 브랜드명/색/분위기 단서로 사용 |
| 로고/이미지/md | 가능 | AI 에이전트가 참고해 인쇄 안전한 벡터 무드로 번역 |
| 명단 | 선택 | 있으면 참가자별, 없으면 현장 수기용 |
| CSV/TSV | 가능 | 이름·소속·직무·소개 등을 파싱 |

## 자세한 문서

- [인쇄 가이드](docs/print-guide.md)
- [고급 CLI 사용법](docs/advanced-cli.md)
- [가드레일](docs/guardrails.md)
- [FAQ / 트러블슈팅](docs/troubleshooting.md)
- [쇼케이스 예시](docs/showcase/mood-showcase.html)

## 범위

- 지원: macOS, Google Chrome, Preview, `sips`, 탐사 A4 8칸 라벨지
- 비범위: 다른 라벨지 규격, 자동 `lpr` 인쇄, DB 저장, QR 이미지 자동 생성, 풀블리드/테두리 디자인

## 라이선스

[MIT](LICENSE)
