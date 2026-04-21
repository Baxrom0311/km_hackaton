from __future__ import annotations

import unittest

from posture_ai.vision.visual import VisualControls, handle_visual_key


class VisualHotkeyTests(unittest.TestCase):
    def test_d_toggles_landmarks(self) -> None:
        controls = VisualControls(show_landmarks=True)

        should_exit = handle_visual_key(ord("d"), controls)

        self.assertFalse(should_exit)
        self.assertFalse(controls.show_landmarks)

    def test_i_n_h_toggle_panels_and_notifications(self) -> None:
        controls = VisualControls(show_info=True, show_help=True, notifications_enabled=True)

        handle_visual_key(ord("i"), controls)
        handle_visual_key(ord("n"), controls)
        handle_visual_key(ord("h"), controls)

        self.assertFalse(controls.show_info)
        self.assertFalse(controls.notifications_enabled)
        self.assertFalse(controls.show_help)

    def test_q_and_escape_request_exit(self) -> None:
        controls = VisualControls()

        self.assertTrue(handle_visual_key(ord("q"), controls))
        self.assertTrue(handle_visual_key(27, controls))


if __name__ == "__main__":
    unittest.main()
    