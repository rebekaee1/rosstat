/**
 * Группы взаимосвязанных индикаторов, между которыми пользователь может
 * переключаться pill-ссылками («Состав ИПЦ», «Режим ВВП», варианты ППИ,
 * первичное/вторичное жильё). Один индикатор принадлежит максимум одной
 * группе. Если код не входит ни в одну — pill-блок не показывается.
 *
 * Вторичные коды (YoY, QoQ, квартальные агрегаты) скрыты из листинга категории
 * через INDICATOR_HIDDEN_FROM_LISTING в backend/app/data/indicator_seo.py.
 *
 * label — RU fallback; labelKey — messages.ru/en (VariantGroupPicker / related cards).
 */
import { t } from '../i18n/messages';

export const VARIANT_GROUPS = [
  {
    label: 'Состав индекса потребительских цен',
    labelKey: 'variant.cpi.group',
    codes: [
      { code: 'cpi', label: 'Все товары и услуги', labelKey: 'variant.cpi.all' },
      { code: 'cpi-food', label: 'Продовольствие', labelKey: 'variant.cpi.food' },
      { code: 'cpi-nonfood', label: 'Непродовольственные', labelKey: 'variant.cpi.nonfood' },
      { code: 'cpi-services', label: 'Услуги', labelKey: 'variant.cpi.services' },
    ],
  },
  // gdp-nominal — режимы на /russia/indicator/gdp-nominal?mode=… (gdpNominalViewMode*).
  // gdp-real — режимы на /russia/indicator/gdp-real?mode=… (gdpRealViewMode*).
  {
    label: 'ВВП по использованию',
    labelKey: 'variant.gdpUse.group',
    codes: [
      { code: 'gdp-consumption', label: 'Домохозяйства', labelKey: 'variant.gdpUse.households' },
      { code: 'gdp-government', label: 'Государство', labelKey: 'variant.gdpUse.government' },
      { code: 'gdp-investment', label: 'Инвестиции', labelKey: 'variant.gdpUse.investment' },
    ],
  },
  // ИЦП: режимы на /russia/indicator/ppi?mode=… (ppiViewMode*), не variant-URL.
  // ИПП: общий индекс + четыре раздела ОКВЭД2 — РАЗНЫЕ ряды (variant).
  {
    label: 'Состав промышленного производства',
    labelKey: 'variant.ipi.group',
    codes: [
      { code: 'ipi', label: 'Все отрасли', labelKey: 'variant.ipi.all' },
      { code: 'ipi-mining', label: 'Добыча', labelKey: 'variant.ipi.mining' },
      { code: 'ipi-manufacturing', label: 'Обработка', labelKey: 'variant.ipi.manufacturing' },
      { code: 'ipi-energy', label: 'Энергетика', labelKey: 'variant.ipi.energy' },
      { code: 'ipi-water', label: 'Водоснабжение', labelKey: 'variant.ipi.water' },
    ],
  },
  {
    label: 'Цены на топливо',
    labelKey: 'variant.fuel.group',
    codes: [
      { code: 'fuel-ai92', label: 'Бензин АИ-92', labelKey: 'variant.fuel.ai92' },
      { code: 'fuel-ai95', label: 'Бензин АИ-95', labelKey: 'variant.fuel.ai95' },
      { code: 'fuel-diesel', label: 'Дизельное топливо', labelKey: 'variant.fuel.diesel' },
    ],
  },
  {
    label: 'Внешняя торговля товарами',
    labelKey: 'variant.tradeGoods.group',
    codes: [
      { code: 'exports', label: 'Экспорт товаров', labelKey: 'variant.tradeGoods.exports' },
      { code: 'imports', label: 'Импорт товаров', labelKey: 'variant.tradeGoods.imports' },
    ],
  },
  {
    label: 'Внешняя торговля услугами',
    labelKey: 'variant.tradeServices.group',
    codes: [
      { code: 'services-exports', label: 'Экспорт услуг', labelKey: 'variant.tradeServices.exports' },
      { code: 'services-imports', label: 'Импорт услуг', labelKey: 'variant.tradeServices.imports' },
    ],
  },
  {
    label: 'Внешний баланс',
    labelKey: 'variant.extBalance.group',
    codes: [
      { code: 'trade-balance', label: 'Торговый баланс', labelKey: 'variant.extBalance.trade' },
      { code: 'current-account', label: 'Сальдо текущего счёта', labelKey: 'variant.extBalance.current' },
    ],
  },
  {
    label: 'Рынок жилья',
    labelKey: 'variant.housing.group',
    codes: [
      { code: 'housing-price-primary', label: 'Первичное жильё', labelKey: 'variant.housing.primary' },
      { code: 'housing-price-secondary', label: 'Вторичное жильё', labelKey: 'variant.housing.secondary' },
    ],
  },
  {
    label: 'Доступность жилья',
    labelKey: 'variant.afford.group',
    codes: [
      { code: 'housing-affordability', label: 'Вторичное жильё', labelKey: 'variant.afford.secondary' },
      { code: 'housing-affordability-primary', label: 'Первичное жильё', labelKey: 'variant.afford.primary' },
    ],
  },
  {
    label: 'Ставки по кредитам юридическим лицам',
    labelKey: 'variant.creditCorp.group',
    codes: [
      { code: 'credit-rate-corp-short', label: 'До 1 года', labelKey: 'variant.term.short' },
      { code: 'credit-rate-corp-1to3y', label: 'От 1 до 3 лет', labelKey: 'variant.term.1to3' },
      { code: 'credit-rate-corp-over3y', label: 'Свыше 3 лет', labelKey: 'variant.term.over3' },
    ],
  },
  {
    label: 'Ставки по кредитам физическим лицам',
    labelKey: 'variant.creditInd.group',
    codes: [
      { code: 'credit-rate-ind-short', label: 'До 1 года', labelKey: 'variant.term.short' },
      { code: 'credit-rate-ind-1to3y', label: 'От 1 до 3 лет', labelKey: 'variant.term.1to3' },
      { code: 'credit-rate-ind-over3y', label: 'Свыше 3 лет', labelKey: 'variant.term.over3' },
    ],
  },
  {
    label: 'Ставки по вкладам физических лиц',
    labelKey: 'variant.deposit.group',
    codes: [
      { code: 'deposit-rate', label: 'До 1 года', labelKey: 'variant.term.short' },
      { code: 'deposit-rate-medium', label: 'От 1 до 3 лет', labelKey: 'variant.term.1to3' },
      { code: 'deposit-rate-long', label: 'Свыше 3 лет', labelKey: 'variant.term.over3' },
    ],
  },
  {
    label: 'Федеральный бюджет',
    labelKey: 'variant.budget.group',
    codes: [
      { code: 'budget-revenue', label: 'Доходы', labelKey: 'variant.budget.revenue' },
      { code: 'budget-expenditure', label: 'Расходы', labelKey: 'variant.budget.expenditure' },
      { code: 'budget-deficit', label: 'Дефицит/профицит', labelKey: 'variant.budget.deficit' },
    ],
  },
  {
    label: 'Кредиты и вклады населения',
    labelKey: 'variant.creditDeposit.group',
    codes: [
      { code: 'consumer-credit', label: 'Кредиты физлицам', labelKey: 'variant.creditDeposit.credit' },
      { code: 'deposits-individual', label: 'Вклады физлицам', labelKey: 'variant.creditDeposit.deposits' },
    ],
  },
  {
    label: 'Денежные агрегаты',
    labelKey: 'variant.money.group',
    codes: [
      { code: 'm0', label: 'М0', labelKey: 'variant.money.m0' },
      { code: 'm1', label: 'М1', labelKey: 'variant.money.m1' },
      { code: 'm2', label: 'М2', labelKey: 'variant.money.m2' },
    ],
  },
  {
    label: 'Рынок труда: занятость',
    labelKey: 'variant.labor.group',
    codes: [
      { code: 'labor-force', label: 'Рабочая сила', labelKey: 'variant.labor.force' },
      { code: 'employment', label: 'Занятое население', labelKey: 'variant.labor.employment' },
    ],
  },
  {
    label: 'Заработная плата',
    labelKey: 'variant.wages.group',
    codes: [
      { code: 'wages-nominal', label: 'Номинальная', labelKey: 'variant.wages.nominal' },
      { code: 'wages-real', label: 'Реальная', labelKey: 'variant.wages.real' },
    ],
  },
];

