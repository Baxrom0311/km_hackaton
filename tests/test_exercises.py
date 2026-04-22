from __future__ import annotations

import unittest

from posture_ai.core.exercises import (
    Exercise,
    EXERCISES_DB,
    recommend_exercises,
    get_daily_routine,
    _ISSUE_TO_GROUP,
)


class ExercisesDBTests(unittest.TestCase):
    def test_all_groups_have_exercises(self) -> None:
        for group, exercises in EXERCISES_DB.items():
            self.assertGreater(len(exercises), 0, f"Group '{group}' is empty")

    def test_exercises_have_required_fields(self) -> None:
        for group, exercises in EXERCISES_DB.items():
            for ex in exercises:
                self.assertIsInstance(ex, Exercise)
                self.assertTrue(ex.name, f"Exercise in '{group}' has empty name")
                self.assertTrue(ex.target)
                self.assertTrue(ex.description)
                self.assertGreater(ex.duration_sec, 0)
                self.assertIn(ex.difficulty, ("oson", "o'rta"))
                self.assertTrue(ex.benefit)

    def test_issue_to_group_mapping_valid(self) -> None:
        for issue, group in _ISSUE_TO_GROUP.items():
            self.assertIn(
                group, EXERCISES_DB,
                f"Issue '{issue}' maps to unknown group '{group}'",
            )


class RecommendExercisesTests(unittest.TestCase):
    def test_empty_issues_returns_fallback(self) -> None:
        result = recommend_exercises([])
        # Fallback: sit_duration mashqlari qo'shilishi kerak
        self.assertGreater(len(result), 0)

    def test_head_tilt_issues(self) -> None:
        result = recommend_exercises([("Boshingizni ko'taring!", 5)])
        self.assertGreater(len(result), 0)
        # Birinchi mashq head_tilt guruhidan bo'lishi kerak
        head_exercises = {ex.name for ex in EXERCISES_DB["head_tilt"]}
        self.assertIn(result[0].name, head_exercises)

    def test_max_exercises_limit(self) -> None:
        many_issues = [
            ("Boshingizni ko'taring!", 10),
            ("Yelkalaringizni tekislang!", 8),
            ("Oldinga engashmang!", 6),
            ("Bo'yningizni to'g'rilang!", 4),
            ("Ekranga yaqin!", 3),
        ]
        result = recommend_exercises(many_issues, max_exercises=3)
        self.assertLessEqual(len(result), 3)

    def test_no_duplicate_exercises(self) -> None:
        issues = [
            ("Boshingizni ko'taring!", 5),
            ("Yelkalaringizni tekislang!", 5),
            ("Oldinga engashmang!", 5),
            ("Yelkalaringizni oching!", 5),
        ]
        result = recommend_exercises(issues, max_exercises=8)
        names = [ex.name for ex in result]
        self.assertEqual(len(names), len(set(names)), "Duplicate exercises found")

    def test_unknown_issue_ignored(self) -> None:
        result = recommend_exercises([("Noma'lum muammo!", 10)])
        # Noma'lum muammo uchun fallback mashqlar qaytariladi
        self.assertIsInstance(result, list)

    def test_multiple_issues_prioritized(self) -> None:
        issues = [
            ("Oldinga engashmang!", 10),  # eng ko'p
            ("Boshingizni ko'taring!", 2),  # kam
        ]
        result = recommend_exercises(issues, max_exercises=2)
        self.assertGreater(len(result), 0)
        # Birinchi mashq forward_lean guruhidan bo'lishi kerak
        forward_exercises = {ex.name for ex in EXERCISES_DB["forward_lean"]}
        self.assertIn(result[0].name, forward_exercises)


class DailyRoutineTests(unittest.TestCase):
    def test_daily_routine_from_issues(self) -> None:
        issues = [
            "Boshingizni ko'taring!",
            "Boshingizni ko'taring!",
            "Yelkalaringizni tekislang!",
            "Oldinga engashmang!",
        ]
        result = get_daily_routine(issues)
        self.assertGreater(len(result), 0)
        self.assertLessEqual(len(result), 4)

    def test_empty_daily_routine(self) -> None:
        result = get_daily_routine([])
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
