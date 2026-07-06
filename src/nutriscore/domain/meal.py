"""The ``Meal`` aggregate and pure meal-type inference.

A meal is a single event-sourced aggregate. Its current state is rehydrated by
folding its event stream; command methods validate invariants and *return* new
events (they never persist — that is the application service's job).
"""

from __future__ import annotations

from datetime import datetime

from ..config import Settings
from .errors import InvalidCommand, MealAlreadyConcluded, MealNotFound
from .events import (
    DomainEvent,
    FoodItemAdded,
    MealConcluded,
    MealStarted,
    MealType,
    NutritionInfo,
)


def infer_meal_type(when: datetime, settings: Settings) -> MealType:
    """Infer the meal type from the time of day using configured windows.

    Windows are ``(start_hour, end_hour)`` half-open on the hour; any hour not
    covered by a window is a snack.
    """

    hour = when.hour
    for meal_type, (start, end) in (
        (MealType.breakfast, settings.breakfast_window),
        (MealType.lunch, settings.lunch_window),
        (MealType.dinner, settings.dinner_window),
    ):
        if start <= hour < end:
            return meal_type
    return MealType.snack


class Meal:
    """Rehydratable meal aggregate.

    ``version`` is the number of events applied, used as the expected sequence
    for optimistic-concurrency appends.
    """

    def __init__(self) -> None:
        self.meal_id: str | None = None
        self.meal_type: MealType | None = None
        self.started: bool = False
        self.concluded: bool = False
        self.food_count: int = 0
        self.version: int = 0

    @classmethod
    def rehydrate(cls, events: list[DomainEvent]) -> "Meal":
        meal = cls()
        for event in events:
            meal._apply(event)
        return meal

    def _apply(self, event: DomainEvent) -> None:
        if isinstance(event, MealStarted):
            self.meal_id = event.meal_id
            self.meal_type = event.meal_type
            self.started = True
        elif isinstance(event, FoodItemAdded):
            self.food_count += 1
        elif isinstance(event, MealConcluded):
            self.concluded = True
        self.version += 1

    # -- Commands -----------------------------------------------------------

    def start(self, meal_id: str, when: datetime, settings: Settings) -> MealStarted:
        if self.started:
            raise InvalidCommand("meal already started")
        return MealStarted(
            meal_id=meal_id,
            meal_type=infer_meal_type(when, settings),
            started_at=when,
        )

    def add_food(
        self,
        name: str,
        quantity: float | None,
        weight_grams: float | None,
        nutrition: NutritionInfo | None,
        when: datetime,
    ) -> FoodItemAdded:
        if not self.started:
            raise MealNotFound(self.meal_id or "<unstarted>")
        if self.concluded:
            raise MealAlreadyConcluded(self.meal_id or "<unknown>")
        if not name or not name.strip():
            raise InvalidCommand("food name is required")
        if (quantity is None) == (weight_grams is None):
            raise InvalidCommand("exactly one of quantity or weight_grams is required")
        return FoodItemAdded(
            meal_id=self.meal_id,
            name=name.strip(),
            quantity=quantity,
            weight_grams=weight_grams,
            nutrition=nutrition,
            added_at=when,
        )

    def conclude(self, when: datetime) -> MealConcluded:
        if not self.started:
            raise MealNotFound(self.meal_id or "<unstarted>")
        if self.concluded:
            raise MealAlreadyConcluded(self.meal_id or "<unknown>")
        return MealConcluded(meal_id=self.meal_id, concluded_at=when)
