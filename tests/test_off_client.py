"""OpenFoodFacts client: response parsing and graceful degradation.

Uses httpx's MockTransport so no network is touched.
"""

import asyncio

import httpx

from nutriscore.openfoodfacts.client import OpenFoodFactsClient, parse_nutrition


def _client(handler) -> OpenFoodFactsClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return OpenFoodFactsClient("https://off.test", client=http)


def test_parse_nutrition_extracts_fields():
    product = {
        "code": "737628064502",
        "product_name": "Yogurt",
        "nutriscore_grade": "b",
        "nutriments": {"energy-kcal_100g": 60, "sugars_100g": 4.5, "proteins_100g": 3.2},
    }
    info = parse_nutrition(product)
    assert info.off_product_id == "737628064502"
    assert info.product_name == "Yogurt"
    assert info.nutri_score_grade == "b"
    assert info.energy_kcal_100g == 60
    assert info.sugars_100g == 4.5


def test_search_products_maps_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "products": [
                    {"code": "1", "product_name": "Apple", "brands": "Acme"},
                    {"code": "2", "product_name": ""},  # skipped: no name
                ]
            },
        )

    result = asyncio.run(_client(handler).search_products("apple"))
    assert len(result) == 1
    assert result[0].id == "1"
    assert result[0].brand == "Acme"


def test_get_nutrition_returns_info():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": 1,
                "product": {"code": "1", "product_name": "Apple", "nutriscore_grade": "a"},
            },
        )

    info = asyncio.run(_client(handler).get_nutrition("1"))
    assert info is not None
    assert info.nutri_score_grade == "a"


def test_get_nutrition_missing_product_degrades_to_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": 0})

    assert asyncio.run(_client(handler).get_nutrition("nope")) is None


def test_http_error_degrades_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    assert asyncio.run(_client(handler).search_products("x")) == []
    assert asyncio.run(_client(handler).get_nutrition("x")) is None
