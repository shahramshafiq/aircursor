"""Gesture state machine. Pure logic: no cv2, no mouse, fully testable.

The engine is fed one frame at a time through update(landmarks, now). It
owns the two One Euro filters, the coordinate mapper, pinch state, drag
state, and all cooldowns. It returns a small result describing the mapped
target, the discrete actions to run this frame, any drag press/release
edge, and a HUD label. main.py is responsible for applying the result to
a backend, which is what keeps this class unit testable.
"""

from euro_filter import OneEuroFilter
from mapping import CoordinateMapper
import hand


def classify_posture(fingers):
    """Turn the four finger up/down booleans into one posture label.

    Kept separate from GestureEngine so it is trivial to unit test on its
    own: feed a finger dict, get a label back.
    """
    idx = fingers["index"]
    mid = fingers["middle"]
    ring = fingers["ring"]
    pinky = fingers["pinky"]

    if idx and mid and ring and pinky:
        return "palm"
    if (not idx) and (not mid) and (not ring) and (not pinky):
        return "fist"
    if idx and mid and (not ring) and (not pinky):
        return "two_finger"
    if idx and (not mid):
        return "move"
    return "other"


class PostureDebouncer:
    """Filters single frame MediaPipe noise out of the posture label.

    A real webcam occasionally misreads one finger for one frame (motion
    blur, a bad angle). Without this, that single bad frame would flip the
    mode for an instant, for example dropping out of MOVE for one frame
    and back, which reads as a misfire to the user. A posture only takes
    effect once the SAME label has been seen for `need` consecutive
    frames, so a one frame blip never changes the confirmed posture, while
    a real gesture change still lands within a couple of frames (well
    under 100ms at typical webcam frame rates).

    The very first label ever fed is confirmed immediately: there is no
    prior confirmed state to protect, and a brand new session should react
    at once rather than wait.
    """

    def __init__(self, need=2):
        self.need = need
        self.confirmed = None
        self.candidate = None
        self.streak = 0

    def feed(self, label):
        if self.confirmed is None:
            self.confirmed = label
            self.candidate = label
            self.streak = 1
            return self.confirmed
        if label == self.candidate:
            self.streak = self.streak + 1
        else:
            self.candidate = label
            self.streak = 1
        if self.streak >= self.need:
            self.confirmed = label
        return self.confirmed

    def reset(self):
        self.confirmed = None
        self.candidate = None
        self.streak = 0


