// K2 «Бренд»: грань, медаль, световой шов, эмблема, пустые состояния, флаг-капля, векторные флаги.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import FacetMark, { FacetMedal } from './FacetMark';
import LightSeam from './LightSeam';
import Emblem from './Emblem';
import EmptyState from './EmptyState';
import FacetCoin from './FacetCoin';
import { FACET_COIN_TONES } from './brandTones';
import CountryFlag from '../CountryFlag';
import { FLAG_ART_CODES, flagArt } from './flagArt';
import Brand from '../Brand';
import { renderPage } from '../../test/renderPage';

describe('FacetMark', () => {
  it('рисует ромб заданной ширины; tall — пропорция 1:2,1; декоративен', () => {
    const { container } = render(<><FacetMark size={14} /><FacetMark size={10} tall /></>);
    const [a, b] = container.querySelectorAll('svg.fe-facet');
    expect(a.getAttribute('width')).toBe('14');
    expect(a.getAttribute('height')).toBe('14');
    expect(a.getAttribute('aria-hidden')).toBe('true');
    expect(b.getAttribute('height')).toBe('21');
    // четыре грани: основа и четыре наложения света и тени
    expect(a.querySelectorAll('polygon').length).toBe(5);
  });

  it('у каждого экземпляра свой id градиента (несколько граней на странице не путаются)', () => {
    const { container } = render(<><FacetMark /><FacetMark /></>);
    const ids = [...container.querySelectorAll('linearGradient')].map((g) => g.id);
    expect(new Set(ids).size).toBe(2);
  });

  it('пульс «обновлено» — класс, анимируется только opacity', () => {
    const { container } = render(<FacetMark size={6} pulse />);
    expect(container.querySelector('svg').getAttribute('class')).toContain('fe-facet--pulse');
  });

  it('место в рейтинге: цифра в графитовом круге, без гранёной медали (круг 6)', () => {
    const { container } = render(<><FacetMedal rank={1} /><FacetMedal rank={2} /><FacetMedal rank={3} /></>);
    const medals = [...container.querySelectorAll('.fe-medal')];
    expect(medals.map((m) => m.textContent)).toEqual(['1', '2', '3']);
    expect(medals[0].querySelector('svg')).toBeNull();
    expect(medals[0].getAttribute('data-rank')).toBe('1');
  });
});

describe('LightSeam', () => {
  it('луч: декоративный блок с гранью 10 px по центру', () => {
    const { container } = render(<LightSeam />);
    const seam = container.querySelector('.fe-seam');
    expect(seam.getAttribute('aria-hidden')).toBe('true');
    expect(seam.querySelector('svg.fe-facet').getAttribute('width')).toBe('10');
  });

  it('грань-стрела 56×10 для заголовка секции', () => {
    const { container } = render(<LightSeam variant="arrow" />);
    const arrow = container.querySelector('svg.fe-facet-arrow');
    expect(arrow.getAttribute('width')).toBe('56');
    expect(arrow.getAttribute('height')).toBe('10');
  });
});

describe('FacetCoin', () => {
  it('простой круг с иконкой (круг 6): без граней-камня, тон принимается и игнорируется', () => {
    expect(FACET_COIN_TONES).toHaveLength(6);
    const { container } = render(<><FacetCoin tone={0}><i data-testid="a" /></FacetCoin><FacetCoin tone={7} size={48} /></>);
    const coins = container.querySelectorAll('.fe-coin');
    expect(coins[0].querySelector('.fe-coin__icon [data-testid="a"]')).toBeTruthy();
    expect(coins[0].querySelector('.fe-coin__icon').getAttribute('aria-hidden')).toBe('true');
    expect(coins[0].querySelector('svg')).toBeNull();
    expect(coins[1].style.getPropertyValue('--fe-coin-size')).toBe('48px');
  });
});

describe('Emblem', () => {
  it('картинка с размерами, пустым alt и ленивой загрузкой; vector и photo — разные файлы', () => {
    const { container } = render(<><Emblem size={64} /><Emblem size={64} variant="photo" spin eager /></>);
    const [vec, photo] = container.querySelectorAll('img');
    expect(vec.getAttribute('src')).toBe('/brand/emblem-f.svg');
    expect(vec.getAttribute('alt')).toBe('');
    expect(vec.getAttribute('width')).toBe('64');
    expect(vec.getAttribute('loading')).toBe('lazy');
    expect(photo.getAttribute('src')).toBe('/brand/emblem-f-phone.webp');
    // Стеклянная F не квадратная (856x1000): size это высота, ширина считается по пропорции кадра.
    expect(photo.getAttribute('height')).toBe('64');
    expect(photo.getAttribute('width')).toBe('55');
    expect(photo.getAttribute('loading')).toBe('eager');
    expect(photo.closest('.fe-emblem').className).toContain('fe-emblem--spin');
  });
});

