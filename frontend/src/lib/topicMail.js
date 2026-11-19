import { useEffect, useState } from 'react';
import { fetchTopicMailConfig } from './api';

/**
 * Подписка на показатель по почте (совет 19.11.2026): включена ли на сервере (`RUSTATS_TOPIC_MAIL_ENABLED`).
 * Ответ запоминается на вкладку; ошибка сети = выключено (форма не рисуется).
 */
let configPromise = null;
function loadConfig() {
  if (!configPromise) {
    configPromise = fetchTopicMailConfig().catch(() => ({ enabled: false }));
  }
  return configPromise;
}

/** Для тестов: сбросить запомненный ответ конфигурации. */
export function resetTopicMailConfig() { configPromise = null; }

export function useTopicMailEnabled() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let alive = true;
    loadConfig().then((c) => { if (alive) setEnabled(Boolean(c?.enabled)); });
    return () => { alive = false; };
  }, []);
  return enabled;
}
