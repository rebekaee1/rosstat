/** Первая буква имени (или почты) для кружка в кнопке кабинета; пусто, если назвать нечем (круг 11, G, U2). */
export function accountInitial(user) {
  const text = String(user?.display_name || user?.email || '').trim();
  return text ? Array.from(text)[0].toUpperCase() : '';
}
