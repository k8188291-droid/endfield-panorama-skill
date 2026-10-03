"""Behavioral checks use simulated capture responses, never game input."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_panorama as runner


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.profile = runner.load_profile(runner.ROOT / 'capture-profile.json')

    def test_complete_capture_keeps_69_frames_and_balanced_pitch(self):
        calls = []
        def command(*args):
            calls.append(args)
            return {'ok': True, 'image': f'frame-{len(calls)}.png', 'width': 1600, 'height': 900}
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as tmp:
            base = Path(tmp)
            runner.capture_rows(base, self.profile, command)
            frames = [r for p in base.glob('*/manifest.json') for r in runner.read_json(p)]
            self.assertEqual(len(frames), 69)
            self.assertEqual(len({f['image'] for f in frames}), 69)
        pitch = [c for c in calls if '--y' in c]
        signed_total = sum(float(c[c.index('--seconds') + 1]) *
                           (1 if float(c[c.index('--y') + 1]) > 0 else -1) for c in pitch)
        self.assertAlmostEqual(signed_total, 0)

    def test_focus_loss_preserves_frames_and_does_not_retry_or_restore(self):
        calls = []
        def command(*args):
            calls.append(args)
            if len(calls) == 4:
                raise RuntimeError('Game lost focus')
            return {'ok': True, 'image': f'frame-{len(calls)}.png', 'width': 1600, 'height': 900}
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as tmp:
            with self.assertRaisesRegex(RuntimeError, 'lost focus'):
                runner.capture_rows(Path(tmp), self.profile, command)
            self.assertEqual(len(runner.read_json(Path(tmp) / 'middle/manifest.json')), 3)
            self.assertEqual(len(calls), 4)

    def test_resolution_change_aborts_before_saving_changed_frame(self):
        count = 0
        def command(*args):
            nonlocal count
            count += 1
            return {'ok': True, 'image': 'x.png', 'width': 1600 if count == 1 else 1920, 'height': 900}
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as tmp:
            with self.assertRaisesRegex(RuntimeError, 'resolution changed'):
                runner.capture_rows(Path(tmp), self.profile, command)
            self.assertEqual(len(runner.read_json(Path(tmp) / 'middle/manifest.json')), 1)

    def test_main_stops_owned_server_on_capture_failure(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as tmp, \
                patch.object(runner, 'ROOT', Path(tmp)), \
                patch.object(runner, 'load_profile', return_value=self.profile), \
                patch.object(runner, 'check_environment', return_value={'ok': True}), \
                patch.object(runner, 'start_server', return_value='owned-server'), \
                patch.object(runner, 'stop_server') as stop, \
                patch.object(runner, 'capture_rows', side_effect=RuntimeError('F8 emergency stop')):
            with self.assertRaisesRegex(RuntimeError, 'F8'):
                runner.main(['--prepared', '--delay', '0', '--session', 'failure-check'])
            stop.assert_called_once_with('owned-server')
            self.assertEqual(runner.read_json(Path(tmp) / 'last-run.json')['state'], 'failed')

    def test_existing_session_is_rejected_before_server_start(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT) as tmp, \
                patch.object(runner, 'ROOT', Path(tmp)), \
                patch.object(runner, 'load_profile', return_value=self.profile), \
                patch.object(runner, 'check_environment', return_value={'ok': True}), \
                patch.object(runner, 'start_server') as start:
            (Path(tmp) / 'captures-existing').mkdir()
            with self.assertRaises(FileExistsError):
                runner.main(['--prepared', '--session', 'existing'])
            start.assert_not_called()

    def test_dry_run_never_starts_server(self):
        with patch.object(runner, 'start_server') as start:
            self.assertEqual(runner.main(['--dry-run']), 0)
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
