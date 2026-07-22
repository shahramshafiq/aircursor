"""Headless smoke tests for AirCursor.

Never opens the camera or a window, never touches the real mouse (only the
FakeBackend), never starts the keyboard listener. Run from the project
folder with: py -3.12 tests/smoke_test.py
"""

import os
import sys
import math
import random

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
sys.path.insert(0, PARENT)

from euro_filter import OneEuroFilter
from mapping import CoordinateMapper
from gestures import GestureEngine, PostureDebouncer, classify_posture
from backends import FakeBackend
import hand
import hints
from main import process_frame, toggle_control, apply_result, build_parser
from tutorial import TutorialFlow

PASSED = 0
FAILED = 0


def check(name, condition):
    global PASSED, FAILED
    if condition:
        PASSED = PASSED + 1
        print("PASS  " + name)
    else:
        FAILED = FAILED + 1
        print("FAIL  " + name)


class LM:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


def make_hand(index_up=True, middle_up=False, ring_up=False, pinky_up=False,
              pinch=False, index_tip=(0.5, 0.5)):
    points = []
    for _ in range(21):
        points.append(LM(0.5, 0.5))

    points[0] = LM(0.5, 0.9)   # wrist
    points[9] = LM(0.5, 0.5)   # middle mcp, gives hand_size 0.4

    itx, ity = index_tip
    points[8] = LM(itx, ity)   # index tip
    if index_up:
        points[6] = LM(itx, ity + 0.1)
    else:
        points[6] = LM(itx, ity - 0.1)
    points[5] = LM(itx, ity + 0.15)

    points[12] = LM(0.45, 0.3 if middle_up else 0.7)
    points[10] = LM(0.45, 0.4 if middle_up else 0.6)

    points[16] = LM(0.55, 0.3 if ring_up else 0.7)
    points[14] = LM(0.55, 0.4 if ring_up else 0.6)

    points[20] = LM(0.6, 0.3 if pinky_up else 0.7)
    points[18] = LM(0.6, 0.4 if pinky_up else 0.6)

    if pinch:
        points[4] = LM(itx + 0.02, ity + 0.02)
    else:
        points[4] = LM(itx - 0.3, ity + 0.1)
    points[3] = LM(itx - 0.1, ity + 0.1)
    return points


def scale_hand(points, factor):
    scaled = []
    for p in points:
        scaled.append(LM(p.x * factor, p.y * factor, p.z))
    return scaled


def variance(values):
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    total = 0.0
    for v in values:
        total = total + (v - mean) * (v - mean)
    return total / n


# ---------- One Euro Filter ----------

def test_euro_noise():
    random.seed(7)
    flt = OneEuroFilter(min_cutoff=1.2, beta=0.03)
    freq = 60.0
    raw = []
    out = []
    t = 0.0
    for i in range(300):
        noise = (random.random() - 0.5) * 20.0
        x = 100.0 + noise
        raw.append(x)
        out.append(flt.filter(x, t))
        t = t + 1.0 / freq
    in_var = variance(raw[1:])
    out_var = variance(out[1:])
    check("euro reduces noise variance", out_var < in_var * 0.25)


def test_euro_ramp():
    flt = OneEuroFilter(min_cutoff=1.2, beta=0.03)
    freq = 60.0
    t = 0.0
    last_in = 0.0
    last_out = 0.0
    for i in range(300):
        x = i * 0.5
        last_in = x
        last_out = flt.filter(x, t)
        t = t + 1.0 / freq
    err = abs(last_out - last_in)
    check("euro tracks ramp with small lag", err < 5.0)


# ---------- Mapping ----------

def test_mapping():
    mapper = CoordinateMapper(1920, 1080, margin=0.15)
    cx, cy = mapper.map_point(0.5, 0.5)
    check("map center to screen center", abs(cx - 960) < 1 and abs(cy - 540) < 1)

    lx, ly = mapper.map_point(0.0, 0.0)
    check("map below region clamps to zero", lx == 0 and ly == 0)

    hx, hy = mapper.map_point(1.0, 1.0)
    check("map above region clamps to max", abs(hx - 1920) < 1 and abs(hy - 1080) < 1)

    mx, my = mapper.map_point(0.15, 0.15)
    check("margin edge maps to origin", abs(mx) < 1 and abs(my) < 1)


