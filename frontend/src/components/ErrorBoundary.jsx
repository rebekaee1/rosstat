import { Component } from 'react';
import { track, events } from '../lib/track';
import { resolveBrowserLocale } from '../i18n/locale';
import { translate } from '../i18n/messages';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('React ErrorBoundary caught:', error, info);
    import('@sentry/react').then(Sentry => {
      Sentry.captureException(error, { extra: { componentStack: info?.componentStack } });
    }).catch(() => {});
  }

  render() {
    if (this.state.hasError) {
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
            <button
              onClick={() => { track(events.ERROR_RELOAD); window.location.reload(); }}
              className="px-6 py-2 bg-champagne text-white rounded-lg hover:bg-champagne/90 transition-colors"
            >
              {t('error.boundary.reload')}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
