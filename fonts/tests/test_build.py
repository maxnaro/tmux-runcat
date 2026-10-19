"""Check reproducibility and preserve the user's existing font metrics/features."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

FONT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FONT_DIR / "vendor/fonttools-4.67.0-py3-none-any.whl"))
from fontTools.ttLib import TTFont


class FontBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="runcat-build-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.environment = dict(os.environ, XDG_DATA_HOME=cls.temporary.name)
        cls.data = Path(cls.temporary.name) / "tmux-runcat"
        cls.build()

    @classmethod
    def build(cls):
        subprocess.run(["bash", str(FONT_DIR / "setup.sh"), "--build-only"],
                       env=cls.environment, check=True, stdout=subprocess.DEVNULL)

    def test_repeated_builds_are_identical(self):
        def hashes():
            return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (self.data / "generated").iterdir()}

        before = hashes()
        self.build()
        self.assertEqual(before, hashes())

    def test_original_characters_and_features_are_preserved(self):
        for style in ("Regular", "Bold", "Italic", "BoldItalic"):
            with self.subTest(style=style):
                original = TTFont(self.data / f"source/JetBrainsMonoNerdFont-{style}.ttf")
                patched = TTFont(self.data / f"generated/JetBrainsMonoRunCat-{style}.ttf")
                for code, name in original.getBestCmap().items():
                    self.assertEqual(patched.getBestCmap()[code], name)
                for name, metrics in original["hmtx"].metrics.items():
                    self.assertEqual(patched["hmtx"][name], metrics)
                for table in ("GSUB", "GPOS", "GDEF", "OS/2"):
                    self.assertEqual(original.getTableData(table), patched.getTableData(table))

    def test_larger_cat_halves_fit_two_regular_cells(self):
        font = TTFont(self.data / "generated/JetBrainsMonoRunCat-Regular.ttf")
        advance = font["hmtx"]["space"][0]
        for frame in range(5):
            halves = []
            for code in (0xEFF0 + frame, 0xEFF5 + frame):
                name = font.getBestCmap()[code]
                glyph = font["glyf"][name]
                self.assertEqual(font["hmtx"][name][0], advance)
                self.assertGreaterEqual(glyph.xMin, 0)
                self.assertLessEqual(glyph.xMax, advance)
                halves.append(glyph)
            self.assertGreater(max(g.yMax for g in halves) - min(g.yMin for g in halves), 450)

    def test_sleep_pose_is_bundled_and_fits_two_cells(self):
        font = TTFont(self.data / "generated/JetBrainsMonoRunCat-Regular.ttf")
        self.assertEqual(font["name"].getDebugName(1), "JetBrainsMono RunCat Active")
        for code in (0xEFFA, 0xEFFB):
            name = font.getBestCmap()[code]
            glyph = font["glyf"][name]
            self.assertEqual(font["hmtx"][name][0], 600)
            self.assertGreaterEqual(glyph.xMin, 0)
            self.assertLessEqual(glyph.xMax, 600)
            self.assertGreater(glyph.numberOfContours, 0)
            coordinates, ends, _ = glyph.getCoordinates(font["glyf"])
            areas = []
            start = 0
            for end in ends:
                points = coordinates[start:end+1]
                areas.append(sum(points[i-1][0]*points[i][1] - points[i][0]*points[i-1][1]
                                 for i in range(len(points))))
                start = end+1
            self.assertTrue(any(area < 0 for area in areas))
            self.assertTrue(any(area > 0 for area in areas))


if __name__ == "__main__":
    unittest.main()