export function findVariantGroup(code) {
  return VARIANT_GROUPS.find((group) => group.codes.some((item) => item.code === code));
}

/** Подписи режима в variant-группе (не название среза) — для карточек «Похожие». */
const GENERIC_VARIANT_MEMBER_LABELS = new Set([
  'Индекс',
  'Год к году',
  'Кв/кв',
  'Г/г',
  'Помесячно',
  'Поквартально',
  'Годовой',
  'Годовая (декабрь к декабрю)',
  'Номинальная',
  'Недельная',
  'Среднее за квартал',
  'Скользящее 12 мес.',
  'Доходы',
  'Расходы',
  'Дефицит/профицит',
  'Кредиты физлицам',
  'Вклады физлицам',
]);

/**
 * Короткая подпись для карточек «Похожие индикаторы» — без обрезки длинного name из БД.
 * Для variant-групп: короткий label из pills + контекст группы.
 */
export function relatedIndicatorCardCopy(code, fallbackName, fallbackUnit) {
  const group = findVariantGroup(code);
  const member = group?.codes.find((item) => item.code === code);
  if (member && group) {
    const groupLabel = group.labelKey ? t(group.labelKey) : group.label;
    const memberLabel = member.labelKey ? t(member.labelKey) : member.label;
    const groupContext =
      group.labelKey === 'variant.cpi.group'
        ? t('variant.cpi.context')
        : groupLabel;
    if (GENERIC_VARIANT_MEMBER_LABELS.has(member.label)) {
      return {
        title: groupLabel,
        subtitle: memberLabel,
      };
    }
    return {
      title: memberLabel,
      subtitle: groupContext,
    };
  }
  return {
    title: fallbackName,
    subtitle: fallbackUnit || null,
  };
}

