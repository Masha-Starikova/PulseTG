import type { PostMetrics } from '../types/audit';

interface PostCardProps {
  post: PostMetrics;
  variant: 'best' | 'worst';
  rank?: number;
}

/* Карточка поста (лучший / худший) */
export function PostCard({ post, variant, rank }: PostCardProps) {
  const accent = variant === 'best' ? 'text-forest-300' : 'text-red-400';
  const badge = rank ? `#${rank}` : variant === 'best' ? 'Лучший' : 'Худший';
  const badgeBg =
    variant === 'best'
      ? 'bg-forest-500/20 text-forest-300'
      : 'bg-red-500/20 text-red-400';

  return (
    <div className="bg-surface-card border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className={`text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full ${badgeBg}`}>
          {badge}
        </span>
        <span className={`text-sm font-medium ${accent}`}>
          ER {post.er ?? 0}%
        </span>
      </div>

      <p className="text-sm text-text-secondary leading-relaxed mb-3 line-clamp-3">
        {post.text_preview || '(без текста)'}
      </p>

      <div className="flex gap-4 text-xs text-text-muted">
        <span>{(post.views ?? 0).toLocaleString('ru-RU')} просм.</span>
        <span>{post.reactions ?? 0} реакц.</span>
        <span>{post.forwards ?? 0} реп.</span>
      </div>
    </div>
  );
}
