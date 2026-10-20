"""Check reproducibility and preserve the user's existing font metrics/features."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

FONT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FONT_DIR / "vendor/fonttools-4.67.0-py3-none-any.whl"))
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable


class FontBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="runcat-build-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.environment = {key: value for key, value in os.environ.items()
                           if not key.startswith("RUNCAT_")}
        cls.environment["XDG_DATA_HOME"] = cls.temporary.name
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
                patched = TTFont(self.data / f"generated/RunCat-{style}.ttf")
                for code, name in original.getBestCmap().items():
                    self.assertEqual(patched.getBestCmap()[code], name)
                for name, metrics in original["hmtx"].metrics.items():
                    self.assertEqual(patched["hmtx"][name], metrics)
                for table in ("GSUB", "GPOS", "GDEF", "OS/2"):
                    self.assertEqual(original.getTableData(table), patched.getTableData(table))

    def test_larger_cat_halves_fit_two_regular_cells(self):
        font = TTFont(self.data / "generated/RunCat-Regular.ttf")
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
        font = TTFont(self.data / "generated/RunCat-Regular.ttf")
        self.assertEqual(font["name"].getDebugName(1), "JetBrainsMono RunCat v3")
        for code in range(0xEFFA, 0xF000):
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

    def test_breathing_lifts_the_body_without_moving_its_base(self):
        font = TTFont(self.data / "generated/RunCat-Regular.ttf")
        for half in (0, 1):
            glyphs = [font["glyf"][font.getBestCmap()[0xEFFA + 2*frame + half]] for frame in range(3)]
            self.assertLess(glyphs[0].yMax, glyphs[1].yMax)
            self.assertLess(glyphs[1].yMax, glyphs[2].yMax)
            self.assertLess(max(g.yMin for g in glyphs) - min(g.yMin for g in glyphs), 15)

    def test_all_sizes_have_eight_poses_with_safe_cell_and_row_bounds(self):
        for style in ("Regular", "Bold", "Italic", "BoldItalic"):
            font = TTFont(self.data / f"generated/RunCat-{style}.ttf")
            heights = []
            for cells in (1, 2, 3):
                for frame in range(8):
                    if cells == 1:
                        codes = [0xF600+frame]
                    elif cells == 3:
                        codes = [0xF620+3*frame+half for half in range(3)]
                    elif frame < 5:
                        codes = [0xEFF0+frame, 0xEFF5+frame]
                    else:
                        codes = [0xEFFA+2*(frame-5), 0xEFFB+2*(frame-5)]
                    glyphs = []
                    for code in codes:
                        name = font.getBestCmap()[code]
                        glyph = font["glyf"][name]
                        self.assertEqual(font["hmtx"][name][0], 600)
                        self.assertGreaterEqual(glyph.xMin, 0)
                        self.assertLessEqual(glyph.xMax, 600)
                        self.assertGreaterEqual(glyph.yMin, 0)
                        self.assertLessEqual(glyph.yMax, font["hhea"].ascent)
                        glyphs.append(glyph)
                    if frame == 0:
                        heights.append(max(g.yMax for g in glyphs)-min(g.yMin for g in glyphs))
            self.assertLess(heights[0], heights[1])
            self.assertLess(heights[1], heights[2])


class CustomFontBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="runcat-custom-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.sources = cls.root / "base fonts with spaces"
        cls.sources.mkdir()
        cls.environment = {key: value for key, value in os.environ.items()
                           if not key.startswith("RUNCAT_")}
        cls.environment.update(XDG_DATA_HOME=str(cls.root / "data"),
                               PYTHONPATH=str(FONT_DIR / "vendor/fonttools-4.67.0-py3-none-any.whl"),
                               PYTHONDONTWRITEBYTECODE="1")
        cls.styles = ("Regular", "Bold", "Italic", "BoldItalic")
        for style in cls.styles:
            # A real, tiny TrueType family with different units/metrics from
            # JetBrainsMono and no sCapHeight (as in older third-party fonts).
            builder = FontBuilder(2048, isTTF=True)
            glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
            cmap = {32: "space"}
            for code in range(33, 127):
                name = f"ascii{code}"
                pen = TTGlyphPen(None)
                pen.moveTo((80, 0))
                pen.lineTo((80, 1400))
                pen.lineTo((1000, 1400))
                pen.lineTo((1000, 0))
                pen.closePath()
                glyphs[name] = pen.glyph()
                cmap[code] = name
            builder.setupGlyphOrder(list(glyphs))
            builder.setupCharacterMap(cmap)
            builder.setupGlyf(glyphs)
            builder.setupHorizontalMetrics({name: (1234, 0) for name in glyphs})
            builder.setupHorizontalHeader(ascent=1900, descent=-500)
            builder.setupNameTable({"familyName": "Test Mono", "styleName": style,
                                    "uniqueFontIdentifier": f"TestMono-{style}",
                                    "fullName": f"Test Mono {style}", "psName": f"TestMono-{style}"})
            builder.setupOS2(version=1, sTypoAscender=1900, sTypoDescender=-500,
                             usWinAscent=1900, usWinDescent=500)
            builder.setupPost(isFixedPitch=1)
            builder.save(cls.sources / f"{style}.ttf")
        cls.output = cls.root / "four faces"
        cls.build(cls.output, *cls.face_args(), "--family", "My Mono RunCat")

    @classmethod
    def face_args(cls):
        return ["--base-font", str(cls.sources / "Regular.ttf"),
                "--bold-font", str(cls.sources / "Bold.ttf"),
                "--italic-font", str(cls.sources / "Italic.ttf"),
                "--bold-italic-font", str(cls.sources / "BoldItalic.ttf")]

    @classmethod
    def build(cls, output, *args, check=True):
        return subprocess.run([sys.executable, str(FONT_DIR / "build-runcat-font.py"),
                               str(cls.sources), str(output), *map(str, args)],
                              env=cls.environment, check=check, capture_output=True, text=True)

    def test_custom_faces_preserve_original_outlines_and_metrics(self):
        for style in self.styles:
            with self.subTest(style=style):
                original = TTFont(self.sources / f"{style}.ttf")
                patched = TTFont(self.output / f"RunCat-{style}.ttf")
                self.assertFalse(hasattr(original["OS/2"], "sCapHeight"))
                self.assertEqual(patched["name"].getDebugName(1), "My Mono RunCat")
                for code, name in original.getBestCmap().items():
                    self.assertEqual(patched.getBestCmap()[code], name)
                    self.assertEqual(original["hmtx"][name], patched["hmtx"][name])
                    self.assertEqual(original["glyf"][name].compile(original["glyf"]),
                                     patched["glyf"][name].compile(patched["glyf"]))
                # The character range grows for this ASCII-only fixture;
                # the original metrics and style properties must stay intact.
                def os2_properties(font):
                    values = vars(font["OS/2"]).copy()
                    values.pop("usLastCharIndex")
                    values["panose"] = vars(values["panose"])
                    return values

                self.assertEqual(os2_properties(original), os2_properties(patched))
                self.assertEqual(patched["OS/2"].usLastCharIndex, 0xF637)
                self.assertEqual(original["hhea"].ascent, patched["hhea"].ascent)
                self.assertEqual(original["hhea"].descent, patched["hhea"].descent)
                for code in [*range(0xEFF0, 0xF000), *range(0xF600, 0xF608), *range(0xF620, 0xF638)]:
                    name = patched.getBestCmap()[code]
                    glyph = patched["glyf"][name]
                    self.assertEqual(patched["hmtx"][name][0], 1234)
                    self.assertGreaterEqual(glyph.xMin, 0)
                    self.assertLessEqual(glyph.xMax, 1234)
                    self.assertGreaterEqual(glyph.yMin, 0)
                    self.assertLessEqual(glyph.yMax, 1900)

    def test_custom_build_is_reproducible(self):
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.build(self.output, *self.face_args(), "--family", "My Mono RunCat")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output.iterdir()})

    def test_setup_accepts_environment_and_installs_only_current_manifest(self):
        environment = dict(self.environment, RUNCAT_BASE_FONT=str(self.sources / "Regular.ttf"),
                           RUNCAT_FONT_FAMILY="Environment Mono RunCat", WSL_DISTRO_NAME="",
                           XDG_CACHE_HOME=str(self.root / "cache"))
        generated = Path(environment["XDG_DATA_HOME"]) / "tmux-runcat/generated"
        generated.mkdir(parents=True, exist_ok=True)
        (generated / "stale.ttf").write_bytes(b"not part of this build")
        subprocess.run(["bash", str(FONT_DIR / "setup.sh")], env=environment, check=True,
                       stdout=subprocess.DEVNULL)
        manifest = json.loads((generated / "font-names.json").read_text())
        self.assertEqual(list(manifest), ["RunCat-Regular.ttf"])
        self.assertEqual((generated / "font-family.txt").read_text(), "Environment Mono RunCat\n")
        installed = Path(environment["XDG_DATA_HOME"]) / "fonts/tmux-runcat"
        self.assertEqual([path.name for path in installed.iterdir()], ["RunCat-Regular.ttf"])
        self.assertTrue((installed / "RunCat-Regular.ttf").is_symlink())

    def test_single_face_derives_family_and_supports_unicode_override(self):
        output = self.root / "single face"
        self.build(output, "--base-font", self.sources / "Regular.ttf")
        self.assertEqual((output / "font-family.txt").read_text(), "Test Mono RunCat v3\n")
        self.build(output, "--base-font", self.sources / "Regular.ttf", "--family", "猫 Mono RunCat")
        font = TTFont(output / "RunCat-Regular.ttf")
        self.assertEqual(font["name"].getDebugName(1), "猫 Mono RunCat")
        font["name"].getDebugName(6).encode("ascii")

    def test_unsupported_fonts_fail_before_producing_files(self):
        for problem, message in (("proportional", "must be monospaced"),
                                 ("collision", "U+F600 collides"),
                                 ("variable", "static TrueType"),
                                 ("outlines", "static TrueType")):
            with self.subTest(problem=problem):
                font = TTFont(self.sources / "Regular.ttf")
                if problem == "proportional":
                    font["hmtx"][font.getBestCmap()[ord("W")]] = (1000, 0)
                elif problem == "collision":
                    for table in font["cmap"].tables:
                        if table.isUnicode():
                            table.cmap[0xF600] = font.getBestCmap()[ord("H")]
                elif problem == "variable":
                    font["fvar"] = newTable("fvar")
                    font["fvar"].axes, font["fvar"].instances = [], []
                else:
                    del font["glyf"]
                    del font["loca"]
                path = self.root / f"{problem}.ttf"
                font.save(path)
                output = self.root / f"rejected-{problem}"
                result = self.build(output, "--base-font", path, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_faces_from_different_families_are_rejected(self):
        font = TTFont(self.sources / "Bold.ttf")
        for record in font["name"].names:
            if record.nameID == 1:
                record.string = "Other Mono".encode(record.getEncoding())
        path = self.root / "other-bold.ttf"
        font.save(path)
        result = self.build(self.root / "mixed", "--base-font", self.sources / "Regular.ttf",
                            "--bold-font", path, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same base font family", result.stderr)


if __name__ == "__main__":
    unittest.main()
