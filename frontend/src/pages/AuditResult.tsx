import { type ReactNode, useState } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { AuditReport, PostMetrics } from '../types/audit';
import { MetricCard } from '../components/MetricCard';
import { PostCard } from '../components/PostCard';

interface AuditResultProps {
  report: AuditReport;
  channelUsername: string;
  onReset: () => void;
}

/* ─── Helpers ─── */

/** Оборачивает секцию в try/catch — если рендер падает, показывает ошибку вместо краша */
function SafeSection({ name, children }: { name: string; children: () => ReactNode }) {
  try {
    const content = children();
    return <>{content}</>;
  } catch (err) {
    console.error(`[SafeSection:${name}] render crashed:`, err);
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3">
        <p className="text-xs text-red-400">Ошибка рендера секции: {name}</p>
        <p className="text-xs text-red-400/60 mt-1">
          {err instanceof Error ? err.message : String(err)}
        </p>
      </div>
    );
  }
}

/**
 * Backend возвращает strengths/problems как строку (одна строка с \n),
 * а фронтенд ожидает string[]. Нормализуем в массив.
 */
function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((v) => typeof v === 'string' && v.trim());
  if (typeof value === 'string' && value.trim()) {
    return value.split('\n').map((s) => s.replace(/^[-•*]\s*/, '').trim()).filter(Boolean);
  }
  return [];
}

/* ─── Main Component ─── */

