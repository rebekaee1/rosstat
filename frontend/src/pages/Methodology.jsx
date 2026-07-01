import { Link } from 'react-router-dom';
import {
  Database, LineChart, GitBranch, ShieldCheck, RefreshCw, AlertTriangle,
  Sigma, Layers, Ban, Eye,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';

const CARD = 'rounded-2xl bg-surface border border-border-subtle p-5 md:p-6';
const H2 = 'font-display text-2xl md:text-3xl font-bold text-text-primary mb-4 leading-tight';
const P = 'text-text-secondary leading-relaxed';

function Step({ n, title, children }) {
  return (
    <li className="relative pl-14 pb-8 last:pb-0">
      <span className="absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-champagne/10 border border-champagne/30 text-champagne font-display font-bold">
        {n}
      </span>
      <h3 className="text-base font-semibold text-text-primary mb-2">{title}</h3>
      <p className={`${P} text-[15px]`}>{children}</p>
    </li>
  );
}

function MethodRow({ family, series, model }) {
  return (
    <tr className="border-t border-border-subtle align-top">
      <td className="py-4 pr-4 font-semibold text-text-primary whitespace-nowrap">{family}</td>
      <td className="py-4 pr-4 text-text-secondary text-[14px]">{series}</td>
      <td className="py-4 text-text-secondary text-[14px]">{model}</td>
    </tr>
  );
}

export default function Methodology() {
  useDocumentMeta({
    title: 'Методология прогнозирования — Forecast Economy',
    description:
      'Как рассчитываются прогнозы экономических показателей России: подготовка ряда, диагностика, статистические модели, доверительные интервалы, обновление и ограничения. Прозрачная методология на официальных данных Росстата, Банка России и Минфина.',
    path: '/methodology',
  });

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
        Методология
      </p>
      <h1 className="font-display text-3xl md:text-5xl font-bold text-text-primary mb-6 leading-[1.1]">
        Как мы рассчитываем прогнозы
      </h1>
      <p className="text-lg text-text-secondary leading-relaxed mb-4">
        Каждый прогноз на Forecast Economy строится статистической моделью, обученной на
        официальном историческом ряде показателя. Мы не подгоняем результат под ожидания и не
        добавляем экспертных допущений: прогнозное значение определяют исходные данные и
        алгоритм, описанный на этой странице.
      </p>
      <p className={`${P} mb-4`}>
        Ниже разобран весь путь расчёта — от подготовки исходного ряда до доверительного
        интервала вокруг прогнозной линии. Отдельно перечислены показатели, которые мы
        сознательно не прогнозируем, и объяснено почему.
      </p>
      <p className={`${P} mb-12`}>
        Методология подчинена одному требованию: любое прогнозное значение должно
        воспроизводиться из опубликованных данных по описанной процедуре. Именно это отличает
        статистический расчёт от экспертного суждения и позволяет проверить результат
        независимо.
      </p>

      {/* Принципы */}
      <section className="mb-16">
        <h2 className={H2}>Принципы</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className={CARD}>
            <Database className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">Только официальные данные</h3>
            <p className={`${P} text-[14px]`}>
              Источником служат публикации Росстата, Банка России и Минфина. Новостные сводки и
              данные агрегаторов мы не используем. Первоисточник указан на карточке каждого
              показателя, и его можно сверить напрямую.
            </p>
          </div>
          <div className={CARD}>
            <Sigma className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">Воспроизводимость</h3>
            <p className={`${P} text-[14px]`}>
              Прогноз получается из истории ряда по фиксированному алгоритму. При одних и тех же
              данных результат всегда одинаков и не зависит от того, кто и когда запустил расчёт.
            </p>
          </div>
          <div className={CARD}>
            <ShieldCheck className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">Оценка неопределённости</h3>
            <p className={`${P} text-[14px]`}>
              Помимо центрального значения мы приводим диапазон, в котором показатель окажется с
              высокой вероятностью. С удлинением горизонта диапазон закономерно расширяется, и
              это видно прямо на графике.
            </p>
          </div>
          <div className={CARD}>
            <Ban className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">Границы применимости</h3>
            <p className={`${P} text-[14px]`}>
              Там, где статистический прогноз недостоверен по своей природе — биржевые
              котировки, валютные курсы внутри дня, ежедневные цены, — мы его не публикуем и
              указываем причину.
            </p>
          </div>
        </div>
      </section>

      {/* Этапы расчёта */}
      <section className="mb-16">
        <h2 className={H2}>Этапы расчёта</h2>
        <p className={`${P} mb-8`}>
          Каждый показатель проходит одну и ту же последовательность — от подготовки ряда до
          восстановления будущих значений и оценки их точности.
        </p>
        <ol className="relative">
          <Step n="1" title="Подготовка и сверка ряда">
            Исторические значения сверяются с публикацией источника и приводятся к единому
            формату. Разрывы, вызванные сменой методологии счёта, учитываются отдельно. Ряд
            рассматривается на своей естественной частоте — месячной, квартальной или годовой.
          </Step>
          <Step n="2" title="Диагностика ряда">
            Перед выбором модели ряд исследуется на наличие тренда, сезонности и устойчивости
            колебаний во времени. Стационарность проверяется расширенным тестом Дики — Фуллера;
            от его результата зависит форма, в которой ряд лучше поддаётся прогнозу.
          </Step>
          <Step n="3" title="Выбор преобразования">
            Ряд прогнозируется в той форме, где его поведение наиболее устойчиво: в исходных
            уровнях, в приростах или в логарифмических приростах. Для показателей, способных
            менять знак — сальдо, счета, дефицит бюджета, — применяется преобразование,
            корректное вблизи нуля, где логарифм не определён.
          </Step>
          <Step n="4" title="Обучение модели">
            На подготовленном ряде оценивается статистическая модель. Её основу составляет
            регрессия по прошлым значениям с несколькими окнами обучения; ряды с выраженной
            сезонностью описываются моделями семейства ARIMA и SARIMA. Незначимые и
            взаимозависимые факторы исключаются, чтобы модель отражала устойчивую зависимость, а
            не случайные особенности отдельной выборки.
          </Step>
          <Step n="5" title="Взвешивание и возврат в единицы показателя">
            Оценки, полученные на разных окнах обучения, объединяются с весами, обратными их
            разбросу: чем стабильнее окно, тем выше его вклад. После этого прогноз переводится
            обратно в исходные единицы — рубли, проценты или пункты индекса.
          </Step>
          <Step n="6" title="Доверительный интервал">
            Вокруг центральной оценки строится диапазон неопределённости, опирающийся на
            историческую точность модели. Он расширяется по мере удаления в будущее и показывает,
            где прогноз надёжен, а где к нему следует относиться с осторожностью.
          </Step>
        </ol>
      </section>

      {/* Модель под тип показателя */}
      <section className="mb-16">
        <h2 className={H2}>Модель под тип показателя</h2>
        <p className={`${P} mb-6`}>
          Единой модели на все случаи не существует. Семейство модели подбирается под природу
          показателя — его частоту, сезонность и возможность отрицательных значений.
        </p>
        <div className={`${CARD} overflow-x-auto`}>
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
                <th className="pb-3 pr-4">Тип ряда</th>
                <th className="pb-3 pr-4">Примеры</th>
                <th className="pb-3">Подход</th>
              </tr>
            </thead>
            <tbody>
              <MethodRow
                family="Месячные"
                series="Зарплаты, рынок труда, денежная масса, ставки, бюджет, внешняя торговля"
                model="Универсальная авторегрессионная модель. Форма ряда и набор значимых лагов подбираются автоматически, обучение идёт по нескольким окнам с исключением избыточных факторов."
              />
              <MethodRow
                family="Квартальные положительные"
                series="ВВП и его компоненты, экспорт и импорт, внешний долг, инвестиции"
                model="Модель на логарифмических приростах: она учитывает мультипликативный характер роста и сезонность внутри года."
              />
              <MethodRow
                family="Квартальные со сменой знака"
                series="Счёт текущих операций, сальдо потоков"
                model="Модель на приростах уровня: она корректна при переходе показателя через ноль, где логарифмические преобразования неприменимы."
              />
              <MethodRow
                family="Инфляция (ИПЦ)"
                series="Индекс потребительских цен и его состав"
                model="Комбинированная модель, учитывающая сезонность цен и накопление индекса от месяца к месяцу."
              />
              <MethodRow
                family="Производные ряды"
                series="Годовые итоги, изменение к прошлому году, изменение к предыдущему периоду"
                model="Отдельно не прогнозируются. Их значения выводятся из прогноза базового ряда тем же преобразованием, поэтому прогноз остаётся согласованным во всех режимах отображения."
              />
            </tbody>
          </table>
        </div>
        <div className="mt-5 flex gap-3 items-start rounded-2xl bg-champagne/5 border border-champagne/20 p-4">
          <Layers className="w-5 h-5 text-champagne shrink-0 mt-0.5" />
          <p className="text-[14px] text-text-secondary leading-relaxed">
            Когда вы меняете режим графика — уровень, изменение к прошлому году или к предыдущему
            периоду, годовой итог, — прогноз пересчитывается из одной базовой оценки. Поэтому
            значения в разных режимах не противоречат друг другу.
          </p>
        </div>
      </section>

      {/* Обновление */}
      <section className="mb-16">
        <h2 className={H2}>Обновление прогноза</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className={CARD}>
            <RefreshCw className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">Модель следует за данными</h3>
            <p className={`${P} text-[14px]`}>
              Как только источник публикует новое наблюдение, ряд дополняется, а модель
              переоценивается на расширенной истории. Прогнозная линия сдвигается вперёд без
              ручного вмешательства.
            </p>
          </div>
          <div className={CARD}>
            <GitBranch className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">Пересчёт производных рядов</h3>
            <p className={`${P} text-[14px]`}>
              Обновление базового ряда автоматически запускает пересчёт всех зависящих от него
              показателей — годовых итогов и относительных изменений.
            </p>
          </div>
        </div>
      </section>

      {/* Что не прогнозируем */}
      <section className="mb-16">
        <h2 className={H2}>Что мы не прогнозируем</h2>
        <p className={`${P} mb-6`}>
          Для части показателей мы намеренно не публикуем прогноз. Статистическая экстраполяция
          опирается на инерцию ряда, а на коротких и рыночных данных динамику определяют текущие
          новости и настроение участников, поэтому прошлое почти не помогает предсказать будущее.
        </p>
        <ul className="space-y-3">
          {[
            ['Биржевые котировки и индексы', 'Курсы валют, акции и биржевые товары реагируют на новости мгновенно; вчерашняя динамика почти ничего не говорит о завтрашней.'],
            ['Криптовалюты', 'Высокая волатильность и спекулятивная природа рынка делают статистическую оценку ненадёжной.'],
            ['Ежедневные и внутринедельные ряды', 'На горизонте нескольких дней преобладает шум; содержательный прогноз становится возможен начиная с месячной частоты.'],
          ].map(([t, d]) => (
            <li key={t} className="flex gap-3 items-start rounded-2xl bg-surface border border-border-subtle p-4">
              <Ban className="w-5 h-5 text-text-tertiary shrink-0 mt-0.5" />
              <span className="text-[14px] text-text-secondary leading-relaxed">
                <strong className="text-text-primary">{t}.</strong> {d}
              </span>
            </li>
          ))}
        </ul>
        <p className={`${P} mt-6 text-[14px]`}>
          Для таких показателей мы приводим полную историю без прогнозной линии, а переключатель
          прогноза на карточке остаётся неактивным.
        </p>
      </section>

      {/* Как читать */}
      <section className="mb-16">
        <h2 className={H2}>Как читать прогноз на графике</h2>
        <div className="flex gap-3 items-start rounded-2xl bg-surface border border-border-subtle p-5 mb-4">
          <Eye className="w-5 h-5 text-champagne shrink-0 mt-0.5" />
          <div className="text-[14px] text-text-secondary leading-relaxed space-y-2">
            <p>
              Сплошная линия — фактические данные источника. Пунктирная линия — прогноз.
              Полупрозрачная полоса вокруг пунктира — доверительный интервал, то есть наиболее
              вероятный диапазон будущих значений.
            </p>
            <p>
              Те же прогнозные значения продублированы в таблице под графиком вместе с границами
              интервала. Их можно выгрузить и использовать в собственных расчётах.
            </p>
          </div>
        </div>
      </section>

      {/* Ограничения / дисклеймер */}
      <section className="mb-12">
        <h2 className={H2}>Ограничения и ответственность</h2>
        <div className="flex gap-3 items-start rounded-2xl bg-surface border border-border-subtle p-5">
          <AlertTriangle className="w-5 h-5 text-champagne shrink-0 mt-0.5" />
          <div className="text-[15px] text-text-secondary leading-relaxed space-y-3">
            <p>
              Прогноз опирается на устойчивые закономерности прошлого и может расходиться с
              фактом при экономических шоках, изменении денежно-кредитной или бюджетной политики,
              а также при пересмотре исторических данных самим источником. Чем дальше горизонт,
              тем выше неопределённость оценки.
            </p>
            <p>
              Все материалы носят информационный характер и не являются индивидуальной
              инвестиционной рекомендацией, финансовой или юридической консультацией.
            </p>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-champagne text-obsidian font-semibold text-sm hover:bg-champagne/90 transition-colors"
        >
          <LineChart className="w-4 h-4" />
          Смотреть индикаторы
        </Link>
        <Link
          to="/about"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-border-subtle text-text-secondary font-semibold text-sm hover:text-text-primary hover:border-champagne/40 transition-colors"
        >
          О проекте
        </Link>
      </div>
    </div>
  );
}
