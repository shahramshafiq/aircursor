"""Hand landmark helpers built on top of the MediaPipe classic hands API.

Every geometry helper takes a plain landmark list where each item exposes
.x .y .z (normalized to the frame). That keeps the module testable: unit
tests pass simple fake landmark objects with no MediaPipe involved.
"""

import math

# Landmark ids from the MediaPipe hand model
WRIST = 0
THUMB_TIP = 4
THUMB_IP = 3
INDEX_TIP = 8
INDEX_PIP = 6
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_PIP = 10
MIDDLE_MCP = 9
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18


def distance(point_a, point_b):
    gapx = point_a.x - point_b.x
    gapy = point_a.y - point_b.y
    return math.sqrt(gapx * gapx + gapy * gapy)


def fingers_up(landmarks):
    """Return dict of booleans for index, middle, ring, pinky.

    A finger is up when its tip is above its pip. Image y grows downward,
    so an extended finger has a smaller tip.y than pip.y. The thumb is not
    included here because y based thumb detection is unreliable.
    """
    state = {}
    state["index"] = landmarks[INDEX_TIP].y < landmarks[INDEX_PIP].y
    state["middle"] = landmarks[MIDDLE_TIP].y < landmarks[MIDDLE_PIP].y
    state["ring"] = landmarks[RING_TIP].y < landmarks[RING_PIP].y
    state["pinky"] = landmarks[PINKY_TIP].y < landmarks[PINKY_PIP].y
    return state


def hand_size(landmarks):
    """Reference length used to make pinch distances scale invariant."""
    return distance(landmarks[WRIST], landmarks[MIDDLE_MCP])


def pinch_ratio(landmarks, tip_a=THUMB_TIP, tip_b=INDEX_TIP):
    """Distance between two tips normalized by hand size.

    Small when the two fingers touch, larger when they are apart. Because
    it is divided by hand size, the same pose gives a similar ratio near
    or far from the camera.
    """
    raw = distance(landmarks[tip_a], landmarks[tip_b])
    size = hand_size(landmarks)
    if size < 1e-6:
        size = 1e-6
    return raw / size
