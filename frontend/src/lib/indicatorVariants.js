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
  // Туризм по России (20.11.2026): срезы повторяют backend/app/data/tourism_russia.py::VARIANT_GROUPS (тест сверяет).
  {
    label: 'Траты иностранцев в России',
    labelKey: 'variant.tourTravelExports.group',
    codes: [
      { code: 'tour-travel-exports', label: 'Все поездки', labelKey: 'variant.tourTravelExports.travel-exports' },
      { code: 'tour-travel-business-exports', label: 'Деловые', labelKey: 'variant.tourTravelExports.travel-business-exports' },
      { code: 'tour-travel-personal-exports', label: 'Личные', labelKey: 'variant.tourTravelExports.travel-personal-exports' },
    ],
  },
  {
    label: 'Траты россиян за границей',
    labelKey: 'variant.tourTravelImports.group',
    codes: [
      { code: 'tour-travel-imports', label: 'Все поездки', labelKey: 'variant.tourTravelImports.travel-imports' },
      { code: 'tour-travel-business-imports', label: 'Деловые', labelKey: 'variant.tourTravelImports.travel-business-imports' },
      { code: 'tour-travel-personal-imports', label: 'Личные', labelKey: 'variant.tourTravelImports.travel-personal-imports' },
    ],
  },
  {
    label: 'Въезд иностранцев по странам',
    labelKey: 'variant.tourInbound.group',
    codes: [
      { code: 'tour-inbound-trips', label: 'Все страны', labelKey: 'variant.tourInbound.inbound-trips' },
      { code: 'tour-inbound-kazakhstan', label: 'Казахстан', labelKey: 'variant.tourInbound.inbound-kazakhstan' },
      { code: 'tour-inbound-china', label: 'Китай', labelKey: 'variant.tourInbound.inbound-china' },
      { code: 'tour-inbound-uzbekistan', label: 'Узбекистан', labelKey: 'variant.tourInbound.inbound-uzbekistan' },
      { code: 'tour-inbound-abkhazia', label: 'Абхазия', labelKey: 'variant.tourInbound.inbound-abkhazia' },
      { code: 'tour-inbound-tajikistan', label: 'Таджикистан', labelKey: 'variant.tourInbound.inbound-tajikistan' },
      { code: 'tour-inbound-belarus', label: 'Беларусь', labelKey: 'variant.tourInbound.inbound-belarus' },
      { code: 'tour-inbound-armenia', label: 'Армения', labelKey: 'variant.tourInbound.inbound-armenia' },
      { code: 'tour-inbound-mongolia', label: 'Монголия', labelKey: 'variant.tourInbound.inbound-mongolia' },
      { code: 'tour-inbound-kyrgyzstan', label: 'Киргизия', labelKey: 'variant.tourInbound.inbound-kyrgyzstan' },
      { code: 'tour-inbound-azerbaijan', label: 'Азербайджан', labelKey: 'variant.tourInbound.inbound-azerbaijan' },
      { code: 'tour-inbound-georgia', label: 'Грузия', labelKey: 'variant.tourInbound.inbound-georgia' },
      { code: 'tour-inbound-germany', label: 'Германия', labelKey: 'variant.tourInbound.inbound-germany' },
    ],
  },
  {
    label: 'Выезд россиян по странам',
    labelKey: 'variant.tourOutbound.group',
    codes: [
      { code: 'tour-outbound-trips', label: 'Все страны', labelKey: 'variant.tourOutbound.outbound-trips' },
      { code: 'tour-outbound-turkey', label: 'Турция', labelKey: 'variant.tourOutbound.outbound-turkey' },
      { code: 'tour-outbound-abkhazia', label: 'Абхазия', labelKey: 'variant.tourOutbound.outbound-abkhazia' },
      { code: 'tour-outbound-kazakhstan', label: 'Казахстан', labelKey: 'variant.tourOutbound.outbound-kazakhstan' },
      { code: 'tour-outbound-uae', label: 'ОАЭ', labelKey: 'variant.tourOutbound.outbound-uae' },
      { code: 'tour-outbound-china', label: 'Китай', labelKey: 'variant.tourOutbound.outbound-china' },
      { code: 'tour-outbound-egypt', label: 'Египет', labelKey: 'variant.tourOutbound.outbound-egypt' },
      { code: 'tour-outbound-georgia', label: 'Грузия', labelKey: 'variant.tourOutbound.outbound-georgia' },
      { code: 'tour-outbound-thailand', label: 'Таиланд', labelKey: 'variant.tourOutbound.outbound-thailand' },
      { code: 'tour-outbound-armenia', label: 'Армения', labelKey: 'variant.tourOutbound.outbound-armenia' },
      { code: 'tour-outbound-uzbekistan', label: 'Узбекистан', labelKey: 'variant.tourOutbound.outbound-uzbekistan' },
      { code: 'tour-outbound-azerbaijan', label: 'Азербайджан', labelKey: 'variant.tourOutbound.outbound-azerbaijan' },
      { code: 'tour-outbound-vietnam', label: 'Вьетнам', labelKey: 'variant.tourOutbound.outbound-vietnam' },
    ],
  },
  {
    label: 'Россияне по данным стран назначения',
    labelKey: 'variant.tourDestinations.group',
    codes: [
      { code: 'tour-dest-egypt', label: 'Египет', labelKey: 'variant.tourDestinations.dest-egypt' },
      { code: 'tour-dest-thailand', label: 'Таиланд', labelKey: 'variant.tourDestinations.dest-thailand' },
      { code: 'tour-dest-uzbekistan', label: 'Узбекистан', labelKey: 'variant.tourDestinations.dest-uzbekistan' },
      { code: 'tour-dest-kazakhstan', label: 'Казахстан', labelKey: 'variant.tourDestinations.dest-kazakhstan' },
      { code: 'tour-dest-vietnam', label: 'Вьетнам', labelKey: 'variant.tourDestinations.dest-vietnam' },
      { code: 'tour-dest-maldives', label: 'Мальдивы', labelKey: 'variant.tourDestinations.dest-maldives' },
      { code: 'tour-dest-maldives-monthly', label: 'Мальдивы по месяцам', labelKey: 'variant.tourDestinations.dest-maldives-monthly' },
      { code: 'tour-dest-indonesia', label: 'Индонезия', labelKey: 'variant.tourDestinations.dest-indonesia' },
      { code: 'tour-dest-sri-lanka', label: 'Шри-Ланка', labelKey: 'variant.tourDestinations.dest-sri-lanka' },
      { code: 'tour-dest-belarus', label: 'Беларусь', labelKey: 'variant.tourDestinations.dest-belarus' },
      { code: 'tour-dest-seychelles', label: 'Сейшелы', labelKey: 'variant.tourDestinations.dest-seychelles' },
      { code: 'tour-dest-dominican-republic', label: 'Доминикана', labelKey: 'variant.tourDestinations.dest-dominican-republic' },
      { code: 'tour-dest-mongolia', label: 'Монголия', labelKey: 'variant.tourDestinations.dest-mongolia' },
      { code: 'tour-dest-mongolia-monthly', label: 'Монголия по месяцам', labelKey: 'variant.tourDestinations.dest-mongolia-monthly' },
      { code: 'tour-dest-mauritius', label: 'Маврикий', labelKey: 'variant.tourDestinations.dest-mauritius' },
      { code: 'tour-dest-mauritius-monthly', label: 'Маврикий по месяцам', labelKey: 'variant.tourDestinations.dest-mauritius-monthly' },
      { code: 'tour-dest-zanzibar', label: 'Занзибар', labelKey: 'variant.tourDestinations.dest-zanzibar' },
      { code: 'tour-dest-cuba', label: 'Куба', labelKey: 'variant.tourDestinations.dest-cuba' },
      { code: 'tour-dest-tajikistan', label: 'Таджикистан', labelKey: 'variant.tourDestinations.dest-tajikistan' },
      { code: 'tour-dest-dubai', label: 'Дубай: СНГ и Восточная Европа', labelKey: 'variant.tourDestinations.dest-dubai' },
    ],
  },
  {
    label: 'Туризм в экономике',
    labelKey: 'variant.tourEconomy.group',
    codes: [
      { code: 'tour-gva', label: 'Добавленная стоимость', labelKey: 'variant.tourEconomy.gva' },
      { code: 'tour-gva-share', label: 'Доля в ВВП', labelKey: 'variant.tourEconomy.gva-share' },
      { code: 'tour-gva-volume', label: 'Реальный рост', labelKey: 'variant.tourEconomy.gva-volume' },
    ],
  },
  {
    label: 'Авиаперевозки пассажиров',
    labelKey: 'variant.tourAir.group',
    codes: [
      { code: 'tour-air-passengers', label: 'Все рейсы', labelKey: 'variant.tourAir.air-passengers' },
      { code: 'tour-air-passengers-domestic', label: 'Внутренние', labelKey: 'variant.tourAir.air-passengers-domestic' },
      { code: 'tour-air-passengers-international', label: 'Международные', labelKey: 'variant.tourAir.air-passengers-international' },
      { code: 'tour-air-passengers-charter', label: 'Чартеры', labelKey: 'variant.tourAir.air-passengers-charter' },
    ],
  },
  {
    label: 'Пассажиропоток аэропортов',
    labelKey: 'variant.tourAirports.group',
    codes: [
      { code: 'tour-airport-sheremetyevo', label: 'Шереметьево', labelKey: 'variant.tourAirports.airport-sheremetyevo' },
      { code: 'tour-airport-vnukovo', label: 'Внуково', labelKey: 'variant.tourAirports.airport-vnukovo' },
      { code: 'tour-airport-domodedovo', label: 'Домодедово', labelKey: 'variant.tourAirports.airport-domodedovo' },
      { code: 'tour-airport-pulkovo', label: 'Пулково', labelKey: 'variant.tourAirports.airport-pulkovo' },
      { code: 'tour-airport-koltsovo', label: 'Кольцово', labelKey: 'variant.tourAirports.airport-koltsovo' },
      { code: 'tour-airport-tolmachevo', label: 'Толмачёво', labelKey: 'variant.tourAirports.airport-tolmachevo' },
    ],
  },
  {
    label: 'Железная дорога',
    labelKey: 'variant.tourRail.group',
    codes: [
      { code: 'tour-rail-passengers', label: 'Пассажиры', labelKey: 'variant.tourRail.rail-passengers' },
      { code: 'tour-rail-passenger-km', label: 'Пассажирооборот', labelKey: 'variant.tourRail.rail-passenger-km' },
    ],
  },
  {
    label: 'Гостиницы и средства размещения',
    labelKey: 'variant.tourHotels.group',
    codes: [
      { code: 'tour-hotel-guests', label: 'Размещённые', labelKey: 'variant.tourHotels.hotel-guests' },
      { code: 'tour-hotel-nights', label: 'Ночёвки', labelKey: 'variant.tourHotels.hotel-nights' },
      { code: 'tour-hotel-count', label: 'Число объектов', labelKey: 'variant.tourHotels.hotel-count' },
      { code: 'tour-hotel-rooms', label: 'Номера', labelKey: 'variant.tourHotels.hotel-rooms' },
      { code: 'tour-hotel-beds', label: 'Места', labelKey: 'variant.tourHotels.hotel-beds' },
      { code: 'tour-hotel-revenue', label: 'Доходы', labelKey: 'variant.tourHotels.hotel-revenue' },
      { code: 'tour-hotel-workers', label: 'Работники', labelKey: 'variant.tourHotels.hotel-workers' },
      { code: 'tour-new-hotel-beds', label: 'Новые места', labelKey: 'variant.tourHotels.new-hotel-beds' },
    ],
  },
  {
    label: 'Цены на поездки и экскурсии',
    labelKey: 'variant.tourCpiTrips.group',
    codes: [
      { code: 'tour-cpi-tourism', label: 'Все услуги туризма', labelKey: 'variant.tourCpiTrips.cpi-tourism' },
      { code: 'tour-cpi-domestic', label: 'Внутренний туризм', labelKey: 'variant.tourCpiTrips.cpi-domestic' },
      { code: 'tour-cpi-abroad', label: 'Зарубежный туризм', labelKey: 'variant.tourCpiTrips.cpi-abroad' },
      { code: 'tour-cpi-turkey', label: 'Турция', labelKey: 'variant.tourCpiTrips.cpi-turkey' },
      { code: 'tour-cpi-egypt', label: 'Египет', labelKey: 'variant.tourCpiTrips.cpi-egypt' },
      { code: 'tour-cpi-belarus', label: 'Беларусь', labelKey: 'variant.tourCpiTrips.cpi-belarus' },
      { code: 'tour-cpi-caucasus', label: 'Закавказье', labelKey: 'variant.tourCpiTrips.cpi-caucasus' },
      { code: 'tour-cpi-central-asia', label: 'Средняя Азия', labelKey: 'variant.tourCpiTrips.cpi-central-asia' },
      { code: 'tour-cpi-se-asia', label: 'Юго-Восточная Азия', labelKey: 'variant.tourCpiTrips.cpi-se-asia' },
      { code: 'tour-cpi-black-sea', label: 'Черноморское побережье', labelKey: 'variant.tourCpiTrips.cpi-black-sea' },
      { code: 'tour-cpi-russia-tours', label: 'Туры по России', labelKey: 'variant.tourCpiTrips.cpi-russia-tours' },
      { code: 'tour-cpi-river-cruise', label: 'Речной круиз', labelKey: 'variant.tourCpiTrips.cpi-river-cruise' },
      { code: 'tour-cpi-excursions', label: 'Экскурсии', labelKey: 'variant.tourCpiTrips.cpi-excursions' },
      { code: 'tour-cpi-bus-excursion', label: 'Автобусная экскурсия', labelKey: 'variant.tourCpiTrips.cpi-bus-excursion' },
    ],
  },
  {
    label: 'Цены на гостиницы и санатории',
    labelKey: 'variant.tourCpiStay.group',
    codes: [
      { code: 'tour-cpi-hotels', label: 'Все средства размещения', labelKey: 'variant.tourCpiStay.cpi-hotels' },
      { code: 'tour-cpi-hotel-1', label: 'Гостиница 1*', labelKey: 'variant.tourCpiStay.cpi-hotel-1' },
      { code: 'tour-cpi-hotel-2', label: 'Гостиница 2*', labelKey: 'variant.tourCpiStay.cpi-hotel-2' },
      { code: 'tour-cpi-hotel-3', label: 'Гостиница 3*', labelKey: 'variant.tourCpiStay.cpi-hotel-3' },
      { code: 'tour-cpi-hotel-4-5', label: 'Гостиница 4*–5*', labelKey: 'variant.tourCpiStay.cpi-hotel-4-5' },
      { code: 'tour-cpi-hostel', label: 'Хостел', labelKey: 'variant.tourCpiStay.cpi-hostel' },
      { code: 'tour-cpi-sanatoria', label: 'Санаторно-оздоровительные', labelKey: 'variant.tourCpiStay.cpi-sanatoria' },
      { code: 'tour-cpi-sanatorium-day', label: 'Санаторий', labelKey: 'variant.tourCpiStay.cpi-sanatorium-day' },
      { code: 'tour-cpi-rest-house-day', label: 'Дом отдыха', labelKey: 'variant.tourCpiStay.cpi-rest-house-day' },
    ],
  },
  {
    label: 'Цена дня отдыха',
    labelKey: 'variant.tourStayPrice.group',
    codes: [
      { code: 'tour-price-sanatorium', label: 'Санаторий', labelKey: 'variant.tourStayPrice.price-sanatorium' },
      { code: 'tour-price-rest-house', label: 'Дом отдыха', labelKey: 'variant.tourStayPrice.price-rest-house' },
    ],
  },
  {
    label: 'Налоги с туристов',
    labelKey: 'variant.tourTaxes.group',
    codes: [
      { code: 'tour-tax', label: 'Туристический налог', labelKey: 'variant.tourTaxes.tax' },
      { code: 'tour-resort-fee', label: 'Курортный сбор', labelKey: 'variant.tourTaxes.resort-fee' },
    ],
  },
  {
    label: 'Турфирмы и турпакеты',
    labelKey: 'variant.tourFirms.group',
    codes: [
      { code: 'tour-packages', label: 'Турпакеты', labelKey: 'variant.tourFirms.packages' },
      { code: 'tour-packages-domestic', label: 'Туры по России', labelKey: 'variant.tourFirms.packages-domestic' },
      { code: 'tour-packages-outbound', label: 'Туры за рубеж', labelKey: 'variant.tourFirms.packages-outbound' },
      { code: 'tour-packages-value', label: 'Стоимость турпакетов', labelKey: 'variant.tourFirms.packages-value' },
      { code: 'tour-package-price', label: 'Средняя цена тура', labelKey: 'variant.tourFirms.package-price' },
      { code: 'tour-package-price-domestic', label: 'Цена тура по России', labelKey: 'variant.tourFirms.package-price-domestic' },
      { code: 'tour-package-price-outbound', label: 'Цена тура за рубеж', labelKey: 'variant.tourFirms.package-price-outbound' },
      { code: 'tour-firm-tourists-russia', label: 'Туристы по России', labelKey: 'variant.tourFirms.firm-tourists-russia' },
      { code: 'tour-firm-tourists-abroad', label: 'Туристы за рубеж', labelKey: 'variant.tourFirms.firm-tourists-abroad' },
      { code: 'tour-agencies', label: 'Число турфирм', labelKey: 'variant.tourFirms.agencies' },
    ],
  },
  {
    label: 'Расходы семей на отдых',
    labelKey: 'variant.tourHousehold.group',
    codes: [
      { code: 'tour-household-spending', label: 'На человека', labelKey: 'variant.tourHousehold.household-spending' },
      { code: 'tour-household-spending-share', label: 'Доля в расходах', labelKey: 'variant.tourHousehold.household-spending-share' },
    ],
  },
  {
    label: 'Санатории',
    labelKey: 'variant.tourSanatoria.group',
    codes: [
      { code: 'tour-sanatorium-guests', label: 'Размещённые', labelKey: 'variant.tourSanatoria.sanatorium-guests' },
      { code: 'tour-sanatorium-nights', label: 'Ночёвки', labelKey: 'variant.tourSanatoria.sanatorium-nights' },
      { code: 'tour-sanatorium-revenue', label: 'Доходы', labelKey: 'variant.tourSanatoria.sanatorium-revenue' },
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

function lowerFirst(text) {
  return text ? text.charAt(0).toLowerCase() + text.slice(1) : text;
}

/** Подпись участника встречается более чем в одной группе (и потому неоднозначна без названия группы). */
function isSharedMemberLabel(member) {
  const key = member.labelKey || member.label;
  let groups = 0;
  for (const group of VARIANT_GROUPS) {
    if (group.codes.some((item) => (item.labelKey || item.label) === key)) groups += 1;
  }
  return groups > 1;
}

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
    // Подпись «До 1 года» повторяется в нескольких группах (кредиты юрлицам, физлицам, вклады):
    // отдельно она ничего не говорит, поэтому название собираем из группы и подписи.
    if (isSharedMemberLabel(member)) {
      return {
        title: `${groupLabel}, ${lowerFirst(memberLabel)}`,
        subtitle: null,
      };
    }
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
