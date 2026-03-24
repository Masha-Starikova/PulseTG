interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
}

/* Карточка с одной метрикой */
export function MetricCard({ label, value, subtitle }: MetricCardProps) {
  return (
    <div className="bg-surface-card border border-border rounded-xl p-4 flex flex-col gap-1">
      <span className="text-xs text-text-muted uppercase tracking-wider">
        {label}
      </span>
      <span className="text-2xl font-semibold text-gold-400 tabular-nums">
        {value}
      </span>
      {subtitle && (
        <span className="text-xs text-text-secondary">{subtitle}</span>
      )}
    </div>
  );
}
