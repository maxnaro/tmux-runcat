"""Convert the bundled CC0 Pet Cats pixels to foreground-colored outlines."""

import math
from pathlib import Path
import zipfile

import png
import spinning_cat

BASE = 0xF700
XLARGE_BASE = 0xE400
SPIN_BASE = 0x100000
MIRROR_BASE = 0x101000
FAMILY_BASES = {"stocky": 0x102000, "lanky": 0x103000,
                "fluffy": 0x104000, "bobtail": 0x105000}
FAMILY_BOUNDS = (10, 40, 18, 34)
MANIFEST = Path(__file__).with_name("pet-cats") / "animations.tsv"


def animations():
    return [line.split("\t") for line in MANIFEST.read_text().splitlines()
            if line and not line.startswith("#")]


def rectangles(pixels, accept):
    """Join adjacent pixels into horizontal runs, preserving exact boundaries."""
    contours = []
    for y, row in enumerate(pixels):
        x = 0
        while x < len(row):
            if not accept(row[x]):
                x += 1
                continue
            left = x
            while x < len(row) and accept(row[x]):
                x += 1
            contours.append([(left, 50-y-1), (left, 50-y), (x, 50-y), (x, 50-y-1)])
    return contours


# Cat 1 tail masks in its native outline coordinates: (cutoff x, first y,
# last y), with inclusive pixel rows. Each entry follows one source frame.
# Keeping cuts above moving paws matters: the raised tail and rear legs
# occupy the same x columns, but different rows, during walking and running.
BOBTAIL_CUTS = {
    "walk": (
        ((20, 26, 31),), ((20, 27, 31),), ((20, 26, 31),),
        ((20, 27, 31),), ((20, 27, 31),), ((20, 27, 30),),
        ((20, 26, 31),), ((20, 27, 31),),
    ),
    "run": (
        ((16, 25, 29),), ((16, 26, 30),), ((18, 26, 29),),
        ((20, 27, 28),), ((22, 27, 28),), ((22, 26, 28),),
        ((20, 25, 29),), ((16, 23, 26),),
    ),
    "idle": (
        ((21, 19, 20), (20, 21, 21)),
        ((21, 19, 20), (20, 21, 22)),
        ((21, 19, 19), (20, 20, 23)),
        ((21, 19, 19), (20, 20, 22)),
        ((21, 19, 19), (20, 20, 21)),
        ((21, 19, 19), (20, 20, 21)),
        ((21, 19, 19), (20, 20, 22)),
        ((21, 19, 20), (20, 21, 23)),
        ((21, 20, 20), (20, 21, 22)),
        ((21, 19, 20), (20, 21, 21)),
    ),
    "stretch": (
        ((21, 19, 19), (20, 20, 22)), ((18, 20, 25),),
        ((17, 21, 26),), *((((17, 25, 30),),) * 5),
        *((((16, 25, 30),),) * 3), ((17, 24, 29),),
        ((18, 20, 27),),
    ),
}


def shorten_tail(contours, action, frame):
    """Clip only each frame's tail pixels, retaining merged body runs."""
    if action not in BOBTAIL_CUTS:
        return contours
    cuts = BOBTAIL_CUTS[action][frame]
    result = []
    for contour in contours:
        left = min(x for x, _ in contour)
        right = max(x for x, _ in contour)
        bottom = min(y for _, y in contour)
        top = max(y for _, y in contour)
        for cutoff, first, last in cuts:
            if first <= bottom <= last:
                left = max(left, cutoff)
        if left < right:
            result.append([(left, bottom), (left, top), (right, top), (right, bottom)])
    return result


def family_outline(contours, variant, action, frame):
    """Sculpt CC0 pixel outlines into relatives without resampling a bitmap.

    The silhouettes share the original coordinate system. Gait edits move
    individual legs and the torso separately, preserving the floor and cadence.
    Cat 5 supplies the fluffy coat; the other relatives derive from Cat 1.
    """
    if variant == "bobtail":
        contours = shorten_tail(contours, action, frame)
    floor = min(y for contour in contours for _, y in contour)
    moving = action in ("walk", "run")
    wave = math.sin(frame * math.tau / 8) if moving else 0
    result = []
    for contour in contours:
        cx = sum(x for x, _ in contour) / len(contour)
        cy = sum(y for _, y in contour) / len(contour)
        leg = moving and cy < floor + 4
        shaped = []
        for x, y in contour:
            if variant == "stocky":
                x = 27 + (x - 27) * 1.12
                y = floor + (y - floor) * 0.78
                if moving and not leg:
                    y += abs(wave) * 0.7
                if leg:
                    x += wave * (0.9 if cx < 27 else -0.9)
            elif variant == "lanky":
                x = 27 + (x - 27) * 0.88
                y = floor + (y - floor) * 1.12
                if leg:
                    x += wave * (1.0 if cx < 27 else -1.0)
                elif moving:
                    y += wave * 0.3
            elif variant == "fluffy":
                if leg:
                    x += wave * (0.6 if cx < 27 else -0.6)
                elif moving:
                    y += abs(wave) * 0.4
            elif variant == "bobtail":
                x = 28 + (x - 28) * 0.95
                if leg:
                    x += math.sin(frame * math.tau / 4) * (0.8 if cx < 27 else -0.8)
                elif moving:
                    y += abs(wave) * 0.5
            shaped.append((max(10, min(40, x)), max(18, min(34, y))))
        result.append(shaped)
    return result