# ---------- Fingers and pinch ----------

def test_fingers():
    point = make_hand(index_up=True, middle_up=False, ring_up=False, pinky_up=False)
    fu = hand.fingers_up(point)
    check("pointing reads index only",
          fu["index"] and not fu["middle"] and not fu["ring"] and not fu["pinky"])

    two = make_hand(index_up=True, middle_up=True)
    fu = hand.fingers_up(two)
    check("two finger reads index and middle",
          fu["index"] and fu["middle"] and not fu["ring"] and not fu["pinky"])

    palm = make_hand(index_up=True, middle_up=True, ring_up=True, pinky_up=True)
    fu = hand.fingers_up(palm)
    check("palm reads all four up",
          fu["index"] and fu["middle"] and fu["ring"] and fu["pinky"])

    fist = make_hand(index_up=False, middle_up=False, ring_up=False, pinky_up=False)
    fu = hand.fingers_up(fist)
    check("fist reads all four down",
          not fu["index"] and not fu["middle"] and not fu["ring"] and not fu["pinky"])


def test_pinch_ratio():
    open_hand = make_hand(pinch=False)
    closed_hand = make_hand(pinch=True)
    r_open = hand.pinch_ratio(open_hand, hand.THUMB_TIP, hand.INDEX_TIP)
    r_closed = hand.pinch_ratio(closed_hand, hand.THUMB_TIP, hand.INDEX_TIP)
    check("pinch ratio shrinks when tips meet", r_closed < r_open)

    scaled = scale_hand(closed_hand, 0.5)
    r_scaled = hand.pinch_ratio(scaled, hand.THUMB_TIP, hand.INDEX_TIP)
    check("pinch ratio is scale invariant", abs(r_scaled - r_closed) < 0.02)


# ---------- Posture classification and debouncing ----------

def test_classify_posture():
    def f(index=False, middle=False, ring=False, pinky=False):
        return {"index": index, "middle": middle, "ring": ring, "pinky": pinky}

    check("all four up classifies as palm",
          classify_posture(f(True, True, True, True)) == "palm")
    check("all four down classifies as fist",
          classify_posture(f(False, False, False, False)) == "fist")
    check("index and middle classifies as two_finger",
          classify_posture(f(True, True, False, False)) == "two_finger")
    check("index alone classifies as move",
          classify_posture(f(True, False, False, False)) == "move")
    check("middle alone classifies as other",
          classify_posture(f(False, True, False, False)) == "other")
    check("ring and pinky only classifies as other",
          classify_posture(f(False, False, True, True)) == "other")


def test_posture_debouncer_unit():
    deb = PostureDebouncer(need=2)
    check("first label confirms immediately", deb.feed("move") == "move")
    check("repeating the same label stays confirmed", deb.feed("move") == "move")

    # A single frame flicker to a different label must NOT flip yet.
    check("one flicker frame does not confirm", deb.feed("fist") == "move")
    # Back to the real label right away: the flicker never took hold.
    check("returning to the real label stays confirmed", deb.feed("move") == "move")

    # A genuine, sustained change confirms once it has held `need` frames.
    check("first frame of a new label does not confirm yet",
          deb.feed("palm") == "move")
    check("new label confirms on the second consecutive frame",
          deb.feed("palm") == "palm")
    check("confirmed label holds afterward", deb.feed("palm") == "palm")

    deb2 = PostureDebouncer(need=3)
    deb2.feed("move")
    check("need=3 requires three frames, not confirmed after one",
          deb2.feed("fist") == "move")
    check("need=3 not confirmed after two",
          deb2.feed("fist") == "move")
    check("need=3 confirmed after three", deb2.feed("fist") == "fist")


