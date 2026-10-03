"""Synthetic projection fixtures check coverage and offline output, without game input."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
import stitch_panorama as stitcher


class ProjectionTests(unittest.TestCase):
    def test_partial_and_complete_coverage_agree_with_alpha_and_viewer(self):
        rotations = [
            [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
            [[-1, 0, 0], [0, 1, 0], [0, 0, -1]],
            [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
            [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
            [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.png'
            stitcher.save(source, np.full((240, 320, 3), (60, 120, 180), np.uint8))
            for name, views, complete in [('partial', rotations[:1], False), ('full', rotations, True)]:
                with self.subTest(name=name):
                    output = root / name
                    output.mkdir()
                    records = [{'image': str(source), 'K': [[80, 0, 160], [0, 70, 120], [0, 0, 1]],
                                'R': rotation} for rotation in views]
                    stitcher.render(records, output, 512)
                    report = json.loads((output / 'report.json').read_text())
                    with Image.open(output / 'panorama.png') as image:
                        self.assertEqual(image.size, (512, 256))
                        alpha = np.array(image.getchannel('A'))
                        self.assertEqual(int((alpha == 0).sum()), report['unobserved_pixels'])
                        self.assertEqual(report['unobserved_pixels'] == 0, complete)
                    viewer = (output / 'view-panorama.html').read_text()
                    self.assertNotIn('__IMAGE_DATA__', viewer)
                    self.assertNotIn('__COVERAGE__', viewer)
                    self.assertIn('data:image/png;base64,', viewer)


if __name__ == '__main__':
    unittest.main()
