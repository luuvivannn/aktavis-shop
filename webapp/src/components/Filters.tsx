import { SlidersHorizontal, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { CatalogFilters, Category, SortBy } from "@/lib/api";
import { haptic, hapticSelect } from "@/lib/telegram";

import { ActionButton, Chip, Heading } from "./ui";

// Same order as the old Mini App. «Под заказ» moved to its own tab.
export const CATEGORIES: { value: Category | null; label: string }[] = [
  { value: null, label: "Все" },
  { value: "shoes", label: "Обувь" },
  { value: "tops", label: "Худи / Футболки" },
  { value: "jackets", label: "Куртки" },
  { value: "pants", label: "Шорты/Штаны" },
  { value: "bags", label: "Сумки" },
  { value: "accessories", label: "Аксессуары" },
];

const SORTS: { value: SortBy; label: string }[] = [
  { value: "newest", label: "Сначала новые" },
  { value: "price_asc", label: "Дешевле" },
  { value: "price_desc", label: "Дороже" },
];

const CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL"];
const SHOE_SIZES = ["36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"];

function sizesFor(category: Category | null): string[] | null {
  if (category === "shoes") return SHOE_SIZES;
  if (category && ["tops", "jackets", "pants"].includes(category)) return CLOTHING_SIZES;
  return null;
}

export const DEFAULT_FILTERS: CatalogFilters = {
  category: null,
  size: null,
  sort_by: "newest",
  price_min: null,
  price_max: null,
};

/** Filters besides the category, for the badge on the filter button. */
export function activeFilterCount(f: CatalogFilters): number {
  return [f.size, f.price_min, f.price_max, f.sort_by !== "newest" || null].filter(
    (v) => v !== null && v !== undefined,
  ).length;
}

export function CategoryChips({
  value,
  onChange,
}: {
  value: Category | null;
  onChange: (c: Category | null) => void;
}) {
  return (
    // Fades out on the right, where the row scrolls under the filter button.
    <div className="no-scrollbar -ml-4 flex gap-2 overflow-x-auto pl-4 pr-6 [mask-image:linear-gradient(to_right,black_calc(100%-32px),transparent)]">
      {CATEGORIES.map((c) => (
        <Chip
          key={c.label}
          active={value === c.value}
          onClick={() => {
            if (value === c.value) return;
            hapticSelect();
            onChange(c.value);
          }}
        >
          {c.label}
        </Chip>
      ))}
    </div>
  );
}

export function FilterButton({ count, onClick }: { count: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Фильтры"
      className="relative grid size-9 shrink-0 place-items-center rounded-full border border-line bg-surface/75 text-ink backdrop-blur-md"
    >
      <SlidersHorizontal size={17} strokeWidth={1.75} />
      {count > 0 && (
        <span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-accent text-[10px] font-bold text-on-accent">
          {count}
        </span>
      )}
    </button>
  );
}

/** Bottom sheet with sort, size and price. Changes apply on «Показать». */
export function FilterSheet({
  open,
  filters,
  onClose,
  onApply,
}: {
  open: boolean;
  filters: CatalogFilters;
  onClose: () => void;
  onApply: (f: CatalogFilters) => void;
}) {
  const [draft, setDraft] = useState(filters);
  useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const sizes = sizesFor(draft.category);
  const set = (patch: Partial<CatalogFilters>) => {
    hapticSelect();
    setDraft((d) => ({ ...d, ...patch }));
  };
  const number = (v: string) => (v.trim() ? Math.max(0, Number(v.replace(/\D/g, ""))) : null);

  return (
    <AnimatePresence>
      {open && (
        <div className="bottom-visible fixed inset-x-0 top-0 z-50">
          <motion.div
            className="absolute inset-0 bg-black/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-label="Фильтры"
            className="pb-safe absolute inset-x-0 bottom-0 rounded-t-[28px] border-t border-line bg-surface"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "tween", duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 600) onClose();
            }}
          >
            <div className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-line" />
            <div className="flex items-center justify-between px-5 pb-2 pt-3">
              <Heading>Фильтры</Heading>
              <button
                type="button"
                onClick={onClose}
                aria-label="Закрыть"
                className="grid size-9 place-items-center rounded-full bg-muted text-ink-2"
              >
                <X size={18} />
              </button>
            </div>

            <div className="max-h-[60vh] space-y-6 overflow-y-auto px-5 py-3">
              <section>
                <h3 className="mb-2.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                  Сортировка
                </h3>
                <div className="flex flex-wrap gap-2">
                  {SORTS.map((s) => (
                    <Chip key={s.value} active={draft.sort_by === s.value} onClick={() => set({ sort_by: s.value })}>
                      {s.label}
                    </Chip>
                  ))}
                </div>
              </section>

              {sizes && (
                <section>
                  <h3 className="mb-2.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                    Размер
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    <Chip active={!draft.size} onClick={() => set({ size: null })}>
                      Любой
                    </Chip>
                    {sizes.map((s) => (
                      <Chip key={s} active={draft.size === s} onClick={() => set({ size: s })}>
                        {s}
                      </Chip>
                    ))}
                  </div>
                </section>
              )}

              <section>
                <h3 className="mb-2.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                  Цена, €
                </h3>
                <div className="flex items-center gap-3">
                  {(["price_min", "price_max"] as const).map((key) => (
                    <input
                      key={key}
                      inputMode="numeric"
                      placeholder={key === "price_min" ? "от" : "до"}
                      value={draft[key] ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, [key]: number(e.target.value) }))}
                      className="h-12 w-full rounded-2xl border border-line bg-surface px-4 text-[16px] text-ink outline-none placeholder:text-ink-3 focus:border-accent-line"
                    />
                  ))}
                </div>
              </section>
            </div>

            <div className="flex gap-3 px-5 pb-4 pt-3">
              <ActionButton
                variant="secondary"
                icon={false}
                className="w-auto justify-center px-6"
                onClick={() => {
                  haptic("light");
                  onApply({ ...DEFAULT_FILTERS, category: draft.category });
                }}
              >
                Сбросить
              </ActionButton>
              <ActionButton
                icon={false}
                className="justify-center"
                onClick={() => {
                  haptic("medium");
                  onApply(draft);
                }}
              >
                Показать
              </ActionButton>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
