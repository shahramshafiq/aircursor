"""AirCursor: a touch free mouse driven by hand gestures through a webcam.

Real time pipeline: capture, mirror, MediaPipe hands, gesture engine,
then apply the engine result to a mouse backend and draw the HUD. The
mouse is only ever moved through the backend, which lets the whole engine
be unit tested with a fake backend and no camera.

Safety: control starts on (or observing with --no-control) and can always
be paused from the keyboard with the C key or the global Ctrl+Alt+H
hotkey, so a hand driven cursor can never trap the user.
"""

import argparse
import sys
import time

from backends import PynputBackend
from gestures import GestureEngine
import hud


def apply_result(result, backend, control_on):
    """Perform one engine result on the backend. Returns nothing.

    Move first (so a frozen click position is set before the click lands),
    then press or release for drags, then the discrete actions.

    Every backend call is wrapped: on the real machine a single failing
    pynput move, click, or scroll (which can happen on some platforms or
    when a display drops) must never take down the whole capture loop.

    When control is off this issues ZERO backend calls and returns at once,
    which is what makes --no-control and a paused session truly hands off.
    """
    if not control_on:
        return

    target = result.get("target", None)
    if target is not None:
        try:
            backend.move(target[0], target[1])
        except Exception:
            pass

    if result.get("press", None) == "left":
        try:
            backend.press("left")
        except Exception:
            pass
    if result.get("release", None) == "left":
        try:
            backend.release("left")
        except Exception:
            pass

    for action in result.get("actions", []):
        name = action[0]
        try:
            if name == "left_click":
                backend.click("left")
            elif name == "right_click":
                backend.click("right")
            elif name == "scroll":
                backend.scroll(0, action[1])
        except Exception:
            pass


def toggle_control(control_on, engine, backend):
    """Flip control on or off, returning the new state.

    Safety critical: if control is being turned OFF while a drag is
    physically held down, release the button first. Otherwise the release
    edge the engine emits later would be swallowed by apply_result (control
    is off), leaving the real mouse button stuck down and the user trapped.
    """
    if control_on and getattr(engine, "dragging", False):
        try:
            backend.release("left")
        except Exception:
            pass
        engine.dragging = False
    return not control_on


def process_frame(engine, backend, landmarks, now, control_on):
    """Drive the engine for one frame and apply it. Testable without cv2."""
    result = engine.update(landmarks, now)
    apply_result(result, backend, control_on)
    return result


def _screen_to_view(target, screen_size, view_w, view_h):
    """Map a screen pixel target back into camera view pixels for the dot."""
    if target is None:
        return None
    sw, sh = screen_size
    if sw <= 0 or sh <= 0:
        return None
    vx = target[0] / sw * view_w
    vy = target[1] / sh * view_h
    return (vx, vy)


def build_parser():
    parser = argparse.ArgumentParser(description="AirCursor hand gesture mouse")
    parser.add_argument("--camera", type=int, default=0, help="camera index")
    parser.add_argument("--smooth", type=float, default=1.2,
                        help="One Euro min_cutoff, lower is smoother and laggier")
    parser.add_argument("--beta", type=float, default=0.03,
                        help="One Euro beta, higher reduces lag on fast motion")
    parser.add_argument("--margin", type=float, default=0.15,
                        help="active region margin, smaller needs bigger hand motion")
    parser.add_argument("--debug", action="store_true",
                        help="show raw numbers on the HUD")
    parser.add_argument("--no-control", action="store_true",
                        help="run the full pipeline and HUD but do not move the real mouse")
    return parser


