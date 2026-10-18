import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { activeFilterCount, CategoryChips, DEFAULT_FILTERS, FilterButton, FilterSheet } from "@/components/Filters";
import { ProductCard, ProductCardSkeleton, ProductGrid } from "@/components/ProductCard";
import { ActionButton, BrandName, Card, Heading } from "@/components/ui";
import { useCatalog, type CatalogFilters } from "@/lib/api";
import { CHANNEL_URL } from "@/lib/shop";
import { openLink } from "@/lib/telegram";

// Kept outside the component so filters survive a trip to a product and
// back, but reset when the Mini App is reopened.
let savedFilters: CatalogFilters = DEFAULT_FILTERS;

export function Catalog() {
  const [filters, setFiltersState] = useState(savedFilters);
  const [sheetOpen, setSheetOpen] = useState(false);
  const { data, isPending, isError, refetch, isPlaceholderData } = useCatalog(filters);

  const setFilters = (f: CatalogFilters) => {
    savedFilters = f;
    setFiltersState(f);
    window.scrollTo({ top: 0 });
  };

  return (
    <>
      <header className="px-4 pb-3 pt-5">
        <div className="mb-4 flex items-center gap-2.5">
          <img src={`${import.meta.env.BASE_URL}logo.jpg`} alt="" className="size-9 rounded-full object-cover" />
          <BrandName className="text-[24px] leading-none" />
        </div>
        <Heading as="h1">Каталог</Heading>
        <p className="mt-1.5 text-[15px] text-ink-2">
          Оригинальные вещи · Самая быстрая доставка в любую точку мира
        </p>
      </header>

      <div className="sticky top-0 z-30 bg-bg/25 px-4 py-2.5 backdrop-blur-xl">
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <CategoryChips
              value={filters.category}
              onChange={(category) => setFilters({ ...filters, category, size: null })}
            />
          </div>
          <FilterButton count={activeFilterCount(filters)} onClick={() => setSheetOpen(true)} />
        </div>
      </div>

      <div className="pt-2">
        {isError ? (
          <div className="px-4">
            <Card className="text-center">
              <Heading>Не загрузилось</Heading>
              <p className="mb-5 mt-2 text-[15px] text-ink-2">Проверьте интернет и попробуйте ещё раз.</p>
              <ActionButton icon={false} className="justify-center" onClick={() => refetch()}>
                Обновить
              </ActionButton>
            </Card>
          </div>
        ) : isPending ? (
          <ProductGrid>
            {Array.from({ length: 6 }, (_, i) => (
              <ProductCardSkeleton key={i} />
            ))}
          </ProductGrid>
        ) : data.items.length === 0 && !filters.category && activeFilterCount(filters) === 0 ? (
          <div className="px-4">
            <Card className="text-center">
              <Heading>Скоро здесь будут вещи</Heading>
              <p className="mb-5 mt-2 text-[15px] leading-relaxed text-ink-2">
                Каталог наполняется. Новинки сначала появляются в канале.
              </p>
              <ActionButton onClick={() => openLink(CHANNEL_URL)}>Открыть канал</ActionButton>
            </Card>
          </div>
        ) : data.items.length === 0 ? (
          <div className="px-4">
            <Card className="text-center">
              <Heading>Ничего не нашли</Heading>
              <p className="mb-5 mt-2 text-[15px] text-ink-2">
                Попробуйте другую категорию или сбросьте фильтры.
              </p>
              <ActionButton icon={false} className="justify-center" onClick={() => setFilters(DEFAULT_FILTERS)}>
                Сбросить фильтры
              </ActionButton>
            </Card>
          </div>
        ) : (
          <motion.div animate={{ opacity: isPlaceholderData ? 0.5 : 1 }} transition={{ duration: 0.2 }}>
            <ProductGrid>
              <AnimatePresence initial={false} mode="popLayout">
                {data.items.map((p) => (
                  <motion.div
                    key={p.id}
                    layout="position"
                    className="h-full"
                    initial={{ opacity: 0, scale: 0.97 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.97 }}
                    transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
                  >
                    <ProductCard product={p} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </ProductGrid>
          </motion.div>
        )}
      </div>

      <FilterSheet
        open={sheetOpen}
        filters={filters}
        onClose={() => setSheetOpen(false)}
        onApply={(f) => {
          setSheetOpen(false);
          setFilters(f);
        }}
      />
    </>
  );
}
