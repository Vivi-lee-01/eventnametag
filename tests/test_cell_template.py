"""v0.6 AI 셀 템플릿 — 검증·치환·분기·floor 단위 테스트.

PyYAML/Chrome 비의존. sanitize 경계는 _svg_safe 재사용을 가정한다.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402


# 검증 통과하는 표준 AI 템플릿 (텍스트존 + {{name}} + 저잉크 SVG 배경).
GOOD_TEMPLATE = (
    "<!-- textzone: 0.04,0.32,0.96,0.98 -->\n"
    '<div class="ai-root">\n'
    '  <svg viewBox="0 0 100 68"><rect x="0" y="0" width="100" height="20" '
    'fill="currentColor" opacity="0.1"/></svg>\n'
    '  <div class="ai-name" style="font-size: {{name_size}}; color: var(--brand-dark)">{{name}}</div>\n'
    '  <div class="ai-co" style="color: var(--brand-accent-1)">{{company}}</div>\n'
    '  <div class="ai-org" style="position:absolute;right:4mm;bottom:3mm;font-size:2.5mm;color:var(--brand-dark)">{{organizer}}</div>\n'
    "</div>"
)


class ValidateCellTemplateTests(unittest.TestCase):
    def test_good_template_passes_and_returns_textzone(self):
        ok, tz, reason = generate.validate_cell_template(GOOD_TEMPLATE)
        self.assertTrue(ok, reason)
        self.assertEqual(tz, (0.04, 0.32, 0.96, 0.98))

    def test_missing_name_slot_rejected(self):
        tpl = "<!-- textzone: 0.1,0.4,0.9,0.6 --><div>{{company}}</div>"
        ok, tz, reason = generate.validate_cell_template(tpl)
        self.assertFalse(ok)
        self.assertIsNone(tz)

    def test_missing_textzone_rejected(self):
        tpl = '<div class="ai-root">{{name}}</div>'
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_out_of_range_textzone_rejected(self):
        tpl = "<!-- textzone: 0.1,0.4,1.2,0.6 --><div>{{name}}</div>"
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_inverted_textzone_rejected(self):
        # x1 <= x0
        tpl = "<!-- textzone: 0.9,0.4,0.1,0.6 --><div>{{name}}</div>"
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_unknown_token_rejected(self):
        tpl = "<!-- textzone: 0.1,0.4,0.9,0.6 --><div>{{name}}{{BRAND_DARK}}</div>"
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_missing_organizer_slot_rejected(self):
        tpl = "<!-- textzone: 0.04,0.32,0.96,0.98 --><div>{{name}}</div>"
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertFalse(ok)
        self.assertIn("주최사", reason)

    def test_host_alias_accepted(self):
        tpl = "<!-- textzone: 0.04,0.32,0.96,0.98 --><div>{{name}}{{host}}</div>"
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertTrue(ok, reason)

    def test_script_rejected(self):
        tpl = ("<!-- textzone: 0.1,0.4,0.9,0.6 -->"
               "<div>{{name}}<script>x()</script></div>")
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_event_handler_rejected(self):
        tpl = ('<!-- textzone: 0.1,0.4,0.9,0.6 -->'
               '<div onclick="x()">{{name}}</div>')
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_external_url_rejected(self):
        tpl = ('<!-- textzone: 0.1,0.4,0.9,0.6 -->'
               '<div style="background:url(https://evil/x.png)">{{name}}</div>')
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_unsalvageable_svg_rejected(self):
        # sanitize_svg가 ''로 wholesale 거부하는 svg(javascript: URL은 스트립으로 못 없애
        # fail-closed로 '' 반환) → 템플릿 거부. (svg 내부 <script>는 sanitize가 스트립해
        # non-empty를 반환하므로 거부 대상이 아니다 — 렌더 시 fill이 정화한다. 아래 xmlns 참고.)
        tpl = ('<!-- textzone: 0.1,0.4,0.9,0.6 -->'
               '<div><svg style="background:url(javascript:alert(1))"></svg>{{name}}</div>')
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_svg_with_standard_xmlns_accepted(self):
        # 표준 xmlns(http://www.w3.org/2000/svg)는 무해 — sanitize가 스트립하지만 validate는
        # 거부하지 않는다(AI가 SVG에 습관적으로 추가). 거부하면 정상 디자인이 floor로 떨어진다.
        tpl = ('<!-- textzone: 0.04,0.32,0.96,0.98 -->'
               '<div><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
               '<rect width="10" height="10" fill="currentColor"/></svg>{{name}}{{organizer}}</div>')
        ok, tz, reason = generate.validate_cell_template(tpl)
        self.assertTrue(ok, reason)

    def test_reserved_selector_in_style_rejected(self):
        tpl = ("<!-- textzone: 0.1,0.4,0.9,0.6 -->"
               "<style>.cell{width:50mm}</style><div>{{name}}{{organizer}}</div>")
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_cell_hyphen_class_accepted(self):
        # .cell-name 등 하이픈 BEM 클래스는 예약 셀렉터(.cell)가 아니므로 통과해야 한다.
        tpl = ("<!-- textzone: 0.04,0.32,0.96,0.98 -->"
               "<style>.cell-name{font-size:14px}</style><div class=\"cell-name\">{{name}}{{organizer}}</div>")
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertTrue(ok, reason)

    def test_empty_rejected(self):
        ok, _, _ = generate.validate_cell_template("   ")
        self.assertFalse(ok)

    def test_svg_internal_style_stripped_from_output(self):
        # svg 내부 <style>은 sanitize가 제거 → 셀 경계 침범 불가(@page/.cell 출력 안 됨).
        # lenient: validate는 통과하되 fill 출력에 위험 style이 남지 않아야 한다.
        tpl = ("<!-- textzone: 0.04,0.32,0.96,0.98 -->"
               "<svg><style>@page{margin:9cm}.cell{transform:scale(3)}</style>"
               "<rect width='10' height='10' fill='currentColor'/></svg>{{name}}")
        out = generate.fill_template(tpl, {"name": "김"},
                                     generate._minimal_brand_for_test(), "")
        self.assertNotIn("<style", out.lower())
        self.assertNotIn("@page", out)
        self.assertNotIn("scale(3)", out)
        self.assertIn("<rect", out)  # 무해 svg 본문은 유지

    def test_position_fixed_rejected(self):
        tpl = ("<!-- textzone: 0.1,0.4,0.9,0.6 -->"
               "<div style='position:fixed;top:-50mm'>{{name}}{{organizer}}</div>")
        ok, _, _ = generate.validate_cell_template(tpl)
        self.assertFalse(ok)

    def test_position_absolute_still_accepted(self):
        # position:absolute(셀 내부 배치)는 정상 — 거부되면 안 된다.
        tpl = ("<!-- textzone: 0.04,0.32,0.96,0.98 -->"
               "<div style='position:absolute;top:40%'>{{name}}{{organizer}}</div>")
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertTrue(ok, reason)

    def test_writing_space_must_be_two_thirds_of_cell(self):
        tpl = "<!-- textzone: 0.1,0.45,0.9,0.7 --><div>{{name}}{{organizer}}</div>"
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertFalse(ok)
        self.assertIn("2/3", reason)

    def test_blank_writing_guides_rejected(self):
        tpl = (
            "<!-- textzone: 0.04,0.32,0.96,0.98 -->"
            "<div style='border-bottom:0.3mm dashed #ccc'>{{name}}{{organizer}}</div>"
        )
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertFalse(ok)
        self.assertIn("밑줄/점선", reason)

    def test_venue_copy_rejected(self):
        tpl = (
            "<!-- textzone: 0.04,0.32,0.96,0.98 -->"
            "<div>토스 신논현오피스 9F {{name}}{{organizer}}</div>"
        )
        ok, _, reason = generate.validate_cell_template(tpl)
        self.assertFalse(ok)
        self.assertIn("장소명", reason)


class FillTemplateTests(unittest.TestCase):
    def _brand(self):
        return generate._minimal_brand_for_test()

    def test_name_substituted_as_real_text(self):
        out = generate.fill_template(GOOD_TEMPLATE,
                                     {"name": "김지원", "company": "데모오그"},
                                     self._brand(), "AI Meetup")
        self.assertIn("김지원", out)
        self.assertIn("데모오그", out)
        self.assertIn("TESTBRAND", out)
        self.assertNotIn("{{name}}", out)
        self.assertNotIn("{{company}}", out)
        self.assertNotIn("{{organizer}}", out)

    def test_name_size_token_uses_font_ramp(self):
        # 짧은 이름 → 14mm 램프, 긴 이름 → 더 작은 크기 (셀 침범 방지)
        short = generate.fill_template(GOOD_TEMPLATE, {"name": "김"}, self._brand(), "")
        long = generate.fill_template(
            GOOD_TEMPLATE, {"name": "김지원박서연이도윤최"}, self._brand(), "")
        self.assertIn(generate.name_font_size("김"), short)
        self.assertIn(generate.name_font_size("김지원박서연이도윤최"), long)
        self.assertNotEqual(generate.name_font_size("김"),
                            generate.name_font_size("김지원박서연이도윤최"))

    def test_html_escaped(self):
        out = generate.fill_template(GOOD_TEMPLATE,
                                     {"name": "<b>x</b>", "company": "A&B"},
                                     self._brand(), "")
        self.assertNotIn("<b>x</b>", out)
        self.assertIn("&lt;b&gt;", out)
        self.assertIn("A&amp;B", out)

    def test_svg_kept_but_sanitized(self):
        tpl = ("<!-- textzone: 0.04,0.32,0.96,0.98 -->"
               '<div><svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg">'
               '<rect width="10" height="10" fill="currentColor"/></svg>{{name}}</div>')
        out = generate.fill_template(tpl, {"name": "김"}, self._brand(), "")
        self.assertIn("<rect", out)            # 무해 SVG는 유지
        self.assertNotIn("xmlns", out.lower())  # sanitize가 표준 xmlns 제거

    def test_missing_optional_fields_become_empty(self):
        out = generate.fill_template(GOOD_TEMPLATE, {"name": "김"}, self._brand(), "")
        self.assertNotIn("{{company}}", out)        # company 없어도 토큰은 사라짐
        self.assertIn("김", out)                     # 제공된 이름은 렌더됨
        # 사이즈 토큰은 항상 코드값으로 치환 → 빈 'font-size: ' 오염이 없어야 함
        self.assertNotIn("font-size: ;", out.replace(" ", " "))
        self.assertNotIn("font-size:;", out)
        self.assertIn(generate.name_font_size("김"), out)  # name_size 토큰이 실제 값으로


class BuildCellAiBranchTests(unittest.TestCase):
    def _brand_with_template(self, template=GOOD_TEMPLATE):
        b = generate._minimal_brand_for_test()
        b.setdefault("design", {})["cell_template"] = template
        return b

    def test_valid_template_uses_ai_path(self):
        html = generate.build_cell({"name": "김지원", "company": "A"},
                                   self._brand_with_template(), "Meetup")
        self.assertIn("variant-ai", html)
        self.assertIn("김지원", html)
        self.assertIn("ai-root", html)        # AI 템플릿 구조 마커
        self.assertNotIn("variant-diagonal", html)  # 스켈레톤 경로 아님

    def test_invalid_template_falls_back_to_skeleton(self):
        # textzone 없는 무효 템플릿 → 기존 diagonal 스켈레톤
        bad = generate.build_cell({"name": "김지원", "company": "A", "track": "AI"},
                                  self._brand_with_template("<div>{{name}}{{organizer}}</div>"),
                                  "Meetup")
        self.assertNotIn("variant-ai", bad)
        self.assertIn("variant-diagonal", bad)

    def test_no_template_is_unchanged_skeleton(self):
        # cell_template 없는 brand → 기존 동작 회귀 0
        html = generate.build_cell({"name": "김지원", "company": "A", "track": "AI"},
                                   generate._minimal_brand_for_test(), "Meetup")
        self.assertIn("variant-diagonal", html)
        self.assertNotIn("variant-ai", html)

    def test_empty_cell_ignores_template(self):
        html = generate.build_cell(None, self._brand_with_template(), "Meetup")
        self.assertIn("cell empty", html)
        self.assertNotIn("variant-ai", html)


class BuildPagesFloorOverrideTests(unittest.TestCase):
    def _brand_with_template(self):
        b = generate._minimal_brand_for_test()
        b.setdefault("design", {})["cell_template"] = GOOD_TEMPLATE
        return b

    def test_no_override_uses_ai_template(self):
        pages = generate.build_pages([{"name": "김지원"}], self._brand_with_template(), "Meetup")
        self.assertIn("variant-ai", pages)

    def test_explicit_layout_variant_skips_ai(self):
        # 명시 floor(name_hero) → AI 건너뛰고 스켈레톤
        pages = generate.build_pages([{"name": "김지원"}], self._brand_with_template(),
                                     "Meetup", layout_variant="name_hero")
        self.assertNotIn("variant-ai", pages)
        self.assertIn("variant-name_hero", pages)

    def test_override_does_not_mutate_brand(self):
        b = self._brand_with_template()
        generate.build_pages([{"name": "김지원"}], b, "Meetup", layout_variant="name_hero")
        self.assertIn("cell_template", b["design"])  # 원본 brand 불변

    def test_brand_design_variant_with_no_cli_override_uses_ai(self):
        # brand YAML에 design.layout_variant가 있어도 CLI override(=build_pages layout_variant 인자)가
        # None이면 AI 셀 템플릿이 이긴다. strip 조건은 resolved variant가 아니라 CLI 인자다.
        b = self._brand_with_template()
        b.setdefault("design", {})["layout_variant"] = "name_hero"
        pages = generate.build_pages([{"name": "김지원"}], b, "Meetup")  # layout_variant=None
        self.assertIn("variant-ai", pages)
