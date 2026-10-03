"""Install verified Windows vgamepad files without running upstream setup.py/MSI."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

SOURCE_URL = ('https://files.pythonhosted.org/packages/8a/54/'
              '0eaddc33f84247963af078f364b37153d09fcd6cdc398f243ec3e8842c56/'
              'vgamepad-0.1.0.tar.gz')
SOURCE_SHA256 = '57f6bd01aec0c172947517fb782d150ef9b285f7f4d524c317374fa5c24a89de'
DIST_INFO = 'vgamepad-0.1.0.dist-info'


def build_wheel(source: bytes, destination: Path) -> Path:
    """Package only Python sources, the x64 client DLL and the upstream license."""
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('vgamepad source checksum mismatch; nothing installed')
    files = {}
    prefix = 'vgamepad-0.1.0/'
    with tarfile.open(fileobj=io.BytesIO(source), mode='r:gz') as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            name = member.name[len(prefix):]
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe source archive path')
            if name == 'LICENSE':
                files[f'{DIST_INFO}/LICENSE'] = archive.extractfile(member).read()
            elif ((name.startswith('vgamepad/') and name.endswith('.py')) or
                  name == 'vgamepad/win/vigem/client/x64/ViGEmClient.dll'):
                files[name] = archive.extractfile(member).read()
    required = {'vgamepad/__init__.py', 'vgamepad/win/virtual_gamepad.py',
                'vgamepad/win/vigem/client/x64/ViGEmClient.dll', f'{DIST_INFO}/LICENSE'}
    if not required <= files.keys():
        raise ValueError('Required vgamepad files missing')
    files[f'{DIST_INFO}/METADATA'] = (
        'Metadata-Version: 2.1\nName: vgamepad\nVersion: 0.1.0\n'
        'Summary: Virtual XBox360 and DualShock4 gamepads in python\n'
        'License: MIT\nLicense-File: LICENSE\n\n'
    ).encode()
    files[f'{DIST_INFO}/WHEEL'] = (
        'Wheel-Version: 1.0\nGenerator: endfield-panorama\n'
        'Root-Is-Purelib: false\nTag: py3-none-win_amd64\n\n'
    ).encode()
    record = io.StringIO(newline='')
    writer = csv.writer(record)
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow([name, 'sha256=' + digest, len(data)])
    writer.writerow([f'{DIST_INFO}/RECORD', '', ''])
    files[f'{DIST_INFO}/RECORD'] = record.getvalue().encode()
    wheel = destination / 'vgamepad-0.1.0-py3-none-win_amd64.whl'
    with zipfile.ZipFile(wheel, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return wheel


def main():
    if os.name != 'nt' or struct.calcsize('P') != 8:
        raise RuntimeError('Use Windows with 64-bit Python')
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
        source = response.read(4 * 1024 * 1024 + 1)
    if len(source) > 4 * 1024 * 1024:
        raise ValueError('Unexpected source archive size')
    with tempfile.TemporaryDirectory() as tmp:
        wheel = build_wheel(source, Path(tmp))
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index',
                        '--no-deps', str(wheel)], check=True)


if __name__ == '__main__':
    main()