class GestureEngine:
    def __init__(
        self,
        screen_size,
        margin=0.15,
        min_cutoff=1.2,
        beta=0.03,
        pinch_on=0.35,
        pinch_off=0.5,
        drag_ms=0.35,
        double_ms=0.4,
        click_cooldown=0.12,
        scroll_deadzone=0.02,
        scroll_cooldown=0.05,
        posture_hold_frames=2,
    ):
        screen_w, screen_h = screen_size
        self.mapper = CoordinateMapper(screen_w, screen_h, margin)
        self.euro_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.euro_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.posture = PostureDebouncer(need=posture_hold_frames)

        self.pinch_on = pinch_on
        self.pinch_off = pinch_off
        self.drag_ms = drag_ms
        self.double_ms = double_ms
        self.click_cooldown = click_cooldown
        self.scroll_deadzone = scroll_deadzone
        self.scroll_cooldown = scroll_cooldown

        self.pinch_active = False
        self.pinch_start = 0.0
        self.frozen = None
        self.dragging = False

        self.last_smoothed = (screen_w * 0.5, screen_h * 0.5)
        self.last_click_time = -1000.0
        self.last_left_click_time = -1000.0
        self.last_scroll_time = -1000.0
        self.scroll_ref_y = None

    def _blank_result(self, mode, ratio=0.0, fingers=None):
        return {
            "target": None,
            "actions": [],
            "press": None,
            "release": None,
            "mode": mode,
            "pinch_ratio": ratio,
            "fingers": fingers or {},
        }

    def update(self, landmarks, now):
        # No hand in frame: hold still, drop any active drag, no actions.
        # Reset the debouncer too, so a hand that reappears is classified
        # fresh instead of waiting on a stale confirmed posture.
        if landmarks is None:
            result = self._blank_result("IDLE")
            if self.dragging:
                result["release"] = "left"
                self.dragging = False
            self.pinch_active = False
            self.frozen = None
            self.scroll_ref_y = None
            self.posture.reset()
            return result

        fingers = hand.fingers_up(landmarks)
        ratio = hand.pinch_ratio(landmarks, hand.THUMB_TIP, hand.INDEX_TIP)

        # Debounced posture: the mode only switches once the same reading
        # has held for a couple of frames, so a single misread finger from
        # the camera cannot flip the mode for an instant. The raw fingers
        # dict still goes into the result untouched, for live HUD feedback.
        raw_posture = classify_posture(fingers)
        posture = self.posture.feed(raw_posture)

        palm = posture == "palm"
        fist = posture == "fist"
        two_finger = posture == "two_finger"
        move_posture = posture == "move"

        # Smoothed live cursor from the index fingertip, every frame, so the
        # filters stay warm and a pre-pinch position is always available.
        tip = landmarks[hand.INDEX_TIP]
        mapped_x, mapped_y = self.mapper.map_point(tip.x, tip.y)
        smooth_x = self.euro_x.filter(mapped_x, now)
        smooth_y = self.euro_y.filter(mapped_y, now)
        smoothed_live = (smooth_x, smooth_y)

        # Pinch edges with hysteresis.
        pinch_began = False
        pinch_ended = False
        if self.pinch_active:
            if ratio > self.pinch_off:
                self.pinch_active = False
                pinch_ended = True
        else:
            if ratio < self.pinch_on:
                self.pinch_active = True
                pinch_began = True

        result = self._blank_result("IDLE", ratio, fingers)

        if palm or fist:
            mode = "PAUSED" if palm else "IDLE"
            if self.dragging:
                result["release"] = "left"
                self.dragging = False
            self.pinch_active = False
            self.frozen = None
            self.scroll_ref_y = None
            result["mode"] = mode
            self.last_smoothed = smoothed_live
            return result

        if two_finger:
            result["mode"] = "SCROLL"
            # If a drag was live in MOVE and the middle finger comes up (real
            # or MediaPipe noise), we would otherwise leave the left button
            # pressed forever. Release it before handling scroll/right click.
            if self.dragging:
                result["release"] = "left"
                self.dragging = False
            self._two_finger(result, landmarks, now, pinch_began, pinch_ended)
            self.last_smoothed = smoothed_live
            return result

        if move_posture:
            result["mode"] = "MOVE"
            self.scroll_ref_y = None
            self._move(result, smoothed_live, now, pinch_began, pinch_ended)
            self.last_smoothed = smoothed_live
            return result

        # Any other posture: treat as idle, hold cursor, drop drag.
        if self.dragging:
            result["release"] = "left"
            self.dragging = False
        self.pinch_active = False
        self.frozen = None
        self.scroll_ref_y = None
        result["mode"] = "IDLE"
        self.last_smoothed = smoothed_live
        return result

    def _move(self, result, smoothed_live, now, pinch_began, pinch_ended):
        target = smoothed_live

        if pinch_began:
            self.frozen = self.last_smoothed
            self.pinch_start = now
            self.dragging = False

        if self.pinch_active:
            if not self.dragging:
                target = self.frozen
                if (now - self.pinch_start) >= self.drag_ms:
                    self.dragging = True
                    result["press"] = "left"
                    result["mode"] = "DRAG"
                    target = smoothed_live
            else:
                result["mode"] = "DRAG"
                target = smoothed_live

        if pinch_ended:
            if self.dragging:
                result["release"] = "left"
                self.dragging = False
                result["mode"] = "MOVE"
            else:
                if (now - self.last_click_time) >= self.click_cooldown:
                    target = self.frozen if self.frozen is not None else smoothed_live
                    if (now - self.last_left_click_time) <= self.double_ms:
                        result["mode"] = "DOUBLE CLICK"
                    else:
                        result["mode"] = "LEFT CLICK"
                    result["actions"].append(("left_click",))
                    self.last_left_click_time = now
                    self.last_click_time = now
            self.frozen = None

        result["target"] = target

    def _two_finger(self, result, landmarks, now, pinch_began, pinch_ended):
        # Cursor holds still in two finger posture; it is for scroll and
        # right click only. target stays None unless a click freezes it.
        if pinch_began:
            self.frozen = self.last_smoothed
            self.pinch_start = now
            self.scroll_ref_y = None

        if pinch_ended:
            if (now - self.last_click_time) >= self.click_cooldown:
                result["actions"].append(("right_click",))
                result["mode"] = "RIGHT CLICK"
                result["target"] = self.frozen
                self.last_click_time = now
            self.frozen = None
            return

        if self.pinch_active:
            # Pinch held, waiting for release to fire the right click.
            self.scroll_ref_y = None
            return

        # No pinch: vertical fingertip motion becomes scroll ticks.
        cur_y = landmarks[hand.INDEX_TIP].y
        if self.scroll_ref_y is None:
            self.scroll_ref_y = cur_y
            return

        delta = self.scroll_ref_y - cur_y  # hand up means smaller y, positive
        if abs(delta) >= self.scroll_deadzone:
            if (now - self.last_scroll_time) >= self.scroll_cooldown:
                amount = 1 if delta > 0 else -1
                result["actions"].append(("scroll", amount))
                result["mode"] = "SCROLL"
                self.last_scroll_time = now
                self.scroll_ref_y = cur_y
