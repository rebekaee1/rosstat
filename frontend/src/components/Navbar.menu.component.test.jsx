import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
import { renderPage, mockApiGet } from '../test/renderPage';
import { OPEN_NAV_MENU_EVENT } from '../lib/navItems';

vi.mock('./IndicatorSearch', () => ({
  default: () => <div data-testid="indicator-search-stub" />,
}));

afterEach(() => vi.restoreAllMocks());

function renderNav(locale) {
  mockApiGet([['/auth/me', { user: null }]]);
  return renderPage(<Navbar />, { path: '*', route: '/', locale });
}

describe('Navbar: появление и закрытие панелей', () => {
  it('шапка видна сразу: появление задаётся классом CSS, а не скрытием до старта JS-твина', () => {
    renderNav();
    const nav = screen.getByRole('navigation');
    expect(nav.className).toContain('fe-reveal');
    // начальное состояние не прячет шапку инлайном
    expect(nav.style.opacity).toBe('');
  });

  it('мобильное меню: шторка снизу (диалог в body), закрывается по Esc и возвращает фокус на кнопку', () => {
    renderNav();
    const toggle = screen.getByRole('button', { name: 'Открыть меню' });
    fireEvent.click(toggle);

    const menu = document.getElementById('fe-nav-mobile-menu');
    expect(menu).toBeTruthy();
    // R3: меню телефона стало шторкой снизу (components/BottomSheet.jsx), рисуется порталом в body и держит роль диалога.
    expect(menu.className).toContain('fe-bsheet');
    expect(menu.getAttribute('role')).toBe('dialog');
    expect(menu.getAttribute('aria-modal')).toBe('true');
    expect(menu.parentElement).toBe(document.body);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(toggle.getAttribute('aria-controls')).toBe('fe-nav-mobile-menu');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Открыть меню' }));
  });

  it('мобильное меню: «Войти» и «Регистрация» закреплены внизу вне прокручиваемого списка и выровнены одинаково', async () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const scroll = menu.querySelector('.fe-mnav-scroll');
    const foot = menu.querySelector('.fe-mnav-foot');
    expect(scroll).toBeTruthy();
    expect(foot).toBeTruthy();
    await waitFor(() => expect(foot.querySelectorAll('a').length).toBe(2));
    const login = [...foot.querySelectorAll('a')].find((a) => a.getAttribute('href') === '/login');
    const register = [...foot.querySelectorAll('a')].find((a) => a.getAttribute('href')?.startsWith('/register'));
    expect(login).toBeTruthy();
    expect(register).toBeTruthy();
    // Кнопки не внутри прокручиваемой части — видны сразу.
    expect(scroll.contains(login)).toBe(false);
    expect(scroll.contains(register)).toBe(false);
    // Текст у обеих по центру: раньше «Войти» прижималось влево из-за display:flex.
    expect(login.className).toContain('justify-center');
    expect(register.className).toContain('justify-center');
  });

  it('мобильное меню: у трёх калькуляторов разные значки, а «Валюты» есть в основном разделе', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const calcLinks = ['Калькулятор инфляции', 'Ипотечный калькулятор', 'Сложные проценты']
      .map((name) => [...menu.querySelectorAll('a')].find((a) => a.textContent.trim() === name));
    expect(calcLinks.every(Boolean)).toBe(true);
    const icons = calcLinks.map((a) => a.querySelector('svg').getAttribute('class'));
    expect(new Set(icons).size).toBe(3);
    expect([...menu.querySelectorAll('a')].some((a) => a.getAttribute('href') === '/currencies')).toBe(true);
  });

  it('выпадашка инструментов: конвертер и калькулятор инфляции первыми, затем ипотека, проценты и виджеты; у каждого золотой значок и пометка', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    const menu = screen.getByRole('menu');
    const hrefs = [...menu.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/currencies', '/calculator', '/calculator/mortgage', '/calculator/compound', '/widgets']);
    const names = [...menu.querySelectorAll('.fe-nav-tool__name')].map((n) => n.textContent);
    expect(names.slice(0, 2)).toEqual(['Конвертер валют', 'Калькулятор инфляции']);
    expect(menu.querySelectorAll('.fe-tool-ico svg')).toHaveLength(5);
    expect(menu.className).toContain('fe-nav-panel');
    expect(menu.textContent).toContain('Россия и страны мира');
    expect(menu.textContent).toContain('Для рублёвых кредитов');
    expect(menu.textContent).toContain('Для любой валюты');
    expect(menu.textContent).toContain('Встроить график на сайт');
  });

  it('мобильное меню: «Виджеты» лежат в группе «Инструменты» вместе с калькуляторами', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const widgets = [...menu.querySelectorAll('a')].find((a) => a.getAttribute('href') === '/widgets');
    expect(widgets).toBeTruthy();
    expect(widgets.textContent.trim()).toBe('Виджеты');
    expect(widgets.closest('.fe-mnav-group').textContent).toContain('Инструменты');
  });

  it('мобильное меню закрывается тапом вне панели, но не тапом внутри неё', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');

    fireEvent.mouseDown(menu);
    expect(document.getElementById('fe-nav-mobile-menu')).toBeTruthy();

    fireEvent.mouseDown(document.body);
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
  });

  it('выпадашка инструментов: панель с классом появления, Esc закрывает и возвращает фокус на кнопку', () => {
    renderNav();
    const btn = screen.getByRole('button', { name: /Инструменты/i });
    fireEvent.click(btn);

    const menu = screen.getByRole('menu');
    expect(menu.className).toContain('fe-reveal--panel');
    expect(btn.getAttribute('aria-expanded')).toBe('true');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(btn);
  });

  it('выпадашка инструментов закрывается тапом вне (pointerdown)', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    expect(screen.getByRole('menu')).toBeTruthy();

    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('menu')).toBeNull();
  });
});

