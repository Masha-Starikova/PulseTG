import { useState, type FormEvent } from 'react';

interface AuditFormProps {
  onSubmit: (username: string) => void;
  loading: boolean;
}

/* Форма запуска аудита канала */
export function AuditForm({ onSubmit, loading }: AuditFormProps) {
  const [username, setUsername] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const cleaned = username.trim().replace(/^@/, '');
    if (cleaned.length >= 3) {
      onSubmit(cleaned);
    }
  };

  const isValid = username.trim().replace(/^@/, '').length >= 3;

  return (
    <div className="flex flex-col items-center gap-8 py-12">
      {/* Заголовок */}
      <div className="text-center space-y-3">
        <h2 className="text-3xl font-semibold tracking-tight text-text-primary">
          Аналитика канала
        </h2>
        <p className="text-text-secondary text-sm max-w-sm">
          Введите имя Telegram-канала для глубокого анализа контента, вовлечённости и рекомендаций
        </p>
      </div>

      {/* Форма */}
      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-4">
        <div className="relative">
          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted text-sm">
            @
          </span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="channel_username"
            disabled={loading}
            className="w-full bg-surface-card border border-border rounded-xl pl-8 pr-4 py-3.5 text-sm text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-gold-500/50 focus:ring-1 focus:ring-gold-500/20 disabled:opacity-50"
          />
        </div>

        <button
          type="submit"
          disabled={!isValid || loading}
          className="w-full bg-gold-500 hover:bg-gold-400 text-forest-900 font-medium rounded-xl py-3.5 text-sm uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? 'Анализируем...' : 'Анализировать'}
        </button>
      </form>

      {/* Подсказка */}
      <p className="text-[11px] text-text-muted/60">
        Канал должен быть публичным
      </p>
    </div>
  );
}
