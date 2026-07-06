"""Application service: turns commands into persisted events + projection updates.

This is the write side. Each command rehydrates a meal from its event stream,
invokes an aggregate command, appends the resulting event(s) with optimistic
concurrency, then forwards them to the projections.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from .config import Settings
from .domain.events import FoodItemAdded, MealConcluded, MealStarted
from .domain.meal import Meal
from .domain.errors import MealNotFound
from .eventstore.sqlite import SqliteEventStore
from .openfoodfacts.client import NutritionSource, ProductCandidate
from .projections.registry import Projections


class MealService:
    def __init__(
        self,
        store: SqliteEventStore,
        projections: Projections,
        settings: Settings,
        nutrition_source: NutritionSource | None = None,
    ) -> None:
        self.store = store
        self.projections = projections
        self.settings = settings
        self.nutrition_source = nutrition_source

    def _load(self, meal_id: str) -> Meal:
        events = self.store.load_stream(meal_id)
        if not events:
            raise MealNotFound(meal_id)
        return Meal.rehydrate(events)

    def start_meal(self, when: datetime | None = None) -> MealStarted:
        when = when or datetime.now()
        meal_id = uuid.uuid4().hex
        event = Meal().start(meal_id, when, self.settings)
        self.store.append(meal_id, 0, [event])
        self.projections.handle(event)
        return event

    async def add_food(
        self,
        meal_id: str,
        name: str,
        quantity: float | None = None,
        weight_grams: float | None = None,
        off_product_id: str | None = None,
        when: datetime | None = None,
    ) -> FoodItemAdded:
        when = when or datetime.now()
        meal = self._load(meal_id)
        nutrition = None
        if off_product_id and self.nutrition_source is not None:
            nutrition = await self.nutrition_source.get_nutrition(off_product_id)
        event = meal.add_food(name, quantity, weight_grams, nutrition, when)
        self.store.append(meal_id, meal.version, [event])
        self.projections.handle(event)
        return event

    def conclude_meal(self, meal_id: str, when: datetime | None = None) -> MealConcluded:
        when = when or datetime.now()
        meal = self._load(meal_id)
        event = meal.conclude(when)
        self.store.append(meal_id, meal.version, [event])
        self.projections.handle(event)
        return event

    async def search_foods(self, query: str) -> list[ProductCandidate]:
        if self.nutrition_source is None:
            return []
        return await self.nutrition_source.search_products(query)