function GoTo({ to }) {
  const navigate = useNavigate();
  return <button type="button" data-testid="go" onClick={() => navigate(to)}>go</button>;
}

describe('Navbar: меню закрывается при любом переходе и при открытии поиска', () => {
  it('выпадашка инструментов закрывается, когда адрес сменился не через её ссылку (например, «назад»)', () => {
    mockApiGet([['/auth/me', { user: null }]]);
    renderPage(<><Navbar /><GoTo to="/compare" /></>, { path: '*', route: '/' });
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    expect(screen.getByRole('menu')).toBeTruthy();
    fireEvent.click(screen.getByTestId('go'));
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('мобильное меню тоже закрывается при смене адреса', () => {
    mockApiGet([['/auth/me', { user: null }]]);
    renderPage(<><Navbar /><GoTo to="/compare" /></>, { path: '*', route: '/' });
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    expect(document.getElementById('fe-nav-mobile-menu')).toBeTruthy();
    fireEvent.click(screen.getByTestId('go'));
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
  });

  it('когда открывается окно поиска (Ctrl/Cmd+K), открытые панели меню и затемнение уходят', async () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    expect(screen.getByRole('menu')).toBeTruthy();
    expect(document.querySelector('.fe-nav-scrim')).toBeTruthy();
    const dialog = document.createElement('div');
    dialog.setAttribute('data-fe-search-dialog', '');
    await act(async () => { document.body.appendChild(dialog); });
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
    expect(document.querySelector('.fe-nav-scrim')).toBeNull();
    dialog.remove();
  });

  it('затемнение под меню лёгкое: класс стеклянной подложки, а не сплошной чёрный блюр', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Инструменты/i }));
    const scrim = document.querySelector('.fe-nav-scrim');
    expect(scrim.className).not.toMatch(/backdrop-blur-\[2px\]/);
  });
});

describe('Navbar: меню Курсы валют и мега-панель Страны мира', () => {
  it('в шапке есть «Курсы валют» (короткая подпись «Валюты» до 2xl) и ведёт на /currencies', () => {
    renderNav();
    const nav = screen.getByRole('navigation');
    const rates = within(nav).getByRole('link', { name: /Курсы валют/ });
    expect(rates.getAttribute('href')).toBe('/currencies');
    expect(rates.textContent).toContain('Валюты');
    expect(rates.className).toContain('fe-nav-link');
  });

  it('EN: пункт Exchange rates тоже есть, с короткой подписью Rates', () => {
    renderNav('en');
    const nav = screen.getByRole('navigation');
    const rates = within(nav).getByRole('link', { name: /Exchange rates/ });
    expect(rates.getAttribute('href')).toBe('/currencies');
    expect(rates.textContent).toContain('Rates');
  });

  it('фокус на «Страны мира» открывает панель с флагами и рейтингами, Esc закрывает и возвращает фокус', async () => {
    renderNav();
    const nav = screen.getByRole('navigation');
    expect(document.getElementById('fe-nav-mega')).toBeNull();
    const countries = within(nav).getByRole('link', { name: /Страны/ });
    act(() => { countries.focus(); });
    await waitFor(() => expect(document.getElementById('fe-nav-mega')).toBeTruthy());
    const mega = document.getElementById('fe-nav-mega');
    const hrefs = [...mega.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toContain('/united-states');
    expect(hrefs).toContain('/china');
    expect(hrefs).toContain('/world/rating/gdp-usd');
    expect(hrefs).toContain('/world/rating/unemployment-rate');
    expect(hrefs).toContain('/#countries');
    expect(within(mega).getByText('США')).toBeTruthy();
    expect(countries.getAttribute('aria-expanded')).toBe('true');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.getElementById('fe-nav-mega')).toBeNull();
  });

  it('EN: названия стран в панели по-английски', async () => {
    renderNav('en');
    const nav = screen.getByRole('navigation');
    act(() => { within(nav).getByRole('link', { name: /Countries/ }).focus(); });
    await waitFor(() => expect(document.getElementById('fe-nav-mega')).toBeTruthy());
    expect(within(document.getElementById('fe-nav-mega')).getByText('United States')).toBeTruthy();
    expect(within(document.getElementById('fe-nav-mega')).getByText('Germany')).toBeTruthy();
  });

  it('панель стран закрывается при переходе по адресу', async () => {
    mockApiGet([['/auth/me', { user: null }]]);
    renderPage(<><Navbar /><GoTo to="/compare" /></>, { path: '*', route: '/' });
    act(() => { within(screen.getByRole('navigation')).getByRole('link', { name: /Страны/ }).focus(); });
    await waitFor(() => expect(document.getElementById('fe-nav-mega')).toBeTruthy());
    fireEvent.click(screen.getByTestId('go'));
    expect(document.getElementById('fe-nav-mega')).toBeNull();
  });
});

