/**
 * Страница «Не найдено» на экране (круг 11, G, U35)? Признак: разметка самой страницы (`.z2-nf`; её рисует и серверная 404, и маршрут `*`).
 * Нужна переключателю языка: на 404 смена языка ведёт на главную, а не на несуществующий адрес другого хоста.
 */
export function isNotFoundScreen() {
  if (typeof document === 'undefined') return false;
  return document.querySelector('.z2-nf') !== null;
}
