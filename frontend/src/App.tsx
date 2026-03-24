import { Layout } from './components/Layout';
import { Loader } from './components/Loader';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AuditForm } from './pages/AuditForm';
import { AuditResult } from './pages/AuditResult';
import { useAudit } from './hooks/useAudit';
import { useTelegram } from './hooks/useTelegram';

function App() {
  const { audit, loading, error, startAudit, reset } = useAudit();
  useTelegram();

  /* Определяем текущий экран */
  const isCompleted = audit?.status === 'completed';
  const isFailed = audit?.status === 'failed';
  const report = audit?.report ?? null;
  const showResult = Boolean(report);
  const showLoader = loading && !showResult;
  const showForm = !showResult && !showLoader;

  console.log('APP STATE', { status: audit?.status, hasReport: !!audit?.report, loading, error });

  return (
    <Layout>
      {/* Ошибка */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 mb-6">
          <p className="text-sm text-red-400">{error}</p>
          <button
            onClick={reset}
            className="text-xs text-red-300 underline mt-1"
          >
            Попробовать снова
          </button>
        </div>
      )}

      {/* Форма */}
      {showForm && <AuditForm onSubmit={startAudit} loading={loading} />}

      {/* Лоадер */}
      {showLoader && <Loader status={audit?.status} />}

      {/* Completed но report = null — fallback */}
      {isCompleted && !report && !loading && (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-text-muted text-sm">
            Аудит завершён, но отчёт пуст. Попробуйте снова.
          </p>
          <button
            onClick={reset}
            className="text-sm text-gold-400 border border-gold-500/30 rounded-lg px-4 py-2"
          >
            Новый аудит
          </button>
        </div>
      )}

      {/* Failed без error message — fallback */}
      {isFailed && !error && (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-text-muted text-sm">
            Аудит завершился с ошибкой.
          </p>
          <button
            onClick={reset}
            className="text-sm text-gold-400 border border-gold-500/30 rounded-lg px-4 py-2"
          >
            Попробовать снова
          </button>
        </div>
      )}

      {/* Результат */}
      {showResult && report && (
        <ErrorBoundary onReset={reset}>
          <AuditResult
            report={report}
            channelUsername={audit?.channel_username ?? ''}
            onReset={reset}
          />
        </ErrorBoundary>
      )}
    </Layout>
  );
}

export default App;
