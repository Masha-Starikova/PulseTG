import { useCallback, useEffect, useRef, useState } from 'react';
import type { AuditResponse } from '../types/audit';
import { createAudit, getAudit } from '../services/auditService';

/* Интервал поллинга статуса аудита (мс) */
const POLL_INTERVAL = 2_000;
/* Сколько ошибок подряд допускаем, прежде чем остановить поллинг */
const MAX_CONSECUTIVE_ERRORS = 3;

interface UseAuditReturn {
  audit: AuditResponse | null;
  loading: boolean;
  error: string | null;
  startAudit: (username: string) => Promise<void>;
  reset: () => void;
}

/* Хук для управления жизненным циклом аудита */
export function useAudit(): UseAuditReturn {
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const errorCountRef = useRef(0);

  /* Остановка поллинга */
  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    errorCountRef.current = 0;
  }, []);

  /* Один тик поллинга — вынесен чтобы вызывать и сразу, и по интервалу */
  const pollOnce = useCallback(
    async (auditId: string): Promise<boolean> => {
      try {
        const updated = await getAudit(auditId);
        console.log('POLL UPDATE', {
          status: updated.status,
          hasReport: !!updated.report,
          reportKeys: updated.report ? Object.keys(updated.report) : null,
        });

        errorCountRef.current = 0; // сброс счётчика ошибок при успехе
        setAudit(updated);

        // Останавливаем поллинг не только по статусу, но и при наличии готового отчёта.
        // Это защищает UI от различий контрактов между версиями backend.
        if (updated.report || updated.status === 'completed' || updated.status === 'failed') {
          setLoading(false);
          if (updated.status === 'failed') {
            setError(updated.error_message ?? 'Аудит завершился с ошибкой');
          }
          return true; // сигнал: остановить поллинг
        }
        return false;
      } catch (err) {
        errorCountRef.current += 1;
        console.warn(
          `Poll error (${errorCountRef.current}/${MAX_CONSECUTIVE_ERRORS}):`,
          err instanceof Error ? err.message : err,
        );

        if (errorCountRef.current >= MAX_CONSECUTIVE_ERRORS) {
          setLoading(false);
          setError('Ошибка при получении статуса аудита');
          return true; // остановить поллинг
        }
        return false; // продолжить — может сеть восстановится
      }
    },
    [],
  );

  /* Запуск поллинга статуса */
  const startPolling = useCallback(
    (auditId: string) => {
      stopPolling();

      // Первый запрос — сразу, не ждём 2 секунды
      pollOnce(auditId).then((done) => {
        if (done) return;

        // Запускаем регулярный интервал только если первый запрос не финальный
        timerRef.current = setInterval(async () => {
          const shouldStop = await pollOnce(auditId);
          if (shouldStop) {
            stopPolling();
          }
        }, POLL_INTERVAL);
      });
    },
    [stopPolling, pollOnce],
  );

  /* Создание нового аудита */
  const startAudit = useCallback(
    async (username: string) => {
      setError(null);
      setLoading(true);
      setAudit(null);

      try {
        const created = await createAudit(username);
        console.log('AUDIT CREATED', { id: created.id, status: created.status });
        setAudit(created);
        startPolling(created.id);
      } catch (err) {
        setLoading(false);
        setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
      }
    },
    [startPolling],
  );

  /* Сброс состояния */
  const reset = useCallback(() => {
    stopPolling();
    setAudit(null);
    setLoading(false);
    setError(null);
  }, [stopPolling]);

  /* Очистка при размонтировании */
  useEffect(() => stopPolling, [stopPolling]);

  return { audit, loading, error, startAudit, reset };
}