def test_engine_ignores_single_frame_flicker():
    # A steady MOVE hand, then exactly one noisy frame classified as a
    # fist (as if MediaPipe briefly misread a finger), then back to MOVE.
    # The reported mode must never dip to IDLE for that one bad frame.
    engine = fresh_engine()
    backend = FakeBackend()
    t = 0.0
    for _ in range(3):
        r = process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), t, True)
        t = t + 0.03
    check("settled in MOVE before the flicker", r["mode"] == "MOVE")

    flicker_hand = make_hand(index_up=False, middle_up=False, ring_up=False, pinky_up=False)
    r = process_frame(engine, backend, flicker_hand, t, True)
    check("a single noisy frame does not drop out of MOVE", r["mode"] == "MOVE")
    t = t + 0.03

    r = process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), t, True)
    check("mode is still MOVE right after the flicker clears", r["mode"] == "MOVE")


def test_engine_still_switches_on_a_real_change():
    # The debounce must not block a genuine, sustained gesture change: two
    # consecutive fist frames (need=2 default) must switch the mode.
    engine = fresh_engine()
    backend = FakeBackend()
    t = 0.0
    for _ in range(3):
        r = process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), t, True)
        t = t + 0.03
    check("settled in MOVE before the real change", r["mode"] == "MOVE")

    fist_hand = make_hand(index_up=False, middle_up=False, ring_up=False, pinky_up=False)
    r = process_frame(engine, backend, fist_hand, t, True)
    t = t + 0.03
    check("mode has not switched after only one fist frame", r["mode"] == "MOVE")
    r = process_frame(engine, backend, fist_hand, t, True)
    check("mode switches to IDLE once the fist holds for two frames", r["mode"] == "IDLE")


def test_debounce_resets_when_hand_disappears():
    # When the hand leaves and a new one appears, the very first reading
    # must apply immediately, not wait on a stale confirmed posture.
    engine = fresh_engine()
    backend = FakeBackend()
    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine, backend, None, 1.0, True)
    palm = make_hand(index_up=True, middle_up=True, ring_up=True, pinky_up=True)
    r = process_frame(engine, backend, palm, 2.0, True)
    check("a fresh hand after losing tracking classifies immediately",
          r["mode"] == "PAUSED")


# ---------- CLI ----------

def test_posture_hold_flag():
    args = build_parser().parse_args([])
    check("posture-hold defaults to 2, matching the engine default",
          args.posture_hold == 2)
    args = build_parser().parse_args(["--posture-hold", "5"])
    check("posture-hold parses a custom value", args.posture_hold == 5)
    engine = GestureEngine((1920, 1080), posture_hold_frames=args.posture_hold)
    check("the custom value reaches the debouncer", engine.posture.need == 5)


# ---------- Status hints ----------

def test_status_hints():
    check("no hand always wins the hint",
          hints.status_hint("MOVE", False, "on") == "Show your hand to the camera to begin")
    check("control off asks to press C",
          hints.status_hint("MOVE", True, "off") == "Press C to start controlling your mouse")
    check("observing also asks to press C",
          hints.status_hint("IDLE", True, "observing") == "Press C to start controlling your mouse")
    check("MOVE hint explains the pinch to click",
          "pinch" in hints.status_hint("MOVE", True, "on").lower())
    check("SCROLL hint explains moving the hand",
          "scroll" in hints.status_hint("SCROLL", True, "on").lower())
    check("PAUSED hint explains how to resume",
          "point" in hints.status_hint("PAUSED", True, "on").lower())
    check("an unknown mode still returns a usable default",
          len(hints.status_hint("SOMETHING NEW", True, "on")) > 0)


# ---------- State machine ----------

def fresh_engine():
    return GestureEngine((1920, 1080), margin=0.15)


def test_move_tracks_no_clicks():
    engine = fresh_engine()
    backend = FakeBackend()
    t = 0.0
    xs = [0.4, 0.45, 0.5, 0.55, 0.6]
    for x in xs:
        h = make_hand(index_up=True, middle_up=False, index_tip=(x, 0.5))
        process_frame(engine, backend, h, t, True)
        t = t + 0.03

    moves = []
    clicks = 0
    for call in backend.calls:
        if call[0] == "move":
            moves.append(call)
        if call[0] == "click":
            clicks = clicks + 1
    check("move posture produces move calls", len(moves) >= 3)
    check("move posture issues zero clicks", clicks == 0)
    check("cursor tracks finger to the right", moves[-1][1] > moves[0][1])


