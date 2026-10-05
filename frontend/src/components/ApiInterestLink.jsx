// Точка входа «фальшивой двери» платного API: «API и выгрузка с прогнозом».
// Ничего не рендерит, пока бэкенд не включил api_interest_enabled.
//   variant="toolbar" — рядом со «Скачать»/«Встроить» над графиком показателя;
//   variant="inline"  — вторичная текстовая ссылка в окне лимита скачиваний.
import { useEffect } from 'react';
import { Braces } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';
import { openApiInterest, trackApiInterestView, useApiInterestEnabled } from '../lib/apiInterest';

export default function ApiInterestLink({
  source = 'indicator', code = null, variant = 'toolbar', onActivate, className,
}) {
  const t = useT();
  const enabled = useApiInterestEnabled();
  useEffect(() => {
    if (enabled) trackApiInterestView(source);
  }, [enabled, source]);
  if (!enabled) return null;

  const activate = () => {
    onActivate?.();
    openApiInterest({ source, indicatorCode: code });
  };

  if (variant === 'inline') {
    return (
      <button
        type="button"
        onClick={activate}
        data-no-export="true"
        className={cn(
          FOCUS_RING,
          'fe-press mt-3 w-full rounded-md py-2 text-center text-sm text-text-secondary underline decoration-border-subtle underline-offset-4 hover:text-text-primary pointer-coarse:min-h-11',
          className,
        )}
      >
        {t('apiInterest.limitLink')}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={activate}
      title={t('apiInterest.linkHint')}
      className={cn('fe-help-link fe-press', className)}
      data-no-export="true"
    >
      <Braces className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{t('apiInterest.link')}</span>
    </button>
  );
}
