"""Projections: replaying a known event sequence yields the expected read models."""

from datetime import datetime

from nutriscore.domain.events import (
    FoodItemAdded,
    MealConcluded,
    MealStarted,
    MealType,
    NutritionInfo,
)
from nutriscore.projections.registry import Projections


def _events():
    started = MealStarted(meal_id="m1", meal_type=MealType.dinner, started_at=datetime(2026, 7, 6, 19))
    food_a = FoodItemAdded(
        meal_id="m1",
        name="Pizza",
        weight_grams=300,
        nutrition=NutritionInfo(nutri_score_grade="d", energy_kcal_100g=266),
        added_at=datetime(2026, 7, 6, 19, 5),
    )
    food_b = FoodItemAdded(
        meal_id="m1",
        name="Salad",
        weight_grams=100,
        nutrition=NutritionInfo(nutri_score_grade="a", energy_kcal_100g=20),
        added_at=datetime(2026, 7, 6, 19, 10),
    )
    concluded = MealConcluded(meal_id="m1", concluded_at=datetime(2026, 7, 6, 19, 30))
    return [started, food_a, food_b, concluded]


def test_rebuild_produces_expected_read_models():
    proj = Projections()
    proj.rebuild(_events())

    summary = proj.meals["m1"]
    assert summary.status == "concluded"
    assert summary.item_count == 2

    detail = proj.meal_details["m1"]
    assert [f.name for f in detail.foods] == ["Pizza", "Salad"]
    # worst nutri-score across foods (d beats a)
    assert detail.nutri_score_grade == "d"
    # energy = 266*300/100 + 20*100/100 = 798 + 20
    assert detail.totals.energy_kcal == 818

    assert proj.foods["pizza"].times_eaten == 1
    assert proj.foods["pizza"].meal_ids == ["m1"]


def test_rebuild_is_idempotent():
    proj = Projections()
    proj.rebuild(_events())
    proj.rebuild(_events())
    assert len(proj.meals) == 1
    assert proj.meals["m1"].item_count == 2