def test_quick_pinch_click_frozen():
    engine = fresh_engine()
    backend = FakeBackend()

    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.016, True)

    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), 1.0, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.7, 0.7)), 1.02, True)
    process_frame(engine, backend, make_hand(pinch=False, index_tip=(0.7, 0.7)), 1.05, True)

    left_clicks = 0
    for call in backend.calls:
        if call[0] == "click" and call[1] == "left":
            left_clicks = left_clicks + 1
    check("quick pinch issues exactly one left click", left_clicks == 1)

    moved_location = ("move", 1508, 848)  # mapped 0.7,0.7 approximately
    jumped = moved_location in backend.calls
    check("cursor did not jump to pinch moved location", not jumped)

    froze_at_center = ("move", 960, 540) in backend.calls
    check("click landed at frozen center", froze_at_center)


def test_drag_no_click():
    engine = fresh_engine()
    backend = FakeBackend()

    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), 1.0, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.55, 0.55)), 1.1, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.6, 0.6)), 1.2, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.65, 0.65)), 1.4, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.7, 0.7)), 1.5, True)
    process_frame(engine, backend, make_hand(pinch=False, index_tip=(0.7, 0.7)), 1.6, True)

    has_press = ("press", "left") in backend.calls
    has_release = ("release", "left") in backend.calls
    has_click = False
    for call in backend.calls:
        if call[0] == "click" and call[1] == "left":
            has_click = True
    check("drag presses left", has_press)
    check("drag releases left", has_release)
    check("drag does not emit a click", not has_click)


def test_double_click():
    engine = fresh_engine()
    backend = FakeBackend()

    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    # tap one
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), 1.0, True)
    process_frame(engine, backend, make_hand(pinch=False, index_tip=(0.5, 0.5)), 1.1, True)
    # release gap
    process_frame(engine, backend, make_hand(pinch=False, index_tip=(0.5, 0.5)), 1.2, True)
    # tap two within double window
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), 1.3, True)
    process_frame(engine, backend, make_hand(pinch=False, index_tip=(0.5, 0.5)), 1.4, True)

    left_clicks = 0
    for call in backend.calls:
        if call[0] == "click" and call[1] == "left":
            left_clicks = left_clicks + 1
    check("two quick taps issue two left clicks", left_clicks == 2)


def test_right_click():
    engine = fresh_engine()
    backend = FakeBackend()

    process_frame(engine, backend, make_hand(index_up=True, middle_up=True,
                                             index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine, backend, make_hand(index_up=True, middle_up=True,
                                             pinch=True, index_tip=(0.5, 0.5)), 1.0, True)
    process_frame(engine, backend, make_hand(index_up=True, middle_up=True,
                                             pinch=False, index_tip=(0.5, 0.5)), 1.1, True)

    right_clicks = 0
    left_clicks = 0
    for call in backend.calls:
        if call[0] == "click" and call[1] == "right":
            right_clicks = right_clicks + 1
        if call[0] == "click" and call[1] == "left":
            left_clicks = left_clicks + 1
    check("two finger pinch issues one right click", right_clicks == 1)
    check("two finger pinch issues no left click", left_clicks == 0)


def test_scroll_sign():
    engine = fresh_engine()
    backend = FakeBackend()
    t = 1.0

    def two(y):
        return make_hand(index_up=True, middle_up=True, index_tip=(0.5, y))

    process_frame(engine, backend, two(0.50), t, True)
    t = t + 0.06
    # tiny move under deadzone, should not scroll
    process_frame(engine, backend, two(0.49), t, True)
    t = t + 0.06
    # move up
    process_frame(engine, backend, two(0.44), t, True)
    t = t + 0.06
    process_frame(engine, backend, two(0.39), t, True)
    t = t + 0.06
    # move down
    process_frame(engine, backend, two(0.44), t, True)
    t = t + 0.06
    process_frame(engine, backend, two(0.49), t, True)

    scrolls = []
    for call in backend.calls:
        if call[0] == "scroll":
            scrolls.append(call)

    check("scroll produced ticks", len(scrolls) >= 2)
    first_up = len(scrolls) > 0 and scrolls[0][2] > 0
    saw_down = False
    for s in scrolls:
        if s[2] < 0:
            saw_down = True
    check("scroll up is positive", first_up)
    check("scroll down is negative", saw_down)
    check("scroll is not one per frame", len(scrolls) <= 4)


def test_palm_and_fist_idle():
    engine = fresh_engine()
    backend = FakeBackend()
    palm = make_hand(index_up=True, middle_up=True, ring_up=True, pinky_up=True)
    result = process_frame(engine, backend, palm, 1.0, True)
    check("palm reports PAUSED", result["mode"] == "PAUSED")
    check("palm issues zero backend calls", len(backend.calls) == 0)

    engine2 = fresh_engine()
    backend2 = FakeBackend()
    fist = make_hand(index_up=False, middle_up=False, ring_up=False, pinky_up=False)
    result2 = process_frame(engine2, backend2, fist, 1.0, True)
    check("fist reports IDLE", result2["mode"] == "IDLE")
    check("fist issues zero backend calls", len(backend2.calls) == 0)


def test_click_cooldown_held_pinch():
    engine = fresh_engine()
    backend = FakeBackend()

    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), 1.0, True)
    # hold the pinch for many frames without releasing
    hold_t = 1.0
    for i in range(20):
        hold_t = hold_t + 0.02
        process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), hold_t, True)

    left_clicks = 0
    for call in backend.calls:
        if call[0] == "click" and call[1] == "left":
            left_clicks = left_clicks + 1
    check("held pinch emits no clicks", left_clicks == 0)


