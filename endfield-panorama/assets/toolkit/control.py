"""Local, file-queue camera controller. Does not inject into the game."""
from __future__ import annotations
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'deps'))
QUEUE = ROOT / 'queue'
SHOTS = ROOT / 'screenshots'


def number(value, low, high):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Expected a finite number in [{low}, {high}]')
    return value


def validate(command):
    op = command.get('op')
    if op not in ('look', 'button', 'trigger', 'capture', 'stop'):
        raise ValueError('Unknown operation')
    result = {'op': op}
    if op in ('look', 'button', 'trigger'):
        result['seconds'] = number(command.get('seconds', 0.15), 0.01, 2.0)
    if op == 'look':
        result['x'] = number(command.get('x', 0), -1, 1)
        result['y'] = number(command.get('y', 0), -1, 1)
    if op == 'button':
        button = command.get('button', '').upper()
        if button not in ('A', 'B', 'X', 'Y', 'START', 'BACK', 'LEFT_THUMB',
                          'RIGHT_THUMB', 'LEFT_SHOULDER', 'RIGHT_SHOULDER',
                          'DPAD_UP', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_RIGHT'):
            raise ValueError('Unsupported button')
        result['button'] = button
    if op == 'trigger':
        trigger = command.get('trigger', 'RIGHT').upper()
        if trigger not in ('LEFT', 'RIGHT'):
            raise ValueError('Unsupported trigger')
        result['trigger'] = trigger
    result['settle'] = number(command.get('settle', 0.8), 0, 5)
    return result


class Desktop:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Windows only')
        self.u = C.WinDLL('user32', use_last_error=True)
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.u.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
        self.u.SetProcessDpiAwarenessContext(C.c_void_p(-4))
        self.u.GetForegroundWindow.restype = W.HWND
        self.u.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
        self.u.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        self.u.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
        self.u.IsIconic.argtypes = [W.HWND]
        self.u.GetAsyncKeyState.argtypes = [C.c_int]
        self.u.GetAsyncKeyState.restype = C.c_short
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
        self.k.CloseHandle.argtypes = [W.HANDLE]

    def guard(self):
        if self.u.GetAsyncKeyState(0x77) & 0x8000:  # F8
            raise KeyboardInterrupt('F8 emergency stop')
        hwnd = self.u.GetForegroundWindow()
        pid = W.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, C.byref(pid))
        handle = self.k.OpenProcess(0x1000, False, pid.value)
        if not handle:
            raise RuntimeError('Cannot identify foreground process')
        try:
            buf, size = C.create_unicode_buffer(32768), W.DWORD(32768)
            if not self.k.QueryFullProcessImageNameW(handle, 0, buf, C.byref(size)):
                raise C.WinError(C.get_last_error())
            if Path(buf.value).name.lower() != 'endfield.exe':
                raise RuntimeError('Endfield must be the foreground window')
        finally:
            self.k.CloseHandle(handle)
        if self.u.IsIconic(hwnd):
            raise RuntimeError('Game is minimized')
        return hwnd

    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.guard()
            time.sleep(min(0.02, max(0, end - time.monotonic())))
        self.guard()

    def capture(self):
        from PIL import ImageGrab
        hwnd = self.guard()
        rect, origin = W.RECT(), W.POINT(0, 0)
        if not self.u.GetClientRect(hwnd, C.byref(rect)) or not self.u.ClientToScreen(hwnd, C.byref(origin)):
            raise C.WinError(C.get_last_error())
        width, height = rect.right, rect.bottom
        if width < 64 or height < 64:
            raise RuntimeError('Game client area is too small')
        # Read only the game client rectangle, not the entire desktop.
        bbox = (origin.x, origin.y, origin.x + width, origin.y + height)
        image = ImageGrab.grab(bbox=bbox, all_screens=True)
        if self.guard() != hwnd:
            raise RuntimeError('Foreground window changed while capturing; discarded image')
        SHOTS.mkdir(exist_ok=True)
        path = SHOTS / (time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8] + '.png')
        image.save(path)
        return {'image': str(path), 'width': width, 'height': height}


