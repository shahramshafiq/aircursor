"""Maps a normalized fingertip position to a real screen pixel.

The hand should not need to reach the very edge of the camera view. An
inner active region [margin, 1 - margin] on each axis is stretched to the
full screen, then clamped so the cursor can still hit every corner.
"""


def _clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


class CoordinateMapper:
    def __init__(self, screen_width, screen_height, margin=0.15):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.margin = margin

    def map_point(self, norm_x, norm_y):
        span = 1.0 - 2.0 * self.margin
        if span < 1e-6:
            span = 1e-6

        rel_x = (norm_x - self.margin) / span
        rel_y = (norm_y - self.margin) / span

        rel_x = _clamp(rel_x, 0.0, 1.0)
        rel_y = _clamp(rel_y, 0.0, 1.0)

        screen_x = rel_x * self.screen_width
        screen_y = rel_y * self.screen_height

        screen_x = _clamp(screen_x, 0.0, self.screen_width)
        screen_y = _clamp(screen_y, 0.0, self.screen_height)
        return screen_x, screen_y