def test_no_hand_safe():
    engine = fresh_engine()
    backend = FakeBackend()
    result = process_frame(engine, backend, None, 1.0, True)
    check("no hand reports IDLE", result["mode"] == "IDLE")
    check("no hand issues zero backend calls", len(backend.calls) == 0)


def test_toggle_off_mid_drag_releases():
    # Start a real drag while control is on, then pause with the toggle.
    # The physical button must be released so pausing never traps the user.
    engine = fresh_engine()
    backend = FakeBackend()

    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), 1.0, True)
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.55, 0.55)), 1.4, True)
    check("drag is active before pause", engine.dragging is True)
    pressed = ("press", "left") in backend.calls
    check("drag pressed the button", pressed)

    new_state = toggle_control(True, engine, backend)
    check("toggle turns control off", new_state is False)
    check("toggle clears the drag flag", engine.dragging is False)
    check("toggle released the stuck button", ("release", "left") in backend.calls)


def test_apply_result_off_is_zero_action():
    # A rich result while control is off must reach the backend zero times.
    backend = FakeBackend()
    loaded = {
        "target": (100, 200),
        "press": "left",
        "release": "left",
        "actions": [("left_click",), ("right_click",), ("scroll", 1)],
    }
    apply_result(loaded, backend, False)
    check("apply_result with control off issues zero calls", len(backend.calls) == 0)


class BoomBackend(FakeBackend):
    # Fails on every action, to prove one bad pynput call cannot kill a frame.
    def move(self, x, y):
        raise RuntimeError("move failed")

    def click(self, button):
        raise RuntimeError("click failed")

    def scroll(self, dx, dy):
        raise RuntimeError("scroll failed")


def test_backend_failure_does_not_propagate():
    backend = BoomBackend()
    loaded = {
        "target": (10, 20),
        "press": None,
        "release": None,
        "actions": [("left_click",), ("scroll", 1)],
    }
    ok = True
    try:
        apply_result(loaded, backend, True)
    except Exception:
        ok = False
    check("failing backend calls are swallowed, not raised", ok)


def _res(mode="IDLE", actions=None):
    return {"mode": mode, "actions": actions or [], "fingers": {},
            "pinch_ratio": 0.0, "target": None}


