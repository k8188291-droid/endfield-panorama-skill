"""Capture overlapping real game frames using the running controller."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('--count', type=int, default=18)
parser.add_argument('--x', type=float, default=0.6)
parser.add_argument('--y', type=float, default=0)
parser.add_argument('--seconds', type=float, default=0.25)
parser.add_argument('--session', default='')
args = parser.parse_args()
if not 1 <= args.count <= 40 or not args.name.replace('-', '').replace('_', '').isalnum():
    raise SystemExit('Invalid series name/count')
if args.session and not args.session.replace('-', '').replace('_', '').isalnum():
    raise SystemExit('Invalid session name')
base = root / ('captures-' + args.session if args.session else 'captures')
folder = base / (time.strftime('%Y%m%d-%H%M%S-') + args.name)
folder.mkdir(parents=True)
manifest = []
for index in range(args.count + 1):
    command = [sys.executable, str(root / 'control.py'), 'capture'] if index == 0 else [
        sys.executable, str(root / 'control.py'), 'look', '--x', str(args.x), '--y', str(args.y),
        '--seconds', str(args.seconds), '--settle', '0.8']
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode:
        raise SystemExit(process.stderr or process.stdout)
    record = json.loads(process.stdout)
    if not record['ok']:
        raise SystemExit(record)
    record['index'] = index
    record['input'] = None if index == 0 else {'x': args.x, 'y': args.y, 'seconds': args.seconds}
    manifest.append(record)
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(record), flush=True)
print('Manifest: ' + str(folder / 'manifest.json'), flush=True)
