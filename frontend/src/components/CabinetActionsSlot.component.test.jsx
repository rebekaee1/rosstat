import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderToString } from 'react-dom/server';
import { renderPage } from '../test/renderPage';
import CabinetActionsSlot from './CabinetActionsSlot';
import { CabinetActionsContext } from '../lib/cabinetActionsContext';
import { russiaIndicatorSubject } from '../lib/cabinetSubjects';

const subject = russiaIndicatorSubject('cpi', 'Инфляция');

describe('CabinetActionsSlot (круг 11, F)', () => {
  it('без кнопок кабинета слот пуст и ничего не занимает', () => {
    renderPage(<CabinetActionsSlot subject={subject} />);
    expect(screen.queryByTestId('cabinet-actions')).toBeNull();
  });

  it('проп renderActions рисует кнопки и получает предмет страницы', () => {
    const seen = [];
    renderPage(
      <CabinetActionsSlot
        subject={subject}
        renderActions={(s) => { seen.push(s); return <button type="button">В избранное</button>; }}
      />,
    );
    expect(screen.getByRole('button', { name: 'В избранное' })).toBeTruthy();
    expect(seen[0].kind).toBe('indicator');
    expect(seen[0].watch.subjectKey).toBe('cpi');
  });

  it('контекст работает так же; пустой предмет кнопок не даёт', () => {
    renderPage(
      <CabinetActionsContext.Provider value={() => <span>кнопки</span>}>
        <CabinetActionsSlot subject={subject} />
        <CabinetActionsSlot subject={null} />
      </CabinetActionsContext.Provider>,
    );
    expect(screen.getAllByText('кнопки')).toHaveLength(1);
  });

  it('при серверной отрисовке слот пуст, чтобы разметка и первый кадр в браузере совпали', () => {
    const html = renderToString(
      <CabinetActionsContext.Provider value={() => <span>кнопки</span>}>
        <CabinetActionsSlot subject={subject} />
      </CabinetActionsContext.Provider>,
    );
    expect(html).toBe('');
  });
});
