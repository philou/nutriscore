"""Domain layer: events, aggregate, and pure business rules (no I/O)."""

from .errors import (
    DomainError,
    InvalidCommand,
    MealAlreadyConcluded,
    MealNotFound,
)
from .events import (
    DomainEvent,
    FoodItemAdded,
    MealConcluded,
    MealStarted,
    MealType,
    NutritionInfo,
)
from .meal import Meal, infer_meal_type

__all__ = [
    "DomainError",
    "InvalidCommand",
    "MealAlreadyConcluded",
    "MealNotFound",
    "DomainEvent",
    "FoodItemAdded",
    "MealConcluded",
    "MealStarted",
    "MealType",
    "NutritionInfo",
    "Meal",
    "infer_meal_type",
]
