export const tg = window.Telegram?.WebApp;

let currentMainHandler = null;
let currentBackHandler = null;

export function initTelegram() {
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation?.();
  } catch (e) {
    console.error("Telegram WebApp init failed:", e);
  }
}

export function setMainButton(text, handler) {
  if (!tg?.MainButton) return;

  if (currentMainHandler) {
    try { tg.MainButton.offClick(currentMainHandler); } catch {}
  }
  currentMainHandler = handler;

  if (handler) {
    tg.MainButton.setText(text);
    tg.MainButton.onClick(handler);
    tg.MainButton.show();
    tg.MainButton.enable();
  } else {
    tg.MainButton.hide();
  }
}

export function hideMainButton() {
  setMainButton(null, null);
}

export function showMainProgress() { tg?.MainButton?.showProgress(); }
export function hideMainProgress() { tg?.MainButton?.hideProgress(); }

export function setBackButton(handler) {
  if (!tg?.BackButton) return;

  if (currentBackHandler) {
    try { tg.BackButton.offClick(currentBackHandler); } catch {}
  }
  currentBackHandler = handler;

  if (handler) {
    tg.BackButton.onClick(handler);
    tg.BackButton.show();
  } else {
    tg.BackButton.hide();
  }
}

export function hideBackButton() {
  setBackButton(null);
}

export function haptic(style = "light") {
  tg?.HapticFeedback?.impactOccurred?.(style);
}

export function notify(type = "success") {
  tg?.HapticFeedback?.notificationOccurred?.(type);
}

export function showAlert(message) {
  if (tg?.showAlert) {
    tg.showAlert(message);
  } else {
    alert(message);
  }
}

export function currentUser() {
  return tg?.initDataUnsafe?.user || null;
}
