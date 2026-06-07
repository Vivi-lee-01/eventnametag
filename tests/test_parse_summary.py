"""P0-B 명단 파싱·무결성 보고 회귀 테스트.

검증 대상:
- _looks_mojibake(): 정상 악센트 라틴/한글/영문은 통과, cp1252 깨짐만 탐지
- parse_attendees(): 이름만 모드는 절대 drop 안 함(인코딩 의심도 유지+경고),
  CSV 모드는 빈 이름 row를 사유와 함께 보고
- format_parse_summary(): 제외 0이면 깔끔, 제외/인코딩경고 분리 보고
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import generate  # noqa: E402


def _mojibake(s: str) -> str:
    """UTF-8 바이트를 latin-1로 잘못 디코드한 깨짐 문자열 재현.

    latin-1은 256바이트를 모두 매핑해 예외가 없다(cp1252는 일부 바이트 미정의).
    한글 1글자(UTF-8 3바이트)는 U+0080–00FF 문자 3개 연속으로 풀려, 실제
    mojibake와 동일하게 'Latin-1 문자 연속' 패턴을 만든다.
    """
    return s.encode("utf-8").decode("latin-1")


class MojibakeHeuristicTests(unittest.TestCase):
    def test_legit_accented_latin_not_flagged(self):
        # 정상 외국 이름 — 악센트 문자가 단독이라 인코딩 의심 아님
        for name in ["Zoë", "Renée", "Müller", "José", "Søren", "Łukasz"]:
            self.assertFalse(generate._looks_mojibake(name), f"오탐: {name}")

    def test_korean_and_english_not_flagged(self):
        for name in ["김지원", "박서연", "이도윤", "John Smith", "Anne-Marie"]:
            self.assertFalse(generate._looks_mojibake(name), f"오탐: {name}")

    def test_real_mojibake_flagged(self):
        # cp1252로 잘못 읽힌 한글은 Latin-1 문자가 연속으로 나타남
        for src in ["안녕", "김지원", "박서연"]:
            broken = _mojibake(src)
            self.assertTrue(generate._looks_mojibake(broken), f"미탐: {broken!r}")

    def test_replacement_char_and_bom_flagged(self):
        self.assertTrue(generate._looks_mojibake("�이름"))   # U+FFFD 대체문자
        self.assertTrue(generate._looks_mojibake("﻿이름"))   # BOM


class NamesOnlyNeverDropsTests(unittest.TestCase):
    def test_accented_names_all_kept(self):
        kept, dropped = generate.parse_attendees("Zoë\nRenée\n김지원")
        self.assertEqual(len(kept), 3)
        self.assertEqual(dropped["encoding_warn"], 0)

    def test_mojibake_name_kept_with_warning(self):
        broken = _mojibake("김지원")
        kept, dropped = generate.parse_attendees(f"박서연\n{broken}")
        # 의심돼도 절대 drop하지 않는다 — 둘 다 유지
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped["encoding_warn"], 1)
        # encoding_warn은 '제외'가 아니다
        self.assertEqual(dropped["encoding"], 0)


class CsvDropClassificationTests(unittest.TestCase):
    def test_empty_name_row_dropped_and_reported(self):
        # 헤더 없는 TSV: 가운데 행은 이름이 비어 제외돼야 함
        text = "김지원\t회사A\tPM\n\t회사B\tQA\n박서연\t회사C\tPM"
        kept, dropped = generate.parse_attendees(text)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped["empty_name"], 1)

    def test_clean_list_no_drops(self):
        text = "김지원\t회사A\tPM\n박서연\t회사B\tQA"
        kept, dropped = generate.parse_attendees(text)
        self.assertEqual(len(kept), 2)
        self.assertEqual(sum(v for k, v in dropped.items() if k != "encoding_warn"), 0)


class SummaryFormatTests(unittest.TestCase):
    def _d(self, **kw):
        base = {"empty_name": 0, "few_columns": 0, "encoding": 0,
                "header_skip": 0, "encoding_warn": 0}
        base.update(kw)
        return base

    def test_no_drops_is_clean(self):
        self.assertEqual(
            generate.format_parse_summary(3, self._d()),
            "✓ 명단 3명 파싱",
        )

    def test_drops_reported(self):
        s = generate.format_parse_summary(2, self._d(empty_name=1, header_skip=1))
        self.assertIn("⚠ 2행 제외", s)
        self.assertIn("빈 이름 1", s)
        self.assertIn("헤더 추정 1", s)

    def test_encoding_warn_not_counted_as_drop(self):
        s = generate.format_parse_summary(2, self._d(encoding_warn=1))
        self.assertNotIn("제외", s)
        self.assertIn("인코딩 의심 1명", s)
        self.assertIn("유지", s)


if __name__ == "__main__":
    unittest.main()
