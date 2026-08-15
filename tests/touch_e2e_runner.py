"""
End-to-end synthetic-touch navigation checks.

Runs REAL Screens with the REAL TouchButtons + TouchInput input stack (events
injected via TouchInput.inject_event) rendering through the REAL DPI28Emulator
composition — no mocks anywhere in the touch path.

This file is deliberately NOT named test_*.py: the main pytest suite installs
MagicMock stand-ins for gui.renderer / hardware.buttons at import time
(tests/base.py), which would corrupt these real-module tests. Instead,
tests/test_touch_e2e.py launches this script in a clean subprocess.

Exit code 0 = all scenarios passed.
"""
import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

os.environ["SEEDSIGNER_TOUCH"] = "1"

# Hardware-only modules that don't exist on a desktop dev machine
for mod in ["RPi", "RPi.GPIO", "spidev", "picamera", "picamera.array",
            "seedsigner.hardware.camera", "seedsigner.hardware.pivideostream",
            "seedsigner.hardware.microsd"]:
    sys.modules[mod] = MagicMock()

# CRITICAL: hardware/buttons.py derives its key-code constants from the GPIO
# pin numbers, branching on RPI_INFO['P1_REVISION']. TouchButtons hardcodes the
# P1_REVISION == 3 (40-pin) values, so the mock must report the same revision or
# screens will wait on key codes TouchButtons never emits.
sys.modules["RPi.GPIO"].RPI_INFO = {"P1_REVISION": 3}
sys.modules["RPi"].GPIO = sys.modules["RPi.GPIO"]

from PIL import Image, ImageDraw

from seedsigner.gui.renderer import Renderer
from seedsigner.hardware.DPI28 import DPI28Emulator
from seedsigner.hardware.touchbuttons import TouchButtons
from seedsigner.hardware.buttons import HardwareButtonsConstants


class E2ERenderer(Renderer):
    """In-memory renderer: 240x240 canvas pushed through DPI28Emulator."""

    @classmethod
    def configure_instance(cls):
        renderer = cls.__new__(cls)
        cls._instance = renderer
        # Screens resolve the singleton via the base class
        Renderer._instance = renderer
        renderer.canvas_width = 240
        renderer.canvas_height = 240
        renderer.canvas = Image.new("RGB", (240, 240))
        renderer.draw = ImageDraw.Draw(renderer.canvas)
        renderer.disp = DPI28Emulator(_width=240, _height=240)
        renderer.display_type = "dpi28"
        renderer.frames = 0

    def show_image(self, image=None, alpha_overlay=None, show_direct=False, is_background_thread=False):
        if alpha_overlay:
            if image is None:
                image = self.canvas
            image = Image.alpha_composite(image, alpha_overlay)
        if image:
            self.canvas.paste(image)
        self.disp.show_image(self.canvas)
        self.frames += 1


