import { useEffect, useMemo } from 'react';
import { getTelegramWebApp, isTelegramMiniApp, initTelegramApp } from '../services/telegram';

/* Хук для работы с Telegram WebApp */
export function useTelegram() {
  const webApp = useMemo(() => getTelegramWebApp(), []);
  const isMiniApp = useMemo(() => isTelegramMiniApp(), []);

  useEffect(() => {
    initTelegramApp();
  }, []);

  return { webApp, isMiniApp };
}
