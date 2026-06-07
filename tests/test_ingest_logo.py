"""로고 색 추출 결정론 테스트 (Task 1~3).

unittest.TestCase + @skipUnless(Image) 패턴 — test_safety_gate.py 컨벤션 따름.
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ingest_logo  # noqa: E402

try:
    from PIL import Image  # type: ignore
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, "PIL 필요")
class RasterColorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _two_block_png(self, top, bottom):
        img = Image.new("RGB", (40, 40), top)
        for y in range(20, 40):
            for x in range(40):
                img.putpixel((x, y), bottom)
        p = self.tmp / "logo.png"
        img.save(p)
        return p

    def test_extracts_two_dominant_colors(self):
        png = self._two_block_png((10, 20, 30), (200, 210, 220))
        colors = ingest_logo.extract_colors_from_raster(png, max_colors=4)
        self.assertIn("#0a141e", colors)   # (10,20,30)
        self.assertIn("#c8d2dc", colors)   # (200,210,220)


class SvgColorTests(unittest.TestCase):
    def test_extracts_fill_and_stop_colors(self):
        svg = '<svg><path fill="#AABBCC"/><stop stop-color="#123"/>' \
              '<rect style="fill:#aabbcc"/></svg>'
        colors = ingest_logo.extract_colors_from_svg(svg)
        self.assertEqual(colors, ["#aabbcc", "#112233"])  # 순서 보존·중복 병합·3자리 확장


class ColorClassifyTests(unittest.TestCase):
    def test_assigns_dark_light_accents(self):
        colors = ["#0a141e", "#c8d2dc", "#ff0055", "#00ddaa"]
        bc = ingest_logo.logo_to_brand_colors(colors)
        self.assertEqual(bc["primary_dark"], "#0a141e")   # 최저 휘도
        self.assertEqual(bc["primary_light"], "#c8d2dc")  # 최고 휘도
        self.assertIn("accent_1", bc)
        self.assertIn("accent_2", bc)

    def test_synthesizes_light_when_all_dark(self):
        bc = ingest_logo.logo_to_brand_colors(["#0a0a0a", "#111111"])
        self.assertEqual(bc["primary_light"], "#ffffff")  # 밝은 색 없으면 흰색 합성


class ExtractFromLogoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        import extract_brand
        self.eb = extract_brand

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_builds_brand_dict_with_design_and_label_stubs(self):
        # ingest_logo를 monkeypatch — 색 추출을 결정론 고정
        orig = ingest_logo.logo_to_brand_colors
        ingest_logo.logo_to_brand_colors = lambda c: {
            "primary_dark": "#0a0a0b", "primary_light": "#fafafa", "accent_1": "#00ddaa"}
        try:
            brand = self.eb.build_brand_from_logo(
                colors=["#0a0a0b", "#fafafa", "#00ddaa"], wordmark="Acme")
        finally:
            ingest_logo.logo_to_brand_colors = orig
        self.assertEqual(brand["colors"]["primary_dark"], "#0a0a0b")
        self.assertEqual(brand["wordmark"]["text"], "Acme")
        # 에이전트가 채울 라벨 스텁 + 빈 design 슬롯 존재
        self.assertIn("symbol", brand["_labels"])
        self.assertIn("mood", brand["_labels"])
        self.assertEqual(brand["design"]["illustration_svg_inline"], "")


if __name__ == "__main__":
    unittest.main()
