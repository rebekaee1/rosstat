import { Component } from 'react';
import { track, events } from '../lib/track';
import { resolveBrowserLocale } from '../i18n/locale';
import { translate } from '../i18n/messages';
import { isChunkLoadError, recoverFromStaleChunk } from '../lib/chunkRecovery';
import Button from './Button';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, reloading: false, busy: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('React ErrorBoundary caught:', error, info);
    // Устаревший чанк после релиза: одна перезагрузка вместо экрана ошибки.
    // false (идёт ввод/загрузка файла, или уже перезагружались) — обычный экран.
    if (isChunkLoadError(error) && recoverFromStaleChunk()) this.setState({ reloading: true });
    import('@sentry/react').then(Sentry => {
      Sentry.captureException(error, { extra: { componentStack: info?.componentStack } });
    }).catch(() => {});
  }

  render() {
    if (this.state.hasError) {
      if (this.state.reloading) return null;
      // fallback задан (в т.ч. null) — крошечный виджет не роняет страницу.
      if (this.props.fallback !== undefined) return this.props.fallback;
      const locale = resolveBrowserLocale();
      const t = (key) => translate(key, undefined, locale);
      return (
        <div className="min-h-screen flex items-center justify-center bg-surface p-8">
          <div className="text-center max-w-md">
            <h1 className="text-2xl font-display text-text-primary mb-4">
              {t('error.boundary.title')}
            </h1>
            <p className="text-text-secondary mb-6">
              {t('error.boundary.body')}
            </p>
            <Button
              loading={this.state.busy}
              onClick={() => { this.setState({ busy: true }); track(events.ERROR_RELOAD); window.location.reload(); }}
              className="px-6"
            >
              {t('error.boundary.reload')}
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
