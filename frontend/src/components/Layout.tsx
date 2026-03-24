import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

/* Базовый лейаут приложения */
export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Шапка */}
      <header className="border-b border-border px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gold-500 flex items-center justify-center">
            <span className="text-forest-900 font-bold text-sm">P</span>
          </div>
          <h1 className="text-lg font-semibold tracking-tight text-text-primary">
            PulseTG
          </h1>
          <span className="text-xs text-text-muted ml-auto uppercase tracking-widest">
            Analytics
          </span>
        </div>
      </header>

      {/* Контент */}
      <main className="flex-1 px-4 py-6">
        <div className="max-w-2xl mx-auto">{children}</div>
      </main>

      {/* Футер */}
      <footer className="border-t border-border px-6 py-3">
        <p className="text-center text-xs text-text-muted">
          PulseTG &middot; Telegram Channel Analytics
        </p>
      </footer>
    </div>
  );
}
