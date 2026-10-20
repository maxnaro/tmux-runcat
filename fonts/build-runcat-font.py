#!/usr/bin/env python3
"""Add the cat poses to copies of JetBrainsMono NF. Requires fonttools."""

import argparse
import json
from pathlib import Path
import shutil

from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import SVGPath
from fontTools.ttLib import TTFont


class OutlinePen(BasePen):
    """Flatten curves before clipping the silhouette into two terminal cells."""

    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.contours = []

    def _moveTo(self, point):
        self.points = [point]

    def _lineTo(self, point):
        self.points.append(point)

    def _qCurveToOne(self, control, end):
        start = self._getCurrentPoint()
        for step in range(1, 33):
            t = step / 32
            self.points.append(tuple((1-t)**2 * start[i] + 2*(1-t)*t * control[i] + t*t * end[i] for i in (0, 1)))

    def _curveToOne(self, first, second, end):
        start = self._getCurrentPoint()
        for step in range(1, 33):
            t = step / 32
            self.points.append(tuple((1-t)**3 * start[i] + 3*(1-t)**2*t * first[i] + 3*(1-t)*t*t * second[i] + t**3 * end[i] for i in (0, 1)))

    def _closePath(self):
        self.contours.append(self.points)

    _endPath = _closePath


def clip_polygon(points, boundary, keep_right):
    output = []
    if not points:
        return output
    previous = points[-1]
    for current in points:
        inside = (current[0] >= boundary) if keep_right else (current[0] <= boundary)
        was_inside = (previous[0] >= boundary) if keep_right else (previous[0] <= boundary)
        if inside != was_inside:
            t = (boundary - previous[0]) / (current[0] - previous[0])
            output.append((boundary, previous[1] + t * (current[1] - previous[1])))
        if inside:
            output.append(current)
        previous = current
    return output


def contour_area(points):
    return sum(points[i-1][0]*points[i][1] - points[i][0]*points[i-1][1]
               for i in range(len(points)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="extracted JetBrainsMono Nerd Font release")
    parser.add_argument("output", type=Path, help="directory for Windows installer font files")
    parser.add_argument("--cat-only", action="store_true", help="omit clean NF family files")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Include a clean installation of the complete official font family.
    if not args.cat_only:
        for path in args.source.glob("*.ttf"):
            shutil.copyfile(path, args.output / ("NF-3.5.1-" + path.name))

    cat = TTFont(Path(__file__).with_name("runcat-tmux.ttf"))
    cat_glyphs = cat.getGlyphSet()
    outlines = []
    for code in range(0xEFF0, 0xEFF5):
        pen = OutlinePen(cat_glyphs)
        cat_glyphs[cat.getBestCmap()[code]].draw(pen)
        outlines.append(pen.contours)
    points = [point for contours in outlines for contour in contours for point in contour]
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    pen = OutlinePen(None)
    SVGPath(str(Path(__file__).with_name("sleeping-cat.svg"))).draw(pen)
    # The SVG uses even-odd filling; TrueType uses winding direction. Its
    # interior details therefore need the opposite winding to the silhouette.
    orientation = contour_area(pen.contours[0])
    sleep_outline = []
    for index, contour in enumerate(pen.contours):
        if index and contour_area(contour) * orientation > 0:
            contour = list(reversed(contour))
        sleep_outline.append([(x, 1024-y) for x, y in contour])
    for style in ("Regular", "Bold", "Italic", "BoldItalic"):
        font = TTFont(args.source / f"JetBrainsMonoNerdFont-{style}.ttf", recalcTimestamp=False)
        original_cmap = font.getBestCmap().copy()
        advance = font["hmtx"]["space"][0]
        order = list(font.getGlyphOrder())
        scale = min((2 * advance - 80) / (xmax - xmin), font["OS/2"].sCapHeight / (ymax - ymin))
        sleep_floor = min(y for contour in sleep_outline for _, y in contour)
        for code in range(0xEFF0, 0xF000):
            assert code not in original_cmap, "Cat codepoint collides with an existing icon"
            name = f"runcat{code - 0xEFF0}"
            if code < 0xEFFA:
                half, frame = divmod(code - 0xEFF0, 5)
                contours = outlines[frame]
            else:
                breath, half = divmod(code - 0xEFFA, 2)
                # Anchor the lower silhouette while the body rises by 4/8%.
                contours = [[(x, sleep_floor + (y-sleep_floor)*(1+0.04*breath))
                             for x, y in contour] for contour in sleep_outline]
            pen = TTGlyphPen(None)
            for contour in contours:
                transformed = [(40 + (x-xmin)*scale, 20 + (y-ymin)*scale) for x, y in contour]
                clipped = clip_polygon(transformed, half * advance, True)
                clipped = clip_polygon(clipped, (half+1) * advance, False)
                if len(clipped) < 3:
                    continue
                local = [(x-half*advance, y) for x, y in clipped]
                pen.moveTo(local[0])
                for point in local[1:]:
                    pen.lineTo(point)
                pen.closePath()
            glyph = pen.glyph()
            font["glyf"][name] = glyph
            glyph.recalcBounds(font["glyf"])
            font["hmtx"][name] = (advance, glyph.xMin)
            order.append(name)
            for table in font["cmap"].tables:
                if table.isUnicode() and table.format != 14:
                    table.cmap[code] = name
        font.setGlyphOrder(order)
        family = "JetBrainsMono RunCat v2"
        face = {"BoldItalic": "Bold Italic"}.get(style, style)
        names = {1: family, 2: face, 3: f"{family}-{style}-3.5.1",
                 4: f"{family} {face}", 6: f"JetBrainsMonoRunCatV2-{style}",
                 16: family, 17: face}
        for record in font["name"].names:
            if record.nameID in names:
                record.string = names[record.nameID].encode(record.getEncoding())
        for name_id, value in names.items():
            font["name"].setName(value, name_id, 3, 1, 0x409)
        destination = args.output / f"JetBrainsMonoRunCat-{style}.ttf"
        font.save(destination)
        # Existing characters, glyphs, metrics and font features are preserved.
        saved = TTFont(destination)
        assert all(saved.getBestCmap()[code] == glyph for code, glyph in original_cmap.items())
        assert saved["hmtx"]["space"][0] == advance
        print(destination)

    manifest = {}
    for path in args.output.glob("*.ttf"):
        font = TTFont(path)
        family = font["name"].getDebugName(1)
        face = font["name"].getDebugName(2)
        manifest[path.name] = f"{family} {face} (TrueType)"
    (args.output / "font-names.json").write_text(json.dumps(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
