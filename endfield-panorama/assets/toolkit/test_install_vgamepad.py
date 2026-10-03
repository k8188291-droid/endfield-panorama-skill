"""Installation checks never invoke upstream setup scripts or a driver installer."""
import base64
import csv
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import install_vgamepad as installer


def fixture():
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as archive:
        for name, content in {
            'LICENSE': b'MIT license fixture',
            'setup.py': b'raise RuntimeError("must never execute")',
            'vgamepad/__init__.py': b'',
            'vgamepad/win/virtual_gamepad.py': b'',
            'vgamepad/win/vigem/client/x64/ViGEmClient.dll': b'client fixture',
            'vgamepad/win/vigem/install/x64/ViGEmBusSetup_x64.msi': b'installer fixture',
        }.items():
            member = tarfile.TarInfo('vgamepad-0.1.0/' + name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return data.getvalue()


class InstallTests(unittest.TestCase):
    def test_modified_source_rejected_before_wheel_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                installer.build_wheel(b'untrusted bytes', Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_runtime_wheel_excludes_setup_and_driver_and_has_valid_record(self):
        source = fixture()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(installer, 'SOURCE_SHA256', hashlib.sha256(source).hexdigest()):
            wheel = installer.build_wheel(source, Path(tmp))
            with zipfile.ZipFile(wheel) as archive:
                self.assertFalse(any(n.endswith(('.msi', 'setup.py')) for n in archive.namelist()))
                self.assertIn('vgamepad/win/vigem/client/x64/ViGEmClient.dll', archive.namelist())
                self.assertIn(installer.DIST_INFO + '/LICENSE', archive.namelist())
                record = archive.read(installer.DIST_INFO + '/RECORD').decode()
                for name, digest, size in csv.reader(io.StringIO(record)):
                    if not digest:
                        continue
                    content = archive.read(name)
                    expected = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
                    self.assertEqual(digest, 'sha256=' + expected)
                    self.assertEqual(int(size), len(content))


if __name__ == '__main__':
    unittest.main()
