import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scope_repro.statistics import holm_adjust, mean_std_ci, paired_effect_size
from scope_repro.utils.rng import generate_seed_rows, load_seed_rows, save_seed_rows


class SeedProtocolTests(unittest.TestCase):
    def test_generate_seed_rows_uses_separate_reproducible_streams(self):
        rows = generate_seed_rows(trials=3, base_seed=2026062300)

        self.assertEqual(rows[0]["trial_id"], 0)
        self.assertEqual(rows[0]["master_seed"], 2026062300)
        self.assertEqual(rows[0]["deployment_seed"], 2026062301)
        self.assertEqual(rows[0]["energy_seed"], 2026062302)
        self.assertEqual(rows[1]["master_seed"], 2026062400)
        self.assertNotEqual(rows[0]["deployment_seed"], rows[0]["energy_seed"])

    def test_seed_rows_round_trip_to_csv(self):
        rows = generate_seed_rows(trials=2, base_seed=2026062300)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.csv"
            save_seed_rows(rows, path)
            loaded = load_seed_rows(path)

        self.assertEqual(loaded, rows)


class StatisticsTests(unittest.TestCase):
    def test_mean_std_ci_uses_trial_level_sample_standard_deviation(self):
        summary = mean_std_ci([1.0, 2.0, 3.0])

        self.assertAlmostEqual(summary["mean"], 2.0)
        self.assertAlmostEqual(summary["std"], 1.0)
        self.assertAlmostEqual(summary["ci_low"], 2.0 - 4.302652729911275 / math.sqrt(3))
        self.assertAlmostEqual(summary["ci_high"], 2.0 + 4.302652729911275 / math.sqrt(3))

    def test_paired_effect_size_uses_signed_paired_differences(self):
        effect = paired_effect_size([4.0, 5.0, 6.0], [2.0, 3.0, 5.0])

        self.assertAlmostEqual(effect, (5.0 / 3.0) / math.sqrt(1.0 / 3.0))

    def test_holm_adjust_is_monotone_after_sorting(self):
        adjusted = holm_adjust([0.001, 0.04, 0.02])

        self.assertEqual(len(adjusted), 3)
        self.assertAlmostEqual(adjusted[0], 0.003)
        self.assertAlmostEqual(adjusted[2], 0.04)
        self.assertAlmostEqual(adjusted[1], 0.04)


if __name__ == "__main__":
    unittest.main()

