import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import { ArrowLeft, ExternalLink, Activity, Info, TrendingUp, TrendingDown, Database, Terminal, Download } from 'lucide-react';
import {
  useIndicator, useIndicatorData, useIndicatorStats, useInflation, useForecast,
} from '../lib/hooks';
import { formatValue, formatDate, formatChange, unitSuffix, unitDigits, cn, isCpiIndex } from '../lib/format';
import { CATEGORIES } from '../lib/categories';
import useDocumentMeta from '../lib/useMeta';
import IndicatorChart from '../components/IndicatorChart';
import ForecastTable from '../components/ForecastTable';
import DataTable from '../components/DataTable';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { ChartSkeleton, SkeletonBox } from '../components/Skeleton';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, trackOutbound, events } from '../lib/track';

const SEO_MAP = {
  cpi: {
    title: 'Индекс потребительских цен (ИПЦ) — прогноз и данные',
    description: 'ИПЦ России: исторические данные с 1991 года, скользящая 12-месячная инфляция, прогноз на 12 месяцев. Данные Росстата, обновление ежедневно.',
  },
  'cpi-food': {
    title: 'ИПЦ на продовольственные товары — прогноз и данные',
    description: 'Индекс потребительских цен на продовольствие: динамика, инфляция продовольственных товаров, прогноз. Данные Росстата с 1991 года.',
  },
  'cpi-nonfood': {
    title: 'ИПЦ на непродовольственные товары — прогноз и данные',
    description: 'Индекс цен на непродовольственные товары: динамика, инфляция, прогноз на 12 месяцев. Данные Росстата с 1991 года.',
  },
  'cpi-services': {
    title: 'ИПЦ на услуги — прогноз и данные',
    description: 'Индекс потребительских цен на услуги: динамика цен, инфляция в сфере услуг, прогноз. Данные Росстата с 1991 года.',
  },
  'key-rate': {
    title: 'Ключевая ставка ЦБ РФ — график и история',
    description: 'Ключевая ставка Банка России: ежедневный ряд, визуализация и справка. Источник — cbr.ru.',
  },
  'usd-rub': {
    title: 'Курс доллара к рублю (USD/RUB) — график и прогноз',
    description: 'Официальный курс доллара к рублю ЦБ РФ: ежедневные данные, история.',
  },
  'eur-rub': {
    title: 'Курс евро к рублю (EUR/RUB) — график и прогноз',
    description: 'Официальный курс евро к рублю ЦБ РФ: ежедневные данные, история.',
  },
  'cny-rub': {
    title: 'Курс юаня к рублю (CNY/RUB) — график и прогноз',
    description: 'Официальный курс юаня к рублю ЦБ РФ: ежедневные данные, история.',
  },
  ruonia: {
    title: 'Ставка RUONIA — график и динамика',
    description: 'RUONIA: индикативная ставка однодневных рублёвых межбанковских кредитов. Данные Банка России.',
  },
  m0: {
    title: 'Денежная масса М0 — график и прогноз',
    description: 'Наличные деньги в обращении (агрегат М0): данные Банка России, история.',
  },
  m2: {
    title: 'Денежная масса М2 — график и прогноз',
    description: 'Широкая денежная масса (агрегат М2): данные Банка России, история.',
  },
  'mortgage-rate': {
    title: 'Ставка по ипотеке — график и прогноз',
    description: 'Средневзвешенная ставка по ипотечным жилищным кредитам в рублях. Данные Банка России.',
  },
  'deposit-rate': {
    title: 'Ставка по вкладам — график и прогноз',
    description: 'Средневзвешенная ставка по вкладам физических лиц в рублях. Данные Банка России.',
  },
  'auto-loan-rate': {
    title: 'Ставка по автокредитам — график и прогноз',
    description: 'Средневзвешенная ставка по автокредитам физическим лицам в рублях. Данные Банка России.',
  },
  'inflation-quarterly': {
    title: 'Инфляция квартальная — график и данные',
    description: 'Квартальный индекс инфляции, рассчитанный на основе месячных ИПЦ Росстата.',
  },
  'inflation-annual': {
    title: 'Инфляция годовая — график и прогноз',
    description: 'Годовая инфляция: скользящий 12-месячный показатель роста цен. Расчёт на основе ИПЦ.',
  },
  'unemployment': {
    title: 'Уровень безработицы в России — данные и прогноз',
    description: 'Безработица по методологии МОТ: ежемесячные данные с 2015 года, динамика. Данные Росстата.',
  },
  'wages-nominal': {
    title: 'Средняя заработная плата в России — данные и прогноз',
    description: 'Среднемесячная номинальная начисленная зарплата: ежемесячные данные, динамика. Данные Росстата.',
  },
  'wages-real': {
    title: 'Реальная заработная плата — индекс и динамика',
    description: 'Индекс реальной заработной платы с учётом инфляции. Расчёт: номинальная зарплата / ИПЦ.',
  },
  'gdp-nominal': {
    title: 'ВВП России — номинальный, квартальные данные',
    description: 'Валовой внутренний продукт России в текущих ценах: квартальные данные с 2011 года, прогноз. Данные Росстата.',
  },
  'gdp-yoy': {
    title: 'Рост ВВП России (год к году) — данные',
    description: 'Темп роста номинального ВВП к аналогичному кварталу прошлого года. Расчёт на основе данных Росстата.',
  },
  'gdp-qoq': {
    title: 'Рост ВВП России (квартал к кварталу) — данные',
    description: 'Темп роста номинального ВВП к предыдущему кварталу. Расчёт на основе данных Росстата.',
  },
  m1: {
    title: 'Денежная масса М1 — график и прогноз',
    description: 'Денежный агрегат М1 (наличные + переводные депозиты): данные Банка России, история.',
  },
  'consumer-credit': {
    title: 'Кредиты физическим лицам — данные и прогноз',
    description: 'Задолженность по кредитам физлицам (портфель): данные Банка России, динамика, прогноз.',
  },
  'business-credit': {
    title: 'Кредиты бизнесу — данные и прогноз',
    description: 'Задолженность по кредитам юрлицам и ИП (портфель): данные Банка России, динамика, прогноз.',
  },
  'deposits-individual': {
    title: 'Вклады физических лиц — данные и прогноз',
    description: 'Суммарные вклады населения в банках РФ: данные Банка России, история.',
  },
  'deposits-business': {
    title: 'Депозиты организаций — данные и прогноз',
    description: 'Суммарные депозиты нефинансовых организаций: данные Банка России, история, прогноз.',
  },
  'budget-deficit': {
    title: 'Дефицит бюджета России — данные и прогноз',
    description: 'Помесячный дефицит/профицит федерального бюджета РФ: данные Минфина, история с 2011 года.',
  },
  'inflation-weekly': {
    title: 'Недельная инфляция — данные Росстата',
    description: 'ИПЦ за неделю (к предыдущей неделе): еженедельные данные Росстата по ценам.',
  },
  'unemployment-quarterly': {
    title: 'Безработица квартальная — данные',
    description: 'Средний уровень безработицы за квартал: расчёт на основе месячных данных Росстата.',
  },
  'unemployment-annual': {
    title: 'Безработица среднегодовая — данные',
    description: 'Скользящее среднее безработицы за 12 месяцев: расчёт на основе данных Росстата.',
  },
  'housing-price-primary': {
    title: 'Цены на первичное жильё — индекс и динамика',
    description: 'Индекс цен на первичном рынке жилья (2010=100): квартальные данные Росстата.',
  },
  'housing-price-secondary': {
    title: 'Цены на вторичное жильё — индекс и динамика',
    description: 'Индекс цен на вторичном рынке жилья (2010=100): квартальные данные Росстата.',
  },
  'housing-yoy-primary': {
    title: 'Цены на первичное жильё (год к году) — данные',
    description: 'Изменение индекса цен на первичном рынке жилья к аналогичному кварталу предыдущего года. Расчёт на основе данных Росстата.',
  },
  'housing-yoy-secondary': {
    title: 'Цены на вторичное жильё (год к году) — данные',
    description: 'Изменение индекса цен на вторичном рынке жилья к аналогичному кварталу предыдущего года. Расчёт на основе данных Росстата.',
  },
  ipi: {
    title: 'Индекс промышленного производства — данные и прогноз',
    description: 'ИПП России (2023=100): ежемесячные данные с 2015 года, динамика. Данные Росстата.',
  },
  'ipi-yoy': {
    title: 'ИПП (год к году) — данные',
    description: 'Изменение индекса промышленного производства к аналогичному месяцу предыдущего года.',
  },
  population: {
    title: 'Численность населения России — данные',
    description: 'Численность постоянного населения РФ: ежегодные данные с 2010 года. Данные Росстата.',
  },
  'population-natural-growth': {
    title: 'Естественный прирост населения — данные',
    description: 'Естественный прирост (рождения минус смерти): ежегодные данные с 1990 года. Росстат.',
  },
  'population-total-growth': {
    title: 'Общий прирост населения — данные',
    description: 'Общий прирост населения (естественный + миграция): ежегодные данные. Росстат.',
  },
  'population-migration': {
    title: 'Миграционный прирост — данные',
    description: 'Миграционный прирост населения: ежегодные данные с 1990 года. Данные Росстата.',
  },
  'current-account': {
    title: 'Сальдо текущего счёта — данные и прогноз',
    description: 'Сальдо счёта текущих операций платёжного баланса РФ: квартальные данные Банка России с 2000 года.',
  },
  'current-account-yoy': {
    title: 'Текущий счёт (изменение г/г) — данные',
    description: 'Изменение сальдо текущего счёта к аналогичному кварталу предыдущего года.',
  },
  ppi: {
    title: 'Индекс цен производителей (ИЦП) — данные и прогноз',
    description: 'ИЦП России (2010=100): ежемесячные данные с 2011 года, динамика промышленных цен. Данные Росстата.',
  },
  'ppi-yoy': {
    title: 'ИЦП (год к году) — данные',
    description: 'Изменение индекса цен производителей к аналогичному месяцу предыдущего года.',
  },
  exports: {
    title: 'Экспорт товаров из России — данные и прогноз',
    description: 'Экспорт товаров по методологии платёжного баланса: квартальные данные с 1994 года. Банк России.',
  },
  imports: {
    title: 'Импорт товаров в Россию — данные и прогноз',
    description: 'Импорт товаров по методологии платёжного баланса: квартальные данные с 1994 года. Банк России.',
  },
  'trade-balance': {
    title: 'Торговый баланс России — данные и прогноз',
    description: 'Торговый баланс (экспорт минус импорт товаров): квартальные данные. Банк России.',
  },
  'exports-yoy': {
    title: 'Экспорт (изменение г/г) — данные',
    description: 'Изменение экспорта товаров к аналогичному кварталу предыдущего года.',
  },
  'imports-yoy': {
    title: 'Импорт (изменение г/г) — данные',
    description: 'Изменение импорта товаров к аналогичному кварталу предыдущего года.',
  },
  'international-reserves': {
    title: 'Международные резервы России — данные',
    description: 'Золотовалютные резервы РФ: еженедельные данные Банка России в млрд долларов.',
  },
  'external-debt': {
    title: 'Внешний долг России — данные',
    description: 'Внешний долг РФ: квартальные данные с 2003 года в млн долларов. Банк России.',
  },
  'gdp-consumption': {
    title: 'Расходы домохозяйств — компонент ВВП',
    description: 'Расходы на конечное потребление домашних хозяйств в текущих ценах. Квартальные данные Росстата.',
  },
  'gdp-government': {
    title: 'Государственное потребление — компонент ВВП',
    description: 'Расходы государственного управления на конечное потребление. Квартальные данные Росстата.',
  },
  'gdp-investment': {
    title: 'Инвестиции в основной капитал — данные',
    description: 'Валовое накопление основного капитала: строительство, оборудование, транспорт. Квартальные данные Росстата.',
  },
  'labor-force': {
    title: 'Рабочая сила в России — данные',
    description: 'Численность экономически активного населения: ежемесячные данные с 2015 года. Данные Росстата.',
  },
  employment: {
    title: 'Занятость в России — данные',
    description: 'Численность занятого населения: ежемесячные данные с 2015 года. Данные Росстата.',
  },
  'wages-yoy': {
    title: 'Рост зарплат (год к году) — данные',
    description: 'Изменение средней номинальной зарплаты к аналогичному месяцу предыдущего года.',
  },
  'budget-revenue': {
    title: 'Доходы федерального бюджета — данные и прогноз',
    description: 'Помесячные доходы федерального бюджета РФ: данные Минфина, история с 2011 года.',
  },
  'budget-expenditure': {
    title: 'Расходы федерального бюджета — данные и прогноз',
    description: 'Помесячные расходы федерального бюджета РФ: данные Минфина, история с 2011 года.',
  },
  'services-exports': {
    title: 'Экспорт услуг из России — данные',
    description: 'Экспорт услуг по методологии платёжного баланса: квартальные данные Банка России.',
  },
  'services-imports': {
    title: 'Импорт услуг в Россию — данные',
    description: 'Импорт услуг по методологии платёжного баланса: квартальные данные Банка России.',
  },
  'fdi-net': {
    title: 'Прямые иностранные инвестиции (ПИИ) — данные',
    description: 'Чистый приток ПИИ по данным платёжного баланса: квартальные данные Банка России.',
  },
  'gold-price': {
    title: 'Цена золота ЦБ РФ — график и динамика',
    description: 'Учётная цена на золото Банка России в рублях за грамм: ежедневные данные.',
  },
  'exports-qoq': {
    title: 'Экспорт (изменение кв/кв) — данные',
    description: 'Изменение экспорта товаров к предыдущему кварталу.',
  },
  'imports-qoq': {
    title: 'Импорт (изменение кв/кв) — данные',
    description: 'Изменение импорта товаров к предыдущему кварталу.',
  },
  births: {
    title: 'Число рождений в России — данные',
    description: 'Число родившихся в России за год: данные Росстата с 1990 года.',
  },
  deaths: {
    title: 'Число смертей в России — данные',
    description: 'Число умерших в России за год: данные Росстата с 1990 года.',
  },
  'birth-rate': {
    title: 'Коэффициент рождаемости в России — данные',
    description: 'Число родившихся на 1000 человек населения: данные Росстата.',
  },
  'death-rate': {
    title: 'Коэффициент смертности в России — данные',
    description: 'Число умерших на 1000 человек населения: данные Росстата.',
  },
  'working-age-population': {
    title: 'Население в трудоспособном возрасте — данные',
    description: 'Численность населения в трудоспособном возрасте (млн чел.): данные Росстата.',
  },
  pensioners: {
    title: 'Численность пенсионеров в России — данные',
    description: 'Общая численность пенсионеров на 1 января: данные Росстата/СФР.',
  },
  'retail-trade': {
    title: 'Оборот розничной торговли — данные и прогноз',
    description: 'Оборот розничной торговли в текущих ценах: ежемесячные данные Росстата.',
  },
  'housing-commissioned': {
    title: 'Ввод в действие жилых домов — данные',
    description: 'Ввод жилья в млн кв.м: ежемесячные данные Росстата с 2005 года.',
  },
  'depreciation-rate': {
    title: 'Степень износа основных фондов — данные',
    description: 'Степень износа основных фондов в %: годовые данные Росстата с 1990 года.',
  },
  'grad-students': {
    title: 'Численность аспирантов в России — данные',
    description: 'Численность аспирантов на начало учебного года: данные Росстата.',
  },
  'doctoral-students': {
    title: 'Численность докторантов в России — данные',
    description: 'Численность докторантов на начало учебного года: данные Росстата.',
  },
  'rd-organizations': {
    title: 'Организации НИР в России — данные',
    description: 'Число организаций, выполнявших научные исследования и разработки: данные Росстата.',
  },
  'rd-personnel': {
    title: 'Персонал НИР в России — данные',
    description: 'Численность персонала, занятого научными исследованиями: данные Росстата.',
  },
  'innovation-activity': {
    title: 'Уровень инновационной активности — данные',
    description: 'Уровень инновационной активности организаций (%): данные Росстата.',
  },
  'tech-innovation-share': {
    title: 'Доля организаций с технологическими инновациями — данные',
    description: 'Удельный вес организаций с технологическими инновациями: данные Росстата.',
  },
  'small-business-innovation': {
    title: 'Инновации малых предприятий — данные',
    description: 'Удельный вес малых предприятий с инновационной деятельностью: данные Росстата.',
  },
  'construction-work': {
    title: 'Объём строительных работ — данные и прогноз',
    description: 'Объём строительных работ в России: ежемесячные данные Росстата, динамика и прогноз. Краткосрочные экономические показатели.',
  },
  'capital-investment': {
    title: 'Инвестиции в основной капитал — данные и прогноз',
    description: 'Инвестиции в основной капитал России: ежемесячные данные Росстата, динамика и прогноз.',
  },
  'pop-under-working-age': {
    title: 'Население моложе трудоспособного возраста — данные',
    description: 'Численность населения моложе трудоспособного возраста (0–15 лет): исторические данные Росстата с 1990 года.',
  },
  'pop-over-working-age': {
    title: 'Население старше трудоспособного возраста — данные',
    description: 'Численность населения старше трудоспособного возраста: данные Росстата с 1990 года.',
  },
};

