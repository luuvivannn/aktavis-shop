import { Heart, Info, PackageSearch, ShoppingBag, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";

import { useFavorites } from "@/lib/favorites";
import { navigate, type Route } from "@/lib/router";
import { hapticSelect } from "@/lib/telegram";
import { cn } from "@/lib/utils";

const TABS: { route: Route["name"]; path: string; label: string; icon: LucideIcon }[] = [
  { route: "catalog", path: "/", label: "Каталог", icon: ShoppingBag },
  { route: "favorites", path: "/favorites", label: "Избранное", icon: Heart },
  { route: "custom-order", path: "/custom-order", label: "Под заказ", icon: PackageSearch },
  { route: "about", path: "/about", label: "О магазине", icon: Info },
];

/** Floating bottom bar; the active tab sits on a soft pink pill. */
export function TabBar({ active }: { active: Route["name"] }) {
  const favoritesCount = useFavorites().length;
  return (
    <nav className="pb-safe bottom-visible fixed inset-x-0 z-40 px-3">
      <div className="mb-3 grid grid-cols-4 rounded-[28px] border border-line bg-surface/90 p-1.5 shadow-float backdrop-blur-xl">
        {TABS.map(({ route, path, label, icon: Icon }) => {
          const on = route === active;
          return (
            <button
              key={route}
              type="button"
              onClick={() => {
                if (on) return window.scrollTo({ top: 0, behavior: "smooth" });
                hapticSelect();
                navigate(path);
              }}
              className="flex flex-col items-center gap-0.5 py-1"
            >
              <span className="relative grid h-8 w-14 place-items-center">
                {on && (
                  <motion.span
                    layoutId="tab-pill"
                    className="absolute inset-0 rounded-full bg-accent-tint"
                    transition={{ type: "spring", stiffness: 500, damping: 38 }}
                  />
                )}
                <Icon
                  size={22}
                  strokeWidth={on ? 2 : 1.6}
                  className={cn("relative", on ? "text-accent" : "text-ink")}
                />
                {route === "favorites" && favoritesCount > 0 && (
                  <span className="absolute right-1.5 top-0 grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-bold text-on-accent">
                    {favoritesCount}
                  </span>
                )}
              </span>
              <span className={cn("text-[11px] text-ink-2", on && "font-semibold text-ink")}>
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
