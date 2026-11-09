// Круг 10 (R10-A): английские подписи цен на главной. API отдаёт short_name уже с единицей («Potatoes, kg»), а unit как
// «roubles per kg»: в плитке это давало повтор и сырой оборот. Здесь имя без хвоста-единицы и единица в виде «per kg».

/** Короткие имена ходовых позиций для плиток (длинные ведомственные названия в плитку не влезают). */
const TILE_NAMES_EN = {
  'ceni-hleb-pshenichnyy': 'Wheat bread',
  'ceni-moloko': 'Milk, 2.5–3.2% fat',
  'ceni-yaytsa': 'Eggs',
  'ceni-kury': 'Chicken',
  'ceni-kartofel': 'Potatoes',
  'ceni-ai95': 'Petrol AI-95',
  'ceni-proezd-avtobus': 'City bus fare',
  'ceni-arenda-1k': 'One-room flat rent',
  'ceni-elektroenergiya': 'Electricity',
  'ceni-sahar': 'Sugar',
  'ceni-govyadina-beskostnaya': 'Boneless beef',
  'ceni-internet': 'Home internet',
};

/** «roubles per 10 eggs» -> «10 eggs»; «roubles» без единицы -> ''. */
export function enPer(unit) {
  const m = String(unit || '').match(/^(?:roubles|rubles)(?:\s+per\s+(.*))?$/i);
  return m ? (m[1] || '').trim() : '';
}

/** Единица для плитки: «per kg», «per 10 eggs», «per month»; для безликих «item/service» ничего не пишем. */
export function enPerLabel(unit) {
  const per = enPer(unit);
  if (!per || /^(item|service|operation|type of work|procedure|visit)$/i.test(per)) return '';
  return `per ${per}`;
}

/** Имя без хвоста «, kg» (единица стоит отдельной строкой). */
export function enTileName(it) {
  if (TILE_NAMES_EN[it?.code]) return TILE_NAMES_EN[it.code];
  const name = String(it?.short_name || it?.name || '');
  const per = enPer(it?.unit);
  if (per && name.toLowerCase().endsWith(`, ${per.toLowerCase()}`)) return name.slice(0, -(per.length + 2));
  return name;
}

/** Рубль в английской записи ставится перед числом: «₽125.86». */
export function enMoney(valueText) {
  return `₽${valueText}`;
}
