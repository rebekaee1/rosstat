/**
 * Standalone-сборка поведенческого сбора для ЧИСТЫХ SSR-страниц
 * (/today*, /region-rating/*, /region-vs/*, /calendar/*, годовые landing'и) —
 * там React-бандл не грузится, и без этого файла ~43k URL SEO-программы были
 * слепой зоной собственного счётчика (их видела только Метрика).
 *
 * Один исходник — два бандла: SPA импортирует behavior.js как модуль, а этот
 * entry собирается отдельным чанком с фиксированным именем
 * /assets/behavior-standalone.js и подключается строкой в SSR-хроме
 * (seo_renderer.py). Полный паритет сбора: session_start с портретом,
 * pageview, клики, dwell, scroll, vitals, ошибки. Consent уважается так же.
 */
import { behaviorInit } from './lib/behavior';

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', behaviorInit, { once: true });
} else {
  behaviorInit();
}