const FREQ_MAP = {
  monthly: 'Помесячно',
  quarterly: 'Ежеквартально',
  annual: 'Ежегодно',
  weekly: 'Еженедельно',
  irregular: 'Нерегулярно',
  daily: 'По дням',
};

const INFLATION_DESCRIPTION =
  'Накопленная инфляция за 12 месяцев показывает, на сколько процентов выросли ' +
  'потребительские цены за последний год. Рассчитывается как произведение 12 ' +
  'последовательных месячных индексов ИПЦ минус 100%.';

const INFLATION_METHODOLOGY =
  'Формула: (∏ᵢ₌₁¹² ИПЦᵢ / 100) × 100 − 100, где ИПЦᵢ — индекс потребительских ' +
  'цен за i-й месяц в % к предыдущему месяцу.';

const QUARTERLY_DESCRIPTION =
  'Квартальная инфляция показывает, на сколько процентов выросли потребительские цены за квартал (3 месяца). ' +
  'Рассчитывается как произведение 3 последовательных месячных индексов ИПЦ минус 100%.';

const QUARTERLY_METHODOLOGY =
  'Формула: (ИПЦ₁ / 100) × (ИПЦ₂ / 100) × (ИПЦ₃ / 100) × 100 − 100.';

const ANNUAL_DESCRIPTION =
  'Годовая инфляция — изменение цен за последние 12 месяцев. ' +
  'Рассчитывается как произведение 12 последовательных месячных индексов ИПЦ минус 100%.';

