import type { Product } from "@/lib/api";
import { mainPrice, secondaryPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** "520€", or the marked-down price in red with the old one struck through,
 *  and USDT underneath for older złoty posts. One component for the card
 *  and the product page, so prices always look the same. */
export function Price({ product, size = "sm" }: { product: Product; size?: "sm" | "lg" }) {
  const price = mainPrice(product);
  const other = secondaryPrice(product);
  const big = size === "lg";
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span
          className={cn(
            "font-semibold tracking-tight",
            big ? "text-[28px]" : "text-[16px]",
            price?.original ? "text-sale" : "text-ink",
          )}
        >
          {price ? price.current : "Цена по запросу"}
        </span>
        {price?.original && (
          <span className={cn("text-ink-3 line-through", big ? "text-[17px]" : "text-[13px]")}>
            {price.original}
          </span>
        )}
      </div>
      {other && (
        <div className={cn("text-ink-3", big ? "mt-1 text-[15px]" : "mt-0.5 text-[12px]")}>{other}</div>
      )}
    </div>
  );
}
