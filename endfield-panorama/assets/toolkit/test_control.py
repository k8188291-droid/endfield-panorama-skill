import unittest
import control


class Pad:
    def __init__(self):
        self.active = False
    def right_joystick_float(self, **kwargs):
        self.active = True
    def update(self):
        pass
    def reset(self):
        self.active = False


class Desktop:
    def guard(self):
        pass
    def wait(self, seconds):
        raise RuntimeError('Game lost focus')
    def capture(self):
        raise AssertionError('Must not capture after loss of focus')


class Tests(unittest.TestCase):
    def test_neutral_after_focus_loss(self):
        pad = Pad()
        with self.assertRaisesRegex(RuntimeError, 'lost focus'):
            control.execute(pad, None, Desktop(), {'op': 'look', 'x': 0.5})
        self.assertFalse(pad.active)

    def test_reject_nonfinite_or_long_input(self):
        for value in (float('nan'), float('inf'), -0.1, 3):
            with self.assertRaises(ValueError):
                control.validate({'op': 'look', 'seconds': value})

    def test_reject_out_of_range_axis(self):
        with self.assertRaises(ValueError):
            control.validate({'op': 'look', 'x': 1.1})

    def test_reject_unknown_button(self):
        with self.assertRaises(ValueError):
            control.validate({'op': 'button', 'button': 'invalid'})


if __name__ == '__main__':
    unittest.main()
