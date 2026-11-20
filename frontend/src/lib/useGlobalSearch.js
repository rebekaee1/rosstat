import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from './api';
import { useLocale } from '../i18n';
import { searchTextFromLink } from './searchSynonyms';

// Раздел (правка 17) входит в ключ и запрос только когда он есть: без него ключ и адрес прежние.
const searchKey = (locale, q, limit, section) => (section
  ? ['catalog-search', 'v3', locale, q, limit, section]
  : ['catalog-search', 'v3', locale, q, limit]);
const fetchSearch = (q, limit, signal, section) => api
  .get('/search', { params: section ? { q, limit, section } : { q, limit }, signal }).then((r) => r.data);

/**
 * Недописанное последнее слово (18.11.2026). Пока второе слово набрано на 1–2 буквы, сервер честно отвечает
 * пустотой: короткое слово для него — целое слово, а не начало («коэффициент ро», «уровень бе», «цена бе»).
 * Человек видел «ничего не найдено» посреди набора и исправлял опечатку, которой не было (Пульс за 17.11.2026).
 * Возвращает дописанную часть и начало слова; null — если последнее слово нельзя считать недописанным.
 */
export function unfinishedTail(query) {
  const words = String(query || '').trim().split(/\s+/).filter(Boolean);
  if (words.length < 2) return null;
  const fragment = words[words.length - 1].toLowerCase().replace(/ё/g, 'е');
  if (!/^[a-zа-я]{1,2}$/.test(fragment)) return null;
  const stable = words.slice(0, -1).join(' ');
  if ([...stable].length < 3) return null;
  return { stable, fragment };
}

/**
 * Ряды, в названии, регионе или стране которых есть слово, начинающееся с набранных букв.
 * Сначала совпавшие по названию, затем только по месту («коэффициент ро»: рождаемость выше, чем любой ряд России).
 */
export function rowsStartingWith(results, fragment) {
  const start = new RegExp(`(^|[^a-zа-я0-9])${fragment}`);
  const has = (...parts) => start.test(parts.filter(Boolean).join(' ').toLowerCase().replace(/ё/g, 'е'));
  const byName = [];
  const byPlace = [];
  for (const item of results || []) {
    if (has(item?.name, item?.name_en)) byName.push(item);
    else if (has(item?.region_name, item?.country_name)) byPlace.push(item);
  }
  return [...byName, ...byPlace];
}

const isPlainEmpty = (data) => Boolean(data) && Array.isArray(data.results) && data.results.length === 0
  && data.reason === 'no_coverage' && !(data.nearest?.results?.length);

/**
 * One server search across public catalogues; never display another query's hits.
 * Единственное исключение — недописанное последнее слово: если на весь запрос сервер ответил пусто, показываются
 * ряды выдачи по дописанной части, в которых есть слово с таким началом. Все набранные слова остаются условием.
 */
export default function useGlobalSearch(query, { enabled = true, limit = 100, section = null } = {}) {
  const { locale } = useLocale();
  // Вставленная ссылка на поиск другого сайта (ЕМИСС, Росстат): ищем то, что искали там, и пишем «Показаны результаты для».
  const fromLink = searchTextFromLink(query);
  const needle = fromLink || String(query || '').trim();
  const [settled, setSettled] = useState(needle);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(needle), 300);
    return () => clearTimeout(timer);
  }, [needle]);
  const isDebouncing = needle !== settled;
  const queryClient = useQueryClient();
  const request = useQuery({
    queryKey: searchKey(locale, settled, limit, section),
    queryFn: ({ signal }) => fetchSearch(settled, limit, signal, section),
    enabled: enabled && Boolean(settled) && !isDebouncing,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
  });
  // Подгрузка заранее: подсказка уже «горячая», когда человек её нажимает (паузу набора обходим).
  const prefetch = (text) => {
    const q = String(text || '').trim();
    if (!q) return;
    queryClient.prefetchQuery({
      queryKey: searchKey(locale, q, limit, section),
      queryFn: ({ signal }) => fetchSearch(q, limit, signal, section),
      staleTime: 60_000,
    }).catch(() => {});
  };
  // Подсказка нажата: пауза набора не нужна, ищем сразу.
  const flush = (text) => setSettled(String(text || '').trim());

  // Запрос по дописанной части обычно уже в кэше: человек только что прошёл через него при наборе.
  const tail = !isDebouncing && isPlainEmpty(request.data) ? unfinishedTail(settled) : null;
  const stable = useQuery({
    queryKey: searchKey(locale, tail?.stable || '', limit, section),
    queryFn: ({ signal }) => fetchSearch(tail.stable, limit, signal, section),
    enabled: enabled && Boolean(tail),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
  });
  if (!tail) {
    if (fromLink && request.data && !request.data.corrected_query) {
      return { ...request, data: { ...request.data, corrected_query: fromLink }, isDebouncing, prefetch, flush };
    }
    return { ...request, isDebouncing, prefetch, flush };
  }
  if (!stable.data && !stable.isError) {
    // Ответ по дописанной части ещё идёт: не показываем «ничего не найдено» раньше времени.
    return { ...request, data: undefined, isPending: true, isLoading: true, isFetching: true, isSuccess: false, isDebouncing, prefetch, flush };
  }
  const rows = rowsStartingWith(stable.data?.results, tail.fragment);
  if (!rows.length) return { ...request, isDebouncing, prefetch, flush };
  const { nearest: _nearest, suggest: _suggest, reason: _reason, ...rest } = stable.data;
  const data = {
    ...rest, results: rows, total: rows.length, has_more: false, unfinished: tail,
    ...(rest.corrected_query ? { corrected_query: `${rest.corrected_query} ${tail.fragment}` } : {}),
  };
  return { ...request, data, isDebouncing, prefetch, flush };
}
