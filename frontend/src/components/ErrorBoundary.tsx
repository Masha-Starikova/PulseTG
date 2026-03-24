import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/* Ловит ошибки рендера и показывает fallback вместо пустого экрана */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center gap-4 py-16 px-4 text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
            <span className="text-red-400 text-xl">!</span>
          </div>
          <h2 className="text-lg font-medium text-text-primary">
            Что-то пошло не так
          </h2>
          <p className="text-sm text-text-muted max-w-sm">
            Произошла ошибка при отображении результатов. Попробуйте снова.
          </p>
          {this.state.error && (
            <pre className="text-xs text-red-400/70 bg-red-500/5 rounded-lg p-3 max-w-full overflow-auto">
              {this.state.error.message}
            </pre>
          )}
          <button
            onClick={this.handleReset}
            className="text-sm text-gold-400 border border-gold-500/30 rounded-lg px-4 py-2 hover:bg-gold-500/10 transition-colors"
          >
            Попробовать снова
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
