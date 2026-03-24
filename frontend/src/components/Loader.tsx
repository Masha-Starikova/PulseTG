import type { AuditStatus } from '../types/audit';

/* Текст для каждого статуса */
const STATUS_TEXT: Record<string, string> = {
  pending: 'Ожидание в очереди...',
  running: 'Анализируем канал...',
};

interface LoaderProps {
  status?: AuditStatus;
}

/* Лоадер с анимацией и текстом статуса */
export function Loader({ status }: LoaderProps) {
  const text = status ? STATUS_TEXT[status] ?? 'Загрузка...' : 'Загрузка...';

  return (
    <div className="flex flex-col items-center gap-6 py-16">
      {/* Пульсирующий индикатор */}
      <div className="relative w-16 h-16">
        <div className="absolute inset-0 rounded-full border-2 border-gold-500/30 animate-ping" />
        <div className="absolute inset-2 rounded-full border-2 border-gold-500/50 animate-pulse" />
        <div className="absolute inset-4 rounded-full bg-gold-500/20 animate-pulse" />
        <div className="absolute inset-[22px] rounded-full bg-gold-500" />
      </div>

      <p className="text-text-secondary text-sm animate-pulse">{text}</p>
    </div>
  );
}
