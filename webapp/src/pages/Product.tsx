import { ChevronLeft } from "lucide-react";
import { useEffect, useState } from "react";

import { FavoriteButton } from "@/components/FavoriteButton";
import { Gallery } from "@/components/Gallery";
import { Price } from "@/components/Price";
import { ActionButton, Badge, Card, Heading, Skeleton } from "@/components/ui";
import { useProduct, type ProductDetail } from "@/lib/api";
import { productTitle } from "@/lib/format";
import { sellerLink } from "@/lib/shop";
import { haptic, openLink, setMainButton, tg } from "@/lib/telegram";

/** The photo URL makes Telegram show the item to the seller in the chat. */
function orderMessage(p: ProductDetail): string {
  const lines = [`Привет! Хочу купить ${productTitle(p)}, размер ${p.size || "—"}`];
  if (p.main_photo) lines.push(new URL(p.main_photo, location.origin).href);
  return lines.join("\n");
}

function writeToSeller(p: ProductDetail) {
  haptic("medium");
  openLink(sellerLink(orderMessage(p)));
}

/** In Telegram the buy button is Telegram's own; our HTML one stays for
 *  the browser and for items that can't be bought. */
function useNativeBuyButton(p: ProductDetail | undefined): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    setShown(setMainButton(p ? "Написать продавцу" : null, p ? () => writeToSeller(p) : undefined));
    return () => {
      setMainButton(null);
    };
  }, [p]);
  return shown;
}

export function ProductPage({ id }: { id: number }) {
  const { data: p, isPending, isError } = useProduct(id);
  const nativeBuyButton = useNativeBuyButton(p?.status === "in_stock" ? p : undefined);

  if (isPending) {
    return (
      <div className="space-y-4 px-4 pt-4">
        <Skeleton className="aspect-[4/5] rounded-[24px]" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-8 w-32" />
      </div>
    );
  }
  if (isError || !p) {
    return (
      <div className="px-4 pt-4">
        <BrowserBack />
        <Card className="text-center">
          <Heading>Товар не найден</Heading>
          <p className="mt-2 text-[15px] text-ink-2">Возможно, его уже убрали из каталога.</p>
        </Card>
      </div>
    );
  }

  const sold = p.status === "sold";
  const available = p.status === "in_stock";

  return (
    <>
      <div className="space-y-4 px-4 pt-4">
        <BrowserBack />
        <Gallery photos={p.photos} grayscale={sold}>
          <div className="absolute left-3 top-3 flex gap-1.5">
            {sold ? <Badge tone="dark">Продано</Badge> : p.is_new && <Badge>NEW</Badge>}
          </div>
          <FavoriteButton id={p.id} className="absolute right-3 top-3" />
        </Gallery>

        <div className="px-1 pt-1">
          {p.brand && (
            <div className="text-[12px] font-semibold uppercase tracking-[0.1em] text-ink-2">{p.brand}</div>
          )}
          <Heading as="h1" className="mt-1 text-[36px]">
            {p.name}
          </Heading>
          <div className="mt-3">
            <Price product={p} size="lg" />
          </div>
        </div>

        {p.note && (
          <Card className="border-accent-line bg-accent-tint py-4 text-[15px] text-accent-ink">{p.note}</Card>
        )}

        {p.description && (
          <Card>
            <Heading className="mb-2 text-[26px]">Описание</Heading>
            <p className="whitespace-pre-line text-[15px] leading-relaxed text-ink-2">{p.description}</p>
          </Card>
        )}
      </div>

      {!nativeBuyButton && (
        <div className="px-4 pt-4">
          <ActionButton
            disabled={!available}
            icon={available ? undefined : false}
            onClick={() => writeToSeller(p)}
          >
            {available ? "Написать продавцу" : sold ? "Уже продано" : "Сейчас недоступно"}
          </ActionButton>
        </div>
      )}
    </>
  );
}

/** Outside Telegram (a browser during development) there is no header
 *  back button, so show our own. */
function BrowserBack() {
  if (tg) return null;
  return (
    <button
      type="button"
      onClick={() => history.back()}
      className="-ml-1 flex items-center gap-1 text-[15px] text-ink-2"
    >
      <ChevronLeft size={20} /> Назад
    </button>
  );
}
