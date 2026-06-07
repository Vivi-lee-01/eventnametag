import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import _svg_safe  # noqa: E402


class SvgSanitizeTests(unittest.TestCase):
    def test_strips_script(self):
        out = _svg_safe.sanitize_svg('<svg><script>alert(1)</script><rect/></svg>')
        self.assertNotIn("<script", out.lower())
        self.assertIn("<rect", out)

    def test_strips_foreign_object(self):
        out = _svg_safe.sanitize_svg('<svg><foreignObject><body/></foreignObject></svg>')
        self.assertNotIn("foreignobject", out.lower())

    def test_strips_remote_href(self):
        out = _svg_safe.sanitize_svg('<svg><image href="https://x/y.png"/><use xlink:href="http://z"/></svg>')
        self.assertNotIn("http", out.lower())

    def test_strips_event_handlers(self):
        out = _svg_safe.sanitize_svg('<svg><rect onclick="x()" onload="y()"/></svg>')
        self.assertNotIn("onclick", out.lower())
        self.assertNotIn("onload", out.lower())

    def test_rejects_non_svg(self):
        self.assertEqual(_svg_safe.sanitize_svg("<div>not svg</div>"), "")
        self.assertEqual(_svg_safe.sanitize_svg(""), "")

    def test_preserves_clean_vector(self):
        clean = '<svg viewBox="0 0 10 10"><path d="M0 0 L10 10" fill="#0a0a0b"/></svg>'
        out = _svg_safe.sanitize_svg(clean)
        self.assertIn("<path", out)
        self.assertIn("M0 0 L10 10", out)

    # ── 보안 회귀 벡터 (2026-06-02 code-review HIGH/MEDIUM 대응) ──

    def test_strips_single_quoted_handler(self):
        out = _svg_safe.sanitize_svg("<svg><rect onclick='x()'/></svg>")
        self.assertNotIn("onclick", out.lower())

    def test_strips_unquoted_handler(self):
        out = _svg_safe.sanitize_svg("<svg><rect onload=y()/></svg>")
        self.assertNotIn("onload", out.lower())

    def test_strips_smil_set(self):
        out = _svg_safe.sanitize_svg('<svg><set attributeName="href" to="javascript:alert(1)"/></svg>')
        self.assertNotIn("javascript", out.lower())
        self.assertNotIn("<set", out.lower())

    def test_strips_animate(self):
        out = _svg_safe.sanitize_svg('<svg><animate attributeName="x" to="5"/></svg>')
        self.assertNotIn("<animate", out.lower())

    def test_nested_script_fully_stripped(self):
        out = _svg_safe.sanitize_svg('<svg><script>a<script>b</script>c</script><rect/></svg>')
        self.assertNotIn("<script", out.lower())

    def test_javascript_uri_rejected(self):
        # javascript: 잔여 시 fail-closed로 통째 거부
        out = _svg_safe.sanitize_svg('<svg><rect fill="url(javascript:alert(1))"/></svg>')
        self.assertEqual(out, "")

    # ── xmlns 네임스페이스 버그 회귀 테스트 (2026-06-03 fix/v0.5-svg-sanitize-xmlns) ──

    def test_xmlns_standard_survives(self):
        # 표준 xmlns 포함 장식 SVG 가 통과해야 함 (v0.5 silent-empty 버그 재현)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'viewBox="0 0 100 100" preserveAspectRatio="none">'
            '<polygon points="0,0 50,100 100,0" fill="#ff0"/>'
            '<polygon points="0,100 50,0 100,100" fill="#00f"/>'
            '<circle cx="50" cy="50" r="20" fill="none" stroke="#f00" stroke-width="3"/>'
            '</svg>'
        )
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotEqual(out.strip(), "", "xmlns 포함 SVG가 빈 문자열로 거부됨 (버그)")
        self.assertIn("<polygon", out)
        self.assertIn("<circle", out)

    def test_xmlns_xlink_survives(self):
        # xmlns:xlink 형태도 표준 w3.org URI 이면 통과
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<rect width="10" height="10" fill="red"/>'
            '</svg>'
        )
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotEqual(out.strip(), "")
        self.assertIn("<rect", out)

    def test_external_image_href_still_blocked(self):
        # image 태그 + 외부 href 는 여전히 차단돼야 함
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.com/x.png"/></svg>'
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotIn("<image", out.lower())
        # image 태그 제거 후 잔여 https: 가 없어야 함 (또는 전체 거부)
        self.assertNotIn("evil.com", out)

    def test_external_use_href_still_blocked(self):
        # use + 외부 xlink:href 는 차단
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><use xlink:href="http://evil.com/sym"/></svg>'
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotIn("<use", out.lower())
        self.assertNotIn("evil.com", out)

    def test_onload_handler_still_blocked_with_xmlns(self):
        # xmlns 있어도 onload 핸들러는 제거돼야 함
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect onload="evil()"/></svg>'
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotIn("onload", out.lower())

    def test_foreignobject_still_blocked_with_xmlns(self):
        # xmlns 있어도 foreignObject 는 제거
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><body/></foreignObject></svg>'
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotIn("foreignobject", out.lower())

    def test_script_still_blocked_with_xmlns(self):
        # xmlns 있어도 script 는 제거
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect/></svg>'
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotIn("<script", out.lower())
        self.assertIn("<rect", out)

    # ── 글루(glued) 핸들러 회귀 테스트 (2026-06-03 보안 회귀 수정) ──

    def test_glued_onload_after_xmlns_blocked(self):
        # xmlns 제거 후 onload 가 앞 토큰에 글루되는 케이스 — 반드시 차단
        svg = '<svg><g xmlns="http://www.w3.org/2000/svg"onload="alert(1)"/></svg>'
        out = _svg_safe.sanitize_svg(svg)
        self.assertNotRegex(out.lower(), r"on\w+\s*=")

    def test_glued_onload_no_xmlns_blocked(self):
        # 공백 없이 속성에 글루된 핸들러 — xmlns 무관하게 차단 (기존 pre-existing 약점)
        svg = '<svg><rect fill="red"onload="x()"/></svg>'
        self.assertNotRegex(_svg_safe.sanitize_svg(svg).lower(), r"on\w+\s*=")

    # ── 인접 핸들러 쌍 회귀 테스트 (2026-06-03 lookbehind + 경계없는 잔여스캔) ──

    def test_adjacent_handler_pair_blocked(self):
        # 첫 핸들러 제거 후 두 번째가 글루되어 살아남는 케이스 — 반드시 차단
        out = _svg_safe.sanitize_svg('<svg><rect onclick="a()"onload="alert(1)"/></svg>')
        self.assertNotRegex(out, r"on\w+\s*=")

    def test_triple_adjacent_handlers_blocked(self):
        # 세 핸들러 연속 글루 — 모두 차단
        out = _svg_safe.sanitize_svg('<svg><rect ona="1()"onb="2()"onc="3()"/></svg>')
        self.assertNotRegex(out, r"on\w+\s*=")


if __name__ == "__main__":
    unittest.main()
