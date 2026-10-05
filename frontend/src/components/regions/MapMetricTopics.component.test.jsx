import { describe, it, expect, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderPage } from '../../test/renderPage';
import MapMetricTopics from './MapMetricTopics';

const INDICATORS = [
  { code: 'inc-1', name: 'Доходы населения', section: 'Доходы' },
  { code: 'inc-2', name: 'Доходы бюджета', section: 'Доходы' },
  { code: 'pop-1', name: 'Численность населения', section: 'Население' },
];

describe('MapMetricTopics', () => {
  it('шторка «Все показатели по темам» живёт в body, а не внутри панели страницы', () => {
    const onPick = vi.fn();
    const { container } = renderPage(
      <div className="fe-glass" data-testid="panel">
        <MapMetricTopics indicators={INDICATORS} sections={[]} activeCode={null} onPick={onPick} />
      </div>,
    );
    expect(document.querySelector('.fe-sheet')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /по темам/i }));
    const sheet = document.querySelector('.fe-sheet');
    expect(sheet).toBeTruthy();
    // fixed-слой не должен оказаться внутри предка с backdrop-filter: он вынесен порталом.
    expect(container.contains(sheet)).toBe(false);
    expect(sheet.parentElement).toBe(document.body);
    expect(screen.getByRole('dialog')).toBeTruthy();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.querySelector('.fe-sheet')).toBeNull();
  });
});
