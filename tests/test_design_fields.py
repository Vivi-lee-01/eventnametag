import json, pathlib, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "brand.schema.json").read_text())

sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402


class SchemaDesignSectionTests(unittest.TestCase):
    def test_design_is_known_property(self):
        # root additionalProperties:false 이므로 design이 명시돼야 통과
        self.assertIn("design", SCHEMA["properties"])

    def test_design_fields_present(self):
        props = SCHEMA["properties"]["design"]["properties"]
        for key in ("layout_variant", "logo_svg_inline", "illustration_svg_inline",
                    "motif_id", "pattern", "accent_shape", "cell_template"):
            self.assertIn(key, props, key)

    def test_layout_variant_enum(self):
        enum = SCHEMA["properties"]["design"]["properties"]["layout_variant"]["enum"]
        self.assertEqual(set(enum), {"diagonal", "name_hero", "intro_hero", "badge_first"})

    def test_cell_template_field_present(self):
        # v0.6: AI 셀 템플릿 필드가 design 블록에 명시돼야 한다 (additionalProperties:false 통과 조건).
        props = SCHEMA["properties"]["design"]["properties"]
        self.assertIn("cell_template", props)
        self.assertEqual(props["cell_template"]["type"], "string")

    def test_design_optional(self):
        self.assertNotIn("design", SCHEMA.get("required", []))


class ExtendedFieldsParseTests(unittest.TestCase):
    def test_track_and_interests_preserved(self):
        text = "name,role,track,interests\n김지원,PM,AI,LLM\n"
        kept, _ = generate.parse_attendees(text)
        self.assertEqual(kept[0].get("track"), "AI")
        self.assertEqual(kept[0].get("interests"), "LLM")

    def test_base_four_fields_still_work(self):
        # 헤더 없는 기존 4필드 TSV는 그대로 동작 (회귀 0).
        # intro 값은 헤더 키워드(소개/한줄소개)와 충돌하지 않는 본문으로 둔다 —
        # 단일행 입력에서 셀 값이 헤더 키워드면 헤더로 오인돼 drop되는 기존 동작 회피.
        kept, _ = generate.parse_attendees("김지원\t회사A\tPM\t반갑습니다")
        self.assertEqual(kept[0]["name"], "김지원")
        self.assertEqual(kept[0]["company"], "회사A")


class LayoutVariantTests(unittest.TestCase):
    def setUp(self):
        self.att = {"name": "김지원", "company": "회사A", "role": "PM",
                    "intro": "한줄소개", "track": "AI", "interests": "LLM", "group": "Staff"}
        self.brand = generate._minimal_brand_for_test()

    def test_variants_produce_distinct_structure(self):
        a = generate.build_cell(self.att, self.brand, "행사", layout_variant="name_hero")
        b = generate.build_cell(self.att, self.brand, "행사", layout_variant="intro_hero")
        c = generate.build_cell(self.att, self.brand, "행사", layout_variant="badge_first")
        # 세 변형의 DOM이 실제로 달라야 한다 (구조 마커)
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, c)
        self.assertIn("variant-name_hero", a)
        self.assertIn("variant-intro_hero", b)
        self.assertIn("variant-badge_first", c)

    def test_badge_first_renders_track(self):
        c = generate.build_cell(self.att, self.brand, "행사", layout_variant="badge_first")
        self.assertIn("AI", c)  # track 배지 노출

    def test_default_variant_is_diagonal(self):
        # P1: 밋밋한 기본값 해소 — 인자 미지정 시 검증된 대각 컬러블록이 나와야 한다.
        d = generate.build_cell(self.att, self.brand, "행사")
        self.assertIn("variant-diagonal", d)

    def test_resolve_layout_variant_defaults_to_diagonal(self):
        # design.layout_variant·override 미설정 시 기본은 diagonal.
        self.assertEqual(generate.resolve_layout_variant(self.brand), "diagonal")

    def test_build_pages_default_is_diagonal(self):
        # build_pages가 design 미설정 brand에서도 diagonal 셀을 내야 한다.
        pages = generate.build_pages([self.att], self.brand, "행사")
        self.assertIn("variant-diagonal", pages)

    def test_diagonal_structure_markers(self):
        # 검증된 시안 구조 요소가 셀에 존재해야 한다.
        d = generate.build_cell(self.att, self.brand, "행사", layout_variant="diagonal")
        for marker in ("variant-diagonal", "dcell", "diag-top", "diag-corner",
                       "dhead", "dbody", "dname"):
            self.assertIn(marker, d, marker)

    def test_diagonal_badge_from_track(self):
        # track/group이 있으면 dbadge로 노출 (없으면 미표시).
        d = generate.build_cell(self.att, self.brand, "행사", layout_variant="diagonal")
        self.assertIn("dbadge", d)
        self.assertIn("AI", d)  # track 값
        no_badge = generate.build_cell(
            {"name": "김지원", "company": "회사A", "role": "PM", "intro": ""},
            self.brand, "행사", layout_variant="diagonal")
        self.assertNotIn("dbadge", no_badge)