def main():
    args = build_parser().parse_args()

    import cv2
    import mediapipe as mp

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("Camera not found. Check the --camera index and that no other app is using it.")
        return 1
    # Ask for 720p for a cleaner demo and consistent HUD layout. If the
    # webcam does not support it, it silently keeps its native resolution.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    backend = PynputBackend()
    screen_size = backend.screen_size
    engine = GestureEngine(
        screen_size,
        margin=args.margin,
        min_cutoff=args.smooth,
        beta=args.beta,
    )

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.6,
        model_complexity=1,
    )

    control_on = not args.no_control
    observing = args.no_control

    # Numbers surfaced on the debug HUD so the app can be tuned live.
    tunables = {
        "smooth": args.smooth,
        "beta": args.beta,
        "margin": args.margin,
        "pinch_on": engine.pinch_on,
        "pinch_off": engine.pinch_off,
    }

    # Gesture legend shows on first run, then auto hides so the demo stays
    # clean. H toggles it and cancels the auto hide.
    legend_on = True
    auto_hide_at = time.time() + 12.0

    print("AirCursor running.")
    print("Gestures: point = move, pinch = click, hold pinch = drag,")
    print("          two fingers = scroll, two + pinch = right click,")
    print("          open palm = pause, fist = idle.")
    print("Keys: C control, F fullscreen, H legend, Q quit. Global pause Ctrl+Alt+H.")

    # Global hotkey so the user can always regain the mouse.
    listener = None
    state = {"toggle": False}

    def on_hotkey():
        state["toggle"] = True

    try:
        from pynput import keyboard
        listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+h": on_hotkey})
        listener.start()
    except Exception:
        listener = None

    window = "AirCursor"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    fullscreen = False

    prev_time = time.time()
    fps = 0.0
    exit_code = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Lost the camera feed. Exiting.")
                exit_code = 1
                break

            frame = cv2.flip(frame, 1)
            view_h, view_w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            processed = hands.process(rgb)

            now = time.time()
            gap = now - prev_time
            if gap > 1e-6:
                fps = 0.9 * fps + 0.1 * (1.0 / gap)
            prev_time = now

            landmarks = None
            if processed.multi_hand_landmarks:
                hand_lms = processed.multi_hand_landmarks[0]
                landmarks = hand_lms.landmark
                mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

            if state["toggle"]:
                state["toggle"] = False
                control_on = toggle_control(control_on, engine, backend)
                observing = False

            result = process_frame(engine, backend, landmarks, now, control_on)

            if control_on:
                control_state = "on"
            elif observing:
                control_state = "observing"
            else:
                control_state = "off"

            # Prefer the engine target for the dot, but when there is no
            # target this frame (scroll, idle, pause) fall back to the last
            # smoothed live position so the cursor dot never blinks out. This
            # is purely visual and does not move the real mouse.
            dot_target = result.get("target", None)
            if dot_target is None:
                dot_target = getattr(engine, "last_smoothed", None)
            dot = _screen_to_view(dot_target, screen_size, view_w, view_h)

            if legend_on and auto_hide_at is not None and now >= auto_hide_at:
                legend_on = False

            hud.draw_hud(frame, result, control_state, fps, dot,
                         debug=args.debug, show_legend=legend_on,
                         pinch_on=engine.pinch_on, pinch_off=engine.pinch_off,
                         tunables=tunables)

            cv2.imshow(window, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
            elif key == ord("c"):
                control_on = toggle_control(control_on, engine, backend)
                observing = False
            elif key == ord("h"):
                legend_on = not legend_on
                auto_hide_at = None
            elif key == ord("f"):
                fullscreen = not fullscreen
                if fullscreen:
                    cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN,
                                          cv2.WINDOW_FULLSCREEN)
                else:
                    cv2.setWindowProperty(window, cv2.WND_PROP_FULLSCREEN,
                                          cv2.WINDOW_NORMAL)
    finally:
        # If a drag was mid press, let go so the mouse is not stuck down.
        # Only release when control is on: that is the only state in which a
        # press ever reached the real mouse, so this stays zero action in
        # observe or paused mode (toggle_control already handled pause).
        if control_on and getattr(engine, "dragging", False):
            try:
                backend.release("left")
            except Exception:
                pass
        # Each cleanup step is independent so one failure cannot skip the
        # rest, above all stopping the global keyboard listener.
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        try:
            cap.release()
        except Exception:
            pass
        try:
            hands.close()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
