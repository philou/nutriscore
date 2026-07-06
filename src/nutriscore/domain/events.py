"""Immutable domain events and the value objects they carry.

Events are the source of truth: application state is derived by folding the
event log. They are frozen Pydantic models so they can be (de)serialized to and
from the SQLite event store and never mutated after construction.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class NutritionInfo(BaseModel):
    """Nutrition snapshot for a food, sourced from OpenFoodFacts at record time.

    All fields are optional so a food can be recorded even when OpenFoodFacts is
    unavailable or the product is unknown (graceful degradation). Values are per
    100g/100ml as reported by OpenFoodFacts.
    """

    model_config = ConfigDict(frozen=True)

    off_product_id: str | None = None
    product_name: str | None = None
    energy_kcal_100g: float | None = None
    fat_100g: float | None = None
    saturated_fat_100g: float | None = None
    carbohydrates_100g: float | None = None
    sugars_100g: float | None = None
    proteins_100g: float | None = None
    salt_100g: float | None = None
    nutri_score_grade: str | None = None


class MealStarted(BaseModel):
    model_config = ConfigDict(frozen=True)

    meal_id: str
    meal_type: MealType
    started_at: datetime


class FoodItemAdded(BaseModel):
    model_config = ConfigDict(frozen=True)

    meal_id: str
    name: str
    quantity: float | None = None
    weight_grams: float | None = None
    nutrition: NutritionInfo | None = None
    added_at: datetime


class MealConcluded(BaseModel):
    model_config = ConfigDict(frozen=True)

    meal_id: str
    concluded_at: datetime


# Discriminated by class name when persisted; see eventstore serialization.
DomainEvent = MealStarted | FoodItemAdded | MealConcluded
