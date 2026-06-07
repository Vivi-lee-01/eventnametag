"""P0-C 회귀 게이트: §2-1 PNG-only 인쇄 lock의 테스트화.

인쇄 경로는 반드시 PNG 래스터 + Preview 수동 인쇄여야 한다. PDF 직접 인쇄나
lpr 자동 인쇄 경로가 코드/문서/CLI에 신설되면 Sindoh rangecheck·silent fail이
재현되므로 이 테스트로 차단한다.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATE_PY = ROOT / "scripts" / "generate.py"
SKILL_MD = ROOT / "SKILL.md"
AGENTS_MD = ROOT / "AGENTS.md"


# lpr을 실제 subprocess 인자(명령 토큰)로 넘기는 호출 패턴.
# 산문/안내 문구의 "lpr 직접 인쇄 금지" 같은 *금지 설명*은 잡지 않고,
# `subprocess.run(["lpr", ...])` 같은 실제 호출만 차단한다.
LPR_INVOCATION_RE = re.compile(r"""["']lpr["']""")
# 자동 인쇄 의도를 드러내는 subprocess + lpr 조합
LPR_SUBPROCESS_RE = re.compile(r"(?:run|Popen|call|check_output)\s*\(\s*\[?\s*['\"]lpr['\"]")


class PngOnlyEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.source = GENERATE_PY.read_text(encoding="utf-8")

    def test_no_lpr_invocation_in_code(self):
        # lpr 직접 제출 자동 인쇄 경로(subprocess 호출)가 코드에 없어야 한다 (§2-1 금지).
        # 안내 문구의 'lpr 직접 인쇄 금지'는 정상이므로 명령 토큰 패턴만 검사.
        self.assertIsNone(
            LPR_INVOCATION_RE.search(self.source),
            "lpr을 명령 인자로 넘기는 호출 금지 (§2-1 PNG-only lock)",
        )
        self.assertIsNone(
            LPR_SUBPROCESS_RE.search(self.source),
            "subprocess로 lpr 자동 인쇄 금지 (§2-1 PNG-only lock)",
        )

    def test_subprocess_open_targets_png_via_preview(self):
        # 인쇄용 open 호출 대상은 PNG (Preview). PDF를 Preview로 여는 경로 금지.
        # open -a Preview 호출의 대상이 png_path 변수여야 한다
        self.assertRegex(
            self.source,
            r'open["\s,]+.*-a["\s,]+.*Preview.*png_path',
            "Preview 인쇄 대상은 png_path 여야 함",
        )
        # PDF를 Preview/인쇄로 직접 여는 호출이 없어야 한다
        self.assertNotRegex(
            self.source,
            r'open[^\n]*Preview[^\n]*pdf_path',
            "PDF를 Preview로 직접 여는 경로 금지 (PNG-only)",
        )

    def test_render_pipeline_is_pdf_to_png_raster(self):
        # render_pdf_and_png는 Chrome PDF → sips PNG(300dpi) 래스터 경로를 유지
        self.assertIn("print-to-pdf", self.source, "Chrome PDF 중간 산출물 경로 유지")
        self.assertIn("sips", self.source, "sips 래스터 변환 경로 유지")
        self.assertRegex(self.source, r'"-Z",\s*"3508"', "A4 300dpi 세로 픽셀(3508)로 래스터")

    def test_skill_md_forbids_lpr_invocation(self):
        # 문서(SKILL.md)에 lpr 자동 인쇄가 명령 토큰으로 들어가지 않음
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIsNone(LPR_INVOCATION_RE.search(text), "SKILL.md에 lpr 명령 안내 금지")

    def test_agents_md_states_png_only(self):
        # AGENTS.md(P0-D)가 존재하면 PNG-only 인쇄를 명시하고, lpr을 명령으로 권장하지 않음
        if not AGENTS_MD.exists():
            self.skipTest("AGENTS.md 미존재 (P0-D 미적용 환경)")
        text = AGENTS_MD.read_text(encoding="utf-8")
        self.assertIn("PNG", text)
        self.assertIsNone(LPR_INVOCATION_RE.search(text), "AGENTS.md에 lpr 명령 안내 금지")


if __name__ == "__main__":
    unittest.main()