describe('EmptyState', () => {
  it('стандартные фразы по-русски и по-английски; ошибка — alert, ожидание — status', () => {
    const { unmount } = renderPage(<><EmptyState variant="no-results" /><EmptyState variant="error" /><EmptyState variant="waiting" /></>);
    expect(screen.getByText('Ничего не нашли')).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('Не удалось загрузить');
    expect(screen.getByRole('status').textContent).toContain('Загружаем данные');
    unmount();
    renderPage(<EmptyState />, { locale: 'en' });
    expect(screen.getByText('No data yet')).toBeTruthy();
  });

  it('своя фраза, подсказка и действие; осколок ограничен 80–120 px', () => {
    const { container } = renderPage(<EmptyState title="Свой текст" hint="Подсказка" action={<button type="button">Повторить</button>} size={400} />);
    expect(screen.getByText('Свой текст')).toBeTruthy();
    expect(screen.getByText('Подсказка')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy();
    expect(container.querySelector('svg.fe-empty__shard').getAttribute('width')).toBe('120');
  });
});

describe('CountryFlag', () => {
  it('по умолчанию — прежний эмодзи; без кода ничего не рисуется', () => {
    const { container } = render(<><CountryFlag code="DE" /><CountryFlag code="" /></>);
    const flags = container.querySelectorAll('.fe-flag');
    expect(flags.length).toBe(1);
    expect(flags[0].textContent).toBe('\u{1F1E9}\u{1F1EA}');
  });

  it('glass: векторный флаг в капле без текста-эмодзи, цвет свечения и размер', () => {
    const { container } = render(<CountryFlag code="DE" glass size={44} />);
    const flag = container.querySelector('.fe-flag--glass');
    expect(flag.getAttribute('aria-hidden')).toBe('true');
    expect(flag.querySelector('.fe-flag__drop svg.fe-flag__art rect')).toBeTruthy();
    expect(flag.textContent).toBe('');
    expect(flag.style.getPropertyValue('--fe-flag-size')).toBe('44px');
    expect(flag.style.getPropertyValue('--fe-flag-glow')).toBe('#DD0000');
  });

  it('glass: размер зажат в 36–44 px; для кода без рисунка остаётся эмодзи', () => {
    const { container } = render(<><CountryFlag code="DE" glass size={80} /><CountryFlag code="LK" glass /></>);
    const [de, lk] = container.querySelectorAll('.fe-flag--glass');
    expect(de.style.getPropertyValue('--fe-flag-size')).toBe('44px');
    expect(lk.querySelector('svg')).toBeNull();
    expect(lk.textContent).toBe('\u{1F1F1}\u{1F1F0}');
  });
});

describe('flagArt', () => {
  it('каждый рисунок — корректный XML внутри svg', () => {
    for (const code of FLAG_ART_CODES) {
      const { svg, glow } = flagArt(code);
      const doc = new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`, 'image/svg+xml');
      expect(doc.querySelector('parsererror'), code).toBeNull();
      expect(doc.documentElement.children.length, code).toBeGreaterThan(0);
      expect(glow, code).toMatch(/^#[0-9A-F]{6}$/i);
    }
  });

  it('покрыты крупные страны каталога и работают коды UK и EL', () => {
    for (const code of ['RU', 'US', 'CN', 'DE', 'JP', 'GB', 'FR', 'IN', 'BR', 'TR', 'KZ', 'BY', 'UA', 'PL', 'AU', 'CA', 'KR', 'SA', 'ZA', 'MX']) {
      expect(flagArt(code), code).not.toBeNull();
    }
    expect(flagArt('UK').svg).toBe(flagArt('GB').svg);
    expect(flagArt('EL').svg).toBe(flagArt('GR').svg);
    expect(flagArt('de').svg).toBe(flagArt('DE').svg);
    expect(flagArt('')).toBeNull();
    expect(flagArt('LK')).toBeNull();
  });

  it('у каждой страны из карты slug-ов подбора стран есть векторный флаг (кроме явно не нарисованных)', async () => {
    const { SLUG_ISO, isoForSlug } = await import('../../lib/slugFlags');
    const missing = Object.entries(SLUG_ISO).filter(([, iso]) => !flagArt(iso)).map(([slug]) => slug);
    expect(missing).toEqual([]);
    expect(isoForSlug('germany')).toBe('DE');
    expect(isoForSlug('nowhere')).toBe('');
  });
});

describe('Brand (логотип-кристалл)', () => {
  it('знак объёмный: градиент, световая грань, гранёный камень и блик; надпись и размеры прежние', () => {
    const { container } = render(<Brand compact />);
    const svg = container.querySelector('svg');
    expect(svg.getAttribute('viewBox')).toBe('0 0 40 44');
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.querySelector('.fe-brand-vol')).toBeTruthy();
    expect(svg.querySelectorAll('.fe-brand-top').length).toBe(2);
    expect(svg.querySelector('.fe-brand-glint')).toBeTruthy();
    expect(container.querySelector('.fe-brand-wordmark').textContent).toBe('forecasteconomyECONOMIC INTELLIGENCE');
    expect(container.querySelector('.fe-brand').className).toContain('fe-brand-compact');
  });

  it('у двух логотипов на странице (шапка и подвал) разные id градиентов', () => {
    const { container } = render(<><Brand /><Brand /></>);
    const ids = [...container.querySelectorAll('linearGradient')].map((g) => g.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
