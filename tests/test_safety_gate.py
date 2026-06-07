"""P0 인쇄안전 닫힌 루프 테스트 (verify_print_safety / render_with_safety_loop).

verify 로직(잉크·대비)은 합성 PNG/색으로 Chrome 없이 단위검증한다.
실렌더 경로(Chrome→sips)는 skipUnless로 환경 있을 때만 돈다.
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None

try:
    import yaml as _yaml  # type: ignore
    YAML_AVAILABLE = _yaml is not None
except Exception:  # pragma: no cover
    YAML_AVAILABLE = False

CHROME_AVAILABLE = pathlib.Path(generate.CHROME_BIN).exists() and shutil.which("sips") is not None


def _solid_png(path: pathlib.Path, rgb: tuple[int, int, int], size: int = 64) -> None:
    """단색 PNG를 합성한다. (0,0,0)=잉크 100% / (255,255,255)=잉크 0%."""
    Image.new("RGB", (size, size), rgb).save(path)


# ─────────────────────── verify_print_safety — 단위 (Chrome 불필요) ───────────────────────

@unittest.skipUnless(Image is not None, "PIL 필요")
class VerifyPrintSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _brand(self, dark="#0a0a0b", light="#fafafa", ink_thr=None):
        b = {"colors": {"primary_dark": dark, "primary_light": light}}
        if ink_thr is not None:
            b["print"] = {"ink_coverage_warning": ink_thr}
        return b

    def test_low_ink_high_contrast_ok(self):
        """저잉크(거의 흰색) + 고대비 brand → 통과, 실패 0."""
        png = self.tmp / "white.png"
        _solid_png(png, (250, 250, 250))  # 잉크 ~2%
        res = generate.verify_print_safety(png, self._brand())
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["failures"], [])

    def test_high_ink_detected(self):
        """고잉크(거의 검정) PNG → ink_coverage 실패 감지."""
        png = self.tmp / "black.png"
        _solid_png(png, (10, 10, 10))  # 잉크 ~96%
        res = generate.verify_print_safety(png, self._brand())
        self.assertFalse(res["ok"])
        checks = [f["check"] for f in res["failures"]]
        self.assertIn("ink_coverage", checks)

    def test_ink_threshold_from_brand(self):
        """brand.print.ink_coverage_warning가 게이트 임계로 쓰인다 (기본 35% 대신)."""
        png = self.tmp / "mid.png"
        # 50% 회색 → 잉크 ~50%. brand 임계 25면 fail, 기본 35도 fail이라 임계 70으로 검증.
        _solid_png(png, (128, 128, 128))
        res = generate.verify_print_safety(png, self._brand(ink_thr=70))
        self.assertTrue(res["ok"], res)  # 50% < 70% 임계 → 통과
        res2 = generate.verify_print_safety(png, self._brand(ink_thr=10))
        self.assertFalse(res2["ok"])  # 50% > 10% 임계 → 실패

    def test_low_contrast_detected(self):
        """텍스트색 ≈ 배경색(저대비) brand → contrast 실패 감지."""
        png = self.tmp / "white2.png"
        _solid_png(png, (250, 250, 250))  # 잉크는 통과
        res = generate.verify_print_safety(png, self._brand(dark="#777777", light="#888888"))
        self.assertFalse(res["ok"])
        checks = [f["check"] for f in res["failures"]]
        self.assertIn("contrast", checks)
        self.assertNotIn("ink_coverage", checks)

    def test_ocr_overflow_hooks_are_noop(self):
        """확장 지점(_verify_name_ocr/_verify_overflow)은 이번 범위에서 no-op."""
        png = self.tmp / "white3.png"
        _solid_png(png, (255, 255, 255))
        self.assertEqual(generate._verify_name_ocr(png, [{"name": "김지원"}]), [])
        self.assertEqual(generate._verify_overflow(png, [{"name": "김지원"}]), [])


# ─────────────────────── 강도하향/preset 헬퍼 — 단위 ───────────────────────

class DowngradeAndPresetTests(unittest.TestCase):
    def test_downgrade_strips_decorations(self):
        b = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
             "design": {"pattern": "wave", "motif_id": "x", "accent_shape": "blob",
                        "illustration_svg_inline": "<svg></svg>", "layout_variant": "diagonal"}}
        out = generate._downgrade_design(b, fix_contrast=False)
        for key in ("pattern", "motif_id", "accent_shape", "illustration_svg_inline"):
            self.assertNotIn(key, out["design"], key)
        # layout_variant는 강도하향에서 보존 (장식만 제거)
        self.assertEqual(out["design"]["layout_variant"], "diagonal")
        # 원본 불변
        self.assertIn("pattern", b["design"])

    def test_downgrade_fixes_contrast_when_requested(self):
        b = {"colors": {"primary_dark": "#777777", "primary_light": "#ffffff"}}
        out = generate._downgrade_design(b, fix_contrast=True)
        self.assertEqual(out["colors"]["primary_dark"], generate.SAFE_DARK_TEXT)
        ratio = generate.contrast_ratio(out["colors"]["primary_dark"], out["colors"]["primary_light"])
        self.assertGreaterEqual(ratio, generate.CONTRAST_GATE_THRESHOLD)

    def test_downgrade_skips_contrast_fix_on_dark_bg(self):
        """배경이 어두워 안전 다크값으로도 대비를 못 만들면 색을 강제하지 않는다."""
        b = {"colors": {"primary_dark": "#333333", "primary_light": "#000000"}}
        out = generate._downgrade_design(b, fix_contrast=True)
        self.assertEqual(out["colors"]["primary_dark"], "#333333")

    def test_safe_preset_uses_name_hero_no_decorations(self):
        b = {"colors": {"primary_dark": "#777777", "primary_light": "#ffffff"},
             "design": {"pattern": "wave", "layout_variant": "diagonal"}}
        out = generate._safe_preset_brand(b)
        self.assertEqual(out["design"]["layout_variant"], "name_hero")
        self.assertNotIn("pattern", out["design"])

    def test_ink_gate_threshold_default_and_override(self):
        self.assertEqual(generate._ink_gate_threshold({}), generate.DEFAULT_INK_GATE_THRESHOLD)
        self.assertEqual(generate._ink_gate_threshold({"print": {"ink_coverage_warning": 25}}), 25.0)

    def test_downgrade_strips_cell_template(self):
        b = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
             "design": {"cell_template": "<!-- textzone: 0,0.4,1,0.6 --><div>{{name}}</div>",
                        "layout_variant": "diagonal"}}
        out = generate._downgrade_design(b, fix_contrast=False)
        self.assertNotIn("cell_template", out["design"])
        # 원본 불변
        self.assertIn("cell_template", b["design"])

    def test_safe_preset_strips_cell_template(self):
        b = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
             "design": {"cell_template": "<!-- textzone: 0,0.4,1,0.6 --><div>{{name}}</div>"}}
        out = generate._safe_preset_brand(b)
        self.assertNotIn("cell_template", out["design"])
        self.assertEqual(out["design"]["layout_variant"], "name_hero")


# ─────────────────────── render_with_safety_loop — render_pdf_and_png 가짜 주입 (Chrome 불필요) ───────────────────────

@unittest.skipUnless(Image is not None, "PIL 필요")
class SafetyLoopFakeRenderTests(unittest.TestCase):
    """render_pdf_and_png를 합성 PNG 생성기로 교체해 루프 분기를 Chrome 없이 검증한다."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._orig_render = generate.render_pdf_and_png
        self._orig_skeletons = generate.get_candidate_skeletons
        self._orig_build = generate._build_print_html
        # _build_print_html은 skeleton 파일 로드에 의존 → 루프 분기 검증엔 불필요하므로 stub
        generate.get_candidate_skeletons = lambda brand: ["r1"]
        generate._build_print_html = lambda *a, **k: "<html></html>"

    def tearDown(self):
        generate.render_pdf_and_png = self._orig_render
        generate.get_candidate_skeletons = self._orig_skeletons
        generate._build_print_html = self._orig_build
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _install_render(self, rgb_sequence):
        """호출 순서대로 다른 색 PNG를 뱉는 가짜 render_pdf_and_png 설치."""
        calls = {"i": 0}

        def fake(html_path, out_dir):
            idx = min(calls["i"], len(rgb_sequence) - 1)
            rgb = rgb_sequence[idx]
            calls["i"] += 1
            png = out_dir / f"fake-{calls['i']}.png"
            _solid_png(png, rgb)
            return (out_dir / "fake.pdf", png)

        generate.render_pdf_and_png = fake
        return calls

    def test_first_pass_no_retry(self):
        """1차에 저잉크·고대비 → 재시도·fallback 0 (기존 정상 출력 회귀 없음)."""
        self._install_render([(250, 250, 250)])
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Demo", self.tmp)
        self.assertEqual(report["retried"], 0)
        self.assertFalse(report["fallback_used"])
        self.assertEqual(report["final_failures"], [])

    def test_high_ink_recovers_via_retry(self):
        """1차 고잉크 → 재시도에서 저잉크 PNG 나오면 통과 (fallback 미사용)."""
        self._install_render([(10, 10, 10), (250, 250, 250)])
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Demo", self.tmp, max_retries=2)
        self.assertGreaterEqual(report["retried"], 1)
        self.assertFalse(report["fallback_used"])
        self.assertEqual(report["final_failures"], [])

    def test_persistent_high_ink_falls_back(self):
        """모든 시도에서 고잉크 지속 → preset fallback 사용."""
        self._install_render([(10, 10, 10)])  # 항상 검정
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Demo", self.tmp, max_retries=2)
        self.assertTrue(report["fallback_used"])
        self.assertEqual(report["retried"], 2)

    def test_low_contrast_recovers_via_retry(self):
        """저대비 brand → 재시도에서 텍스트색 강제 보정 후 통과."""
        # PNG는 항상 저잉크(통과). 실패 요인은 brand 대비뿐.
        self._install_render([(250, 250, 250)])
        brand = {"colors": {"primary_dark": "#777777", "primary_light": "#ffffff"}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Demo", self.tmp, max_retries=2)
        # 첫 재시도에서 대비 보정(SAFE_DARK_TEXT) → 통과, fallback 불필요
        self.assertFalse(report["fallback_used"])
        self.assertEqual(report["final_failures"], [])
        self.assertGreaterEqual(report["retried"], 1)


# ─────────────────────── G5: 텍스트영역 대비 게이트 — 단위 ───────────────────────

@unittest.skipUnless(Image is not None, "PIL 필요")
class TextRegionContrastTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _brand(self):
        return {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}

    def test_light_background_passes(self):
        png = self.tmp / "light.png"
        _solid_png(png, (250, 250, 250), size=128)  # 흰 배경 → 어두운 글자 대비 충분
        fails = generate._verify_text_region_contrast(png, self._brand())
        self.assertEqual(fails, [])

    def test_dark_decoration_behind_name_fails(self):
        # 이름 밴드(세로 32~60%) 영역이 어두운 중간톤 → 어두운 글자와 대비 붕괴
        png = self.tmp / "muddy.png"
        Image.new("RGB", (128, 128), (60, 60, 60)).save(png)
        fails = generate._verify_text_region_contrast(png, self._brand())
        self.assertTrue(fails)
        self.assertEqual(fails[0]["check"], "text_region_contrast")

    @staticmethod
    def _per_cell_top_banded(path, size=128):
        """**row 0을 제외한** 칸 행(1~3)의 상단 ~22%만 어둡게, 각 칸 이름밴드(세로 32~60%)는 흰색.
        row 0을 흰색으로 남기는 게 핵심: 전역 단일 샘플(top 20% = 이미지 rows 0~20%) 구현은
        흰 영역만 보고 '통과'하지만, per-cell 루프는 row 1~3 칸 상단의 dark를 만나 'fail'한다.
        → 이 이미지는 global-flattening 회귀를 실제로 잡는 가드다(균일 이미지로는 구분 불가)."""
        img = Image.new("RGB", (size, size), (250, 250, 250))
        ch = size / 4  # 4 rows
        for cyi in range(1, 4):  # row 0 제외 — 전역 top-strip이 흰색이어야 회귀 가드 성립
            for y in range(int(cyi * ch), int(cyi * ch + 0.22 * ch)):
                for x in range(size):
                    img.putpixel((x, y), (30, 30, 30))
        img.save(path)

    def test_custom_textzone_samples_declared_region(self):
        # 각 칸 상단만 어둡고 칸별 이름밴드(32~60%)는 흰 PNG. 기본 밴드는 per-cell로 통과,
        # textzone을 각 칸 상단(0,0,1,0.2)으로 주면 칸별 어두운 영역을 샘플 → fail.
        png = self.tmp / "percell_top.png"
        self._per_cell_top_banded(png)
        self.assertEqual(generate._verify_text_region_contrast(png, self._brand()), [])
        fails = generate._verify_text_region_contrast(
            png, self._brand(), textzone=(0.0, 0.0, 1.0, 0.2))
        self.assertTrue(fails)
        self.assertEqual(fails[0]["check"], "text_region_contrast")

    def test_verify_print_safety_threads_textzone(self):
        png = self.tmp / "percell_thread.png"
        self._per_cell_top_banded(png)
        res = generate.verify_print_safety(png, self._brand(), textzone=(0.0, 0.0, 1.0, 0.2))
        checks = [f["check"] for f in res["failures"]]
        self.assertIn("text_region_contrast", checks)


# ─────────────────────── G5: 텍스트영역 대비 루프 연동 — 단위 ───────────────────────

@unittest.skipUnless(Image is not None, "PIL 필요")
class TextRegionLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._orig = (generate.render_pdf_and_png,
                      generate.get_candidate_skeletons,
                      generate._build_print_html)
        generate.get_candidate_skeletons = lambda brand: ["r1"]
        generate._build_print_html = lambda *a, **k: "<html></html>"

    def tearDown(self):
        (generate.render_pdf_and_png,
         generate.get_candidate_skeletons,
         generate._build_print_html) = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _banded_png(path, size=128):
        """흰 배경 + 이름 밴드(세로 32~60%) 전폭에만 어두운 띠.

        밴드는 전체의 ~28% → 잉크 게이트(35%) 통과. 전역 대비는 brand 색 기준이라 통과.
        그러나 G5는 이름 밴드 배경을 샘플 → 어두움 → text_region_contrast만 fail.
        잉크/전역대비 게이트와 G5를 격리해 G5 배선을 단독 검증한다."""
        img = Image.new("RGB", (size, size), (250, 250, 250))
        y0, y1 = int(0.32 * size), int(0.60 * size)
        for y in range(y0, y1):
            for x in range(size):
                img.putpixel((x, y), (40, 40, 40))
        img.save(path)

    def _install_render(self, png_kinds):
        """호출 순서대로 PNG 종류를 뱉는 가짜 render_pdf_and_png 설치.

        png_kinds: "banded"(G5만 fail) 또는 "clean"(전부 통과) 시퀀스."""
        seq = list(png_kinds)
        calls = {"i": 0}

        def fake(html_path, out_dir, **k):
            kind = seq[calls["i"]] if calls["i"] < len(seq) else seq[-1]
            calls["i"] += 1
            png = pathlib.Path(out_dir) / f"p-{calls['i']}.png"
            if kind == "banded":
                self._banded_png(png)
            else:  # clean
                Image.new("RGB", (128, 128), (250, 250, 250)).save(png)
            return (png.with_suffix(".pdf"), png)

        generate.render_pdf_and_png = fake
        return calls

    def test_banded_png_isolates_g5(self):
        """밴드 PNG는 잉크/전역대비 게이트를 통과하고 G5만 fail시킨다 (격리 보증)."""
        png = self.tmp / "banded.png"
        self._banded_png(png)
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        ink = generate.estimate_ink_coverage(png)
        self.assertLess(ink, 35.0, f"밴드 PNG 잉크 {ink:.1f}% — 잉크 게이트를 넘으면 격리 실패")
        res = generate.verify_print_safety(png, brand, attendees=[{"name": "김지원"}])
        checks = [f["check"] for f in res["failures"]]
        self.assertEqual(checks, ["text_region_contrast"],
                         f"G5만 fail해야 격리 성립 — 실제: {res['failures']}")

    def test_dark_decoration_triggers_retry_then_passes(self):
        # 1차: 이름 밴드만 어두움(G5만 fail) → 2차: 흰 배경(통과)
        calls = self._install_render(["banded", "clean"])
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
                 "design": {"illustration_svg_inline": "<svg/>"}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Demo", self.tmp, max_retries=2)
        # G5 fail → 재시도, 2차 clean으로 통과
        self.assertGreaterEqual(report["retried"], 1)
        self.assertFalse(report["fallback_used"])
        self.assertEqual(report["final_failures"], [])
        # 1차(banded) + 2차(clean) = 최소 2회 렌더 → 재시도가 실제 발생했음을 보증
        self.assertGreaterEqual(calls["i"], 2)

    def test_persistent_dark_band_falls_back(self):
        """매 시도 밴드 어두움 지속(G5 계속 fail) → 장식 제거로도 안 풀리면 preset fallback."""
        self._install_render(["banded"])  # 항상 G5 fail
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
                 "design": {"illustration_svg_inline": "<svg/>"}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Demo", self.tmp, max_retries=2)
        self.assertTrue(report["fallback_used"])
        self.assertEqual(report["retried"], 2)


# ─────────────────────── escape hatch — 게이트 우회 ───────────────────────

class EscapeHatchTests(unittest.TestCase):
    """--ignore-ink/--no-contrast-check 주면 finalize_output이 닫힌 루프를 건너뛴다."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._orig_render = generate.render_pdf_and_png
        self._orig_loop = generate.render_with_safety_loop
        self._orig_check_deps = generate.check_dependencies
        self._orig_check_ink = generate.check_ink_coverage
        self._orig_subprocess_run = generate.subprocess.run
        self._orig_open = generate.webbrowser.open
        self._orig_outdir = generate.OUTPUT_DIR
        generate.OUTPUT_DIR = self.tmp
        generate.check_dependencies = lambda: None
        generate.check_ink_coverage = lambda *a, **k: None
        generate.webbrowser.open = lambda *a, **k: None
        generate.subprocess.run = lambda *a, **k: None  # Preview open 등 무력화
        self.loop_called = {"n": 0}
        self.simple_called = {"n": 0}

        def fake_loop(*a, **k):
            self.loop_called["n"] += 1
            png = self.tmp / "loop.png"
            png.write_bytes(b"")
            return png, {"retried": 0, "fallback_used": False, "final_failures": []}

        def fake_simple(html_path, out_dir):
            self.simple_called["n"] += 1
            png = out_dir / "simple.png"
            png.write_bytes(b"")
            return (out_dir / "x.pdf", png)

        generate.render_with_safety_loop = fake_loop
        generate.render_pdf_and_png = fake_simple

    def tearDown(self):
        generate.render_pdf_and_png = self._orig_render
        generate.render_with_safety_loop = self._orig_loop
        generate.check_dependencies = self._orig_check_deps
        generate.check_ink_coverage = self._orig_check_ink
        generate.subprocess.run = self._orig_subprocess_run
        generate.webbrowser.open = self._orig_open
        generate.OUTPUT_DIR = self._orig_outdir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _html(self):
        p = self.tmp / "in.html"
        p.write_text("<html></html>", encoding="utf-8")
        return p

    def test_default_uses_gate(self):
        """escape hatch 없으면 닫힌 루프 실행."""
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        generate.finalize_output(
            self._html(), html_only=False, brand=brand,
            safety_loop={"attendees": [{"name": "김지원"}], "event": "Demo"})
        self.assertEqual(self.loop_called["n"], 1)
        self.assertEqual(self.simple_called["n"], 0)

    def test_ignore_ink_bypasses_gate(self):
        """--ignore-ink → 게이트 우회, 단순 렌더로 떨어짐."""
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        generate.finalize_output(
            self._html(), html_only=False, brand=brand, ignore_ink=True,
            safety_loop={"attendees": [{"name": "김지원"}], "event": "Demo"})
        self.assertEqual(self.loop_called["n"], 0)
        self.assertEqual(self.simple_called["n"], 1)

    def test_no_contrast_check_bypasses_gate(self):
        """--no-contrast-check → 게이트 우회."""
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
        generate.finalize_output(
            self._html(), html_only=False, brand=brand, no_contrast_check=True,
            safety_loop={"attendees": [{"name": "김지원"}], "event": "Demo"})
        self.assertEqual(self.loop_called["n"], 0)
        self.assertEqual(self.simple_called["n"], 1)


# ─────────────────────── 수정1: calibration이 게이트 경로에도 주입되는지 ───────────────────────

class CalibrationInGatePathTests(unittest.TestCase):
    """게이트 경로(_build_print_html)가 calibration transform을 주입하는지 Chrome 없이 HTML 문자열 검사."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._orig_cal = generate.load_calibration

    def tearDown(self):
        generate.load_calibration = self._orig_cal
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _brand(self):
        return {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
                "preferred_skeletons": []}

    def test_calibration_injected_when_present(self):
        """load_calibration이 값을 반환할 때 _build_print_html 결과에 transform이 들어간다."""
        generate.load_calibration = lambda: {"x": 1.5, "y": -2.0}
        html = generate._build_print_html(
            [{"name": "김지원"}], self._brand(), "Test")
        # apply_calibration_transform이 주입하는 CSS 패턴 확인
        self.assertIn("translate(1.5mm, -2.0mm)", html)

    def test_no_calibration_no_transform(self):
        """load_calibration이 None이면 transform CSS가 없다."""
        generate.load_calibration = lambda: None
        html = generate._build_print_html(
            [{"name": "김지원"}], self._brand(), "Test")
        self.assertNotIn("calibration profile", html)

    def test_calibration_applies_to_downgraded_rebuild(self):
        """강도하향 재빌드(render_with_safety_loop 내부)에도 calibration이 들어간다.
        render_pdf_and_png를 가짜로 교체해 Chrome 없이 검증."""
        generate.load_calibration = lambda: {"x": 3.0, "y": 0.5}
        captured = {}

        orig_render = generate.render_pdf_and_png
        def fake_render(html_path, out_dir):
            captured["html"] = pathlib.Path(html_path).read_text(encoding="utf-8")
            png = pathlib.Path(out_dir) / "fake.png"
            png.write_bytes(b"")
            return (pathlib.Path(out_dir) / "fake.pdf", png)

        orig_skeletons = generate.get_candidate_skeletons
        orig_build = generate._build_print_html

        generate.render_pdf_and_png = fake_render
        generate.get_candidate_skeletons = lambda b: ["r1"]
        generate._build_print_html = lambda *a, **k: orig_build(*a, **k)
        try:
            brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
            generate.render_with_safety_loop(
                [{"name": "김지원"}], brand, "Test", self.tmp, max_retries=0)
            self.assertIn("translate(3.0mm, 0.5mm)", captured.get("html", ""))
        finally:
            generate.render_pdf_and_png = orig_render
            generate.get_candidate_skeletons = orig_skeletons
            generate._build_print_html = orig_build


# ─────────────────────── 수정2: skeleton 선택이 게이트 경로에 전달되는지 ───────────────────────

class SkeletonPassthroughTests(unittest.TestCase):
    """사용자가 선택한 skeleton이 render_with_safety_loop까지 흘러가는지 확인."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._orig_cal = generate.load_calibration
        generate.load_calibration = lambda: None  # calibration은 이 테스트와 무관

    def tearDown(self):
        generate.load_calibration = self._orig_cal
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_skeleton_forwarded_to_build(self):
        """render_with_safety_loop에 skeleton='r4' 전달 시 _build_print_html이 그 값을 쓴다."""
        used = {}

        orig_build = generate._build_print_html
        def spy_build(*a, **k):
            used["skeleton"] = k.get("skeleton")
            # HTML만 반환하면 되므로 간단한 stub
            return "<html></html>"

        orig_render = generate.render_pdf_and_png
        def fake_render(html_path, out_dir):
            png = pathlib.Path(out_dir) / "fake.png"
            png.write_bytes(b"")
            return (pathlib.Path(out_dir) / "fake.pdf", png)

        generate._build_print_html = spy_build
        generate.render_pdf_and_png = fake_render
        try:
            brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
            generate.render_with_safety_loop(
                [{"name": "김지원"}], brand, "Test", self.tmp,
                skeleton="r4", max_retries=0)
            self.assertEqual(used.get("skeleton"), "r4")
        finally:
            generate._build_print_html = orig_build
            generate.render_pdf_and_png = orig_render

    def test_skeleton_none_uses_first_candidate(self):
        """skeleton 미지정 시 get_candidate_skeletons[0]이 쓰인다."""
        used = {}

        orig_build = generate._build_print_html
        def spy_build(*a, **k):
            used["skeleton"] = k.get("skeleton")
            return "<html></html>"

        orig_render = generate.render_pdf_and_png
        def fake_render(html_path, out_dir):
            png = pathlib.Path(out_dir) / "fake.png"
            png.write_bytes(b"")
            return (pathlib.Path(out_dir) / "fake.pdf", png)

        orig_skeletons = generate.get_candidate_skeletons
        generate._build_print_html = spy_build
        generate.render_pdf_and_png = fake_render
        generate.get_candidate_skeletons = lambda b: ["r1", "r2"]
        try:
            brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"}}
            generate.render_with_safety_loop(
                [{"name": "김지원"}], brand, "Test", self.tmp, max_retries=0)
            # skeleton=None → _build_print_html 내에서 get_candidate_skeletons[0]="r1" 사용
            self.assertIsNone(used.get("skeleton"))  # None이 그대로 전달됨을 확인
        finally:
            generate._build_print_html = orig_build
            generate.render_pdf_and_png = orig_render
            generate.get_candidate_skeletons = orig_skeletons


@unittest.skipUnless(Image is not None, "PIL 필요")
class AiTemplateSafetyLoopTests(unittest.TestCase):
    """AI 셀 템플릿이 게이트 fail 시 스켈레톤 floor로 떨어지는지 (Chrome 없이 가짜 렌더)."""

    GOOD = ("<!-- textzone: 0.1,0.45,0.9,0.7 --><div class='ai-root'>"
            "<div style='font-size:{{name_size}}'>{{name}}</div></div>")

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._orig = (generate.render_pdf_and_png,
                      generate.get_candidate_skeletons,
                      generate._build_print_html,
                      generate.load_calibration,
                      generate.load_skeleton_template)
        generate.get_candidate_skeletons = lambda brand: ["r1"]
        generate.load_calibration = lambda: None
        generate.load_skeleton_template = lambda sk: "<html><head></head><body><!-- CELLS_HERE --></body></html>"

    def tearDown(self):
        (generate.render_pdf_and_png,
         generate.get_candidate_skeletons,
         generate._build_print_html,
         generate.load_calibration,
         generate.load_skeleton_template) = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _install_render(self, kinds):
        seq = list(kinds)
        calls = {"i": 0}

        def fake(html_path, out_dir, **k):
            kind = seq[calls["i"]] if calls["i"] < len(seq) else seq[-1]
            calls["i"] += 1
            png = pathlib.Path(out_dir) / f"p-{calls['i']}.png"
            if kind == "black":
                Image.new("RGB", (128, 128), (10, 10, 10)).save(png)   # 고잉크 → fail
            else:
                Image.new("RGB", (128, 128), (250, 250, 250)).save(png)  # clean
            return (png.with_suffix(".pdf"), png)

        generate.render_pdf_and_png = fake
        return calls

    def test_ai_template_first_pass_clean(self):
        self._install_render(["clean"])
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
                 "design": {"cell_template": self.GOOD}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Meetup", self.tmp)
        self.assertEqual(report["retried"], 0)
        self.assertFalse(report["fallback_used"])

    def test_ai_template_persistent_fail_falls_back(self):
        # 항상 고잉크 → 재시도(=cell_template 제거)로도 가짜 렌더가 계속 black → preset fallback
        self._install_render(["black"])
        brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
                 "design": {"cell_template": self.GOOD}}
        png, report = generate.render_with_safety_loop(
            [{"name": "김지원"}], brand, "Meetup", self.tmp, max_retries=2)
        self.assertTrue(report["fallback_used"])
        self.assertEqual(report["retried"], 2)

    def test_textzone_is_ai_on_first_pass_then_none_after_downgrade(self):
        # 메커니즘 검증(결과뿐 아니라): 1차는 AI textzone, 강도하향(cell_template 제거) 후
        # retry는 textzone=None(스켈레톤 기본 밴드)을 써야 한다. verify_print_safety를 감싸
        # textzone kwarg를 캡처한다. downgrade가 cell_template strip을 못 하면 이 테스트가 잡는다.
        captured = []
        orig_verify = generate.verify_print_safety

        def capture(*a, **kw):
            captured.append(kw.get("textzone"))
            return orig_verify(*a, **kw)

        generate.verify_print_safety = capture
        try:
            self._install_render(["black", "clean"])  # 1차 고잉크 fail → retry clean 통과
            brand = {"colors": {"primary_dark": "#0a0a0b", "primary_light": "#fafafa"},
                     "design": {"cell_template": self.GOOD}}
            generate.render_with_safety_loop(
                [{"name": "김지원"}], brand, "Meetup", self.tmp, max_retries=2)
        finally:
            generate.verify_print_safety = orig_verify
        self.assertIsNotNone(captured[0])  # 1차: AI 선언 textzone
        self.assertIsNone(captured[1])     # 강도하향 후: cell_template 제거 → 기본 밴드(None)


# ─────────────────────── 실렌더 통합 (Chrome 있을 때만) ───────────────────────

@unittest.skipUnless(CHROME_AVAILABLE and Image is not None and YAML_AVAILABLE,
                     "Chrome+sips+PIL+PyYAML 필요")
class RealRenderSafetyLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_diagonal_passes_first_try(self):
        """기본 diagonal(저잉크)은 실렌더에서 1차 통과 — 회귀 0."""
        brand = generate.load_brand(generate._default_demo_brand_slug())
        attendees = [{"name": "김지원", "company": "LiveClass", "role": "HR Lead"}]
        png, report = generate.render_with_safety_loop(attendees, brand, "Demo", self.tmp)
        self.assertTrue(png.exists())
        self.assertEqual(report["retried"], 0)
        self.assertFalse(report["fallback_used"])


if __name__ == "__main__":
    unittest.main()
