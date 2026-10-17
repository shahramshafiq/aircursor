<div align="center">

# AirCursor

Control your computer's mouse with your bare hand through a webcam, with no touch and no extra hardware.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.21-0097A7?style=flat-square&logo=google&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white)

</div>

## Overview

AirCursor is a touch-free mouse. It reads your hand from a single webcam with MediaPipe Hands, turns finger postures and pinches into mouse actions, and drives the real OS cursor. It is aimed at situations where touching a mouse is impractical, such as limited mobility, sterile environments, or presenting from across a room. A jittery cursor is unusable, so smoothing, click precision and anti-spam logic are treated as the core of the project.

## Key Features

- **Real OS cursor control** from one webcam, with no gloves or markers. The mouse is moved through `pynput`.
- **One Euro Filter smoothing** (one filter per axis), so the cursor stays calm when your hand is still and responsive when it moves.
- **Click freeze:** the cursor is pinned to its pre-pinch position the moment a pinch starts, so the finger motion of pinching cannot pull the click off target.
- **Posture lock during a pinch:** the confirmed posture is frozen for the whole pinch, so the natural finger curl of pinching cannot flip the mode and drop the click. A posture is also debounced and only takes effect after it holds for a set number of frames (default 2).
- **Full mouse vocabulary:** move, left click, double click, drag, right click, scroll and pause, with cooldowns and hysteresis so a held pinch never repeats clicks.
- **Interactive onboarding tutorial** that teaches each gesture with the mouse disconnected. It can be replayed at any time with `T`.
- **Safe by default:** control starts OFF, and a keyboard pause (`C` or the global `Ctrl+Alt+H` hotkey) always works, including mid-drag, where the held button is released first.
- **Live feedback HUD:** current mode, finger indicators, a pinch meter with click and release marks, a control status pill, a plain-English hint line, and a beep plus on-screen flash on every click.

## Tech Stack

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| Hand tracking | MediaPipe Hands 0.10.21 (classic `mp.solutions.hands` API, 21 landmarks per frame) |
| Video and HUD | OpenCV (DirectShow capture, on-screen display) |
| Mouse and hotkey | pynput (cursor, clicks, scroll, global hotkey) |
| Smoothing | One Euro Filter (Casiez, Roussel, Vogel 2012), implemented in `euro_filter.py` |
| Screen size | screeninfo, with a tkinter fallback |
| Numerics | NumPy, pinned below 2 for MediaPipe compatibility |
| Click sound | `winsound` (Windows standard library) |
| Testing | Plain Python smoke tests with a fake mouse backend |

## Project Structure

```text
aircursor/
  main.py              Entry point: webcam loop, key handling, safety toggles, CLI flags
  gestures.py          Gesture state machine: posture debounce, pinch, click, drag, scroll
  hand.py              MediaPipe landmark helpers: finger up/down state, pinch ratio
  euro_filter.py       One Euro Filter used to smooth the fingertip position
  mapping.py           Maps the inner active region of the frame to full screen coordinates
  backends.py          Mouse backend interface, pynput backend, fake backend for tests
  tutorial.py          Onboarding tutorial state machine
  hints.py             Plain-English "what to do now" hint line
  hud.py               OpenCV drawing: mode, fingers, pinch meter, legend, click flash
  tests/
    smoke_test.py      Headless tests: no camera, no window, no real mouse
  requirements.txt     Pinned dependencies
```

## Getting Started

### Prerequisites

- Windows (camera capture uses DirectShow and the click beep uses `winsound`)
- Python 3.12
- A webcam

No environment variables are required.

### Installation

```bash
git clone https://github.com/shahramshafiq/aircursor.git
cd aircursor
py -3.12 -m pip install -r requirements.txt
```

### Run

```bash
py -3.12 main.py
```

On first run an interactive tutorial walks through every gesture: show your hand, point to move, pinch to click, two fingers to scroll, open palm to pause. The mouse is NOT controlled during the tutorial. When it finishes, press `SPACE` to take control.

## Usage

### Gestures

| Gesture | Posture | Action |
|---|---|---|
| Move | Index finger up, middle finger down | Cursor follows the index fingertip |
| Left click | Move posture, quick thumb-to-index pinch and release | Click at the frozen position |
| Double click | Move posture, two quick pinch taps | Two clicks that the OS reads as a double click |
| Drag | Move posture, pinch and hold longer than 0.35 s | Presses the button, drags while held, releases on unpinch |
| Right click | Index and middle fingers up, pinch tap | Single right click |
| Scroll | Index and middle fingers up, move the hand up or down | Scrolls in steps, with a deadzone |
| Pause | Open palm (all four fingers up) | Cursor frozen, no actions |
| Idle | Fist (all four fingers down) | Cursor frozen, no actions |

### Keyboard controls

| Key | Action |
|---|---|
| `SPACE` | Finish the tutorial and take control of the mouse |
| `S` | Skip the tutorial |
| `C` | Toggle control on and off |
| `T` | Replay the tutorial (the mouse stays disconnected until you finish) |
| `Ctrl + Alt + H` | Global hotkey to toggle control |
| `F` | Toggle fullscreen |
| `H` | Toggle the on-screen gesture legend |
| `Q` or `Esc` | Quit |

### Command-line options

```bash
py -3.12 main.py --skip-tutorial --debug
py -3.12 main.py --camera 1 --smooth 1.0 --margin 0.2
```

| Flag | Meaning | Default |
|---|---|---|
| `--camera` | Camera index | 0 |
| `--smooth` | One Euro `min_cutoff`. Lower is smoother but laggier | 1.2 |
| `--beta` | One Euro `beta`. Higher reduces lag on fast motion | 0.03 |
| `--margin` | Active region margin. Smaller means a smaller hand movement covers the screen | 0.15 |
| `--posture-hold` | Frames a posture must hold before the mode switches | 2 |
| `--pinch-on` | Thumb-to-index distance (share of hand size) that registers a pinch | 0.35 |
| `--pinch-off` | Distance that releases a pinch. Must stay above `--pinch-on` | 0.5 |
| `--skip-tutorial` | Go straight to the app (control still starts OFF, press `C`) | off |
| `--debug` | Show raw numbers (pinch ratio, target, finger bits) on the HUD | off |

## Testing

The tests run headless with a fake mouse backend, so no camera is opened and the real mouse is never touched. Install the dependencies first, because the tests import the app modules.

```bash
py -3.12 tests/smoke_test.py
```

The suite has 32 test functions covering the One Euro filter, coordinate mapping, posture classification and debouncing, click, drag, double click, right click and scroll behavior, the finger-curl-during-pinch regressions, the safety toggle, the tutorial flow and the status hints. It exits with code 0 when every check passes.

## Limitations and Roadmap

- Windows only for now: capture uses DirectShow and the click beep uses `winsound`.
- Tracks one hand and maps to the primary monitor only (`max_num_hands=1`, first monitor reported by `screeninfo`).
- Finger up/down is judged by fingertip height against the joint below it in the image, so the hand needs to stay roughly upright and facing the camera.
- Planned: two-hand modifier gestures, a recorder for custom gesture bindings, multi-monitor mapping, saved per-user profiles and a tray app front end.

## Author

**Shahram Shafiq** - [GitHub](https://github.com/shahramshafiq) | [LinkedIn](https://www.linkedin.com/in/shahramshafiq/)