const ANNUAL_METHODOLOGY =
  'Формула: (∏ᵢ₌₁¹² ИПЦᵢ / 100) × 100 − 100, скользящее окно 12 месяцев.';

const WEEKLY_DESCRIPTION =
  'Недельный ИПЦ — изменение потребительских цен за неделю по данным Росстата. ' +
  'Публикуется еженедельно, является оперативным индикатором инфляционных процессов.';

const WEEKLY_METHODOLOGY =
  'Источник — еженедельные бюллетени Росстата «Об оценке индекса потребительских цен». ' +
  'Официальный агрегированный недельный ИПЦ по всей потребительской корзине. Значение 100 = без изменений.';

function TelemetryCard({
  label, value, unit, change, pctChange, meta, delay = 0,
  deltaSuffix = 'к пред. месяцу',
}) {
  const ref = useRef(null);
  const valRef = useRef(null);
  const animated = useRef(false);
  
  useEffect(() => {
    if (animated.current || !ref.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animated.current = true;
    const tween = gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.4 + delay * 0.1 }
    );
    return () => tween.kill();
  }, [delay]);

  const digits = unitDigits(unit);
  useEffect(() => {
    if (value == null || !valRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      valRef.current.textContent = formatValue(value, digits);
      return;
    }
    const raw = valRef.current.textContent.replace(/\s/g, '') || '0';
    const from = parseFloat(raw) || 0;
    const target = Number(value);
    const counter = { v: from };
    const tween = gsap.to(counter, {
      v: target,
      duration: from === 0 ? 1.5 : 0.6,
      ease: 'power2.out',
      delay: from === 0 ? 0.2 : 0,
      onUpdate() {
        if (valRef.current) {
          valRef.current.textContent = formatValue(counter.v, digits);
        }
      },
    });
    return () => tween.kill();
  }, [value, digits]);

  const changeNum = change != null ? Number(change) : null;
  const isUp = changeNum != null && changeNum > 0;
  const isDown = changeNum != null && changeNum < 0;

  return (
    <div ref={ref} className="group relative p-4 sm:p-6 rounded-[2rem] bg-surface border border-border-subtle hover:border-champagne/30 transition-colors duration-500 overflow-hidden lift-hover">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-champagne/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
      
      <p className="text-[10px] uppercase tracking-widest text-text-tertiary font-medium mb-4">
        {label}
      </p>

      <div className="flex items-baseline gap-2 mb-2 flex-wrap">
        <span ref={valRef} className={cn(
          'font-mono font-bold tracking-tight text-text-primary whitespace-nowrap',
          String(formatValue(value, unitDigits(unit))).length > 12
            ? 'text-xl md:text-2xl'
            : 'text-2xl md:text-3xl'
        )}>
          {formatValue(value, unitDigits(unit))}
        </span>
        <span className="text-xs font-medium text-text-tertiary shrink-0 whitespace-nowrap">{unitSuffix(unit)}</span>
      </div>

      <div className="flex flex-col gap-1.5 mt-4 pt-4 border-t border-border-subtle/50">
        {changeNum != null && (
          <div className={cn(
            'flex items-center gap-1.5 text-xs font-mono font-medium flex-wrap',
            isUp ? 'text-positive' : '',
            isDown ? 'text-negative' : '',
            !isUp && !isDown ? 'text-text-tertiary' : ''
          )}>
            {isUp && <TrendingUp className="w-3.5 h-3.5 shrink-0" />}
            {isDown && <TrendingDown className="w-3.5 h-3.5 shrink-0" />}
            <span>{pctChange != null ? `${formatChange(pctChange)}%` : `Δ ${formatChange(changeNum)}`}</span>
            <span className="text-text-tertiary text-[10px] uppercase tracking-wider ml-1">
              {deltaSuffix}
            </span>
          </div>
        )}
        {meta && (
          <div className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
            {meta}
          </div>
        )}
      </div>
    </div>
  );
}

