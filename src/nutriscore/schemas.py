"""Request/response schemas for the HTTP API (kept separate from domain events)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .domain.events import MealType, NutritionInfo


class StartMealResponse(BaseModel):
    meal_id: str
    meal_type: MealType
    started_at: datetime


class AddFoodRequest(BaseModel):
    name: str
    quantity: float | None = None
    weight_grams: float | None = None
    off_product_id: str | None = None


class FoodAddedResponse(BaseModel):
    meal_id: str
    name: str
    quantity: float | None = None
    weight_grams: float | None = None
    nutrition: NutritionInfo | None = None
    added_at: datetime


class ConcludeMealResponse(BaseModel):
    meal_id: str
    concluded_at: datetime
