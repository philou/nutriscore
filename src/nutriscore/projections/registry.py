"""Projection registry: folds events into in-memory read models.

State is held in dicts and rebuilt from scratch on startup by replaying the full
event log. As new events are appended, the application service forwards them to
:meth:`Projections.handle` to keep the read models current.
"""

from __future__ import annotations

from ..domain.events import (
    DomainEvent,
    FoodItemAdded,
    MealConcluded,
    MealStarted,
)
from .models import (
    FoodAggregate,
    FoodEntry,
    MealDetail,
    MealSummary,
    NutrimentTotals,
)

_GRADE_ORDER = "abcde"


def _worst_grade(current: str | None, candidate: str | None) -> str | None:
    grades = [g for g in (current, candidate) if g and g.lower() in _GRADE_ORDER]
    if not grades:
        return current
    return max(grades, key=lambda g: _GRADE_ORDER.index(g.lower()))


class Projections:
    """Container for all read models with a single fold entry point."""

    def __init__(self) -> None:
        self.meals: dict[str, MealSummary] = {}
        self.meal_details: dict[str, MealDetail] = {}
        self.foods: dict[str, FoodAggregate] = {}

    def reset(self) -> None:
        self.meals.clear()
        self.meal_details.clear()
        self.foods.clear()

    def rebuild(self, events: list[DomainEvent]) -> None:
        self.reset()
        for event in events:
            self.handle(event)

    def handle(self, event: DomainEvent) -> None:
        if isinstance(event, MealStarted):
            self._on_started(event)
        elif isinstance(event, FoodItemAdded):
            self._on_food_added(event)
        elif isinstance(event, MealConcluded):
            self._on_concluded(event)

    def _on_started(self, event: MealStarted) -> None:
        self.meals[event.meal_id] = MealSummary(
            meal_id=event.meal_id,
            meal_type=event.meal_type,
            started_at=event.started_at,
            status="recording",
        )
        self.meal_details[event.meal_id] = MealDetail(
            meal_id=event.meal_id,
            meal_type=event.meal_type,
            started_at=event.started_at,
            status="recording",
        )

    def _on_food_added(self, event: FoodItemAdded) -> None:
        summary = self.meals.get(event.meal_id)
        if summary:
            summary.item_count += 1

        detail = self.meal_details.get(event.meal_id)
        if detail:
            detail.foods.append(
                FoodEntry(
                    name=event.name,
                    quantity=event.quantity,
                    weight_grams=event.weight_grams,
                    nutrition=event.nutrition,
                )
            )
            self._recompute_detail_totals(detail)

        key = event.name.strip().lower()
        aggregate = self.foods.get(key)
        if aggregate is None:
            aggregate = FoodAggregate(name=event.name.strip())
            self.foods[key] = aggregate
        aggregate.times_eaten += 1
        if event.meal_id not in aggregate.meal_ids:
            aggregate.meal_ids.append(event.meal_id)

    def _on_concluded(self, event: MealConcluded) -> None:
        summary = self.meals.get(event.meal_id)
        if summary:
            summary.status = "concluded"
            summary.concluded_at = event.concluded_at
        detail = self.meal_details.get(event.meal_id)
        if detail:
            detail.status = "concluded"
            detail.concluded_at = event.concluded_at

    @staticmethod
    def _recompute_detail_totals(detail: MealDetail) -> None:
        energy: float | None = None
        grade: str | None = None
        for food in detail.foods:
            n = food.nutrition
            if n is None:
                continue
            grade = _worst_grade(grade, n.nutri_score_grade)
            if n.energy_kcal_100g is not None and food.weight_grams is not None:
                energy = (energy or 0.0) + n.energy_kcal_100g * food.weight_grams / 100.0
        detail.totals = NutrimentTotals(energy_kcal=energy)
        detail.nutri_score_grade = grade