def test_tutorial_flow():
    tf = TutorialFlow()

    info = tf.update(False, _res(), 0.0)
    check("tutorial starts on the hand step", info["id"] == "hand")
    info = tf.update(False, _res(), 5.0)
    check("no hand does not advance the tutorial", info["id"] == "hand")

    tf.update(True, _res("PAUSED"), 5.0)
    info = tf.update(True, _res("PAUSED"), 5.5)
    check("hand step completes and celebrates", info["celebrating"] is True)
    info = tf.update(True, _res("PAUSED"), 6.5)
    check("tutorial advances to the move step", info["id"] == "move")

    tf.update(True, _res("IDLE"), 6.6)
    info = tf.update(True, _res("IDLE"), 8.0)
    check("wrong posture does not finish the move step",
          info["id"] == "move" and not info["celebrating"])

    tf.update(True, _res("MOVE"), 8.0)
    info = tf.update(True, _res("MOVE"), 9.2)
    check("move step completes when MOVE is held", info["celebrating"] is True)
    info = tf.update(True, _res(), 10.3)
    check("tutorial advances to the click step", info["id"] == "click")

    info = tf.update(True, _res("MOVE", [("left_click",)]), 10.4)
    check("click step completes on a left_click action", info["celebrating"] is True)
    info = tf.update(True, _res(), 11.5)
    check("tutorial advances to the scroll step", info["id"] == "scroll")

    info = tf.update(True, _res("SCROLL", [("scroll", 1)]), 11.6)
    check("scroll step completes on a scroll action", info["celebrating"] is True)
    info = tf.update(True, _res(), 12.7)
    check("tutorial advances to the pause step", info["id"] == "pause")

    tf.update(True, _res("PAUSED"), 12.8)
    info = tf.update(True, _res("PAUSED"), 13.7)
    check("pause step completes when palm is held", info["celebrating"] is True)
    info = tf.update(True, _res(), 14.8)
    check("tutorial reaches done and is finished",
          info["id"] == "done" and tf.finished is True)


def test_tutorial_skip():
    tf = TutorialFlow()
    tf.skip()
    check("skip marks the tutorial finished", tf.finished is True)
    info = tf.update(True, _res(), 1.0)
    check("skip lands on the done screen", info["id"] == "done")


def test_tutorial_blocks_the_mouse():
    # Mirrors the main loop contract: while the tutorial is active the
    # applied control is forced off, so a real pinch must move the mouse
    # zero times. After control is on, the same pinch clicks.
    engine = fresh_engine()
    backend = FakeBackend()
    tf = TutorialFlow()

    t = 0.0
    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), t, False)
    t = 1.0
    process_frame(engine, backend, make_hand(pinch=True, index_tip=(0.5, 0.5)), t, False)
    t = 1.1
    process_frame(engine, backend, make_hand(index_tip=(0.5, 0.5)), t, False)
    check("tutorial (control off) issues zero mouse calls on a pinch",
          len(backend.calls) == 0)

    # Now control is on, the same pinch cycle should click once.
    engine2 = fresh_engine()
    backend2 = FakeBackend()
    process_frame(engine2, backend2, make_hand(index_tip=(0.5, 0.5)), 0.0, True)
    process_frame(engine2, backend2, make_hand(pinch=True, index_tip=(0.5, 0.5)), 0.1, True)
    process_frame(engine2, backend2, make_hand(index_tip=(0.5, 0.5)), 0.2, True)
    clicks = 0
    for call in backend2.calls:
        if call[0] == "click" and call[1] == "left":
            clicks = clicks + 1
    check("control on issues exactly one click on the same pinch", clicks == 1)


def run_all():
    test_euro_noise()
    test_euro_ramp()
    test_mapping()
    test_fingers()
    test_pinch_ratio()
    test_classify_posture()
    test_posture_debouncer_unit()
    test_engine_ignores_single_frame_flicker()
    test_engine_still_switches_on_a_real_change()
    test_debounce_resets_when_hand_disappears()
    test_posture_hold_flag()
    test_status_hints()
    test_move_tracks_no_clicks()
    test_quick_pinch_click_frozen()
    test_drag_no_click()
    test_double_click()
    test_right_click()
    test_scroll_sign()
    test_palm_and_fist_idle()
    test_click_cooldown_held_pinch()
    test_no_hand_safe()
    test_toggle_off_mid_drag_releases()
    test_apply_result_off_is_zero_action()
    test_backend_failure_does_not_propagate()
    test_tutorial_flow()
    test_tutorial_skip()
    test_tutorial_blocks_the_mouse()

    print("")
    print("TOTAL " + str(PASSED + FAILED) + "  PASS " + str(PASSED) + "  FAIL " + str(FAILED))
    if FAILED == 0:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
