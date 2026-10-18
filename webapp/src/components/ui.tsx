/** The few building blocks every screen is made of. Keep new screens on
 *  these so the whole app reads as one style. */
import { ArrowUpRight } from "lucide-react";
import { motion } from "motion/react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Bordered white section, the base of every screen. */
export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn("rounded-[24px] border border-line bg-surface/85 p-5", className)}
      {...props}
    />
  );
}

/** Serif heading used for page titles and card titles. */
export function Heading({
  as: Tag = "h2",
  className,
  ...props
}: ComponentProps<"h2"> & { as?: "h1" | "h2" | "h3" }) {
  return (
    <Tag
      className={cn(
        "font-serif font-semibold text-ink",
        Tag === "h1" ? "text-[40px] leading-[1.05]" : "text-[28px] leading-tight",
        className,
      )}
      {...props}
    />
  );
}

/** AKTAVIS.EU in the shop's purple comic lettering (.wordmark in index.css). */
export function BrandName({ className }: { className?: string }) {
  return <span className={cn("wordmark", className)}>AKTAVIS.EU</span>;
}

export function PageHeader({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("px-4 pb-4 pt-5", className)}>
      {children}
      <Heading as="h1">{title}</Heading>
      {subtitle && <p className="mt-1.5 text-[15px] text-ink-2">{subtitle}</p>}
    </header>
  );
}

type ActionButtonProps = Omit<ComponentProps<typeof motion.button>, "children"> & {
  children: ReactNode;
  variant?: "primary" | "secondary";
  icon?: ReactNode | false;
};

/** Full-width button with the label on the left and ↗ on the right. */
export function ActionButton({
  children,
  variant = "primary",
  icon,
  className,
  disabled,
  ...props
}: ActionButtonProps) {
  return (
    <motion.button
      type="button"
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      disabled={disabled}
      className={cn(
        "flex h-14 w-full items-center justify-between gap-3 rounded-2xl px-5",
        "text-left text-[17px] font-semibold transition-colors",
        "disabled:cursor-default disabled:opacity-50",
        variant === "primary"
          ? "bg-accent text-on-accent shadow-float"
          : "border border-line bg-surface/85 text-ink",
        className,
      )}
      {...props}
    >
      <span className="truncate">{children}</span>
      {icon !== false && (
        <span className="shrink-0 opacity-80">{icon ?? <ArrowUpRight size={22} strokeWidth={1.75} />}</span>
      )}
    </motion.button>
  );
}

/** Rounded filter chip: pink-tinted when on. */
export function Chip({
  active,
  className,
  ...props
}: ComponentProps<"button"> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "h-9 shrink-0 rounded-full border px-4 text-[14px] font-medium transition-colors",
        active
          ? "border-accent-line bg-accent-tint text-accent-ink"
          : "border-line bg-surface/75 text-ink-2 backdrop-blur-md",
        className,
      )}
      {...props}
    />
  );
}

/** Label on the left, value on the right; rows separated by hairlines. */
export function InfoRows({ rows }: { rows: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="divide-y divide-line">
      {rows.map((row) => (
        <div key={row.label} className="flex items-baseline justify-between gap-4 py-3 first:pt-0 last:pb-0">
          <dt className="text-[15px] text-ink-2">{row.label}</dt>
          <dd className="text-right text-[15px] font-medium text-ink">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function BulletList({ items }: { items: ReactNode[] }) {
  return (
    <ul className="space-y-2.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-ink-2">
          <span className="mt-[0.6em] size-1.5 shrink-0 rounded-full bg-ink-3" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-muted", className)} />;
}

export function Badge({ children, tone = "accent" }: { children: ReactNode; tone?: "accent" | "dark" }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2.5 text-[12px] font-semibold",
        tone === "accent"
          ? "border border-accent-line bg-accent-tint text-accent-ink"
          : "bg-ink text-bg",
      )}
    >
      {children}
    </span>
  );
}
