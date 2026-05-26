from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from database.models import ProductCategory, ProductStatus


def _normalize_photo_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/")):
        return path
    return "/" + path


class ProductSummary(BaseModel):
    """Compact product representation for catalog grids."""

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
    is_new: bool = False

    @field_validator("main_photo", mode="before")
    @classmethod
    def _normalize(cls, v: str | None) -> str | None:
        return _normalize_photo_url(v)


class ProductDetail(ProductSummary):
    """Full product view shown on the detail screen."""

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
    """Paginated catalog response."""

    items: list[ProductSummary]
    total: int
    limit: int
    offset: int
