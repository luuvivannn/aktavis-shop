/** A thin, typed layer over window.Telegram.WebApp. Every call is optional:
 *  outside Telegram (a browser during development) they quietly do nothing. */

interface WebApp {
  initData: string;
  initDataUnsafe: {
    start_param?: string;
    user?: { id: number; allows_write_to_pm?: boolean };
  };
  colorScheme: "light" | "dark";
  version: string;
  platform: string;
  ready(): void;
  expand(): void;
  isVersionAtLeast(v: string): boolean;
  setHeaderColor?(color: string): void;
  setBackgroundColor?(color: string): void;
  setBottomBarColor?(color: string): void;
  disableVerticalSwipes?(): void;
  requestWriteAccess?(): void;
  openTelegramLink(url: string): void;
  openLink(url: string): void;
  onEvent(event: string, cb: () => void): void;
  MainButton: {
    setParams(params: {
      text?: string;
      color?: string;
      text_color?: string;
      is_active?: boolean;
      is_visible?: boolean;
    }): void;
    onClick(cb: () => void): void;
    offClick(cb: () => void): void;
    hide(): void;
  };
  BackButton: {
    show(): void;
    hide(): void;
    onClick(cb: () => void): void;
    offClick(cb: () => void): void;
  };
  HapticFeedback?: {
    impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
    selectionChanged(): void;
    notificationOccurred(type: "success" | "warning" | "error"): void;
  };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp };
  }
}

// The SDK script defines WebApp even in a plain browser; initData is only
// filled inside Telegram.
const raw = window.Telegram?.WebApp;
export const tg: WebApp | undefined = raw && raw.initData ? raw : undefined;

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function applyTheme() {
  const dark = tg
    ? tg.colorScheme === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
  const bg = cssVar("--bg");
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", bg);
  if (tg?.isVersionAtLeast("6.1")) {
    tg.setHeaderColor?.(bg);
    tg.setBackgroundColor?.(bg);
  }
  if (tg?.isVersionAtLeast("7.10")) tg.setBottomBarColor?.(bg);
  // The buy button takes its colours from the theme too.
  mainButtonRestyle?.();
}

export function initTelegram() {
  applyTheme();
  if (!tg) {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", applyTheme);
    return;
  }
  tg.ready();
  tg.expand();
  // Scrolling the catalog must not swipe the whole app closed.
  if (tg.isVersionAtLeast("7.7")) tg.disableVerticalSwipes?.();
  tg.onEvent("themeChanged", applyTheme);
}

export function startParam(): string | undefined {
  return tg?.initDataUnsafe.start_param;
}

const WRITE_ACCESS_ASKED_KEY = "aktavis_write_access_asked";

/** The bot's daily promo and hourly cards only reach users who let it
 *  message them. Those who already did are (re-)registered on every open;
 *  everyone else gets Telegram's own "allow messages?" prompt once per
 *  device. If they agree, Telegram tells the bot directly. */
export function setupPromoAudience(subscribe: () => Promise<unknown>) {
  const user = tg?.initDataUnsafe.user;
  if (!tg || !user) return;

  if (user.allows_write_to_pm) {
    subscribe().catch(() => {});
    return;
  }

  if (!tg.requestWriteAccess || !tg.isVersionAtLeast("6.9")) return;
  try {
    if (localStorage.getItem(WRITE_ACCESS_ASKED_KEY)) return;
    localStorage.setItem(WRITE_ACCESS_ASKED_KEY, "1");
  } catch {
    return; // can't remember that we asked — better not to nag every open
  }
  // Let the catalog paint first so the prompt doesn't land on a blank screen.
  setTimeout(() => tg.requestWriteAccess?.(), 1500);
}

export function haptic(style: "light" | "medium" | "soft" = "light") {
  tg?.HapticFeedback?.impactOccurred(style);
}

export function hapticSelect() {
  tg?.HapticFeedback?.selectionChanged();
}

// Inside Telegram even when no initData came with the launch: window.open
// silently does nothing in the phone apps, so the SDK has to open links.
const inTelegram = raw && raw.platform !== "unknown" ? raw : undefined;

/** t.me links open inside Telegram; anything else in the browser. */
export function openLink(url: string) {
  if (inTelegram && url.startsWith("https://t.me/")) inTelegram.openTelegramLink(url);
  else if (inTelegram) inTelegram.openLink(url);
  else window.open(url, "_blank", "noopener");
}

let mainHandler: (() => void) | null = null;
let mainButtonRestyle: (() => void) | null = null;

/** Telegram's own button at the bottom of the screen: taps on it reach the
 *  app on every phone. null hides it. Returns whether it shows. */
export function setMainButton(text: string | null, handler?: () => void): boolean {
  if (!inTelegram?.isVersionAtLeast("6.1")) return false;
  const button = inTelegram.MainButton;
  if (mainHandler) button.offClick(mainHandler);
  mainHandler = null;
  mainButtonRestyle = null;
  if (text === null || !handler) {
    button.hide();
    return false;
  }
  mainHandler = handler;
  mainButtonRestyle = () =>
    button.setParams({ color: cssVar("--accent"), text_color: cssVar("--on-accent") });
  button.setParams({
    text,
    color: cssVar("--accent"),
    text_color: cssVar("--on-accent"),
    is_active: true,
    is_visible: true,
  });
  button.onClick(handler);
  return true;
}

let backHandler: (() => void) | null = null;

/** Telegram's own back button in the header; null hides it. */
export function setBackButton(handler: (() => void) | null) {
  if (!tg) return;
  if (backHandler) tg.BackButton.offClick(backHandler);
  backHandler = handler;
  if (handler) {
    tg.BackButton.onClick(handler);
    tg.BackButton.show();
  } else {
    tg.BackButton.hide();
  }
}