def poses(variant=None):
    if variant is not None and variant not in FAMILY_BASES:
        raise ValueError(f"Unknown Pet Cats family member: {variant}")
    frames = []
    with zipfile.ZipFile(Path(__file__).with_name("vendor") / "Pet-Cats-Pack.zip") as archive:
        for name, filename, count, mode in animations():
            count = int(count)
            if mode == "spin":
                for frame in range(count):
                    mono = rectangles(spinning_cat.pixels(frame, count, variant), lambda pixel: pixel[3])
                    if variant:
                        mono = family_outline(mono, variant, name, frame)
                    frames.append({"mono": mono, "action": name})
                continue
            cat = 5 if variant == "fluffy" else 1
            path = f"Pet Cats Pack/Cat-{cat}/Cat-{cat}-{filename}.png"
            width, height, rows, _ = png.Reader(bytes=archive.read(path)).asRGBA8()
            rows = [[tuple(row[x:x+4]) for x in range(0, len(row), 4)] for row in rows]
            source_count = 1 if mode == "breathing" else count
            if (width, height) != (source_count * 50, 50):
                raise ValueError(f"Unexpected Pet Cats dimensions for {path}: {width}x{height}")
            for frame in range(count):
                source = 0 if mode == "breathing" else frame
                pixels = [row[source*50:(source+1)*50] for row in rows]
                # The first cat has green eyes against orange fur. Keep these
                # as cutouts so the cat can inherit the status foreground.
                if variant == "fluffy":
                    # Exact Cat 5 iris colours: keep grey fur and both eye holes.
                    eyes = {(19, 133, 192), (226, 214, 86)}
                    mono = rectangles(pixels, lambda pixel: pixel[3] >= 128 and pixel[:3] not in eyes)
                elif variant:
                    # Exact Cat 1 green iris mask; no fur-colour threshold.
                    mono = rectangles(pixels, lambda pixel: pixel[3] >= 128 and pixel[:3] != (80, 81, 33))
                else:
                    mono = rectangles(pixels, lambda pixel: pixel[3] and pixel[1] < pixel[0]*0.95)
                if variant:
                    mono = family_outline(mono, variant, name, frame)
                if mode == "breathing":
                    floor = min(y for contour in mono for _, y in contour)
                    def breathe(contours):
                        return [[(x, floor + (y-floor)*(1+0.04*frame)) for x, y in contour]
                                for contour in contours]
                    mono = breathe(mono)
                frames.append({"mono": mono, "action": name})
    # One common coordinate system for every action prevents accidental
    # resizing or baseline shifts between walking, sitting, and sleeping.
    points = [point for frame in frames for contour in frame["mono"] for point in contour]
    bounds = (min(x for x, _ in points), max(x for x, _ in points),
              min(y for _, y in points), max(y for _, y in points))
    original = next(index for index, frame in enumerate(frames) if frame["action"] == "spin")
    layout = [(BASE + index*6 + offset + half, cells, half, index)
              for index in range(original)
              for cells, offset in ((1, 0), (2, 1), (3, 3)) for half in range(cells)]
    layout += [(XLARGE_BASE + index*4 + half, 4, half, index)
               for index in range(original) for half in range(4)]
    sizes = ((1, 0), (2, 1), (3, 3), (4, 6))
    layout += [(SPIN_BASE + (index-original)*10 + offset + half, cells, half, index)
               for index in range(original, len(frames))
               for cells, offset in sizes for half in range(cells)]
    normal_count = len(frames)
    frames += [{"mono": [[(50-x, y) for x, y in reversed(contour)]
                          for contour in frame["mono"]], "action": frame["action"]}
               for frame in frames[:]]
    layout += [(MIRROR_BASE + index*10 + offset + half, cells, half, normal_count+index)
               for index in range(normal_count)
               for cells, offset in sizes for half in range(cells)]
    if variant:
        # Each family block has 860 forward glyphs followed by 860 mirrored
        # glyphs. All four sizes use the same offsets in Python and Rust.
        base = FAMILY_BASES[variant]
        layout = [(base + index*10 + offset + half, cells, half, index)
                  for index in range(len(frames))
                  for cells, offset in sizes for half in range(cells)]
        bounds = FAMILY_BOUNDS
    return frames, layout, bounds
