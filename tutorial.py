"""Interactive onboarding. Teaches one gesture at a time before any real
mouse control happens, so a first time user actually learns how to drive
the cursor instead of guessing.

Pure logic, no cv2, fully testable. It is fed the same per frame result
the gesture engine already produces (plus whether a hand is visible) and
walks a small state machine of steps. A step that needs a posture held
uses a sustain timer; a step that needs an action (a click, a scroll)
completes the instant that action fires. Each completed step plays a short
celebration before advancing, which makes it feel rewarding.
"""

# Each step: id, short title, plain instruction, and how it is satisfied.
# kind "hand": a hand is simply visible.
# kind "mode": the engine reports this mode, held for hold_s seconds.
# kind "action": the engine emits this action once (instant).
STEPS = [
    {
        "id": "hand",
        "title": "Show your hand",
        "body": "Hold your hand up so the camera can see it",
        "kind": "hand",
        "hold_s": 0.4,
    },
    {
        "id": "move",
        "title": "Point to move",
        "body": "Raise only your index finger and move it around",
        "kind": "mode",
        "target": "MOVE",
        "hold_s": 1.0,
    },
    {
        "id": "click",
        "title": "Pinch to click",
        "body": "Touch your thumb and index finger together, then let go",
        "kind": "action",
        "action": "left_click",
    },
    {
        "id": "scroll",
        "title": "Two fingers to scroll",
        "body": "Raise index and middle finger, then move your hand up or down",
        "kind": "action",
        "action": "scroll",
    },
    {
        "id": "pause",
        "title": "Open palm to pause",
        "body": "Open your whole hand to pause the mouse any time",
        "kind": "mode",
        "target": "PAUSED",
        "hold_s": 0.8,
    },
    {
        "id": "done",
        "title": "You are ready",
        "body": "You have learned every gesture. Open palm pauses any time.",
        "kind": "done",
    },
]

CELEBRATE_S = 0.9


class TutorialFlow:
    def __init__(self):
        self.i = 0
        self.hold_start = None
        self.celebrate_until = None
        self.finished = False

    def _info(self, step, progress, celebrating=False, just_done=False):
        return {
            "index": self.i,
            "total": len(STEPS) - 1,  # the "done" screen is not counted
            "id": step["id"],
            "title": step["title"],
            "body": step["body"],
            "progress": max(0.0, min(1.0, progress)),
            "celebrating": celebrating,
            "just_done": just_done,
            "finished": self.finished,
        }

    def _satisfied(self, step, has_hand, result, now):
        kind = step["kind"]
        if kind == "hand":
            if has_hand:
                if self.hold_start is None:
                    self.hold_start = now
                return (now - self.hold_start) >= step["hold_s"], \
                    (now - self.hold_start) / step["hold_s"]
            self.hold_start = None
            return False, 0.0
        if kind == "mode":
            if result.get("mode") == step["target"]:
                if self.hold_start is None:
                    self.hold_start = now
                return (now - self.hold_start) >= step["hold_s"], \
                    (now - self.hold_start) / step["hold_s"]
            self.hold_start = None
            return False, 0.0
        if kind == "action":
            names = [a[0] for a in result.get("actions", [])]
            return step["action"] in names, 0.0
        return False, 0.0

    def update(self, has_hand, result, now):
        step = STEPS[self.i]

        # Playing the short well done animation before moving on.
        if self.celebrate_until is not None:
            if now < self.celebrate_until:
                return self._info(step, 1.0, celebrating=True)
            self.celebrate_until = None
            self.hold_start = None
            if self.i < len(STEPS) - 1:
                self.i += 1
            step = STEPS[self.i]
            if step["kind"] == "done":
                self.finished = True
            return self._info(step, 0.0)

        if step["kind"] == "done":
            self.finished = True
            return self._info(step, 1.0)

        ok, progress = self._satisfied(step, has_hand, result, now)
        if ok:
            self.celebrate_until = now + CELEBRATE_S
            self.hold_start = None
            return self._info(step, 1.0, celebrating=True, just_done=True)
        return self._info(step, progress)

    def skip(self):
        # Jump straight to the ready screen.
        self.i = len(STEPS) - 1
        self.hold_start = None
        self.celebrate_until = None
        self.finished = True
