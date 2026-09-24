import MobileNavSelect from './MobileNavSelect';

/** Two-level navigation shared only by US country and state catalogs. */
export default function UsCatalogNav({
  topics, activeTopic, activeSection, onTopic, onSection,
  sectionKey, sectionLabel, themesLabel, detailLabel,
}) {
  if (!topics.length) return null;
  const selected = topics.find((topic) => topic.id === activeTopic) || topics[0];
  const sectionOptions = selected.sections.map((section) => ({
    value: String(sectionKey(section)),
    label: sectionLabel(section),
    count: section.indicators.length,
  }));

  return (
    <>
      <div className="lg:hidden">
        <MobileNavSelect
          label={themesLabel}
          value={selected.id}
          onChange={onTopic}
          options={topics.map((topic) => ({ value: topic.id, label: topic.label, count: topic.count }))}
        />
        <MobileNavSelect
          label={detailLabel}
          value={String(activeSection)}
          onChange={onSection}
          options={sectionOptions}
        />
      </div>
      <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
        <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
          {themesLabel}
        </div>
        <div className="flex flex-col gap-1">
          {topics.map((topic) => (
            <button
              key={topic.id}
              type="button"
              onClick={() => onTopic(topic.id)}
              aria-current={selected.id === topic.id ? 'true' : undefined}
              className={[
                'flex items-center justify-between gap-3 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                selected.id === topic.id
                  ? 'bg-champagne/12 font-medium text-champagne'
                  : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              ].join(' ')}
            >
              <span className="min-w-0 flex-1">{topic.label}</span>
              <span className="shrink-0 font-mono text-[10px] opacity-60">{topic.count}</span>
            </button>
          ))}
        </div>
        <div className="mb-2 mt-5 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
          {detailLabel}
        </div>
        <div className="flex flex-col gap-1">
          {selected.sections.map((section) => (
            <button
              key={String(sectionKey(section))}
              type="button"
              onClick={() => onSection(String(sectionKey(section)))}
              aria-current={String(activeSection) === String(sectionKey(section)) ? 'true' : undefined}
              className={[
                'flex items-start justify-between gap-2 rounded-xl px-3.5 py-2 text-left text-xs transition-colors',
                String(activeSection) === String(sectionKey(section))
                  ? 'bg-champagne/10 font-medium text-champagne'
                  : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              ].join(' ')}
            >
              <span className="min-w-0 flex-1">{sectionLabel(section)}</span>
              <span className="shrink-0 font-mono text-[10px] opacity-60">{section.indicators.length}</span>
            </button>
          ))}
        </div>
      </aside>
    </>
  );
}