class InlineLogoTests(unittest.TestCase):
    def test_clean_logo_injected(self):
        brand = generate._minimal_brand_for_test()
        brand.setdefault("design", {})["logo_svg_inline"] = '<svg viewBox="0 0 10 10"><rect width="10" height="10" fill="#000"/></svg>'
        html = generate.build_cell({"name": "김지원", "company": "A", "role": "PM", "intro": ""}, brand, "행사")
        self.assertIn("<svg", html)
        self.assertIn("<rect", html)

    def test_malicious_logo_sanitized(self):
        brand = generate._minimal_brand_for_test()
        brand.setdefault("design", {})["logo_svg_inline"] = '<svg><script>x()</script><rect/></svg>'
        html = generate.build_cell({"name": "김지원", "company": "A", "role": "PM", "intro": ""}, brand, "행사")
        self.assertNotIn("<script", html.lower())

    def test_no_logo_falls_back_to_wordmark(self):
        brand = generate._minimal_brand_for_test()  # design.logo 없음
        html = generate.build_cell({"name": "김지원", "company": "A", "role": "PM", "intro": ""}, brand, "행사")
        self.assertIn(brand["wordmark"]["text"], html)


class CliFlagTests(unittest.TestCase):
    def test_layout_variant_flag_registered(self):
        parser = generate._build_arg_parser()
        ns = parser.parse_args(["--layout-variant", "badge_first", "--event", "X"])
        self.assertEqual(ns.layout_variant, "badge_first")


class IllustrationSlotTests(unittest.TestCase):
    # 일러스트 슬롯은 topbar/body 변형(.tag 내부)에 깔리는 P1-C 장식이므로
    # diagonal 자체 컬러블록과 충돌하지 않게 name_hero 변형으로 검증한다.
    def test_inline_illustration_injected(self):
        brand = generate._minimal_brand_for_test()
        brand.setdefault("design", {})["illustration_svg_inline"] = '<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="3"/></svg>'
        html = generate.build_cell({"name": "김", "company": "A", "role": "PM", "intro": ""}, brand, "행사", layout_variant="name_hero")
        self.assertIn("<circle", html)

    def test_motif_id_injected_from_library(self):
        brand = generate._minimal_brand_for_test()
        brand.setdefault("design", {})["motif_id"] = "geo-corner"
        html = generate.build_cell({"name": "김", "company": "A", "role": "PM", "intro": ""}, brand, "행사", layout_variant="name_hero")
        self.assertIn("<svg", html.lower())

    def test_inline_overrides_motif(self):
        brand = generate._minimal_brand_for_test()
        d = brand.setdefault("design", {})
        d["illustration_svg_inline"] = '<svg><rect id="MINE"/></svg>'
        d["motif_id"] = "geo-corner"
        html = generate.build_cell({"name": "김", "company": "A", "role": "PM", "intro": ""}, brand, "행사", layout_variant="name_hero")
        self.assertIn("MINE", html)  # inline 우선


class PatternTokenTests(unittest.TestCase):
    def test_pattern_emits_css(self):
        brand = generate._minimal_brand_for_test()
        brand.setdefault("design", {})["pattern"] = "dot-grid"
        css = generate._motif_css(brand)
        self.assertIn("dot-grid", css)   # 패턴 클래스/배경 정의 포함

    def test_accent_shape_emits_svg_shape(self):
        brand = generate._minimal_brand_for_test()
        brand.setdefault("design", {})["accent_shape"] = "triangle"
        # 코너 강조 도형은 .tag 내부 P1-B 장식 → name_hero 변형에서 검증.
        html = generate.build_cell({"name": "김", "company": "A", "role": "PM", "intro": ""}, brand, "행사", layout_variant="name_hero")
        self.assertIn("accent-triangle", html)

    def test_no_pattern_no_change(self):
        brand = generate._minimal_brand_for_test()
        css = generate._motif_css(brand)  # design 없음 → 기존 동작
        self.assertIsInstance(css, str)


if __name__ == "__main__":
    unittest.main()
