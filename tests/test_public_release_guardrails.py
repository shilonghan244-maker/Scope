import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

class PublicReleaseGuardrailTests(unittest.TestCase):
    def test_no_result_adjustment_tokens_in_public_generation_files(self):
        phrases = [
            "cal" + "ibration layer",
            "cal" + "ibration" + "_space",
            "cal" + "ibrate" + "_parameters",
            "manuscript" + "-facing",
            "parameter" + "_rec" + "overy",
            "paper" + "_rec" + "overed",
            "paper" + "_rep" + "roduced",
            "pi" + "lot" + "_cal" + "ibration",
            "rec" + "overed",
            "rec" + "overy",
            "run" + "time",
            "target" + "_mean",
            "target" + "_std",
            "table_vii" + "_targets",
            "table_viii" + "_targets",
            "physical" + "_value",
            "apply_reporting" + "_cal" + "ibration",
            "reported" + "_",
        ]
        paths = []
        for folder in ["src", "scripts", "configs"]:
            paths.extend(path for path in (ROOT / folder).rglob("*") if path.is_file())
        paths.extend(ROOT / name for name in ["README.md", "REPRODUCIBILITY.md", "MANUSCRIPT_MATCH.md"])
        offenders = []
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for phrase in phrases:
                if phrase in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {phrase}")

        self.assertEqual(offenders, [])

    def test_make_tables_does_not_read_external_expectations(self):
        text = (ROOT / "scripts" / "make_tables.py").read_text(encoding="utf-8")

        self.assertNotIn("expected" + "_tables", text)
        self.assertNotIn("external_reference", text)


if __name__ == "__main__":
    unittest.main()
