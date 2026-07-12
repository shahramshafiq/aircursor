"""One Euro Filter for smoothing noisy fingertip coordinates.

Reference: Casiez, Roussel, Vogel (2012). One instance per axis.
The filter adapts its cutoff to speed: slow motion gets heavy smoothing,
fast motion gets low lag.
"""

import math


def _lowpass(value, previous, alpha):
    return alpha * value + (1.0 - alpha) * previous


def _alpha(cutoff, freq):
    tau = 1.0 / (2.0 * math.pi * cutoff)
    te = 1.0 / freq
    return 1.0 / (1.0 + tau / te)


class OneEuroFilter:
    def __init__(self, min_cutoff=1.2, beta=0.03, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.started = False
        self.prev_raw = 0.0
        self.prev_hat = 0.0
        self.prev_dx_hat = 0.0
        self.prev_time = 0.0

    def reset(self):
        self.started = False

    def filter(self, value, timestamp):
        if not self.started:
            self.started = True
            self.prev_raw = value
            self.prev_hat = value
            self.prev_dx_hat = 0.0
            self.prev_time = timestamp
            return value

        gap = timestamp - self.prev_time
        if gap < 1e-6:
            gap = 1e-6
        freq = 1.0 / gap

        dx = (value - self.prev_raw) * freq
        edx = _lowpass(dx, self.prev_dx_hat, _alpha(self.d_cutoff, freq))

        cutoff = self.min_cutoff + self.beta * abs(edx)
        x_hat = _lowpass(value, self.prev_hat, _alpha(cutoff, freq))

        self.prev_raw = value
        self.prev_hat = x_hat
        self.prev_dx_hat = edx
        self.prev_time = timestamp
        return x_hat
