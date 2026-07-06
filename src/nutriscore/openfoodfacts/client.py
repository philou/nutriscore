"""OpenFoodFacts HTTP client.

Exposes a small :class:`NutritionSource` protocol so the application service can
depend on an interface and tests can inject a fake. All network failures degrade
gracefully: search returns ``[]`` and nutrition lookup returns ``None`` rather
than raising into the recording flow.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel

from ..domain.events import NutritionInfo

logger = logging.getLogger(__name__)


class ProductCandidate(BaseModel):
    """A product returned by a text search, for the user to pick from."""

    id: str
    name: str
    brand: str | None = None


@runtime_checkable
class NutritionSource(Protocol):
    """The nutrition capability the app service depends on."""

    async def search_products(self, query: str) -> list[ProductCandidate]: ...

    async def get_nutrition(self, product_id: str) -> NutritionInfo | None: ...


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_nutrition(product: dict[str, Any]) -> NutritionInfo:
    """Map a raw OpenFoodFacts product dict to a :class:`NutritionInfo`."""

    nutriments = product.get("nutriments") or {}
    code = product.get("code")
    return NutritionInfo(
        off_product_id=str(code) if code else None,
        product_name=product.get("product_name") or None,
        energy_kcal_100g=_to_float(nutriments.get("energy-kcal_100g")),
        fat_100g=_to_float(nutriments.get("fat_100g")),
        saturated_fat_100g=_to_float(nutriments.get("saturated-fat_100g")),
        carbohydrates_100g=_to_float(nutriments.get("carbohydrates_100g")),
        sugars_100g=_to_float(nutriments.get("sugars_100g")),
        proteins_100g=_to_float(nutriments.get("proteins_100g")),
        salt_100g=_to_float(nutriments.get("salt_100g")),
        nutri_score_grade=(product.get("nutriscore_grade") or None),
    )


class OpenFoodFactsClient:
    """Talks to the public OpenFoodFacts API over HTTP.

    An ``httpx.AsyncClient`` may be injected (e.g. with a mock transport in
    tests); otherwise a short-lived client is created per request.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        try:
            if self._client is not None:
                resp = await self._client.get(url, params=params, timeout=self._timeout)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("OpenFoodFacts request to %s failed: %s", url, exc)
            return None

    async def search_products(self, query: str) -> list[ProductCandidate]:
        data = await self._get_json(
            f"{self._base_url}/cgi/search.pl",
            {
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 10,
                "fields": "code,product_name,brands",
            },
        )
        if not data:
            return []
        candidates: list[ProductCandidate] = []
        for product in data.get("products", []):
            code = product.get("code")
            name = product.get("product_name")
            if not code or not name:
                continue
            candidates.append(
                ProductCandidate(id=str(code), name=name, brand=product.get("brands") or None)
            )
        return candidates

    async def get_nutrition(self, product_id: str) -> NutritionInfo | None:
        data = await self._get_json(
            f"{self._base_url}/api/v2/product/{product_id}.json",
            {"fields": "code,product_name,nutriments,nutriscore_grade"},
        )
        if not data:
            return None
        product = data.get("product")
        if not product or data.get("status") == 0:
            return None
        return parse_nutrition(product)