const INDICATOR_PATH_RE = /^\/(?:russia\/)?indicator\/([a-z0-9-]+)\/?$/;

/**
 * Переход между sibling-карточками одной variant-группы (cpi → cpi-food, gdp-nominal → gdp-yoy).
 * Для таких переходов не сбрасываем scroll и сохраняем ?mode= в URL.
 */
export function isVariantSiblingNavigation(fromPathname, toPathname) {
  const fromCode = fromPathname.match(INDICATOR_PATH_RE)?.[1];
  const toCode = toPathname.match(INDICATOR_PATH_RE)?.[1];
  if (!fromCode || !toCode || fromCode === toCode) return false;
  const group = findVariantGroup(fromCode);
  return Boolean(group?.codes.some((item) => item.code === toCode));
}

/** Все коды, входящие в variant-группы (для тестов и аудита). */
export function allVariantMemberCodes() {
  return VARIANT_GROUPS.flatMap((g) => g.codes.map((c) => c.code));
}

/**
 * Две осмысленные строки для мобильного H1 без сокращения текста.
 * Работает для названий вида «Индекс потребительских цен на …».
 * Если разбивка не подходит — null (рендерим одним блоком с text-pretty).
 */
export function indicatorDetailHeaderMobileLines(fullName) {
  if (!fullName) return null;
  const splitAt = fullName.indexOf(' на ');
  if (splitAt <= 0 || !fullName.startsWith('Индекс потребительских цен')) {
    return null;
  }
  const lines = [fullName.slice(0, splitAt), fullName.slice(splitAt + 1)];
  return lines.join(' ') === fullName ? lines : null;
}