export function AuditResult({ report, channelUsername, onReset }: AuditResultProps) {
  const [showRaw, setShowRaw] = useState(false);

  // CRITICAL: debug log — всегда видим что пришло
  console.log('FULL RESPONSE:', report);
  console.log('REPORT:', JSON.stringify(report, null, 2).slice(0, 2000));

  /* ── Абсолютный guard: нет report вообще ── */
  if (!report || typeof report !== 'object') {
    console.error('AuditResult: report is null/invalid', report);
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-text-muted text-sm">Отчёт пуст или повреждён.</p>
        <button onClick={onReset} className="text-sm text-gold-400 border border-gold-500/30 rounded-lg px-4 py-2">
          Новый аудит
        </button>
      </div>
    );
  }

  /* ── Безопасное извлечение данных ── */
  const metrics = report?.metrics;
  const ai = report?.ai as Record<string, unknown> | undefined;

  // Нет метрик → показываем raw JSON чтобы хоть что-то было видно
  if (!metrics) {
    console.error('AuditResult: report.metrics is missing', report);
    return (
      <div className="space-y-4 pb-8">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">@{channelUsername}</h2>
          <button onClick={onReset} className="text-xs text-text-muted border border-border rounded-lg px-3 py-1.5">
            Новый аудит
          </button>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <p className="text-sm text-red-400 mb-2">Данные метрик отсутствуют в отчёте.</p>
        </div>
        <div className="bg-surface-card border border-border rounded-xl p-4">
          <p className="text-xs text-text-muted mb-2">Raw JSON:</p>
          <pre className="text-xs text-text-secondary overflow-auto max-h-96 whitespace-pre-wrap">
            {JSON.stringify(report, null, 2)}
          </pre>
        </div>
      </div>
    );
  }

  const summary = metrics.summary ?? {
    posts_count: 0, avg_views: 0, avg_er: 0,
    avg_forwards: 0, avg_text_length: 0, posts_per_day: 0,
  };
  const engagement = metrics.engagement ?? { formula: '', best_posts: [], worst_posts: [] };
  const trends = metrics.trends ?? { weekly: [], direction: 'unknown' as const };
  const posting_time = metrics.posting_time ?? { by_hour: {}, best_hour: null, by_weekday: {}, best_weekday: null };

  /* Нормализация AI полей — backend может вернуть строку вместо массива */
  const aiSummary = typeof ai?.summary === 'string' ? (ai.summary as string) : '';
  const aiStrengths = toStringArray(ai?.strengths);
  const aiProblems = toStringArray(ai?.problems);
  const aiForecast = typeof ai?.forecast === 'string' ? (ai.forecast as string) : '';
  const aiRecommendations = Array.isArray(ai?.recommendations)
    ? (ai.recommendations as string[]).filter((r) => typeof r === 'string')
    : [];

  /* Топ-3 поста */
  const bestPosts: PostMetrics[] = Array.isArray(engagement.best_posts) ? engagement.best_posts : [];
  const worstPosts: PostMetrics[] = Array.isArray(engagement.worst_posts) ? engagement.worst_posts : [];
  const topPosts = bestPosts.slice(0, 3);

  /* Данные для графика по часам */
  const hourData = posting_time.by_hour && typeof posting_time.by_hour === 'object'
    ? Object.entries(posting_time.by_hour).map(([hour, stats]) => ({
        hour,
        er: Number(stats?.avg_er) || 0,
        views: Number(stats?.avg_views) || 0,
      }))
    : [];

  const weeklyData = Array.isArray(trends.weekly) ? trends.weekly : [];

  const directionLabel: Record<string, string> = {
    growing: 'Растущий', declining: 'Снижающийся',
    stable: 'Стабильный', unknown: 'Недостаточно данных',
  };
  const directionColor: Record<string, string> = {
    growing: 'text-forest-300', declining: 'text-red-400',
    stable: 'text-gold-400', unknown: 'text-text-muted',
  };

  return (
    <div className="space-y-8 pb-8">
      {/* ── Заголовок ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">@{channelUsername}</h2>
          <p className="text-sm text-text-secondary mt-1">
            Тренд:{' '}
            <span className={directionColor[trends.direction] ?? 'text-text-muted'}>
              {directionLabel[trends.direction] ?? 'Неизвестно'}
            </span>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowRaw((v) => !v)}
            className="text-[10px] text-text-muted border border-border rounded-lg px-2 py-1 opacity-50 hover:opacity-100"
          >
            {showRaw ? 'UI' : 'JSON'}
          </button>
          <button
            onClick={onReset}
            className="text-xs text-text-muted hover:text-text-primary border border-border rounded-lg px-3 py-1.5 transition-colors"
          >
            Новый аудит
          </button>
        </div>
      </div>

      {/* ── Debug: Raw JSON toggle ── */}
      {showRaw && (
        <div className="bg-surface-card border border-border rounded-xl p-4">
          <pre className="text-xs text-text-secondary overflow-auto max-h-[70vh] whitespace-pre-wrap">
            {JSON.stringify(report, null, 2)}
          </pre>
        </div>
      )}

      {/* ── Structured UI (each section isolated) ── */}
      {!showRaw && (
        <>
          {/* AI Саммари */}
          <SafeSection name="ai-summary">{() =>
            aiSummary ? (
              <div className="bg-surface-card border border-gold-500/20 rounded-xl p-5">
                <span className="text-[10px] text-gold-400 uppercase tracking-widest">AI Оценка</span>
                <p className="text-sm text-text-secondary mt-2 leading-relaxed">{aiSummary}</p>
              </div>
            ) : null
          }</SafeSection>

          {/* Метрики */}
          <SafeSection name="metrics">{() => (
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Engagement Rate" value={`${summary.avg_er ?? 0}%`} subtitle="Средний ER" />
              <MetricCard label="Просмотры" value={Number(summary.avg_views ?? 0).toLocaleString('ru-RU')} subtitle="В среднем" />
              <MetricCard label="Публикации" value={summary.posts_count ?? 0} subtitle={`${summary.posts_per_day ?? 0} в день`} />
              <MetricCard label="Репосты" value={summary.avg_forwards ?? 0} subtitle="В среднем" />
            </div>
          )}</SafeSection>

          {/* AI Сильные стороны и проблемы */}
          <SafeSection name="strengths-problems">{() =>
            (aiStrengths.length > 0 || aiProblems.length > 0) ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {aiStrengths.length > 0 && (
                  <div className="bg-surface-card border border-forest-600/50 rounded-xl p-4">
                    <span className="text-[10px] text-forest-300 uppercase tracking-widest">Сильные стороны</span>
                    <ul className="mt-2 space-y-1.5">
                      {aiStrengths.map((s, i) => (
                        <li key={i} className="text-sm text-text-secondary leading-relaxed flex gap-2">
                          <span className="text-forest-400 shrink-0">+</span>{s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {aiProblems.length > 0 && (
                  <div className="bg-surface-card border border-red-500/20 rounded-xl p-4">
                    <span className="text-[10px] text-red-400 uppercase tracking-widest">Проблемы</span>
                    <ul className="mt-2 space-y-1.5">
                      {aiProblems.map((p, i) => (
                        <li key={i} className="text-sm text-text-secondary leading-relaxed flex gap-2">
                          <span className="text-red-400 shrink-0">-</span>{p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null
          }</SafeSection>

          {/* Топ-3 поста */}
          <SafeSection name="top-posts">{() =>
            topPosts.length > 0 ? (
              <section className="space-y-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wider">Топ-3 поста</h3>
                <div className="grid gap-3">
                  {topPosts.map((post, i) => (
                    <PostCard key={post?.id ?? i} post={post} variant="best" rank={i + 1} />
                  ))}
                </div>
              </section>
            ) : null
          }</SafeSection>

          {/* График трендов по неделям */}
          <SafeSection name="weekly-trends">{() =>
            weeklyData.length > 1 ? (
              <section className="space-y-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wider">Недельные тренды</h3>
                <div className="bg-surface-card border border-border rounded-xl p-4 h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={weeklyData}>
                      <defs>
                        <linearGradient id="erGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#c4aa4e" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#c4aa4e" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#234d28" />
                      <XAxis dataKey="week" tick={{ fontSize: 10, fill: '#5ab563' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: '#5ab563' }} axisLine={false} tickLine={false} width={35} />
                      <Tooltip
                        contentStyle={{ background: '#132b16', border: '1px solid #234d28', borderRadius: 8, fontSize: 12 }}
                        labelStyle={{ color: '#8fd496' }}
                      />
                      <Area type="monotone" dataKey="avg_er" name="Avg ER %" stroke="#c4aa4e" fill="url(#erGradient)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>
            ) : null
          }</SafeSection>

          {/* График по часам */}
          <SafeSection name="hourly-chart">{() =>
            hourData.length > 0 ? (
              <section className="space-y-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wider">
                  Время публикации
                  {posting_time.best_hour && (
                    <span className="ml-2 text-gold-400 normal-case tracking-normal">лучшее — {posting_time.best_hour}</span>
                  )}
                </h3>
                <div className="bg-surface-card border border-border rounded-xl p-4 h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hourData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#234d28" />
                      <XAxis dataKey="hour" tick={{ fontSize: 9, fill: '#5ab563' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: '#5ab563' }} axisLine={false} tickLine={false} width={30} />
                      <Tooltip
                        contentStyle={{ background: '#132b16', border: '1px solid #234d28', borderRadius: 8, fontSize: 12 }}
                        labelStyle={{ color: '#8fd496' }}
                      />
                      <Bar dataKey="er" name="Avg ER %" fill="#c4aa4e" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            ) : null
          }</SafeSection>

          {/* Худший пост */}
          <SafeSection name="worst-post">{() =>
            worstPosts.length > 0 && worstPosts[0] ? (
              <section className="space-y-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wider">Слабый пост</h3>
                <PostCard post={worstPosts[0]} variant="worst" />
              </section>
            ) : null
          }</SafeSection>

          {/* AI Прогноз */}
          <SafeSection name="forecast">{() =>
            aiForecast ? (
              <section className="space-y-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wider">Прогноз</h3>
                <div className="bg-surface-card border border-border rounded-xl p-4">
                  <p className="text-sm text-text-secondary leading-relaxed">{aiForecast}</p>
                </div>
              </section>
            ) : null
          }</SafeSection>

          {/* AI Рекомендации */}
          <SafeSection name="recommendations">{() =>
            aiRecommendations.length > 0 ? (
              <section className="space-y-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wider">Рекомендации</h3>
                <div className="bg-surface-card border border-border rounded-xl divide-y divide-border">
                  {aiRecommendations.map((rec, i) => (
                    <div key={i} className="px-4 py-3 flex gap-3">
                      <span className="text-gold-500 text-xs mt-0.5 shrink-0">{String(i + 1).padStart(2, '0')}</span>
                      <p className="text-sm text-text-secondary leading-relaxed">{rec}</p>
                    </div>
                  ))}
                </div>
              </section>
            ) : null
          }</SafeSection>
        </>
      )}
    </div>
  );
}
