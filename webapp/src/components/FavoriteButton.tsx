import { Heart } from "lucide-react";
import { motion } from "motion/react";

import { favorites, useFavorites } from "@/lib/favorites";
import { haptic } from "@/lib/telegram";
import { cn } from "@/lib/utils";

export function FavoriteButton({ id, className }: { id: number; className?: string }) {
  const on = useFavorites().includes(id);
  return (
    <motion.button
      type="button"
      aria-label={on ? "Убрать из избранного" : "В избранное"}
      aria-pressed={on}
      whileTap={{ scale: 0.85 }}
      onClick={(e) => {
        e.stopPropagation();
        favorites.toggle(id);
        haptic("light");
      }}
      className={cn(
        "grid size-9 place-items-center rounded-full border border-line/60",
        "bg-surface/80 text-ink backdrop-blur-md",
        className,
      )}
    >
      <motion.span
        key={String(on)}
        initial={{ scale: 0.6 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 600, damping: 18 }}
      >
        <Heart
          size={18}
          strokeWidth={1.75}
          className={cn(on && "fill-current text-like")}
        />
      </motion.span>
    </motion.button>
  );
}
