import { Fragment, useEffect, useState } from 'react';
import { fetchPrefs } from '../../lib/cabinetApi';
import { NUMBER_FORMAT_EVENT, applyPrefs } from '../../lib/cabinetPrefs';
import { useCabinetBoot, useCabinetConfig } from '../../lib/useCabinet';

/**
 * Читает настройки кабинета один раз на вход и отдаёт их сайту (`lib/cabinetPrefs.js`): формат чисел, валюта конвертера, главная страна.
 * Ничего не рисует. Гость и выключенный кабинет: настроек нет, прежние значения сброшены.
 */
export default function CabinetPrefsApplier() {
  const { authed } = useCabinetBoot();
  const { enabled } = useCabinetConfig();
  useEffect(() => {
    if (!enabled || !authed) {
      applyPrefs(null);
      return undefined;
    }
    let alive = true;
    Promise.resolve()
      .then(() => fetchPrefs())
      .then((res) => { if (alive) applyPrefs(res?.data || null); })
      .catch(() => { /* настройки не пришли: сайт остаётся с обычными значениями */ });
    return () => { alive = false; };
  }, [enabled, authed]);
  return null;
}

/**
 * Числа рисуются прямо в разметке, поэтому при смене формата чисел содержимое страницы пересобирается один раз (ключ меняется).
 * Без настройки формата события не бывает, и содержимое не пересоздаётся.
 */
export function NumberFormatBoundary({ children }) {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener(NUMBER_FORMAT_EVENT, bump);
    return () => window.removeEventListener(NUMBER_FORMAT_EVENT, bump);
  }, []);
  return <Fragment key={version}>{children}</Fragment>;
}
