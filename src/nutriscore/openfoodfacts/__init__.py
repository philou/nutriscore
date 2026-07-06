"""OpenFoodFacts integration: text search + nutrition lookup."""

from .client import (
    NutritionSource,
    OpenFoodFactsClient,
    ProductCandidate,
    parse_nutrition,
)

__all__ = [
    "NutritionSource",
    "OpenFoodFactsClient",
    "ProductCandidate",
    "parse_nutrition",
]