def execute(pad, vg, desktop, raw):
    command = validate(raw)
    if command['op'] == 'stop':
        return {'stopped': True}
    desktop.guard()
    try:
        if command['op'] == 'look':
            pad.right_joystick_float(x_value_float=command['x'], y_value_float=command['y'])
            pad.update()
            desktop.wait(command['seconds'])
        elif command['op'] == 'button':
            pad.press_button(button=getattr(vg.XUSB_BUTTON, 'XUSB_GAMEPAD_' + command['button']))
            pad.update()
            desktop.wait(command['seconds'])
        elif command['op'] == 'trigger':
            method = pad.right_trigger_float if command['trigger'] == 'RIGHT' else pad.left_trigger_float
            method(value_float=1.0)
            pad.update()
            desktop.wait(command['seconds'])
    finally:
        pad.reset()
        pad.update()
    desktop.wait(command['settle'])
    return desktop.capture()


def write_json(path, obj):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def serve():
    QUEUE.mkdir(exist_ok=True)
    # Exclusive OS lock is automatically released even after a crash.
    import msvcrt
    lock = open(ROOT / 'server.lock', 'a+b')
    lock.seek(0)
    lock.write(b'0')
    lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise RuntimeError('A controller server is already running')
    pad = None
    try:
        import vgamepad as vg
        pad = vg.VX360Gamepad()
        desktop = Desktop()
        started = time.time()
        write_json(ROOT / 'status.json', {'state': 'ready', 'pid': os.getpid(), 'started': started})
        print('Ready. F8 stops the controller. Commands expire after 15 seconds.', flush=True)
        while True:
            if desktop.u.GetAsyncKeyState(0x77) & 0x8000:
                break
            for path in sorted(QUEUE.glob('*.request.json')):
                response = path.with_name(path.name.replace('.request.json', '.response.json'))
                try:
                    raw = json.loads(path.read_text(encoding='utf-8'))
                    stamp = float(raw['created'])
                    if not math.isfinite(stamp) or stamp < started or not 0 <= time.time() - stamp <= 15:
                        raise RuntimeError('Expired command; no input sent')
                    result = execute(pad, vg, desktop, raw)
                    write_json(response, {'ok': True, **result})
                    if result.get('stopped'):
                        return
                except KeyboardInterrupt:
                    write_json(response, {'ok': False, 'error': 'F8 emergency stop'})
                    return
                except Exception as exc:
                    write_json(response, {'ok': False, 'error': str(exc)})
                finally:
                    path.unlink(missing_ok=True)
            time.sleep(0.02)
    finally:
        if pad is not None:
            pad.reset()
            pad.update()
        write_json(ROOT / 'status.json', {'state': 'stopped'})
        lock.close()


def submit(args):
    raw = validate(vars(args) | {'op': args.action})
    status = json.loads((ROOT / 'status.json').read_text(encoding='utf-8'))
    if status.get('state') != 'ready':
        raise RuntimeError('Start the controller first')
    QUEUE.mkdir(exist_ok=True)
    name = uuid.uuid4().hex
    request = QUEUE / f'{name}.request.json'
    response = QUEUE / f'{name}.response.json'
    write_json(request, raw | {'created': time.time()})
    for _ in range(250):
        if response.exists():
            result = json.loads(response.read_text(encoding='utf-8'))
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result['ok'] else 1
        time.sleep(0.1)
    request.unlink(missing_ok=True)
    raise RuntimeError('No response; request cancelled (a command already running may finish)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['serve', 'look', 'button', 'trigger', 'capture', 'stop', 'screenshot', 'check'])
    parser.add_argument('--x', type=float, default=0)
    parser.add_argument('--y', type=float, default=0)
    parser.add_argument('--seconds', type=float, default=0.15)
    parser.add_argument('--settle', type=float, default=0.8)
    parser.add_argument('--button', default='RIGHT_THUMB')
    parser.add_argument('--trigger', default='RIGHT')
    parser.add_argument('--delay', type=float, default=0)
    args = parser.parse_args()
    try:
        time.sleep(number(args.delay, 0, 30))
        if args.action == 'serve':
            serve()
        elif args.action == 'screenshot':
            print(json.dumps(Desktop().capture(), ensure_ascii=False))
        elif args.action == 'check':
            import winreg
            import importlib.util
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Services\ViGEmBus'):
                    driver = True
            except FileNotFoundError:
                driver = False
            print(json.dumps({'driver_installed': driver, 'vgamepad': bool(importlib.util.find_spec('vgamepad')),
                              'Pillow': bool(importlib.util.find_spec('PIL'))}))
        else:
            return submit(args)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
