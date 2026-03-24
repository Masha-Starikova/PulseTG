import type { TelegramWebApp } from '../types/telegram';

/* Получение инстанса Telegram WebApp (null если вне Telegram) */
export function getTelegramWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

/* Проверка, запущено ли приложение внутри Telegram */
export function isTelegramMiniApp(): boolean {
  return getTelegramWebApp() !== null;
}

/* Инициализация Telegram Mini App */
export function initTelegramApp(): void {
  const tg = getTelegramWebApp();
  if (!tg) return;

  tg.ready();
  tg.expand();
}