export default function IndicatorDetail() {
  const { code } = useParams();
  const headerRef = useRef(null);
  const [showForecast, setShowForecast] = useState(true);
  const [viewMode, setViewMode] = useState('inflation');
  const [chartData, setChartData] = useState([]);
  const [currentRange, setCurrentRange] = useState('5y');

  const seo = SEO_MAP[code] || {};
  useDocumentMeta({
    title: seo.title || `Индикатор ${code}`,
    description: seo.description,
    path: `/indicator/${code}`,
  });

  const {
    data: indicator,
    isLoading: loadingInd,
    isError: indError,
    error: indErr,
    refetch: refetchInd,
    isFetching: fetchingInd,
  } = useIndicator(code);
  const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];
  const isPriceCategory = CPI_CODES.includes(code);
  const canForecast = indicator?.category === 'Цены';
  const forecastEnabled = canForecast && viewMode !== 'quarterly' && viewMode !== 'annual' && viewMode !== 'weekly';
  const shouldSubtract100 = isCpiIndex(code);
  const {
    data: dataResp,
    isLoading: loadingData,
    isError: dataError,
    refetch: refetchData,
    isFetching: fetchingData,
  } = useIndicatorData(code);
  const { data: stats } = useIndicatorStats(code);
  const { data: inflationResp, isLoading: loadingInflation, refetch: refetchInflation } = useInflation(code, {
    enabled: isPriceCategory,
  });
  const { data: forecastResp, refetch: refetchForecast } = useForecast(code);

  const hasCpiTabs = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'].includes(code);
  const hasMainCpiDerived = code === 'cpi';
  const {
    data: quarterlyResp,
    isLoading: loadingQuarterly,
  } = useIndicatorData('inflation-quarterly', undefined, {
    enabled: hasMainCpiDerived && viewMode === 'quarterly',
  });
  const {
    data: annualResp,
    isLoading: loadingAnnual,
  } = useIndicatorData('inflation-annual', undefined, {
    enabled: hasMainCpiDerived && viewMode === 'annual',
  });
  const {
    data: weeklyResp,
    isLoading: loadingWeekly,
  } = useIndicatorData('inflation-weekly', undefined, {
    enabled: hasMainCpiDerived && viewMode === 'weekly',
  });

  const chartMode = isPriceCategory ? viewMode : 'cpi';

  const inflationStats = useMemo(() => {
    if (chartMode !== 'inflation' || !inflationResp?.actuals?.length) return null;
    const a = inflationResp.actuals;
    const current = a[a.length - 1];
    const previous = a.length > 1 ? a[a.length - 2] : null;
    const highest = a.reduce((max, p) => p.value > max.value ? p : max, a[0]);
    const avg = a.reduce((s, p) => s + p.value, 0) / a.length;
    return {
      currentValue: current.value,
      currentDate: current.date,
      previousValue: previous?.value,
      previousDate: previous?.date,
      change: previous ? current.value - previous.value : null,
      highest: { value: highest.value, date: highest.date },
      average: avg,
      dataCount: a.length,
    };
  }, [chartMode, inflationResp]);

  useEffect(() => {
    const els = headerRef.current?.querySelectorAll('[data-animate]');
    if (!els?.length) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(els,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 1, ease: 'power3.out', stagger: 0.1 }
    );
    return () => tween.kill();
  }, []);

  useEffect(() => {
    if (!indicator?.code) return;
    track(events.INDICATOR_VIEW, {
      indicator: indicator.code,
      indicatorCategory: indicator.category,
    });
  }, [indicator?.code, indicator?.category]);

  const rawDataPoints = useMemo(
    () => (Array.isArray(dataResp?.data) ? dataResp.data : []),
    [dataResp?.data],
  );

  const dataPoints = useMemo(() => {
    if (!shouldSubtract100 || !rawDataPoints.length) return rawDataPoints;
    return rawDataPoints.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [rawDataPoints, shouldSubtract100]);

  const displayForecastData = useMemo(() => {
    if (!shouldSubtract100 || !forecastResp?.forecast?.values?.length) return forecastResp;
    return {
      ...forecastResp,
      forecast: {
        ...forecastResp.forecast,
        values: forecastResp.forecast.values.map(v => ({
          ...v,
          value: Number(v.value) - 100,
        })),
      },
    };
  }, [forecastResp, shouldSubtract100]);

  const adj = useCallback((v) => {
    if (v == null || !shouldSubtract100) return v;
    return Number(v) - 100;
  }, [shouldSubtract100]);

  const quarterlyDataPoints = useMemo(() => {
    if (!quarterlyResp?.data?.length) return [];
    return quarterlyResp.data.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [quarterlyResp]);

  const annualDataPoints = useMemo(() => {
    if (!annualResp?.data?.length) return [];
    const byYear = new Map();
    for (const p of annualResp.data) {
      const year = String(p.date).slice(0, 4);
      const existing = byYear.get(year);
      if (!existing || String(p.date) > String(existing.date)) {
        byYear.set(year, p);
      }
    }
    return Array.from(byYear.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [annualResp]);

  const weeklyDataPoints = useMemo(() => {
    if (!weeklyResp?.data?.length) return [];
    return weeklyResp.data.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [weeklyResp]);

  function computeDerivedStats(points, mode) {
    if (!points.length) return null;
    const a = points;
    const current = a[a.length - 1];
    const previous = a.length > 1 ? a[a.length - 2] : null;
    const highest = a.reduce((max, p) => p.value > max.value ? p : max, a[0]);
    const avg = a.reduce((sum, p) => sum + p.value, 0) / a.length;
    return {
      currentValue: current.value,
      currentDate: current.date,
      previousValue: previous?.value,
      previousDate: previous?.date,
      change: previous ? current.value - previous.value : null,
      highest: { value: highest.value, date: highest.date },
      average: avg,
      dataCount: a.length,
    };
  }

  const quarterlyStats = useMemo(() => {
    if (viewMode !== 'quarterly') return null;
    return computeDerivedStats(quarterlyDataPoints);
  }, [viewMode, quarterlyDataPoints]);

  const annualStats = useMemo(() => {
    if (viewMode !== 'annual') return null;
    return computeDerivedStats(annualDataPoints);
  }, [viewMode, annualDataPoints]);

  const weeklyStats = useMemo(() => {
    if (viewMode !== 'weekly') return null;
    return computeDerivedStats(weeklyDataPoints);
  }, [viewMode, weeklyDataPoints]);

  const s = viewMode === 'quarterly' ? quarterlyStats
    : viewMode === 'annual' ? annualStats
    : viewMode === 'weekly' ? weeklyStats
    : inflationStats;
  const cpiPrevDate = dataPoints.length >= 2 ? dataPoints[dataPoints.length - 2].date : null;


  const handleChartData = useCallback((data) => {
    setChartData(data);
  }, []);

  const handleRangeChange = useCallback((range) => {
    setCurrentRange(range);
  }, []);

  const downloadMeta = useMemo(() => ({
    name: indicator?.name, unit: indicator?.unit,
  }), [indicator?.name, indicator?.unit]);

  const downloadMode = isPriceCategory ? chartMode : null;

  const handleDownloadExcel = useCallback(() => {
    downloadExcel(chartData, downloadMode, code, currentRange, downloadMeta);
    track(events.DOWNLOAD_EXCEL, { indicator: code, range: currentRange, indicatorCategory: indicator?.category });
  }, [chartData, downloadMode, code, currentRange, downloadMeta, indicator?.category]);

  const handleDownloadCSV = useCallback(() => {
    downloadCSV(chartData, downloadMode, code, currentRange, downloadMeta);
    track(events.DOWNLOAD_CSV, { indicator: code, range: currentRange, indicatorCategory: indicator?.category });
  }, [chartData, downloadMode, code, currentRange, downloadMeta, indicator?.category]);

  const chartLoading = chartMode === 'inflation' ? loadingInflation
    : chartMode === 'quarterly' ? loadingQuarterly
    : chartMode === 'annual' ? loadingAnnual
    : chartMode === 'weekly' ? loadingWeekly
    : loadingData;

  const hasForecastData = chartMode === 'quarterly'
    ? false
    : chartMode === 'inflation'
      ? inflationResp?.forecast?.length > 0
      : displayForecastData?.forecast?.values?.length > 0;

  const chartEmptyHint = useMemo(() => {
    if (dataError) {
      return 'Не удалось получить исторический ряд. Нажмите «Повторить» выше или проверьте backend / прокси Vite.';
    }
    if (
      hasCpiTabs && !hasMainCpiDerived
      && ['quarterly', 'annual', 'weekly'].includes(viewMode)
    ) {
      return (
        'Для подкатегорий ИПЦ (продовольствие, непродовольственные товары, услуги) квартальная, годовая и недельная агрегации '
        + 'пока не рассчитываются. Используйте вкладку «Инфляция за год» или «Месячная».'
      );
    }
    if (!loadingData && (dataPoints?.length ?? 0) === 0) {
      return (
        'В API пока нет точек для этого кода — например, прод ещё без backfill ключевой ставки, или локальный backend не запущен. '
        + 'После появления данных график заполнится автоматически.'
      );
    }
    return undefined;
  }, [dataError, loadingData, dataPoints, hasCpiTabs, hasMainCpiDerived, viewMode]);

  const refetchIndicatorPage = useCallback(() => {
    refetchInd();
    refetchData();
    if (isPriceCategory) refetchInflation();
    refetchForecast();
  }, [refetchInd, refetchData, refetchInflation, refetchForecast, isPriceCategory]);

  const apiBannerFetching = fetchingInd || fetchingData;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      {(indError || dataError) && (
        <div className="mb-8">
          <ApiRetryBanner
            onRetry={refetchIndicatorPage}
            isFetching={apiBannerFetching}
          >
            {indError && (
              <span className="block">
                Карточка индикатора не загрузилась
                {indErr?.message ? ` (${indErr.message})` : ''}.
              </span>
            )}
            {dataError && (
              <span className="block">
                Исторические данные недоступны — график и таблица без ряда.
              </span>
            )}
          </ApiRetryBanner>
        </div>
      )}

      <div ref={headerRef} className="mb-12 md:mb-16 max-w-4xl">
        <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
          <Link
            to="/"
            className="hover:text-champagne transition-colors lift-hover inline-flex items-center gap-1.5 group"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
            Главная
          </Link>
          {indicator?.category && (() => {
            const cat = CATEGORIES.find(c => c.apiCategory === indicator.category);
            if (!cat) return null;
            return (
              <>
                <span className="text-text-tertiary/40">/</span>
                <Link to={`/category/${cat.slug}`} className="hover:text-champagne transition-colors">
                  {cat.name}
                </Link>
              </>
            );
          })()}
        </nav>

        {loadingInd ? (
          <div className="space-y-4">
            <SkeletonBox className="h-4 w-24" />
            <SkeletonBox className="h-14 w-3/4" />
            <SkeletonBox className="h-6 w-1/2" />
          </div>
        ) : (
          <>
            <div data-animate className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
                <Activity className="w-3 h-3 text-champagne" />
                {FREQ_MAP[indicator?.frequency] || indicator?.frequency}
              </span>
              {indicator?.category && (
                <span className="text-xs font-mono text-text-tertiary">
                  {indicator.category}
                </span>
              )}
            </div>

            <h1 data-animate className="text-4xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-4 leading-tight">
              {indicator?.name || code}
            </h1>
            
            {indicator?.name_en && (
              <p data-animate className="text-sm md:text-base font-mono text-text-tertiary">
                {indicator.name_en}
              </p>
            )}
          </>
        )}
      </div>

      <section className="mb-12">
        {(loadingInd || (chartMode === 'inflation' && loadingInflation) || (chartMode === 'annual' && loadingAnnual) || (chartMode === 'weekly' && loadingWeekly) || (chartMode === 'quarterly' && loadingQuarterly)) ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => <SkeletonBox key={i} className="h-48 rounded-[2rem]" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TelemetryCard
              label={viewMode === 'weekly' ? 'Инфляция за неделю' : 'Текущее значение'}
              value={s?.currentValue ?? adj(indicator?.current_value)}
              unit={indicator?.unit || '%'}
              change={s?.change ?? indicator?.change}
              pctChange={
                indicator?.unit === 'индекс' && (s?.previousValue ?? indicator?.previous_value)
                  ? +(((s?.currentValue ?? indicator?.current_value) - (s?.previousValue ?? indicator?.previous_value))
                      / (s?.previousValue ?? indicator?.previous_value) * 100).toFixed(2)
                  : undefined
              }
              meta={
                viewMode === 'weekly' && Number(s?.currentValue) === 0
                  ? `ДАТА: ${formatDate(s?.currentDate ?? indicator?.current_date, 'full')} · ЦЕНЫ БЕЗ ИЗМЕНЕНИЙ`
                  : `ДАТА: ${formatDate(s?.currentDate ?? indicator?.current_date, 'full')}`
              }
              delay={0}
              deltaSuffix={
                viewMode === 'quarterly' ? 'к пред. кварталу'
                  : viewMode === 'annual' ? 'к пред. значению'
                  : viewMode === 'weekly' ? 'к пред. неделе'
                  : indicator?.frequency === 'quarterly' ? 'к пред. кварталу'
                  : isPriceCategory ? 'к пред. месяцу' : 'к пред. значению'
              }
            />
            <TelemetryCard
              label={
                viewMode === 'weekly' ? 'Предыдущая неделя'
                  : viewMode === 'quarterly' ? 'Предыдущий квартал'
                  : viewMode === 'annual' ? 'Год назад'
                  : isPriceCategory ? 'Предыдущий месяц' : 'Предыдущее значение'
              }
              value={s?.previousValue ?? adj(indicator?.previous_value)}
              unit={indicator?.unit || '%'}
              meta={`ДАТА: ${formatDate(s?.previousDate ?? cpiPrevDate, 'full')}`}
              delay={1}
            />
            {(s?.highest || stats?.highest) && (
              <TelemetryCard
                label="Абсолютный максимум"
                value={s?.highest?.value ?? adj(stats?.highest?.value)}
                unit={indicator?.unit || '%'}
                meta={`ПИК: ${formatDate(s?.highest?.date ?? stats?.highest?.date, 'full')}`}
                delay={2}
              />
            )}
            {(s?.average != null || stats?.average != null) && (
              <TelemetryCard
                label="Среднее значение"
                value={s?.average ?? adj(stats?.average)}
                unit={indicator?.unit || '%'}
                meta={`НАБЛ.: ${s?.dataCount ?? stats?.data_count} ПЕРИОД.`}
                delay={3}
              />
            )}
          </div>
        )}
      </section>

      <section className="mb-16">
        <div className="flex items-center justify-between mb-6 border-b border-border-subtle pb-4 flex-wrap gap-3">
          <div className="flex items-center gap-4">
            <Terminal className="w-4 h-4 text-champagne" />
            {isPriceCategory ? (
              <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle flex-wrap">
                {[
                  { mode: 'inflation', label: 'Инфляция за год', always: true },
                  { mode: 'weekly', label: 'Недельная', always: false },
                  { mode: 'cpi', label: 'Месячная', always: true },
                  { mode: 'quarterly', label: 'Квартальная', always: false },
                  { mode: 'annual', label: 'Годовая', always: false },
                ]
                  .filter(t => t.always || hasCpiTabs)
                  .map(t => (
                    <button
                      key={t.mode}
                      type="button"
                      onClick={() => {
                        setViewMode(t.mode);
                        track(events.CHART_MODE_CHANGE, { mode: t.mode, indicator: code, indicatorCategory: indicator?.category });
                      }}
                      className={cn(
                        'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                        viewMode === t.mode
                          ? 'bg-champagne/15 text-champagne'
                          : 'text-text-tertiary hover:text-text-secondary'
                      )}
                    >
                      {t.label}
                    </button>
                  ))}
              </div>
            ) : (
              <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
                Динамика показателя
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownloadCSV}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
              title="Скачать CSV"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
            <button
              onClick={handleDownloadExcel}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
              title="Скачать Excel"
            >
              <Download className="w-3.5 h-3.5" />
              Excel
            </button>

            <div className="relative group">
              <label className={cn(
                'flex items-center gap-3 select-none',
                forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
              )}>
                <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                  Прогноз
                </span>
                <div
                  role="switch"
                  aria-checked={forecastEnabled && showForecast}
                  aria-label="Показать прогноз"
                  tabIndex={forecastEnabled ? 0 : -1}
                  onClick={() => { if (forecastEnabled) { setShowForecast(v => !v); track(events.FORECAST_TOGGLE, { show: !showForecast, indicator: code, indicatorCategory: indicator?.category }); } }}
                  onKeyDown={e => { if (forecastEnabled && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); setShowForecast(v => !v); track(events.FORECAST_TOGGLE, { show: !showForecast, indicator: code, indicatorCategory: indicator?.category }); } }}
                  className={cn(
                    'relative w-10 h-5 rounded-full transition-colors duration-300',
                    forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed',
                    forecastEnabled && showForecast ? 'bg-champagne/30' : 'bg-obsidian-lighter border border-border-subtle'
                  )}
                >
                  <div className={cn(
                    'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                    forecastEnabled && showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary'
                  )} />
                </div>
              </label>
              {!forecastEnabled && (
                <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
                  {['quarterly', 'annual', 'weekly'].includes(viewMode) ? 'Прогноз недоступен для этого режима' : 'Прогноз скоро будет доступен'}
                </div>
              )}
            </div>
          </div>
        </div>

        {chartLoading ? (
          <ChartSkeleton />
        ) : (
          <div className="relative overflow-hidden rounded-[2rem]">
            <IndicatorChart
              key={`${indicator?.code}-${chartMode}`}
              mode={['quarterly', 'annual', 'weekly'].includes(chartMode) ? 'cpi' : chartMode}
              inflation={inflationResp}
              cpiData={chartMode === 'quarterly' ? quarterlyDataPoints
                : chartMode === 'annual' ? annualDataPoints
                : chartMode === 'weekly' ? weeklyDataPoints
                : dataPoints}
              forecastData={['quarterly', 'annual', 'weekly'].includes(chartMode) ? null : displayForecastData}
              showForecast={forecastEnabled && showForecast}
              onChartData={handleChartData}
              onRangeChange={handleRangeChange}
              referenceLineY={isPriceCategory ? undefined : null}
              cpiChartTitle={
                chartMode === 'quarterly' ? 'Квартальная инфляция (%)'
                  : chartMode === 'annual' ? 'Годовая инфляция (%)'
                  : chartMode === 'weekly' ? 'Недельная инфляция (%)'
                  : isPriceCategory
                    ? undefined
                    : `${indicator?.name || 'Показатель'}${unitSuffix(indicator?.unit) ? ` (${unitSuffix(indicator?.unit)})` : ''}`
              }
              levelTooltipLabel={
                chartMode === 'quarterly' ? 'Кв. инфляция'
                  : chartMode === 'annual' ? 'Год. инфляция'
                  : chartMode === 'weekly' ? 'Нед. ИПЦ'
                  : isPriceCategory ? undefined : 'Значение'
              }
              emptyHint={chartEmptyHint}
              dateFormat={
                chartMode === 'quarterly' ? 'quarterly'
                : chartMode === 'annual' ? 'annual'
                : chartMode !== 'inflation' && indicator?.frequency === 'daily' ? 'day'
                : indicator?.frequency === 'quarterly' ? 'quarterly'
                : indicator?.frequency === 'annual' ? 'annual'
                : 'full'
              }
              unit={indicator?.unit || '%'}
              rangePreset={
                chartMode === 'annual' || indicator?.frequency === 'annual'
                  ? 'annual'
                  : 'default'
              }
              indicatorCode={code}
              indicatorCategory={indicator?.category}
            />
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-16">
        <section className="lg:col-span-1 p-8 rounded-[2rem] bg-obsidian-light border border-border-subtle flex flex-col h-full">
          <div className="flex items-center gap-3 mb-6">
            <Info className="w-4 h-4 text-champagne" />
            <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-text-secondary">
              Методология
            </h3>
          </div>
          
          <div className="prose prose-sm max-w-none">
            <p className="text-text-secondary leading-relaxed">
              {chartMode === 'inflation' ? INFLATION_DESCRIPTION
                : viewMode === 'quarterly' ? QUARTERLY_DESCRIPTION
                : viewMode === 'annual' ? ANNUAL_DESCRIPTION
                : viewMode === 'weekly' ? WEEKLY_DESCRIPTION
                : indicator?.description}
            </p>
            {(chartMode === 'inflation' ? INFLATION_METHODOLOGY
              : viewMode === 'quarterly' ? QUARTERLY_METHODOLOGY
              : viewMode === 'annual' ? ANNUAL_METHODOLOGY
              : viewMode === 'weekly' ? WEEKLY_METHODOLOGY
              : indicator?.methodology) && (
              <p className="text-text-tertiary border-l-2 border-champagne/30 pl-4 my-4 font-mono text-[10px] uppercase tracking-wider">
                {chartMode === 'inflation' ? INFLATION_METHODOLOGY
                  : viewMode === 'quarterly' ? QUARTERLY_METHODOLOGY
                  : viewMode === 'annual' ? ANNUAL_METHODOLOGY
                  : viewMode === 'weekly' ? WEEKLY_METHODOLOGY
                  : indicator?.methodology}
              </p>
            )}
          </div>
          
          {indicator?.source_url && indicator.source_url.startsWith('http') ? (
          <div className="mt-auto pt-6 border-t border-border-subtle">
            <a
              href={indicator.source_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackOutbound(indicator.source_url)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-champagne hover:bg-champagne/10 transition-colors lift-hover w-full justify-center"
            >
              <Database className="w-3.5 h-3.5" />
              Источник: {indicator.source}
              <ExternalLink className="w-3 h-3 ml-auto opacity-50" />
            </a>
          </div>
          ) : indicator?.source ? (
          <div className="mt-auto pt-6 border-t border-border-subtle">
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-text-secondary w-full justify-center">
              <Database className="w-3.5 h-3.5" />
              Источник: {indicator.source}
            </span>
          </div>
          ) : null}
        </section>

        <section className="lg:col-span-2">
          {['quarterly', 'annual', 'weekly'].includes(viewMode) ? (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-1 opacity-20" />
              <p className="text-sm font-medium text-text-secondary text-center max-w-md">
                {viewMode === 'quarterly' && 'Квартальные данные рассчитываются на основе месячных значений ИПЦ'}
                {viewMode === 'annual' && 'Годовая инфляция рассчитывается как скользящее произведение 12 месячных ИПЦ'}
                {viewMode === 'weekly' && 'Недельный ИПЦ публикуется Росстатом еженедельно'}
              </p>
              <p className="text-xs text-center max-w-lg leading-relaxed text-text-tertiary">
                Для прогноза переключитесь на вкладку «Инфляция 12 мес.» или «ИПЦ помесячно»
              </p>
            </div>
          ) : forecastEnabled && showForecast && hasForecastData ? (
            <ForecastTable
              mode={chartMode}
              inflation={inflationResp}
              forecastData={displayForecastData}
              unit={indicator?.unit || '%'}
              dateFormat={
                indicator?.frequency === 'quarterly' ? 'quarterly'
                : indicator?.frequency === 'annual' ? 'annual'
                : 'full'
              }
            />
          ) : forecastEnabled && !showForecast ? (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-4 opacity-20" />
              <p className="text-xs font-mono uppercase tracking-widest text-center">Включите переключатель «Прогноз», чтобы показать таблицу прогноза</p>
            </div>
          ) : (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-1 opacity-20" />
              <p className="text-sm font-medium text-text-secondary text-center max-w-md">
                Прогноз для этого показателя не рассчитан или недоступен
              </p>
              <p className="text-xs text-center max-w-lg leading-relaxed text-text-tertiary">
                Для ступенчатых рядов (ключевая ставка) и показателей без модели прогноз может отсутствовать — это ожидаемо.
              </p>
            </div>
          )}
        </section>
      </div>

      <section>
        <DataTable
          key={`${indicator?.code}-${chartMode}`}
          data={
            chartMode === 'inflation' ? (inflationResp?.actuals || [])
            : chartMode === 'quarterly' ? quarterlyDataPoints
            : chartMode === 'annual' ? annualDataPoints
            : chartMode === 'weekly' ? weeklyDataPoints
            : dataPoints
          }
          title={
            chartMode === 'inflation'
              ? 'Исторические данные — Инфляция 12 мес.'
              : chartMode === 'quarterly'
                ? 'Исторические данные — Квартальная инфляция'
                : chartMode === 'annual'
                  ? 'Исторические данные — Годовая инфляция'
                  : chartMode === 'weekly'
                    ? 'Исторические данные — Недельный ИПЦ'
                    : (isPriceCategory ? 'Исторические данные — ИПЦ' : `Исторические данные — ${indicator?.name || 'ряд'}`)
          }
          dateFormat={
            chartMode === 'quarterly' ? 'quarterly'
            : chartMode === 'annual' ? 'annual'
            : chartMode !== 'inflation' && indicator?.frequency === 'daily' ? 'day'
            : indicator?.frequency === 'quarterly' ? 'quarterly'
            : indicator?.frequency === 'annual' ? 'annual'
            : 'full'
          }
          unit={indicator?.unit || '%'}
        />
      </section>
    </div>
  );
}
