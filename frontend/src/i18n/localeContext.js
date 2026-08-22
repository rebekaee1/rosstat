/**
 * Контекст локали и хуки к нему. Живут отдельно от LocaleProvider:
 * файл с компонентом обязан экспортировать только компонент, иначе
 * hot-reload пересобирает всё дерево вместо одного провайдера.
 */
import { createContext, useContext } from 'react';

export const LocaleContext = createContext({
  locale: 'ru',
  t: (key) => key,
  isPreview: false,
  setPreviewLocale: () => {},
});

export function useLocale() {
  return useContext(LocaleContext);
}

export function useT() {
  return useLocale().t;
}
