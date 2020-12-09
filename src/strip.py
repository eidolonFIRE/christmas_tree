import importlib
from patterns.base import State
import os
from color_utils import color_to_int, to_color
import numpy as np
import ctypes
import re

# detect and load patterns
pattern_files = [f.replace(".py", "") for f in os.listdir("patterns") if os.path.isfile(os.path.join("patterns", f))]
pattern_classes = {}
print("Importing Patterns:")
for name in pattern_files:
    print("    - %s" % name)
    globals()[name] = importlib.import_module("patterns." + name, package=None)
    pattern_classes[name] = globals()[name].__dict__[name]

# detect OS and load visualization istead of hardware when on PC
os_type = " ".join(os.uname())
print("Current OS: %s" % os_type)
if "arm" in os_type:
    print("Loading on Raspberry pi, using pwm hardware.")
    from ledlib.neopixel import Adafruit_NeoPixel, ws
else:
    print("Loading on dev PC, using stub visualization.")
    from stub import Adafruit_NeoPixel_stub as Adafruit_NeoPixel, ws


class LedInterface(object):
    """ Hardware interface
    """
    def __init__(self, length, pin, dma, channel):
        super(LedInterface, self).__init__()
        self._hw = Adafruit_NeoPixel(length, pin=pin, dma=dma, channel=channel, strip_type=ws.WS2811_STRIP_GRB)
        self._hw.begin()
        self.length = length
        self.buffer = np.zeros((length, 3))

        # allocate new array
        self.raw_buffer = (ctypes.c_uint8 * self.length * 4)()
        pointer = int(re.findall("(0x[\w]+)", ctypes.byref(self.raw_buffer).__str__())[0], 16)
        ws.set_buffer(self._hw._channel, pointer)

    def flush(self):
        """ Flush buffer to strip
        """
        buf = np.minimum(np.maximum(np.array(self.buffer * 255, np.uint32), 0), 255)
        packed_buf = (buf[:, 0] << 16) + (buf[:, 1] << 8) + buf[:, 2]

        ctypes.memmove(ctypes.byref(self.raw_buffer), packed_buf.tobytes(), self.length * 4)
        self._hw.show()

    def __getitem__(self, idx):
        return self.buffer[idx]

    def __setitem__(self, idx, value):
        self.buffer[idx] = value


class Strip(object):
    """   """
    def __init__(self, length, pin, dma, channel):
        super(Strip, self).__init__()
        self.leds = LedInterface(length, pin, dma, channel)
        self.active_pats = []

    def step(self):
        for each in self.active_pats:
            if each.state == State.OFF:
                self.active_pats.remove(each)
            elif each.state.value > State.OFF.value:
                each.step(self.leds)
        self.leds.flush()

    def start_pattern(self, name, solo=True):
        ''' start a pattern, stop all others '''
        if name in pattern_classes.keys():
            for each in self.active_pats:
                if each.__class__.__name__ == name:
                    # pattern already running!
                    return
            # start the desired pattern (no duplicates)
            self.active_pats.append(pattern_classes[name](self.leds.length))
            if solo and not self.active_pats[-1].one_shot:
                # stop all other patterns
                for each in self.active_pats:
                    if name != each.__class__.__name__:
                        each.state = State.STOP
        else:
            print("Unknown pattern \"%s\"" % name)
