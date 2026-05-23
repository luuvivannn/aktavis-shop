from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import DBSession
from api.schemas import ProductDetail, ProductList, ProductSummary
from database import ProductCategory, ProductRepository

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductList)
async def list_products(
    session: DBSession,
    category: ProductCategory | None = None,
    brand: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductList:
    repo = ProductRepository(session)
    items = await repo.list_available(
        category=category, brand=brand, limit=limit, offset=offset
    )
    total = await repo.count_available(category=category, brand=brand)
    return ProductList(
        items=[ProductSummary.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/brands", response_model=list[str])
async def list_brands(session: DBSession) -> list[str]:
    return await ProductRepository(session).list_brands()


@router.get("/search", response_model=list[ProductSummary])
async def search_products(
    session: DBSession,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ProductSummary]:
    products = await ProductRepository(session).search(q, limit=limit)
    return [ProductSummary.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(product_id: int, session: DBSession) -> ProductDetail:
    product = await ProductRepository(session).get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return ProductDetail.model_validate(product)
