"""P0-C 회귀 게이트: v0.2 calibration 동작 불변 검증.

v0.2 calibration 모델(단일 calibration.yaml + transform: translate)이 그대로
동작하는지 강제한다. Track 2(비등방·프린터 프로파일)는 본 P0 범위가 아니므로
여기서는 v1 평행이동 모델만 검증한다.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate", ROOT / "scripts" / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


class _FakeYaml:
    """PyYAML 미설치 환경에서도 load_calibration 로직을 검증하기 위한 최소 stub.

    generate.load_calibration은 require_yaml()로 PyYAML을 요구하므로, 본 테스트는
    PyYAML 설치 여부와 무관하게 '로드 분기 로직'만 검증하기 위해 stub을 주입한다.
    PyYAML이 실제 설치돼 있으면 stub 없이도 동일 결과가 나온다.
    """
    YAMLError = ValueError

    @staticmethod
    def safe_load(text):
        data = {}
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            data[k.strip()] = float(v.strip())
        return data


class CalibrationLoadTests(unittest.TestCase):
    def setUp(self):
        # 실 PyYAML이 없으면 stub 주입 (있으면 실제 모듈 그대로 사용)
        self._yaml_patch = None
        if generate.yaml is None:
            self._yaml_patch = mock.patch.object(generate, "yaml", _FakeYaml)
            self._yaml_patch.start()

    def tearDown(self):
        if self._yaml_patch is not None:
            self._yaml_patch.stop()

    def _patched_file(self, body: str):
        d = tempfile.TemporaryDirectory()
        cal = Path(d.name) / "calibration.yaml"
        cal.write_text(body, encoding="utf-8")
        fake = mock.MagicMock()
        fake.exists.return_value = True
        fake.read_text.side_effect = lambda encoding="utf-8": cal.read_text(encoding=encoding)
        return d, mock.patch.object(generate, "CALIBRATION_FILE", fake)

    def test_load_calibration_reads_v1_xy(self):
        # v1 yaml(x/y)을 로드하면 {"x": float, "y": float} 반환
        d, patch = self._patched_file("x: 1.0\ny: 2.0\n")
        with d, patch:
            result = generate.load_calibration()
        self.assertEqual(result, {"x": 1.0, "y": 2.0})

    def test_load_calibration_none_when_zero(self):
        # 0,0 보정은 적용할 게 없으므로 None (보정 단계 스킵)
        d, patch = self._patched_file("x: 0\ny: 0\n")
        with d, patch:
            result = generate.load_calibration()
        self.assertIsNone(result)

    def test_load_calibration_none_when_missing(self):
        # 파일이 없으면 None
        fake = mock.MagicMock()
        fake.exists.return_value = False
        with mock.patch.object(generate, "CALIBRATION_FILE", fake):
            result = generate.load_calibration()
        self.assertIsNone(result)


class CalibrationTransformTests(unittest.TestCase):
    def test_transform_injects_translate(self):
        # apply_calibration_transform은 .a4-sheet에 transform: translate(x,y)를 주입
        html = "<html><head></head><body></body></html>"
        out = generate.apply_calibration_transform(html, {"x": 1.0, "y": 2.0})
        self.assertIn("transform: translate(1.0mm, 2.0mm)", out)
        self.assertIn(".a4-sheet", out)
        # translate만 사용 — scale/skew 같은 비등방 변형은 P0 범위 아님 (§2-3 lock)
        self.assertNotIn("scale(", out)
        self.assertNotIn("skew(", out)

    def test_transform_injected_before_head_close(self):
        # 마지막 정의가 우선되도록 </head> 직전에 inject
        html = "<html><head><style>.a4-sheet{transform:none;}</style></head><body></body></html>"
        out = generate.apply_calibration_transform(html, {"x": -1.0, "y": -2.0})
        self.assertIn("transform: translate(-1.0mm, -2.0mm)", out)
        self.assertLess(out.index("translate(-1.0mm, -2.0mm)"), out.index("</head>"))

    def test_transform_negative_values(self):
        # 위/왼쪽 보정 = 음수값도 그대로 전달
        out = generate.apply_calibration_transform(
            "<head></head>", {"x": -1.5, "y": -2.5}
        )
        self.assertIn("transform: translate(-1.5mm, -2.5mm)", out)


if __name__ == "__main__":
    unittest.main()