def run_screen_async(screen):
    """Run screen.display() in a thread; returns (thread, result-holder)."""
    holder = {}

    def target():
        try:
            holder["result"] = screen.display()
        except Exception as e:  # pragma: no cover - failure reporting only
            holder["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    return t, holder


def tap(x, y, hold_ms=40):
    """Inject a synthetic tap at SCREEN coords (480x640 panel space)."""
    touch = TouchButtons.get_instance().touch
    touch.inject_event("down", x, y)
    time.sleep(hold_ms / 1000.0)
    touch.inject_event("up", x, y)


def button_center_screen_coords(screen, index):
    """Panel (480x640) coords of the center of a rendered Button."""
    btn = screen.buttons[index]
    native_x = getattr(btn, "screen_x", 0) + btn.width // 2
    native_y = btn.screen_y - getattr(btn, "scroll_y", 0) + btn.height // 2
    return native_x * 2, native_y * 2


def wait_for_render(screen, holder, timeout=5.0):
    """Block until the screen thread has rendered and is in its input loop."""
    deadline = time.time() + timeout
    renderer = Renderer.get_instance()
    while time.time() < deadline:
        if "error" in holder:
            raise holder["error"]
        if renderer.frames > 0 and getattr(screen, "buttons", None):
            # One extra beat so _run()'s wait_for loop is actually polling
            time.sleep(0.15)
            return
        time.sleep(0.02)
    raise AssertionError("screen never rendered")


def finish(thread, holder, timeout=5.0):
    thread.join(timeout)
    if thread.is_alive():
        raise AssertionError("screen did not return after input")
    if "error" in holder:
        raise holder["error"]
    return holder.get("result")


PASSED = []
FAILED = []


def scenario(name):
    def deco(fn):
        def wrapper():
            # Fresh input state per scenario
            tb = TouchButtons.get_instance()
            tb.clear_pending_input()
            Renderer.get_instance().frames = 0
            try:
                fn()
                PASSED.append(name)
                print(f"PASS: {name}")
            except Exception as e:
                FAILED.append((name, e))
                print(f"FAIL: {name}: {e!r}")
        wrapper.__name__ = name
        return wrapper
    return deco


@scenario("button_list_two_tap_select_then_confirm")
def s1():
    # Anti-fat-finger contract: tapping a NON-selected item only moves the
    # selection; a second tap on the now-selected item confirms it.
    from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption
    screen = ButtonListScreen(title="Test", button_data=[
        ButtonOption("Alpha"), ButtonOption("Bravo"), ButtonOption("Charlie")])
    t, holder = run_screen_async(screen)
    wait_for_render(screen, holder)
    x, y = button_center_screen_coords(screen, 1)
    tap(x, y)          # first tap: select only
    time.sleep(0.4)
    assert "result" not in holder, "single tap on non-selected item must not activate"
    x, y = button_center_screen_coords(screen, 1)  # re-read: may have scrolled
    tap(x, y)          # second tap: confirm
    assert finish(t, holder) == 1


@scenario("button_list_top_left_corner_goes_back")
def s2():
    from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption, RET_CODE__BACK_BUTTON
    screen = ButtonListScreen(title="Test", show_back_button=True, button_data=[
        ButtonOption("Alpha"), ButtonOption("Bravo")])
    t, holder = run_screen_async(screen)
    wait_for_render(screen, holder)
    tap(20, 20)  # top-left corner (back), screen coords
    assert finish(t, holder) == RET_CODE__BACK_BUTTON


@scenario("touch_bar_down_then_select")
def s3():
    from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption
    screen = ButtonListScreen(title="Test", button_data=[
        ButtonOption("Alpha"), ButtonOption("Bravo"), ButtonOption("Charlie")])
    t, holder = run_screen_async(screen)
    wait_for_render(screen, holder)
    tap(400, 560)   # touch bar right third = KEY3 (down)
    time.sleep(0.3)
    tap(240, 560)   # touch bar middle = KEY2 (select)
    assert finish(t, holder) == 1


@scenario("large_button_grid_tap")
def s4():
    from seedsigner.gui.screens.screen import LargeButtonScreen, ButtonOption
    screen = LargeButtonScreen(title="Menu", show_back_button=False, button_data=[
        ButtonOption("One"), ButtonOption("Two"), ButtonOption("Three"), ButtonOption("Four")])
    t, holder = run_screen_async(screen)
    wait_for_render(screen, holder)
    x, y = button_center_screen_coords(screen, 2)
    tap(x, y)          # select
    time.sleep(0.4)
    tap(x, y)          # confirm
    assert finish(t, holder) == 2


@scenario("tap_on_empty_area_does_not_select")
def s5():
    from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption
    screen = ButtonListScreen(title="Test", show_back_button=True, button_data=[
        ButtonOption("Alpha")])
    t, holder = run_screen_async(screen)
    wait_for_render(screen, holder)
    # Tap dead space between title and button in the middle band that maps to
    # KEY_PRESS nav fallback... on a list screen a bare KEY_PRESS activates the
    # CURRENT selection, so instead probe the top band (KEY_UP): must not return.
    tap(240, 130)  # upper UI area, no button there -> KEY_UP, list stays put
    time.sleep(0.5)
    assert "result" not in holder, f"stray tap activated: {holder.get('result')!r}"
    # Now select explicitly to unblock the thread
    x, y = button_center_screen_coords(screen, 0)
    tap(x, y)
    assert finish(t, holder) == 0


@scenario("drag_off_button_cancels_tap")
def s6():
    # Touch hygiene: down on a control, slide off, release -> must NOT activate.
    from seedsigner.gui.screens.screen import ButtonListScreen, ButtonOption
    screen = ButtonListScreen(title="Test", button_data=[
        ButtonOption("Alpha"), ButtonOption("Bravo")])
    t, holder = run_screen_async(screen)
    wait_for_render(screen, holder)
    touch = TouchButtons.get_instance().touch
    x, y = button_center_screen_coords(screen, 0)  # the SELECTED button (would fire on tap)
    touch.inject_event("down", x, y)
    time.sleep(0.05)
    touch.inject_event("up", 240, 300)  # released on empty UI area
    time.sleep(0.4)
    assert "result" not in holder, f"drag-off activated: {holder.get('result')!r}"
    tap(x, y)  # clean tap on selected button activates
    assert finish(t, holder) == 0


def main():
    # TouchButtons.wait_for consults the Controller singleton for screensaver
    # timing; keep it inert without booting the full app.
    controller = MagicMock()
    controller.screensaver_activation_ms = 10**9
    controller.is_screensaver_start_allowed = False

    E2ERenderer.configure_instance()

    with patch("seedsigner.controller.Controller.get_instance", return_value=controller):
        for fn in (s1, s2, s3, s4, s5, s6):
            fn()

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
