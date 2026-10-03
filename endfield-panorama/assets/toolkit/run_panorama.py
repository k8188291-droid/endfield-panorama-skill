"""Repeatable Endfield photo-mode capture and real-screenshot panorama stitching."""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'deps'))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    from control import write_json as atomic_write
    atomic_write(Path(path), value)


def bounded(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Profile values must be numbers')
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Profile value must be finite and in [{low}, {high}]')
    return value


def load_profile(path):
    profile = read_json(path)
    bounded(profile['axis'], 0.15, 1)
    bounded(profile['settle'], 0, 5)
    rows = profile['rows']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
        raise ValueError('Profile needs 1 to 12 rows')
    names = set()
    for row in rows:
        name = row['name']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', name) or name in names:
            raise ValueError('Row names must be unique simple names')
        names.add(name)
        if type(row['count']) is not int or not 1 <= row['count'] <= 40:
            raise ValueError('Row count must be an integer from 1 to 40')
        bounded(row['yaw_seconds'], 0.01, 2)
        bounded(row['pitch_seconds'], -2, 2)
        if 0 < abs(row['pitch_seconds']) < 0.01:
            raise ValueError('Nonzero pitch duration must be at least 0.01 seconds')
    bounded(profile['restore_pitch_seconds'], -2, 2)
    if 0 < abs(profile['restore_pitch_seconds']) < 0.01:
        raise ValueError('Nonzero restore duration must be at least 0.01 seconds')
    return profile


def check_environment():
    result = {'windows': os.name == 'nt', 'python': sys.version.split()[0],
              'python_64bit': struct.calcsize('P') == 8, 'modules': {}}
    for name in ('PIL', 'numpy', 'cv2', 'vgamepad'):
        try:
            module = importlib.import_module(name)
            result['modules'][name] = getattr(module, '__version__', 'import OK')
        except Exception as exc:
            result['modules'][name] = {'error': str(exc)}
    result['driver_installed'] = False
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Services\ViGEmBus'):
                result['driver_installed'] = True
        except FileNotFoundError:
            pass
    result['ok'] = (result['windows'] and result['python_64bit'] and result['driver_installed']
                    and all(isinstance(v, str) for v in result['modules'].values()))
    return result


def control_command(*args):
    completed = subprocess.run([sys.executable, str(ROOT / 'control.py'), *map(str, args)],
                               cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    value = json.loads(completed.stdout)
    if not value.get('ok'):
        raise RuntimeError(str(value))
    return value


def start_server():
    # Server's OS lock prevents duplicates; wait for THIS PID, not stale status.json.
    with (ROOT / 'server.stdout.log').open('a', encoding='utf-8') as stdout, \
            (ROOT / 'server.stderr.log').open('a', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, str(ROOT / 'control.py'), 'serve'],
                                   cwd=ROOT, stdout=stdout, stderr=stderr,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Controller failed to start; see server.stderr.log. '
                                   'Use --external-server only for an already-running controller.')
            try:
                status = read_json(ROOT / 'status.json')
                if status.get('state') == 'ready' and status.get('pid') == process.pid:
                    return process
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise RuntimeError('Controller startup timed out')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        raise


def stop_server(process=None):
    # Never restore camera after failure: the user may have deliberately hit F8.
    try:
        if read_json(ROOT / 'status.json').get('state') == 'ready':
            control_command('stop')
    except Exception as exc:
        print(f'Controller stop: {exc}', file=sys.stderr, flush=True)
    if process is not None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)


def capture_rows(base, profile, command=control_command):
    """Save every completed frame immediately; no automatic retry after input failure."""
    dimensions = None
    def issue(*args):
        nonlocal dimensions
        result = command(*args)
        if 'image' in result:
            size = (result['width'], result['height'])
            if dimensions is not None and size != dimensions:
                raise RuntimeError('Game resolution changed during capture; start a fresh session')
            dimensions = size
        return result
    for row in profile['rows']:
        print(f"Capturing {row['name']}: {row['count'] + 1} frames", flush=True)
        pitch = row['pitch_seconds']
        if pitch:
            issue('look', '--y', math.copysign(profile['axis'], pitch),
                  '--seconds', abs(pitch), '--settle', profile['settle'])
        folder = base / row['name']
        folder.mkdir()
        manifest = []
        for index in range(row['count'] + 1):
            result = (issue('capture', '--settle', profile['settle']) if index == 0 else
                      issue('look', '--x', profile['axis'], '--seconds', row['yaw_seconds'],
                            '--settle', profile['settle']))
            manifest.append(result | {'index': index, 'input': None if index == 0 else
                                     {'x': profile['axis'], 'y': 0, 'seconds': row['yaw_seconds']}})
            write_json(folder / 'manifest.json', manifest)
    restore = profile['restore_pitch_seconds']
    if restore:
        issue('look', '--y', math.copysign(profile['axis'], restore),
              '--seconds', abs(restore), '--settle', profile['settle'])


