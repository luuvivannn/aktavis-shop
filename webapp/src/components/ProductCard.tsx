import { motion } from "motion/react";
import { useState } from "react";

import type { Product } from "@/lib/api";
import { navigate } from "@/lib/router";
import { haptic } from "@/lib/telegram";
import { cn } from "@/lib/utils";

import { FavoriteButton } from "./FavoriteButton";
import { Price } from "./Price";
import { Badge, Skeleton } from "./ui";

/** The one product tile: catalog and favourites both use it. */
export function ProductCard({ product }: { product: Product }) {
  const [loaded, setLoaded] = useState(false);
  const sold = product.status === "sold";
  return (
    <motion.article
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 500, damping: 32 }}
      onClick={() => {
        haptic("light");
        navigate(`/product/${product.id}`);
      }}
      className="flex h-full cursor-pointer flex-col overflow-hidden rounded-[22px] border border-line bg-surface/85"
    >
      <div className="relative aspect-[4/5] bg-muted">
        {product.main_photo && (
          <img
            src={product.main_photo}
            alt=""
            loading="lazy"
            // A photo already in the cache may finish before onLoad is wired.
            ref={(el) => {
              if (el?.complete && el.naturalWidth) setLoaded(true);
            }}
            onLoad={() => setLoaded(true)}
            className={cn(
              "size-full object-cover transition-opacity duration-500",
              loaded ? "opacity-100" : "opacity-0",
              sold && "grayscale",
            )}
          />
        )}
        <div className="absolute left-2.5 top-2.5 flex gap-1.5">
          {sold ? <Badge tone="dark">Продано</Badge> : product.is_new && <Badge>NEW</Badge>}
        </div>
        <FavoriteButton id={product.id} className="absolute right-2.5 top-2.5" />
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        {product.brand && (
          <div className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">
            {product.brand}
          </div>
        )}
        <div className="line-clamp-2 text-[15px] leading-snug text-ink">{product.name}</div>
        {product.size && <div className="truncate text-[13px] text-ink-2">{product.size}</div>}
        <div className="mt-auto pt-1">
          <Price product={product} />
        </div>
      </div>
    </motion.article>
  );
}

export function ProductCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-[22px] border border-line bg-surface/85">
      <Skeleton className="aspect-[4/5] rounded-none" />
      <div className="space-y-2 p-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-20" />
      </div>
    </div>
  );
}

export function ProductGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 px-4">{children}</div>;
}
