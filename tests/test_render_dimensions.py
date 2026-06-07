"""P0-C 회귀 게이트: 생성 PNG가 A4@300dpi(2480×3508px ±3)인지.

설계 선택(둘 다 둔다):
- test_real_render_*  : Chrome+sips가 있으면 실제 render_pdf_and_png를 돌려 PNG의
  실제 픽셀/dpi를 검증한다. 가장 신뢰도 높은 신호이므로 가능하면 이쪽이 정답이다.
  Chrome 미설치 CI에서는 skipUnless로 graceful skip 한다.
- test_sips_args_*    : Chrome이 없어도 항상 도는 경량 가드. render_pdf_and_png가
  sips에 넘기는 인자(-Z 3508, dpiHeight/Width 300)가 올바르게 구성되는지를
  subprocess.run을 가로채 검사한다. 실제 렌더가 무거운 환경에서도 회귀 신호 유지.
"""
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate", ROOT / "scripts" / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)

CHROME_OK = Path(generate.CHROME_BIN).exists()
SIPS_OK = shutil.which("sips") is not None
try:
    from PIL import Image  # noqa: F401
    PIL_OK = True
except Exception:
    PIL_OK = False

# A4 @ 300dpi
EXPECTED_W = 2480
EXPECTED_H = 3508
TOLERANCE = 3


class SipsArgsTests(unittest.TestCase):
    """경량 가드: Chrome 없이도 항상 실행. sips 인자 구성만 검사."""

    def test_render_pipeline_passes_a4_300dpi_args_to_sips(self):
        calls = []

        def fake_run(cmd, *a, **kw):
            calls.append([str(c) for c in cmd])
            # Chrome PDF·sips PNG 산출물이 있는 것처럼 위장
            out_idx = None
            if "--out" in cmd:
                out_idx = cmd.index("--out")
                Path(cmd[out_idx + 1]).write_bytes(b"\x89PNG\r\n")
            for tok in cmd:
                tok = str(tok)
                if tok.startswith("--print-to-pdf="):
                    Path(tok.split("=", 1)[1]).write_bytes(b"%PDF-1.4")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "in.html"
            html.write_text("<html><body>x</body></html>", encoding="utf-8")
            with mock.patch.object(generate.subprocess, "run", side_effect=fake_run):
                generate.render_pdf_and_png(html, Path(d))

        sips_calls = [c for c in calls if c and c[0] == "sips"]
        self.assertTrue(sips_calls, "sips 호출이 있어야 함")
        # 1) PNG 변환 시 -Z 3508 (A4 세로 300dpi 픽셀)
        z_call = next((c for c in sips_calls if "-Z" in c), None)
        self.assertIsNotNone(z_call, "-Z 리사이즈 호출 필요")
        self.assertEqual(z_call[z_call.index("-Z") + 1], "3508")
        # 2) dpi 메타 300x300 주입
        dpi_call = next((c for c in sips_calls if "dpiHeight" in c), None)
        self.assertIsNotNone(dpi_call, "dpiHeight/Width 호출 필요")
        self.assertEqual(dpi_call[dpi_call.index("-s") + 1], "dpiHeight")
        self.assertIn("300", dpi_call)


@unittest.skipUnless(CHROME_OK and SIPS_OK and PIL_OK, "Chrome/sips/PIL 미설치 — 실제 렌더 skip")
class RealRenderTests(unittest.TestCase):
    """실제 render_pdf_and_png를 돌려 PNG 실픽셀/dpi 검증 (가장 신뢰도 높은 신호)."""

    def test_generated_png_is_a4_300dpi(self):
        from PIL import Image

        # A4 비율 HTML (templates 좌표 lock과 무관하게 @page A4만으로 비율 검증)
        html_text = (
            "<!doctype html><html><head><style>"
            "@page{size:A4;margin:0;}"
            "html,body{margin:0;padding:0;}"
            ".a4-sheet{width:210mm;height:297mm;background:#fff;}"
            "</style></head><body><div class='a4-sheet'></div></body></html>"
        )
        with tempfile.TemporaryDirectory() as d:
            html = Path(d) / "render.html"
            html.write_text(html_text, encoding="utf-8")
            _pdf, png = generate.render_pdf_and_png(html, Path(d))
            with Image.open(png) as im:
                w, h = im.size
                dpi = im.info.get("dpi", (None, None))

        self.assertAlmostEqual(w, EXPECTED_W, delta=TOLERANCE,
                               msg=f"PNG 가로 {w}px ≠ {EXPECTED_W}±{TOLERANCE}")
        self.assertAlmostEqual(h, EXPECTED_H, delta=TOLERANCE,
                               msg=f"PNG 세로 {h}px ≠ {EXPECTED_H}±{TOLERANCE}")
        # dpi 메타 300 (실제 크기 인쇄 보장 근거)
        self.assertAlmostEqual(round(dpi[0]), 300, delta=1)
        self.assertAlmostEqual(round(dpi[1]), 300, delta=1)


if __name__ == "__main__":
    unittest.main()