def stitch(captures, output, width):
    subprocess.run([sys.executable, str(ROOT / 'stitch_panorama.py'), '--captures', str(captures),
                    '--width', str(width), '--output', str(output)], cwd=ROOT, check=True)
    report = read_json(output / 'report.json')
    from PIL import Image
    with Image.open(output / 'panorama.png') as image:
        if image.size != (width, width // 2):
            raise RuntimeError('Unexpected panorama dimensions')
        if report['unobserved_pixels'] == 0 and image.getchannel('A').getextrema() != (255, 255):
            raise RuntimeError('Coverage report and alpha disagree')
    html = (output / 'view-panorama.html').read_text(encoding='utf-8')
    if '__IMAGE_DATA__' in html or 'data:image/png;base64,' not in html:
        raise RuntimeError('Viewer is missing its embedded panorama')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check dependencies without game input')
    parser.add_argument('--dry-run', action='store_true', help='Print plan without starting a controller')
    parser.add_argument('--prepared', action='store_true', help='Photo mode, first person, level, 22 mm, UI hidden')
    parser.add_argument('--external-server', action='store_true', help='Use existing server; stop it after capture')
    parser.add_argument('--delay', type=float, default=8, help='Seconds to switch focus to game before capture')
    parser.add_argument('--session', help='New session name; existing names are rejected')
    parser.add_argument('--profile', type=Path, default=ROOT / 'capture-profile.json')
    parser.add_argument('--width', type=int, default=4096)
    parser.add_argument('--capture-only', action='store_true')
    parser.add_argument('--stitch-only', type=Path, metavar='CAPTURE_DIRECTORY', help='Rebuild without game input')
    args = parser.parse_args(argv)
    if args.check:
        result = check_environment()
        print(json.dumps(result, indent=2))
        return 0 if result['ok'] else 1
    if args.width % 2 or not 512 <= args.width <= 8192:
        parser.error('--width must be even and between 512 and 8192')
    if not math.isfinite(args.delay) or not 0 <= args.delay <= 60:
        parser.error('--delay must be in [0, 60]')
    if args.stitch_only and args.capture_only:
        parser.error('--stitch-only and --capture-only cannot be combined')
    profile = load_profile(args.profile)
    session = args.session or (time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6])
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', session):
        parser.error('--session must be 1 to 80 letters, digits, underscores or hyphens')
    captures = args.stitch_only.resolve() if args.stitch_only else ROOT / ('captures-' + session)
    output = ROOT / 'output' / session
    if args.dry_run:
        print(json.dumps({'session': session, 'captures': str(captures), 'output': str(output),
                          'frames': sum(r['count'] + 1 for r in profile['rows']),
                          'profile': profile, 'mode': 'stitch' if args.stitch_only else 'capture'}, indent=2))
        return 0
    run = {'session': session, 'captures': str(captures), 'output': str(output), 'state': 'starting'}
    if args.stitch_only:
        if not list(captures.glob('*/manifest.json')):
            parser.error('No capture manifests found in --stitch-only directory')
    else:
        if not args.prepared:
            parser.error('Prepare first-person photo mode at 22 mm, level the view, hide UI, then pass --prepared')
        environment = check_environment()
        if not environment['ok']:
            raise RuntimeError('Run Setup.ps1 first: ' + json.dumps(environment))
        captures.mkdir()  # Reject reusing a session, even after a failed capture.
        write_json(captures / 'profile.json', profile)
    if output.exists() and not args.capture_only:
        raise FileExistsError('Output already exists; use a new --session')
    journal = captures / 'run.json' if not args.stitch_only else None
    def save_state(state, **extra):
        run.update(state=state, **extra)
        if journal:
            write_json(journal, run)
        write_json(ROOT / 'last-run.json', run)
    try:
        if not args.stitch_only:
            save_state('capturing')
            process = None
            server_acquired = False
            try:
                if args.external_server:
                    if read_json(ROOT / 'status.json').get('state') != 'ready':
                        raise RuntimeError('External controller is not ready')
                else:
                    process = start_server()
                server_acquired = True
                print(f'Switch to Endfield now. Capture starts in {args.delay:g}s. F8 stops.', flush=True)
                time.sleep(args.delay)
                capture_rows(captures, profile)
                save_state('captured')
            finally:
                if server_acquired:
                    stop_server(process)
        if args.capture_only:
            print('Captured: ' + str(captures), flush=True)
            return 0
        save_state('stitching')
        report = stitch(captures, output, args.width)
        complete = report['unobserved_pixels'] == 0
        save_state('complete' if complete else 'incomplete', report=report)
        print('Viewer: ' + str(output / 'view-panorama.html'), flush=True)
        if not complete:
            print('Coverage has gaps. Keep the output, inspect coverage.png, and recapture missing views.', flush=True)
            return 2
        return 0
    except BaseException as exc:
        save_state('failed', error=str(exc) or type(exc).__name__)
        raise


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print('Stopped: ' + (str(exc) or type(exc).__name__), file=sys.stderr, flush=True)
        raise SystemExit(1)
