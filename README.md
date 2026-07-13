# AirCursor

A touch free mouse. Control the real OS cursor with your bare hand through a webcam.

## Why this matters

Not every situation lets you touch a mouse. AirCursor is built as a real accessibility and convenience product:

- Hands free control for people with limited mobility or repetitive strain injury.
- Sterile settings (surgery prep, labs, kitchens) where touching hardware is a problem.
- Presentations and demos where you want to drive a screen from across the room.
- A clean, camera only input path that needs no wearable and no extra hardware.

The whole point is that it stays usable. A jittery cursor is worthless, so the smoothing, the click precision, and the anti spam logic are treated as the core of the product, not extras.

## Features

- Real OS cursor control from a single webcam, no gloves or markers.
- One Euro Filter smoothing so the cursor is calm when still and responsive when you move.
- Click freeze: the cursor locks in place the instant you start a pinch, so clicks land exactly where you aimed.
- A clean gesture vocabulary: move, left click, double click, drag, right click, scroll, and pause.
- Debounced state machines so a held pinch never machine guns clicks.
- An interactive onboarding tutorial that teaches every gesture before the mouse is ever controlled.
- A polished dark HUD with mode, finger indicators, a pinch meter, and a control pill.
- A hard safety layer: the keyboard can always pause control, even while the hand is driving the mouse.
- Fully testable core: the mouse is behind a backend interface, so the gesture logic runs headless with a fake mouse.

## Quick start

Windows 11, Python 3.12.

```
cd C:\Users\ssg79\OneDrive\Desktop\AirCursor
py -3.12 -m pip install -r requirements.txt
py -3.12 main.py
```

On the first run an interactive tutorial teaches you every gesture one at a time. Your mouse is NOT controlled during the tutorial, so you can practice safely. It walks you through: show your hand, point to move, pinch to click, two fingers to scroll, open palm to pause. When you finish, press SPACE to take control of your mouse.

- Press S at any time to skip the tutorial.
- Add `--skip-tutorial` to go straight to the app (it opens with control off, press C to take over).

Once in the app, control starts OFF for safety. A banner tells you to press C to start driving your mouse.

## Gestures

| Gesture | Posture | What it does |
|---|---|---|
| Move | Index up, middle down | Cursor follows your index fingertip |
| Left click | Move posture, quick thumb to index pinch and release | Single click at the frozen position |
| Double click | Move posture, two quick pinch taps | Two clicks, which the OS reads as a double click |
| Drag | Move posture, pinch and hold past 0.35s | Presses the button, drags while held, releases on unpinch |
| Right click | Two fingers up (index plus middle), pinch tap | Single right click |
| Scroll | Two fingers up, move the hand up or down | Scrolls, up is positive, with a deadzone so it steps smoothly |
| Pause | Open palm (all four fingers up) | Freezes the cursor, no actions |
| Idle | Fist (all four fingers down) | Freezes the cursor, no actions |

## Controls

| Key | Action |
|---|---|
| SPACE | Finish the tutorial and take control of your mouse |
| S | Skip the tutorial |
| C | Toggle control on and off |
| Ctrl + Alt + H | Global hotkey to toggle control, works even when the cursor is being driven |
| F | Toggle fullscreen |
| H | Toggle the on screen gesture legend |
| Q or ESC | Quit |

## How it works

- MediaPipe Hands (classic solutions API, `mp.solutions.hands`) finds 21 hand landmarks per frame from the mirrored webcam image.
- Finger up and down states come from comparing each fingertip to its pip joint. A thumb to index pinch is measured as a distance normalized by hand size, so it works the same near or far from the camera.
- The chosen fingertip is mapped from an inner active region of the frame to the full screen, so you never have to reach the edge of view to reach the edge of the screen.
- The mapped screen coordinates are run through a One Euro Filter (one instance per axis). This is the single most important piece. It removes jitter when the hand is still and keeps lag low when the hand moves.
- Click precision comes from a freeze: the moment a pinch begins the cursor is pinned to its pre pinch position, so the finger motion of pinching cannot drag the cursor off target. It unfreezes when the pinch ends or a drag begins.
- A gesture state machine turns postures and pinch edges into discrete actions, with cooldowns and hysteresis so nothing spams. The state machine is pure logic and does not touch the mouse. The main loop applies its output to a mouse backend.
- Safety: control can always be paused from the keyboard, including a global Ctrl + Alt + H hotkey, so a hand driven cursor can never trap you.

## Tuning

| Flag | Meaning |
|---|---|
| `--smooth` | One Euro min_cutoff. Lower is smoother but laggier, higher is snappier but noisier. Default 1.2 |
| `--beta` | One Euro beta. Higher cuts lag on fast motion. Default 0.03 |
| `--margin` | Active region margin. Smaller means a smaller hand motion covers the screen. Default 0.15 |
| `--debug` | Show raw numbers (pinch ratio, target, finger bits) on the HUD |
| `--no-control` | Run the full pipeline and HUD but do not move the real mouse, so you can observe first |
| `--camera` | Camera index, default 0 |

## Scalability and roadmap

- Two hand support: one hand drives, the other issues modifier gestures.
- A gesture recorder so users can bind custom postures to shortcuts.
- Multi monitor mapping with a per display active region.
- A profile system that saves per user smoothing and margin settings.
- Optional Kalman fusion for even steadier tracking under poor lighting.
- A tray app front end so it launches without a terminal.

## Tests

Headless, no camera, no window, no real mouse.

```
py -3.12 tests/smoke_test.py
```

## Notes

- MediaPipe is pinned to 0.10.21 and numpy to below 2, which is the verified combination for this build.
- License: MIT.
