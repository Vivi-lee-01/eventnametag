import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"

PRODUCTION_TEMPLATES = [
    "r1-topbar.html",
    "r2-sidestrip.html",
    "r3-fullbleed.html",
    "r4-minimal.html",
]
ALL_COORDINATE_TEMPLATES = PRODUCTION_TEMPLATES + ["_calibrate.html"]

EXPECTED_SHEET = {
    "page_size": "A4",
    "page_margin_mm": "0",
    "sheet_width_mm": "210",
    "sheet_height_mm": "297",
    "sheet_padding_mm": ("13", "5", "14"),
    "cell_width_mm": "99",
    "cell_height_mm": "67.5",
    "column_gap_mm": "2",
    "row_gap_mm": "0",
}


def read_template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def extract_rule_block(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n\s*\}}", css, re.S)
    if not match:
        raise AssertionError(f"{selector} rule not found")
    return match.group("body")


def extract_mm_property(rule: str, prop: str) -> str:
    match = re.search(rf"\b{re.escape(prop)}\s*:\s*([^;]+);", rule)
    if not match:
        raise AssertionError(f"{prop} property not found in {rule}")
    return match.group(1).strip()


def extract_template_coordinates(name: str) -> dict:
    html = read_template(name)
    page_match = re.search(r"@page\s*\{(?P<body>.*?)\}", html, re.S)
    if not page_match:
        raise AssertionError(f"@page rule not found in {name}")
    page = page_match.group("body")
    sheet = extract_rule_block(html, ".a4-sheet")
    cell = extract_rule_block(html, ".cell")
    padding = extract_mm_property(sheet, "padding")
    padding_values = tuple(re.findall(r"([0-9.]+)mm", padding))
    return {
        "page_size": re.search(r"\bsize\s*:\s*([^;]+);", page).group(1).strip(),
        "page_margin_mm": re.search(r"\bmargin\s*:\s*([0-9.]+);", page).group(1),
        "sheet_width_mm": re.search(r"\bwidth\s*:\s*([0-9.]+)mm;", sheet).group(1),
        "sheet_height_mm": re.search(r"\bheight\s*:\s*([0-9.]+)mm;", sheet).group(1),
        "sheet_padding_mm": padding_values,
        "cell_width_mm": re.search(r"\bwidth\s*:\s*([0-9.]+)mm;", cell).group(1),
        "cell_height_mm": re.search(r"\bheight\s*:\s*([0-9.]+)mm;", cell).group(1),
        "column_gap_mm": re.search(r"\bcolumn-gap\s*:\s*([0-9.]+)mm;", sheet).group(1),
        "row_gap_mm": re.search(r"\brow-gap\s*:\s*([0-9.]+);", sheet).group(1),
    }


class PrintCoordinateTests(unittest.TestCase):
    def test_production_templates_share_a4_8up_coordinate_source_of_truth(self):
        coordinates = {name: extract_template_coordinates(name) for name in PRODUCTION_TEMPLATES}

        for name, values in coordinates.items():
            self.assertEqual(values, EXPECTED_SHEET, name)
        self.assertEqual(len({tuple(values.items()) for values in coordinates.values()}), 1)

    def test_calibrate_template_uses_same_a4_8up_sheet_coordinates(self):
        self.assertEqual(extract_template_coordinates("_calibrate.html"), EXPECTED_SHEET)

    def test_template_comments_name_a4_8up_source_of_truth(self):
        for name in ALL_COORDINATE_TEMPLATES:
            html = read_template(name)
            self.assertIn("99", html, name)
            self.assertIn("13mm", html, name)
            self.assertIn("5mm", html, name)
            self.assertIn("14mm", html, name)


if __name__ == "__main__":
    unittest.main()
