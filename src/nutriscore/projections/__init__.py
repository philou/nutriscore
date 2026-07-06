"""In-memory read models (projections) rebuilt by replaying the event log."""

from .models import (
    FoodAggregate,
    FoodEntry,
    MealDetail,
    MealSummary,
    NutrimentTotals,
)
from .registry import Projections

__all__ = [
    "FoodAggregate",
    "FoodEntry",
    "MealDetail",
    "MealSummary",
    "NutrimentTotals",
    "Projections",
]
