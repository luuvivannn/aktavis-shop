from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import DBSession
from api.schemas import ProductDetail, ProductList, ProductSummary
from database import ProductRepository
from database.models import ProductCategory, SortBy

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductList)
async def list_products(
    session: DBSession,
    category: ProductCategory | None = None,
    size: Annotated[str | None, Query(max_length=20)] = None,
    sort_by: SortBy = SortBy.NEWEST,
    price_min: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductList:
    """Catalog listing with filters and sort.

    - ``category`` — limit to a specific category enum value.
    - ``size`` — substring match against the product's size string
      (e.g. ``M`` matches ``M (факт M-L)``, ``42`` matches ``6.5 LV (41.5-42.5)``).
    - ``sort_by`` — ``newest`` | ``price_asc`` | ``price_desc``.
    - ``price_min`` / ``price_max`` — EUR price range (PLN for legacy
      zł-only products), inclusive.
    """
    repo = ProductRepository(session)

    items = await repo.list_available(
        category=category,
        size=size,
        sort_by=sort_by,
        price_min=price_min,
        price_max=price_max,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_available(
        category=category,
        size=size,
        price_min=price_min,
        price_max=price_max,
    )

    new_ids = await repo.get_new_product_ids()

    return ProductList(
        items=[_to_summary(p, new_ids) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/search", response_model=list[ProductSummary])
async def search_products(
    session: DBSession,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ProductSummary]:
    """Full-text search over brand/name/description."""
    repo = ProductRepository(session)
    products = await repo.search(q, limit=limit)
    new_ids = await repo.get_new_product_ids()
    return [_to_summary(p, new_ids) for p in products]


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(product_id: int, session: DBSession) -> ProductDetail:
    repo = ProductRepository(session)
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    new_ids = await repo.get_new_product_ids()
    detail = ProductDetail.model_validate(product)
    detail.is_new = product.id in new_ids
    return detail


def _to_summary(product, new_ids: set[int]) -> ProductSummary:
    summary = ProductSummary.model_validate(product)
    summary.is_new = product.id in new_ids
    return summary
