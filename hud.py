"""Heads up display drawing. All cv2 rendering lives here.

Dark glass panels via addWeighted, one cyan accent, a mode readout, finger
indicators, a pinch meter with the click/release thresholds marked, a
control pill, the mapped cursor dot, a toggleable gesture legend, and a
compact key strip. Kept visual so the app looks like a finished product.
"""

import cv2

import hints

ACCENT = (255, 200, 40)      # electric cyan in BGR
PANEL = (28, 28, 28)
WHITE = (240, 240, 240)
GREY = (150, 150, 150)
DIM = (90, 90, 90)
GREEN = (90, 220, 120)
RED = (80, 80, 235)


def _panel(frame, x1, y1, x2, y2, alpha=0.55):
    h, w = frame.shape[:2]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return
    slab = frame[y1:y2, x1:x2].copy()
    box = slab.copy()
    box[:] = PANEL
    blended = cv2.addWeighted(box, alpha, slab, 1.0 - alpha, 0)
    frame[y1:y2, x1:x2] = blended


# Gesture legend rows: (gesture, what it does). Drives the on screen legend
# so a first run user can tell every gesture without reading the docs.
LEGEND = [
    ("Point", "move cursor"),
    ("Pinch", "left click"),
    ("Hold pinch", "drag"),
    ("Two fingers", "scroll up / down"),
    ("Two + pinch", "right click"),
    ("Open palm", "pause control"),
    ("Fist", "idle / stop"),
]