describe('Navbar: круглые кнопки телефона', () => {
  it('поиск, язык и меню одного вида: круг 44 px (класс fe-nav-round)', () => {
    renderNav();
    const toggle = screen.getByRole('button', { name: 'Открыть меню' });
    expect(toggle.className).toContain('fe-nav-round');
    const lang = screen.getAllByRole('button', { name: /Язык/ }).filter((b) => b.className.includes('fe-nav-round'));
    expect(lang).toHaveLength(1);
  });
});

describe('Navbar K3: капсула, сжатие на телефоне, «Ещё» из док-панели', () => {
  async function scrollTo(y) {
    Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
    await act(async () => {
      window.dispatchEvent(new Event('scroll'));
      await new Promise((resolve) => { setTimeout(resolve, 40); });
    });
  }
  afterEach(() => {
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
  });

  it('шапка стеклянная капсула: класс слоя, плотнее после прокрутки, сжимается при движении вниз и возвращается вверх', async () => {
    renderNav();
    const nav = screen.getByRole('navigation');
    expect(nav.className).toContain('fe-navbar--glass');
    expect(nav.className).not.toContain('glass-surface');
    expect(nav.getAttribute('data-scrolled')).toBe('false');
    expect(nav.getAttribute('data-compact')).toBe('false');
    await scrollTo(300);
    expect(nav.getAttribute('data-scrolled')).toBe('true');
    expect(nav.getAttribute('data-compact')).toBe('true');
    await scrollTo(240);
    expect(nav.getAttribute('data-scrolled')).toBe('true');
    expect(nav.getAttribute('data-compact')).toBe('false');
  });

  it('три кружка телефона лежат в одной капсуле', () => {
    renderNav();
    const cluster = document.querySelector('.fe-nav-cluster');
    expect(cluster).toBeTruthy();
    expect(cluster.querySelectorAll('.fe-nav-round')).toHaveLength(2);
    expect(cluster.contains(screen.getByRole('button', { name: 'Открыть меню' }))).toBe(true);
  });

  it('событие «Ещё» из нижней док-панели открывает меню-шторку', () => {
    renderNav();
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
    act(() => { window.dispatchEvent(new CustomEvent(OPEN_NAV_MENU_EVENT)); });
    const menu = document.getElementById('fe-nav-mobile-menu');
    expect(menu).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Закрыть меню' }).getAttribute('aria-expanded')).toBe('true');
  });

  it('у каждого пункта шторки иконка-грань, а «Войти» и «Регистрация» закреплены внизу', async () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
    const menu = document.getElementById('fe-nav-mobile-menu');
    const links = [...menu.querySelectorAll('.fe-mnav-scroll a.fe-mnav-link')];
    expect(links.length).toBeGreaterThan(8);
    expect(links.every((a) => a.querySelector('.fe-mnav-tile svg'))).toBe(true);
    await waitFor(() => expect(menu.querySelectorAll('.fe-mnav-foot a').length).toBe(2));
  });

  it('«Настройки cookie» лежат в меню-шторке и раскрывают настройки (плавающего значка на странице нет)', () => {
    renderNav();
    let opened = 0;
    const onOpen = () => { opened += 1; };
    window.addEventListener('fe:consent:open', onOpen);
    try {
      fireEvent.click(screen.getByRole('button', { name: 'Открыть меню' }));
      const item = screen.getByTestId('menu-cookie-settings');
      expect(item.textContent).toContain('Настройки cookie');
      fireEvent.click(item);
    } finally {
      window.removeEventListener('fe:consent:open', onOpen);
    }
    expect(opened).toBe(1);
    // Меню закрылось, чтобы настройки не оказались под шторкой.
    expect(document.getElementById('fe-nav-mobile-menu')).toBeNull();
  });
});

