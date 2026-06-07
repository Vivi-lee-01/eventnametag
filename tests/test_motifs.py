import pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import _motifs  # noqa: E402
import generate  # noqa: E402

_CHROME = pathlib.Path("/Applications/Google Chrome.app")


class MotifLibraryTests(unittest.TestCase):
    def test_list_motifs_nonempty(self):
        self.assertTrue(len(_motifs.list_motifs()) >= 3)

    def test_get_motif_returns_svg(self):
        mid = _motifs.list_motifs()[0]
        svg = _motifs.get_motif(mid)
        self.assertIn("<svg", svg.lower())

    def test_motifs_are_vector_only(self):
        # 내장 자산은 래스터 data URI를 포함하면 안 됨 (인쇄안전)
        for mid in _motifs.list_motifs():
            self.assertNotIn("data:image/png", _motifs.get_motif(mid).lower())
            self.assertNotIn("http", _motifs.get_motif(mid).lower())

    def test_unknown_motif_returns_empty(self):
        self.assertEqual(_motifs.get_motif("nope-xyz"), "")


class InkGateVectorTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("sips") and _CHROME.exists() and generate.Image is not None,
                         "Chrome+sips+Pillow 필요 (실제 렌더)")
    def test_pattern_render_under_ink_threshold(self):
        # design.pattern(dot-grid) + motif(geo-corner) 적용 PNG를 실제로 렌더해
        # estimate_ink_coverage가 풀블리드 상한(35%) 이하인지 확인.
        # 저잉크 설계라 통과해야 하며, 초과하면 모티프 opacity 하향이 필요하다.
        brand = generate._minimal_brand_for_test()
        d = brand.setdefault("design", {})
        d["pattern"] = "dot-grid"
        d["motif_id"] = "geo-corner"
        d["accent_shape"] = "triangle"
        attendees = [
            {"name": "김지원", "company": "회사A", "role": "PM", "intro": "한 줄 소개"},
            {"name": "박서연", "company": "회사B", "role": "Engineer", "intro": "자동화"},
        ]
        template = generate._inject_variant_css(
            generate._inject_motif_css(
                generate.inject_brand_tokens(generate.load_skeleton_template("r1"), brand), brand))
        # P1-B/C 저잉크 모티프(pattern/motif/accent_shape) 경로를 검증하는 테스트이므로
        # 해당 장식을 렌더하는 name_hero 변형으로 고정한다 (diagonal은 자체 컬러블록 사용).
        filled = generate.build_pages(attendees, brand, "INK GATE TEST", layout_variant="name_hero")
        html = template.replace("<!-- CELLS_HERE -->", filled)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = pathlib.Path(tmp)
            html_path = tmp_dir / "ink-gate.html"
            html_path.write_text(html, encoding="utf-8")
            _pdf, png = generate.render_pdf_and_png(html_path, tmp_dir)
            coverage = generate.estimate_ink_coverage(png)

        self.assertIsNotNone(coverage)
        # 풀블리드 인쇄 상한은 35%이나, 내장 모티프는 저잉크(~2%)이므로 CI 가드는
        # 10%로 좁혀 모티프 opacity 회귀를 인쇄 상한 도달 훨씬 전에 잡는다.
        self.assertLess(coverage, 10.0, f"잉크 커버리지 {coverage:.1f}% > 10% CI 가드 (모티프 강도 회귀 의심)")


if __name__ == "__main__":
    unittest.main()
