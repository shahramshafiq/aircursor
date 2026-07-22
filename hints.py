"""Plain English status hints shown while the app runs.

A first time or non technical user will forget the gesture list within a
minute of finishing the tutorial. Rather than making them remember or hunt
for the legend, the app always shows one short sentence describing what to
do right now, based on what it currently sees. Pure logic, no cv2, so it
is trivial to unit test on its own.
"""

HINTS_BY_MODE = {
    "MOVE": "Pinch your thumb and index finger together to click",
    "DRAG": "Move your hand, then let go of the pinch to drop",
    "SCROLL": "Move your hand up or down to scroll, or pinch to right click",
    "PAUSED": "Cursor paused. Point with your index finger to move again",
    "LEFT CLICK": "Point with your index finger to move the cursor",
    "DOUBLE CLICK": "Point with your index finger to move the cursor",
    "RIGHT CLICK": "Point with your index finger to move the cursor",
}

DEFAULT_HINT = "Point with your index finger to move the cursor"


def status_hint(mode, has_hand, control_state):
    """One short sentence telling the user what to do right now.

    Priority: no hand beats everything (nothing else matters until the
    camera can see you), control being off beats the gesture hints (moving
    your hand does nothing until control is on), and only then does the
    hint describe the current mode.
    """
    if not has_hand:
        return "Show your hand to the camera to begin"
    if control_state != "on":
        return "Press C to start controlling your mouse"
    return HINTS_BY_MODE.get(mode, DEFAULT_HINT)
