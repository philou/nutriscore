"""API tests via TestClient with a fake OpenFoodFacts source (no network)."""

import pytest
from fastapi.testclient import TestClient

from nutriscore.config import Settings
from nutriscore.domain.events import MealType, NutritionInfo
from nutriscore.eventstore.sqlite import SqliteEventStore
from nutriscore.main import create_app
from nutriscore.openfoodfacts.client import ProductCandidate


class FakeNutritionSource:
    """In-memory nutrition source. Set ``available=False`` to simulate OFF down."""

    def __init__(self, available: bool = True) -> None:
        self.available = available
        self._candidates = [ProductCandidate(id="1", name="Apple", brand="Acme")]
        self._nutrition = {
            "1": NutritionInfo(off_product_id="1", nutri_score_grade="a", energy_kcal_100g=52)
        }

    async def search_products(self, query: str) -> list[ProductCandidate]:
        return self._candidates if self.available else []

    async def get_nutrition(self, product_id: str):
        return self._nutrition.get(product_id) if self.available else None


def make_client(source: FakeNutritionSource | None = None) -> TestClient:
    """Return a TestClient; use as a context manager so lifespan startup runs."""
    source = source or FakeNutritionSource()
    app = create_app(
        settings=Settings(),
        nutrition_source=source,
        store=SqliteEventStore(":memory:"),
    )
    return TestClient(app)


def test_full_recording_flow():
    with make_client() as client:
        # Search candidates before adding.
        search = client.get("/foods/search", params={"q": "apple"})
        assert search.status_code == 200
        assert search.json()[0]["id"] == "1"

        # Start a meal.
        started = client.post("/meals")
        assert started.status_code == 201
        meal_id = started.json()["meal_id"]
        assert started.json()["meal_type"] in {t.value for t in MealType}

        # Add a food with a resolved OFF product -> nutrition snapshotted.
        added = client.post(
            f"/meals/{meal_id}/foods",
            json={"name": "Apple", "weight_grams": 150, "off_product_id": "1"},
        )
        assert added.status_code == 201
        assert added.json()["nutrition"]["nutri_score_grade"] == "a"

        # Conclude.
        concluded = client.post(f"/meals/{meal_id}/conclude")
        assert concluded.status_code == 200

        # Query read models.
        detail = client.get(f"/meals/{meal_id}").json()
        assert detail["status"] == "concluded"
        assert detail["foods"][0]["name"] == "Apple"
        assert detail["nutri_score_grade"] == "a"
        assert detail["totals"]["energy_kcal"] == pytest.approx(52 * 150 / 100)

        assert client.get("/meals").json()[0]["meal_id"] == meal_id
        assert client.get("/foods").json()[0]["name"] == "Apple"
        assert client.get("/foods/apple").json()["times_eaten"] == 1


def test_food_recorded_without_nutrition_when_off_unavailable():
    with make_client(FakeNutritionSource(available=False)) as client:
        meal_id = client.post("/meals").json()["meal_id"]
        added = client.post(
            f"/meals/{meal_id}/foods",
            json={"name": "Mystery snack", "quantity": 1, "off_product_id": "1"},
        )
        assert added.status_code == 201
        assert added.json()["nutrition"] is None  # degraded, but recorded


def test_add_food_to_unknown_meal_is_404():
    with make_client() as client:
        resp = client.post("/meals/does-not-exist/foods", json={"name": "x", "quantity": 1})
        assert resp.status_code == 404


def test_add_food_after_conclude_is_409():
    with make_client() as client:
        meal_id = client.post("/meals").json()["meal_id"]
        client.post(f"/meals/{meal_id}/conclude")
        resp = client.post(f"/meals/{meal_id}/foods", json={"name": "x", "quantity": 1})
        assert resp.status_code == 409


def test_add_food_without_measure_is_422():
    with make_client() as client:
        meal_id = client.post("/meals").json()["meal_id"]
        resp = client.post(f"/meals/{meal_id}/foods", json={"name": "x"})
        assert resp.status_code == 422


def test_unknown_meal_detail_is_404():
    with make_client() as client:
        assert client.get("/meals/nope").status_code == 404
