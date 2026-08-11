import { useId, useState } from 'react';
import {
  DEFAULT_WORKBENCH_TAB,
  WORKBENCH_TABS,
  resolveWorkbenchTab,
} from '../../lib/homeWorkbench';
import { track, events } from '../../lib/track';
import HomeRussiaPanel from './HomeRussiaPanel';
import HomeRegionsPanel from './HomeRegionsPanel';
import HomeCountriesPanel from './HomeCountriesPanel';

export default function HomeWorkbench({ indicators, indicatorsLoading }) {
  const baseId = useId();
  const [tab, setTab] = useState(DEFAULT_WORKBENCH_TAB);
  const active = resolveWorkbenchTab(tab);

  const selectTab = (id) => {
    const next = resolveWorkbenchTab(id);
    setTab(next);
    track(events.HOME_WORKBENCH_TAB, { tab: next });
  };

  const onKeyDown = (event) => {
    const idx = WORKBENCH_TABS.findIndex((t) => t.id === active);
    if (idx < 0) return;
    let nextIdx = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      nextIdx = (idx + 1) % WORKBENCH_TABS.length;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      nextIdx = (idx - 1 + WORKBENCH_TABS.length) % WORKBENCH_TABS.length;
    } else if (event.key === 'Home') {
      nextIdx = 0;
    } else if (event.key === 'End') {
      nextIdx = WORKBENCH_TABS.length - 1;
    }
    if (nextIdx == null) return;
    event.preventDefault();
    selectTab(WORKBENCH_TABS[nextIdx].id);
    const btn = document.getElementById(`${baseId}-tab-${WORKBENCH_TABS[nextIdx].id}`);
    btn?.focus();
  };

  return (
    <section data-block="home-workbench" className="mb-10 md:mb-12" aria-labelledby={`${baseId}-title`}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
            Рабочий стол
          </div>
          <h2 id={`${baseId}-title`} className="mt-1 text-lg font-semibold text-text-primary">
            Россия · Регионы · Страны
          </h2>
        </div>
      </div>

      <div
        role="tablist"
        aria-label="Плоскости данных"
        onKeyDown={onKeyDown}
        className="mb-4 flex w-full gap-1 rounded-xl border border-border-subtle bg-surface p-1 sm:w-fit"
      >
        {WORKBENCH_TABS.map((t) => {
          const selected = t.id === active;
          return (
            <button
              key={t.id}
              id={`${baseId}-tab-${t.id}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${t.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => selectTab(t.id)}
              className={`flex-1 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors sm:flex-none ${
                selected
                  ? 'bg-champagne/15 text-champagne'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {WORKBENCH_TABS.map((t) => {
        const selected = t.id === active;
        return (
          <div
            key={t.id}
            id={`${baseId}-panel-${t.id}`}
            role="tabpanel"
            aria-labelledby={`${baseId}-tab-${t.id}`}
            hidden={!selected}
          >
            {selected && t.id === 'russia' && (
              <HomeRussiaPanel indicators={indicators} isLoading={indicatorsLoading} />
            )}
            {selected && t.id === 'regions' && <HomeRegionsPanel />}
            {selected && t.id === 'countries' && <HomeCountriesPanel />}
          </div>
        );
      })}
    </section>
  );
}
