import { useEffect } from "react";

import { ProductCard, ProductCardSkeleton, ProductGrid } from "@/components/ProductCard";
import { ActionButton, Card, Heading, PageHeader } from "@/components/ui";
import { useProducts } from "@/lib/api";
import { favorites, useFavorites } from "@/lib/favorites";
import { navigate } from "@/lib/router";
import { pluralRu } from "@/lib/utils";

export function Favorites() {
  const ids = useFavorites();
  const { data, isPending } = useProducts(ids);

  // Products that no longer exist drop out of the list.
  useEffect(() => {
    if (!data) return;
    const live = new Set(data.map((p) => p.id));
    const gone = ids.filter((id) => !live.has(id));
    if (gone.length) favorites.remove(gone);
  }, [data, ids]);

  if (ids.length === 0) {
    return (
      <>
        <PageHeader title="Избранное" />
        <div className="px-4">
          <Card className="text-center">
            <Heading>Пока пусто</Heading>
            <p className="mb-5 mt-2 text-[15px] leading-relaxed text-ink-2">
              Нажмите на сердечко у товара, и он появится здесь.
            </p>
            <ActionButton onClick={() => navigate("/")}>К каталогу</ActionButton>
          </Card>
        </div>
      </>
    );
  }

  // In the order they were saved (newest first).
  const products = data ? ids.flatMap((id) => data.find((p) => p.id === id) ?? []) : [];

  return (
    <>
      <PageHeader
        title="Избранное"
        subtitle={`${ids.length} ${pluralRu(ids.length, "товар", "товара", "товаров")}`}
      />
      <ProductGrid>
        {isPending
          ? ids.slice(0, 6).map((id) => <ProductCardSkeleton key={id} />)
          : products.map((p) => <ProductCard key={p.id} product={p} />)}
      </ProductGrid>
    </>
  );
}
