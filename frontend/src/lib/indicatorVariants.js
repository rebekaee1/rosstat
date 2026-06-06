/**
 * Группы взаимосвязанных индикаторов, между которыми пользователь может
 * переключаться pill-ссылками («Состав ИПЦ», «Режим ВВП», варианты ППИ,
 * первичное/вторичное жильё). Один индикатор принадлежит максимум одной
 * группе. Если код не входит ни в одну — pill-блок не показывается.
 *
 * Вторичные коды (YoY, QoQ, квартальные агрегаты) скрыты из листинга категории
 * через INDICATOR_HIDDEN_FROM_LISTING в backend/app/data/indicator_seo.py.
 */
export const VARIANT_GROUPS = [
  {
    label: 'Состав индекса потребительских цен',
    codes: [
      { code: 'cpi', label: 'Все товары и услуги' },
      { code: 'cpi-food', label: 'Продовольствие' },
      { code: 'cpi-nonfood', label: 'Непродовольственные' },
      { code: 'cpi-services', label: 'Услуги' },
    ],
  },
  // gdp-nominal — режимы на /indicator/gdp-nominal?mode=… (gdpNominalViewMode*).
  // gdp-real — режимы на /indicator/gdp-real?mode=… (gdpRealViewMode*).
  {
    label: 'ВВП по использованию',
    codes: [
      { code: 'gdp-consumption', label: 'Домохозяйства' },
      { code: 'gdp-government', label: 'Государство' },
      { code: 'gdp-investment', label: 'Инвестиции' },
    ],
  },
  // ИЦП: режимы на /indicator/ppi?mode=… (ppiViewMode*), не variant-URL.
  {
    label: 'Индекс промышленного производства',
    codes: [
      { code: 'ipi-yoy', label: 'Год к году' },
      { code: 'ipi', label: 'Помесячно' },
    ],
  },
  // unemployment — режимы на /indicator/unemployment?mode=… (unemploymentViewMode*).
  // wages-nominal — режимы на /indicator/wages-nominal?mode=… (wagesNominalViewMode*).
  // Phase 1 (звонок 2026-05-22): trade-семьи (exports / imports / current-account)
  // переехали с VariantGroupPicker (отдельные URL'ы для каждого режима) на
  // ViewModePicker (in-page ?mode=yoy|qoq). См. `lib/viewModeFamilies.js` и
  // `pages/IndicatorDetail.jsx::isTrade`. Эти записи удалены сознательно —
  // дублирующие pills'ы над FrequencySwitcher.
  // Phase 3 (ADR-0006): первичное/вторичное — разные ряды (variant).
  // Режимы «Индекс / г/г» — ViewModePicker на карточке parent (?mode=yoy),
  // не отдельные URL (housing-yoy-* скрыты из листинга).
  {
    label: 'Рынок жилья',
    codes: [
      { code: 'housing-price-primary', label: 'Первичное' },
      { code: 'housing-price-secondary', label: 'Вторичное' },
    ],
  },
  {
    label: 'Ставки по кредитам юридическим лицам',
    codes: [
      { code: 'credit-rate-corp-short', label: 'До 1 года' },
      { code: 'credit-rate-corp-1to3y', label: 'От 1 до 3 лет' },
      { code: 'credit-rate-corp-over3y', label: 'Свыше 3 лет' },
    ],
  },
  {
    label: 'Ставки по кредитам физическим лицам',
    codes: [
      { code: 'credit-rate-ind-short', label: 'До 1 года' },
      { code: 'credit-rate-ind-1to3y', label: 'От 1 до 3 лет' },
      { code: 'credit-rate-ind-over3y', label: 'Свыше 3 лет' },
    ],
  },
  {
    label: 'Ставки по вкладам физических лиц',
    codes: [
      { code: 'deposit-rate', label: 'До 1 года' },
      { code: 'deposit-rate-medium', label: 'От 1 до 3 лет' },
      { code: 'deposit-rate-long', label: 'Свыше 3 лет' },
    ],
  },
  {
    label: 'Федеральный бюджет',
    codes: [
      { code: 'budget-revenue', label: 'Доходы' },
      { code: 'budget-expenditure', label: 'Расходы' },
      { code: 'budget-deficit', label: 'Дефицит/профицит' },
    ],
  },
  {
    label: 'Кредиты и вклады населения',
    codes: [
      { code: 'consumer-credit', label: 'Кредиты физлицам' },
      { code: 'deposits-individual', label: 'Вклады физлицам' },
    ],
  },
  {
    label: 'Денежные агрегаты',
    codes: [
      { code: 'm0', label: 'М0' },
      { code: 'm1', label: 'М1' },
      { code: 'm2', label: 'М2' },
    ],
  },
  {
    label: 'Рынок труда: занятость',
    codes: [
      { code: 'labor-force', label: 'Рабочая сила' },
      { code: 'employment', label: 'Занятое население' },
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
    const groupContext =
      group.label === 'Состав индекса потребительских цен'
        ? 'Индекс потребительских цен'
        : group.label;
    if (GENERIC_VARIANT_MEMBER_LABELS.has(member.label)) {
      return {
        title: group.label,
        subtitle: member.label,
      };
    }
    return {
      title: member.label,
      subtitle: groupContext,
    };
  }
  return {
    title: fallbackName,
    subtitle: fallbackUnit || null,
  };
}

const INDICATOR_PATH_RE = /^\/indicator\/([a-z0-9-]+)\/?$/;

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
