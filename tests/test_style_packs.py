import importlib.util
import contextlib
import io
import os
import re
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate", ROOT / "scripts" / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


class StylePackTests(unittest.TestCase):
    def test_style_pack_applies_event_mood_without_requiring_bi_registration(self):
        brand = {
            "name": "Minimal Mono",
            "slug": "minimal-mono",
            "colors": {"primary_dark": "#171717", "primary_light": "#fafafa"},
            "wordmark": {"text": "Minimal Mono", "case": "upper"},
            "signature": {"type": "none"},
        }

        themed = generate.apply_style_pack(brand, "ai-hackathon")

        self.assertEqual(themed["wordmark"]["text"], "Minimal Mono")
        self.assertEqual(themed["colors"]["primary_dark"], "#080B2A")
        self.assertEqual(themed["colors"]["accent_1"], "#7C3AED")
        self.assertEqual(themed["preferred_skeletons"], ["r3", "r1"])
        self.assertEqual(themed["visual_motif"]["type"], "neon_grid")
        self.assertEqual(themed["print"]["recommended_paper"], "glossy_laser")

    def test_showcase_pack_has_eight_user_visible_product_cards(self):
        self.assertEqual(
            list(generate.STYLE_PACKS.keys()),
            [
                "name-first",
                "networking-intro",
                "recruiting",
                "speaker-staff-vip",
                "ai-hackathon",
                "premium-salon",
                "workshop-learning",
                "qr-connect",
            ],
        )
        labels = [pack["label"] for pack in generate.STYLE_PACKS.values()]
        self.assertIn("이름 가독성 최우선형", labels)
        self.assertIn("QR·LinkedIn 연결형", labels)

    def test_product_cards_define_decision_metadata_for_user_choice(self):
        required_fields = {
            "label",
            "description",
            "best_for",
            "emphasis",
            "fields",
            "internal_layout",
            "print_risk",
            "paper",
            "user_explanation",
            "preferred_skeletons",
            "layout_variant",
            "visual_motif",
        }
        for style_id, pack in generate.STYLE_PACKS.items():
            with self.subTest(style_id=style_id):
                self.assertTrue(required_fields.issubset(pack.keys()))
                self.assertIsInstance(pack["fields"], list)
                self.assertGreaterEqual(len(pack["fields"]), 2)
                self.assertIn(pack["layout_variant"], generate.LAYOUT_VARIANTS)
                self.assertNotRegex(pack["user_explanation"], r"skeleton|R[1-4]")
                self.assertNotRegex(pack["label"], r"skeleton|R[1-4]")

    def test_style_pack_sets_layout_variant_so_showcase_cards_are_not_all_diagonal(self):
        brand = {
            "name": "LiveClass",
            "slug": "liveclass",
            "colors": {"primary_dark": "#123456", "primary_light": "#ffffff"},
            "wordmark": {"text": "LiveClass", "case": "title"},
            "signature": {"type": "none"},
        }

        variants = [
            generate.resolve_layout_variant(generate.apply_style_pack(brand, style_id))
            for style_id in generate.STYLE_PACKS
        ]

        self.assertIn("name_hero", variants)
        self.assertIn("intro_hero", variants)
        self.assertIn("badge_first", variants)
        self.assertIn("diagonal", variants)
        self.assertGreater(len(set(variants)), 1)

    def test_illustration_style_uses_print_safe_sticker_scene(self):
        brand = {
            "name": "Minimal Mono",
            "slug": "minimal-mono",
            "colors": {"primary_dark": "#171717", "primary_light": "#fafafa"},
            "wordmark": {"text": "Minimal Mono", "case": "upper"},
            "signature": {"type": "none"},
        }

        themed = generate.apply_style_pack(brand, "workshop-learning")
        css = generate._motif_css(themed)

        self.assertEqual(themed["visual_motif"]["type"], "sticker_scene")
        self.assertIn("mood-sticker", css)
        self.assertIn("sticker-face", css)

    def test_single_preview_fits_iframe_without_internal_scroll(self):
        brand = {
            "name": "LiveClass",
            "slug": "liveclass",
            "colors": {"primary_dark": "#123456", "primary_light": "#ffffff"},
            "wordmark": {"text": "LiveClass", "case": "title"},
            "signature": {"type": "none"},
        }
        attendee = {"name": "김지원", "company": "LiveClass", "role": "HR Lead", "intro": "채용과 조직문화를 만듭니다"}

        html = generate._render_single_preview(brand, "AI Meetup", "r1", attendee)
        preview_page = generate.build_preview_html(brand, "AI Meetup", ["r1"], [attendee])

        self.assertIn("eventnametag-preview-fit", html)
        self.assertIn("overflow: hidden", html)
        self.assertIn("width: 99.1mm", html)
        self.assertIn("height: 67.7mm", html)
        self.assertIn("scrolling=\"no\"", preview_page)
        self.assertIn("시안 1 — 안정적인 기본형", preview_page)
        self.assertNotIn("시안 1 — R1", preview_page)

    def test_agent_ux_treats_skeleton_page_as_advanced_internal_layout(self):
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("내부 구현/인쇄 안전 레이아웃", skill_text)
        self.assertIn("기본 UX가 아니다", skill_text)
        self.assertIn("직접 고를 필요가 없습니다", readme_text)
        self.assertIn("실패 방지용 내부 구현", readme_text)
        self.assertNotIn("시안 2개 생성", readme_text)

    def test_cli_fallback_style_choices_hide_raw_skeleton_ids_by_default(self):
        self.assertEqual(generate.skeleton_choice_label("r1"), "안정적인 기본형")
        self.assertEqual(generate.skeleton_choice_label("r2"), "긴 이름/회사명에 유리")
        self.assertNotIn("R1", generate.skeleton_choice_label("r1"))
        self.assertNotIn("skeleton", generate.skeleton_choice_label("r1").lower())

    def test_quick_brand_hint_applies_to_agent_noninteractive_flow(self):
        brand = {
            "name": "Minimal Mono",
            "slug": "minimal-mono",
            "colors": {"primary_dark": "#171717", "primary_light": "#fafafa"},
            "wordmark": {"text": "Minimal Mono", "case": "upper"},
            "signature": {"type": "none"},
        }

        themed = generate._apply_quick_brand_hint(brand, "LiveClass")

        self.assertEqual(themed["name"], "LiveClass")
        self.assertEqual(themed["wordmark"]["text"], "LiveClass")

    def test_quick_brand_hint_url_uses_hostname_instead_of_ignoring_url(self):
        brand = {
            "name": "Minimal Mono",
            "slug": "minimal-mono",
            "colors": {"primary_dark": "#171717", "primary_light": "#fafafa"},
            "wordmark": {"text": "Minimal Mono", "case": "upper"},
            "signature": {"type": "none"},
        }

        themed = generate._apply_quick_brand_hint(brand, "https://www.liveklass.com/jobs")

        self.assertEqual(themed["name"], "liveklass.com")
        self.assertEqual(themed["wordmark"]["text"], "liveklass.com")

    def test_quick_cli_brand_hint_reaches_generated_output(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            result = subprocess.run(
                [
                    str(ROOT / "bin" / "eventnametag"),
                    "quick",
                    "--event",
                    "Brand Hint Test",
                    "--brand-hint",
                    "AcmeBrand",
                    "--names",
                    "김지원",
                    "--html-only",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            match = re.search(r"HTML-only 출력 파일: (.+\.html)", result.stderr)
            self.assertIsNotNone(match, result.stderr)
            self.assertNotIn("quick-preview", result.stderr)
            self.assertNotIn("시안 preview 생성", result.stderr)
            output_html = Path(match.group(1)).read_text(encoding="utf-8")
        self.assertIn("ACMEBRAND", output_html)
        self.assertNotIn("Minimal Mono", output_html)

    def test_build_showcase_html_contains_mood_labels_and_paper_recommendations(self):
        brand = {
            "name": "LiveClass",
            "slug": "liveclass",
            "colors": {"primary_dark": "#123456", "primary_light": "#ffffff"},
            "wordmark": {"text": "LiveClass", "case": "title"},
            "signature": {"type": "none"},
        }
        attendees = [
            {"name": "김지원", "company": "LiveClass", "role": "HR Lead", "intro": "채용과 조직문화를 만듭니다"}
        ]

        html = generate.build_showcase_html(brand, "AI Meetup", attendees)

        self.assertIn("바로 고르는 네임택 무드", html)
        self.assertIn("8개", html)
        self.assertIn("이름 가독성 최우선형", html)
        self.assertIn("네트워킹·한줄소개형", html)
        self.assertIn("채용행사·직무 강조형", html)
        self.assertIn("스피커·스태프·VIP 구분형", html)
        self.assertIn("AI·해커톤 에너지형", html)
        self.assertIn("프리미엄 살롱형", html)
        self.assertIn("교육·워크숍 캐주얼형", html)
        self.assertIn("QR·LinkedIn 연결형", html)
        self.assertIn("강조 정보", html)
        self.assertIn("인쇄 리스크", html)
        self.assertIn("기본 탐사 A4 8칸 라벨지 기준", html)
        self.assertNotIn("고급 고광택", html)
        self.assertIn("variant-name_hero", html)
        self.assertIn("variant-intro_hero", html)
        self.assertIn("variant-badge_first", html)
        self.assertIn("variant-diagonal", html)

    def test_label_order_uses_standard_paper_only_and_opens_chrome(self):
        product_name, product_url = generate.choose_label_paper_url()

        self.assertEqual(product_name, "기본 탐사 A4 8칸 라벨지")
        self.assertEqual(product_url, "https://link.coupang.com/a/eGNFOI")

        with mock.patch.object(generate.subprocess, "run") as run:
            generate.open_url_in_chrome(product_url)

        run.assert_called_once_with(
            ["open", "-a", "Google Chrome", "https://link.coupang.com/a/eGNFOI"],
            check=True,
            capture_output=True,
        )

    def test_label_paper_guidance_includes_printer_feed_direction_tip(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            generate.print_label_paper_guidance()

        guidance = stderr.getvalue()
        self.assertIn("프린터마다 라벨지 급지 방향이 다를 수 있습니다", guidance)
        self.assertIn("일반 A4 용지에 펜으로 앞/위 방향을 표시", guidance)
        self.assertIn("라벨지의 상하·앞뒤 출력 방향", guidance)


if __name__ == "__main__":
    unittest.main()