def _draw_legend(frame):
    h, w = frame.shape[:2]
    x1 = w - 296
    y1 = 108
    row_h = 32
    y2 = y1 + 44 + row_h * len(LEGEND)
    _panel(frame, x1, y1, w - 16, y2, alpha=0.6)
    cv2.putText(frame, "GESTURES", (x1 + 16, y1 + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, GREY, 1, cv2.LINE_AA)
    yy = y1 + 30 + row_h
    for name, action in LEGEND:
        cv2.putText(frame, name, (x1 + 16, yy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, ACCENT, 1, cv2.LINE_AA)
        cv2.putText(frame, action, (x1 + 150, yy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1, cv2.LINE_AA)
        yy = yy + row_h


def _threshold_tick(frame, bar_x1, bar_x2, bar_y, thresh, color):
    if thresh is None:
        return
    t = thresh
    if t < 0.0:
        t = 0.0
    if t > 1.0:
        t = 1.0
    tx = int(bar_x1 + (1.0 - t) * (bar_x2 - bar_x1))
    cv2.line(frame, (tx, bar_y - 11), (tx, bar_y + 11), color, 2, cv2.LINE_AA)


def _rounded_panel(frame, x1, y1, x2, y2, alpha=0.72):
    # a slightly darker, more solid card for the tutorial so instructions
    # are easy to read over a busy camera image
    h, w = frame.shape[:2]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return
    slab = frame[y1:y2, x1:x2].copy()
    box = slab.copy()
    box[:] = (18, 18, 18)
    frame[y1:y2, x1:x2] = cv2.addWeighted(box, alpha, slab, 1.0 - alpha, 0)
    cv2.rectangle(frame, (x1, y1), (x2 - 1, y1 + 4), ACCENT, -1)


def _center_text(frame, text, cy, font, scale, color, thick):
    w = frame.shape[1]
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    cv2.putText(frame, text, ((w - tw) // 2, cy), font, scale, color, thick, cv2.LINE_AA)


def draw_tutorial(frame, info, has_hand):
    """Big friendly onboarding card. Teaches one gesture at a time."""
    h, w = frame.shape[:2]
    pw = min(760, w - 60)
    ph = 260
    x1 = (w - pw) // 2
    y1 = h - ph - 40
    x2 = x1 + pw
    y2 = y1 + ph
    _rounded_panel(frame, x1, y1, x2, y2)

    finished = info.get("finished", False)
    if not finished:
        tag = "STEP " + str(info["index"] + 1) + " OF " + str(info["total"])
        cv2.putText(frame, tag, (x1 + 30, y1 + 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, GREY, 1, cv2.LINE_AA)

    if info.get("celebrating", False):
        _center_text(frame, "NICE!", y1 + 110, cv2.FONT_HERSHEY_DUPLEX, 1.6, GREEN, 3)
        cx = w // 2
        cv2.circle(frame, (cx, y1 + 165), 26, GREEN, 3, cv2.LINE_AA)
        cv2.line(frame, (cx - 12, y1 + 165), (cx - 3, y1 + 175), GREEN, 3, cv2.LINE_AA)
        cv2.line(frame, (cx - 3, y1 + 175), (cx + 14, y1 + 153), GREEN, 3, cv2.LINE_AA)
        return frame

    _center_text(frame, info["title"], y1 + 100, cv2.FONT_HERSHEY_DUPLEX, 1.2, ACCENT, 2)
    _center_text(frame, info["body"], y1 + 150, cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 1)

    if finished:
        _center_text(frame, "Press  SPACE  to control your mouse",
                     y1 + 210, cv2.FONT_HERSHEY_SIMPLEX, 0.7, GREEN, 2)
    else:
        # progress bar for held gestures
        bar_x1 = x1 + 30
        bar_x2 = x2 - 30
        bar_y = y2 - 46
        cv2.rectangle(frame, (bar_x1, bar_y - 7), (bar_x2, bar_y + 7), DIM, 1)
        fill = int(bar_x1 + info.get("progress", 0.0) * (bar_x2 - bar_x1))
        if fill > bar_x1:
            cv2.rectangle(frame, (bar_x1, bar_y - 7), (fill, bar_y + 7), ACCENT, -1)
        if not has_hand:
            _center_text(frame, "no hand detected", y2 - 16,
                         cv2.FONT_HERSHEY_SIMPLEX, 0.5, RED, 1)
        else:
            _center_text(frame, "press  S  to skip the tutorial", y2 - 16,
                         cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREY, 1)

    # progress dots along the top of the card
    total = info.get("total", 5)
    idx = info.get("index", 0)
    dot_gap = 26
    start_x = w // 2 - (total - 1) * dot_gap // 2
    for i in range(total):
        col = ACCENT if i <= idx else DIM
        cv2.circle(frame, (start_x + i * dot_gap, y1 + 30), 5, col, -1, cv2.LINE_AA)
    return frame


def draw_hud(frame, result, control_state, fps, mapped_dot, has_hand=True,
             debug=False, show_legend=True, pinch_on=None, pinch_off=None,
             tunables=None):
    """control_state is one of 'on', 'off', 'observing'.

    has_hand drives the single status hint line: a plain English sentence
    that always tells a forgetful or non technical user what to do right
    now, so they never have to remember the gesture list.
    pinch_on / pinch_off draw click and release marks on the pinch meter.
    tunables is an optional dict of numbers shown only in debug mode.
    """
    h, w = frame.shape[:2]
    mode = result.get("mode", "IDLE")
    fingers = result.get("fingers", {})
    ratio = result.get("pinch_ratio", 0.0)

    # Top mode panel
    _panel(frame, 16, 16, 360, 96)
    cv2.putText(frame, "MODE", (32, 44), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, GREY, 1, cv2.LINE_AA)
    cv2.putText(frame, mode, (32, 82), cv2.FONT_HERSHEY_DUPLEX,
                1.0, ACCENT, 2, cv2.LINE_AA)

    # FPS small, top right
    fps_text = "FPS " + str(int(fps))
    cv2.putText(frame, fps_text, (w - 120, 40), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, GREY, 1, cv2.LINE_AA)

    # Control pill top right under fps
    if control_state == "on":
        pill_text = "CONTROL ON"
        pill_col = GREEN
    elif control_state == "observing":
        pill_text = "OBSERVING"
        pill_col = ACCENT
    else:
        pill_text = "CONTROL OFF"
        pill_col = RED
    _panel(frame, w - 200, 56, w - 20, 92)
    cv2.putText(frame, pill_text, (w - 190, 80), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, pill_col, 1, cv2.LINE_AA)

    # Finger indicators
    _panel(frame, 16, 108, 360, 168)
    labels = ["I", "M", "R", "P"]
    keys = ["index", "middle", "ring", "pinky"]
    base_x = 40
    for i in range(len(keys)):
        cx = base_x + i * 70
        up = fingers.get(keys[i], False)
        col = ACCENT if up else DIM
        cv2.circle(frame, (cx, 138), 16, col, -1, cv2.LINE_AA)
        cv2.putText(frame, labels[i], (cx - 7, 144), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (20, 20, 20), 2, cv2.LINE_AA)

    # Pinch meter bar
    _panel(frame, 16, 180, 360, 224)
    cv2.putText(frame, "PINCH", (32, 208), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, GREY, 1, cv2.LINE_AA)
    bar_x1 = 120
    bar_x2 = 344
    bar_y = 202
    cv2.rectangle(frame, (bar_x1, bar_y - 8), (bar_x2, bar_y + 8), DIM, 1)
    # ratio near 0 means fully pinched; clamp for display
    display = ratio
    if display > 1.0:
        display = 1.0
    if display < 0.0:
        display = 0.0
    fill = int(bar_x1 + (1.0 - display) * (bar_x2 - bar_x1))
    cv2.rectangle(frame, (bar_x1, bar_y - 8), (fill, bar_y + 8), ACCENT, -1)
    # Mark where a pinch registers (green) and where it releases (grey), so
    # the user can see exactly when a click will fire.
    _threshold_tick(frame, bar_x1, bar_x2, bar_y, pinch_on, GREEN)
    _threshold_tick(frame, bar_x1, bar_x2, bar_y, pinch_off, GREY)

    # Gesture legend, right side, toggleable
    if show_legend:
        _draw_legend(frame)

    # Mapped cursor dot inside the cam view
    if mapped_dot is not None:
        dx, dy = mapped_dot
        cv2.circle(frame, (int(dx), int(dy)), 9, ACCENT, 2, cv2.LINE_AA)
        cv2.circle(frame, (int(dx), int(dy)), 2, WHITE, -1, cv2.LINE_AA)

    # One line, always visible, that says what to do right now. This is the
    # main defense against a user forgetting the gestures: they never have
    # to remember anything or hunt for the legend, they just read this.
    # Urgent cases (no hand, or control is off) get a bigger, brighter
    # banner since those block everything else; an in mode tip is quieter.
    urgent = (not has_hand) or (control_state != "on")
    hint_text = hints.status_hint(mode, has_hand, control_state)
    scale = 0.8 if urgent else 0.6
    thick = 2 if urgent else 1
    color = ACCENT if urgent else WHITE
    panel_h = 52 if urgent else 40
    (tw, th), _ = cv2.getTextSize(hint_text, cv2.FONT_HERSHEY_DUPLEX, scale, thick)
    bx1 = (w - tw) // 2 - 24
    bx2 = (w + tw) // 2 + 24
    by = 92
    _panel(frame, bx1, by, bx2, by + panel_h, alpha=0.7)
    cv2.putText(frame, hint_text, ((w - tw) // 2, by + panel_h - 18),
                cv2.FONT_HERSHEY_DUPLEX, scale, color, thick, cv2.LINE_AA)

    # Bottom key strip, short and readable
    _panel(frame, 16, h - 52, w - 16, h - 16, alpha=0.5)
    keys_hint = ("[C] control   [T] replay tutorial   [H] legend   [F] full screen"
                 "   [Q] quit        Ctrl+Alt+H  global pause")
    cv2.putText(frame, keys_hint, (28, h - 28), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, WHITE, 1, cv2.LINE_AA)

    # Watermark
    cv2.putText(frame, "SHAHRAM SHAFIQ", (w - 220, h - 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, DIM, 1, cv2.LINE_AA)

    if debug:
        target = result.get("target", None)
        lines = []
        lines.append("ratio " + ("%.3f" % ratio))
        if target is not None:
            lines.append("target " + str(int(target[0])) + "," + str(int(target[1])))
        else:
            lines.append("target none")
        up_list = ""
        for k in keys:
            up_list = up_list + k[0].upper() + ("1" if fingers.get(k, False) else "0") + " "
        lines.append(up_list.strip())
        if tunables is not None:
            lines.append("smooth %.2f  beta %.3f" % (
                tunables.get("smooth", 0.0), tunables.get("beta", 0.0)))
            lines.append("margin %.2f  pinch %.2f/%.2f" % (
                tunables.get("margin", 0.0),
                tunables.get("pinch_on", 0.0),
                tunables.get("pinch_off", 0.0)))
            lines.append("posture hold %d frames" % tunables.get("posture_hold", 0))
        yy = 260
        _panel(frame, 16, 236, 360, 236 + 26 * len(lines) + 12)
        for ln in lines:
            cv2.putText(frame, ln, (32, yy), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, WHITE, 1, cv2.LINE_AA)
            yy = yy + 26

    return frame
