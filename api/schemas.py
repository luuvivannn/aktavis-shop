from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from database.models import (
    DeliveryMethod,
    OrderStatus,
    ProductCategory,
    ProductStatus,
)


def _normalize_photo_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/")):
        return path
    return "/" + path


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    name: str
    category: ProductCategory
    size: str | None
    price_pln: int
    price_usdt: int | None
    status: ProductStatus
    main_photo: str | None

    @field_validator("main_photo", mode="before")
    @classmethod
    def _normalize(cls, v: str | None) -> str | None:
        return _normalize_photo_url(v)


class ProductDetail(ProductSummary):
    condition: str | None
    description: str | None
    note: str | None
    photos: list[str]

    @field_validator("photos", mode="before")
    @classmethod
    def _normalize_photos(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        return [p for p in (_normalize_photo_url(item) for item in v) if p]


class ProductList(BaseModel):
    items: list[ProductSummary]
    total: int
    limit: int
    offset: int


class CartItemIn(BaseModel):
    product_id: Annotated[int, Field(gt=0)]
    quantity: Annotated[int, Field(ge=1, le=10)] = 1


class OrderCreateIn(BaseModel):
    items: Annotated[list[CartItemIn], Field(min_length=1, max_length=20)]
    delivery_method: DeliveryMethod = DeliveryMethod.COURIER_WARSAW
    delivery_address: str | None = None
    phone: Annotated[str | None, Field(max_length=50)] = None
    full_name: Annotated[str | None, Field(max_length=200)] = None
    comment: Annotated[str | None, Field(max_length=1000)] = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    price_pln: int
    price_usdt: int | None
    quantity: int
    product: ProductSummary


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: OrderStatus
    delivery_method: DeliveryMethod
    delivery_address: str | None
    phone: str | None
    full_name: str | None
    comment: str | None
    total_pln: int
    total_usdt: int
    created_at: datetime
    items: list[OrderItemOut]


class MeOut(BaseModel):
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    is_premium: bool
