"""Check tail surgery against original source pixels, especially moving paws."""
from pathlib import Path
import sys
import unittest
import zipfile

FONT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FONT_DIR / 'vendor/pypng-0.20220715.0-py3-none-any.whl'))
sys.path.insert(0, str(FONT_DIR))
import png
import pet_cats


def pixel_cells(contours):
    return {(x, y) for contour in contours
            for x in range(int(min(x for x, _ in contour)), int(max(x for x, _ in contour)))
            for y in range(int(min(y for _, y in contour)), int(max(y for _, y in contour)))}


class BobtailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = {}
        with zipfile.ZipFile(FONT_DIR / 'vendor/Pet-Cats-Pack.zip') as archive:
            for action, filename, count, mode in pet_cats.animations():
                if action not in pet_cats.BOBTAIL_CUTS:
                    continue
                width, _, rows, _ = png.Reader(bytes=archive.read(
                    f'Pet Cats Pack/Cat-1/Cat-1-{filename}.png')).asRGBA8()
                rows = [[tuple(row[x:x+4]) for x in range(0, width*4, 4)] for row in rows]
                cls.source[action] = [pet_cats.rectangles(
                    [row[frame*50:(frame+1)*50] for row in rows],
                    lambda pixel: pixel[3] >= 128 and pixel[:3] != (80, 81, 33))
                    for frame in range(int(count))]

    def test_all_moving_frames_shorten_the_raised_tail_without_cutting_paws(self):
        # Sampled tail tips follow the original Cat 1 sheets, independently of
        # the mask table. Rear paws share these x columns in several frames.
        tips = {'walk': [(14, 31), (13, 31), (12, 29), (11, 28),
                         (11, 28), (12, 29), (13, 30), (14, 30)],
                'run': [(10, 29), (10, 30), (10, 29), (11, 28),
                        (13, 28), (15, 28), (14, 29), (11, 26)]}
        for action, frames in self.source.items():
            if action not in tips:
                continue
            for frame, contours in enumerate(frames):
                with self.subTest(action=action, frame=frame):
                    before = pixel_cells(contours)
                    after = pixel_cells(pet_cats.shorten_tail(contours, action, frame))
                    self.assertIn(tips[action][frame], before)
                    self.assertNotIn(tips[action][frame], after)
                    self.assertGreaterEqual(len(before - after), 5)
                    self.assertEqual({p for p in before if p[1] <= 22},
                                     {p for p in after if p[1] <= 22})
                    self.assertTrue(after <= before)

    def test_joined_tail_body_run_keeps_body_after_clipping(self):
        contours = self.source['run'][0]
        after = pixel_cells(pet_cats.shorten_tail(contours, 'run', 0))
        self.assertNotIn((13, 25), after)
        self.assertIn((16, 25), after)
        self.assertIn((25, 25), after)
        # The original bug removed these rear paws instead of the raised tail.
        self.assertIn((15, 20), after)
        self.assertIn((16, 18), after)

    def test_rest_masks_preserve_grounded_feet_and_sleeping_body(self):
        for frame, contours in enumerate(self.source['idle']):
            before = pixel_cells(contours)
            after = pixel_cells(pet_cats.shorten_tail(contours, 'idle', frame))
            with self.subTest(frame=frame):
                self.assertEqual({p for p in before if p[0] >= 21},
                                 {p for p in after if p[0] >= 21})
                self.assertEqual({p for p in before if p[1] == 18},
                                 {p for p in after if p[1] == 18})
        contours = self.source['idle'][0]
        for action in ('sleep', 'deep-sleep', 'spin', 'itch'):
            self.assertEqual(pet_cats.shorten_tail(contours, action, 0), contours)


if __name__ == '__main__':
    unittest.main()
