import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

/** Swipeable photos with native scroll-snap (smooth on every phone). */
export function Gallery({
  photos,
  grayscale,
  children,
}: {
  photos: string[];
  grayscale?: boolean;
  children?: React.ReactNode;
}) {
  const [index, setIndex] = useState(0);
  const [loaded, setLoaded] = useState<Record<number, boolean>>({});
  const track = useRef<HTMLDivElement>(null);

  return (
    <div className="relative overflow-hidden rounded-[24px] border border-line bg-muted">
      <div
        ref={track}
        onScroll={(e) => {
          const el = e.currentTarget;
          setIndex(Math.round(el.scrollLeft / el.clientWidth));
        }}
        className="no-scrollbar flex aspect-[4/5] snap-x snap-mandatory overflow-x-auto"
      >
        {photos.map((src, i) => (
          <img
            key={src}
            src={src}
            alt=""
            ref={(el) => {
              if (el?.complete && el.naturalWidth && !loaded[i]) setLoaded((l) => ({ ...l, [i]: true }));
            }}
            onLoad={() => setLoaded((l) => ({ ...l, [i]: true }))}
            className={cn(
              "size-full shrink-0 snap-center object-cover transition-opacity duration-500",
              loaded[i] ? "opacity-100" : "opacity-0",
              grayscale && "grayscale",
            )}
          />
        ))}
      </div>
      {photos.length > 1 && (
        <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-1.5 rounded-full bg-black/25 px-2 py-1.5 backdrop-blur-md">
          {photos.map((src, i) => (
            <button
              key={src}
              type="button"
              aria-label={`Фото ${i + 1}`}
              onClick={() =>
                track.current?.scrollTo({ left: i * track.current.clientWidth, behavior: "smooth" })
              }
              className={cn(
                "h-1.5 rounded-full bg-white transition-all duration-300",
                i === index ? "w-5" : "w-1.5 opacity-50",
              )}
            />
          ))}
        </div>
      )}
      {children}
    </div>
  );
}
