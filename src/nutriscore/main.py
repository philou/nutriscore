"""FastAPI application: command + query endpoints over the event-sourced core.

The app wires an event store, in-memory projections (rebuilt on startup), and an
OpenFoodFacts client into a :class:`MealService`, exposed to routes via
``request.app.state.service``. ``create_app`` allows tests to inject an isolated
store and a fake nutrition source.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .app_service import MealService
from .config import Settings, get_settings
from .domain.errors import (
    DomainError,
    InvalidCommand,
    MealAlreadyConcluded,
    MealNotFound,
)
from .domain.events import MealType
from .eventstore.sqlite import ConcurrencyError, SqliteEventStore
from .openfoodfacts.client import NutritionSource, OpenFoodFactsClient, ProductCandidate
from .projections.models import FoodAggregate, MealDetail, MealSummary
from .projections.registry import Projections
from .schemas import (
    AddFoodRequest,
    ConcludeMealResponse,
    FoodAddedResponse,
    StartMealResponse,
)


def create_app(
    settings: Settings | None = None,
    nutrition_source: NutritionSource | None = None,
    store: SqliteEventStore | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        event_store = store or SqliteEventStore(settings.db_path)
        projections = Projections()
        projections.rebuild(event_store.load_all())
        source = nutrition_source or OpenFoodFactsClient(
            settings.off_base_url, settings.off_timeout_seconds
        )
        app.state.service = MealService(event_store, projections, settings, source)
        yield

    app = FastAPI(title="nutriscore", lifespan=lifespan)
    _register_error_handlers(app)
    _register_routes(app)
    return app


def get_service(request: Request) -> MealService:
    return request.app.state.service


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(MealNotFound)
    async def _not_found(_: Request, exc: MealNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MealAlreadyConcluded)
    async def _concluded(_: Request, exc: MealAlreadyConcluded) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ConcurrencyError)
    async def _conflict(_: Request, exc: ConcurrencyError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidCommand)
    async def _invalid(_: Request, exc: InvalidCommand) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


def _register_routes(app: FastAPI) -> None:
    # -- Command endpoints (write side) ------------------------------------

    @app.post("/meals", response_model=StartMealResponse, status_code=201)
    def start_meal(service: MealService = Depends(get_service)) -> StartMealResponse:
        event = service.start_meal()
        return StartMealResponse(
            meal_id=event.meal_id, meal_type=event.meal_type, started_at=event.started_at
        )

    @app.post("/meals/{meal_id}/foods", response_model=FoodAddedResponse, status_code=201)
    async def add_food(
        meal_id: str,
        body: AddFoodRequest,
        service: MealService = Depends(get_service),
    ) -> FoodAddedResponse:
        event = await service.add_food(
            meal_id,
            name=body.name,
            quantity=body.quantity,
            weight_grams=body.weight_grams,
            off_product_id=body.off_product_id,
        )
        return FoodAddedResponse(
            meal_id=event.meal_id,
            name=event.name,
            quantity=event.quantity,
            weight_grams=event.weight_grams,
            nutrition=event.nutrition,
            added_at=event.added_at,
        )

    @app.post("/meals/{meal_id}/conclude", response_model=ConcludeMealResponse)
    def conclude_meal(
        meal_id: str, service: MealService = Depends(get_service)
    ) -> ConcludeMealResponse:
        event = service.conclude_meal(meal_id)
        return ConcludeMealResponse(meal_id=event.meal_id, concluded_at=event.concluded_at)

    # -- Lookup endpoint ---------------------------------------------------

    @app.get("/foods/search", response_model=list[ProductCandidate])
    async def search_foods(
        q: str, service: MealService = Depends(get_service)
    ) -> list[ProductCandidate]:
        return await service.search_foods(q)

    # -- Query endpoints (read side, served from projections) --------------

    @app.get("/meals", response_model=list[MealSummary])
    def list_meals(
        meal_type: MealType | None = None,
        on: date | None = None,
        service: MealService = Depends(get_service),
    ) -> list[MealSummary]:
        meals = list(service.projections.meals.values())
        if meal_type is not None:
            meals = [m for m in meals if m.meal_type == meal_type]
        if on is not None:
            meals = [m for m in meals if m.started_at.date() == on]
        return sorted(meals, key=lambda m: m.started_at)

    @app.get("/meals/{meal_id}", response_model=MealDetail)
    def get_meal(meal_id: str, service: MealService = Depends(get_service)) -> MealDetail:
        detail = service.projections.meal_details.get(meal_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"meal {meal_id!r} not found")
        return detail

    @app.get("/foods", response_model=list[FoodAggregate])
    def list_foods(service: MealService = Depends(get_service)) -> list[FoodAggregate]:
        return sorted(
            service.projections.foods.values(),
            key=lambda f: (-f.times_eaten, f.name.lower()),
        )

    @app.get("/foods/{name}", response_model=FoodAggregate)
    def get_food(name: str, service: MealService = Depends(get_service)) -> FoodAggregate:
        aggregate = service.projections.foods.get(name.strip().lower())
        if aggregate is None:
            raise HTTPException(status_code=404, detail=f"food {name!r} not found")
        return aggregate


app = create_app()
