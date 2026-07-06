"""Domain errors, mapped to HTTP status codes at the API boundary."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain rule violations."""


class MealNotFound(DomainError):
    """A command referenced a meal that has no recorded events."""

    def __init__(self, meal_id: str) -> None:
        super().__init__(f"meal {meal_id!r} not found")
        self.meal_id = meal_id


class MealAlreadyConcluded(DomainError):
    """A command tried to modify a meal that has already been concluded."""

    def __init__(self, meal_id: str) -> None:
        super().__init__(f"meal {meal_id!r} is already concluded")
        self.meal_id = meal_id


class InvalidCommand(DomainError):
    """A command was structurally invalid (e.g. bad measure, wrong lifecycle)."""
