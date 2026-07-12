"""Heads up display drawing. All cv2 rendering lives here.

Dark glass panels via addWeighted, one cyan accent, a mode readout, finger
indicators, a pinch meter with the click/release thresholds marked, a
control pill, the mapped cursor dot, a toggleable gesture legend, and a
compact key strip. Kept visual so the app looks like a finished product.
"""

import cv2

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


def draw_hud(frame, result, control_state, fps, mapped_dot, debug=False,
             show_legend=True, pinch_on=None, pinch_off=None, tunables=None):
    """control_state is one of 'on', 'off', 'observing'.

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

    # Bottom key strip, short and readable
    _panel(frame, 16, h - 52, w - 16, h - 16, alpha=0.5)
    keys_hint = ("[C] control   [F] fullscreen   [H] legend   [Q] quit"
                 "        Ctrl+Alt+H  global pause")
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
        yy = 260
        _panel(frame, 16, 236, 360, 236 + 26 * len(lines) + 12)
        for ln in lines:
            cv2.putText(frame, ln, (32, yy), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, WHITE, 1, cv2.LINE_AA)
            yy = yy + 26

    return frame
