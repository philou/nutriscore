"""Read-model shapes served by the query endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ..domain.events import MealType, NutritionInfo


class MealSummary(BaseModel):
    meal_id: str
    meal_type: MealType
    started_at: datetime
    concluded_at: datetime | None = None
    status: str  # "recording" | "concluded"
    item_count: int = 0


class FoodEntry(BaseModel):
    name: str
    quantity: float | None = None
    weight_grams: float | None = None
    nutrition: NutritionInfo | None = None


class NutrimentTotals(BaseModel):
    """Meal-level totals. Energy is summed only for foods recorded by weight
    (scaled from the per-100g value); ``None`` when nothing is measurable."""

    energy_kcal: float | None = None


class MealDetail(BaseModel):
    meal_id: str
    meal_type: MealType
    started_at: datetime
    concluded_at: datetime | None = None
    status: str
    foods: list[FoodEntry] = []
    totals: NutrimentTotals = NutrimentTotals()
    nutri_score_grade: str | None = None  # worst grade among foods


class FoodAggregate(BaseModel):
    name: str
    times_eaten: int = 0
    meal_ids: list[str] = []
