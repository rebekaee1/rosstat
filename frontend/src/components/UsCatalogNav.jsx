import { ChevronDown } from 'lucide-react';
import MobileNavSelect from './MobileNavSelect';
import { compactCount, indicatorsCountText } from '../lib/countryKeyFigures';
import { useLocale, useT } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/z5-country.css';

/** Two-level navigation shared only by US country and state catalogs. */
export default function UsCatalogNav({
  topics, activeTopic, activeSection, onTopic, onSection,
  sectionKey, sectionLabel, themesLabel, detailLabel,
}) {
  const { locale } = useLocale();
  const t = useT();
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
      <aside className="z5-topics hidden min-w-0 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
        <h3 className="z5-aside-title">{themesLabel}</h3>
        <div className="z5-topics__list">
          {topics.map((topic) => (
            <button
              key={topic.id}
              type="button"
              onClick={() => onTopic(topic.id)}
              aria-current={selected.id === topic.id ? 'true' : undefined}
              className={[
                'fe-tap fe-press z5-topic z5-topic--row',
                selected.id === topic.id ? 'is-active' : '',
              ].join(' ')}
            >
              <span className="z5-topic__name"><span className="min-w-0">{topic.label}</span></span>
              <span className="z5-topic__count" title={indicatorsCountText(topic.count, locale, t)}>{compactCount(topic.count, locale)}</span>
            </button>
          ))}
        </div>
        <details className="z5-more" open>
          <summary className="z5-more__summary">
            <span>{detailLabel}</span>
            <ChevronDown size={15} aria-hidden="true" className="z5-more__chevron" />
          </summary>
          <div className="z5-more__chips">
            {selected.sections.map((section) => {
              const key = String(sectionKey(section));
              const current = String(activeSection) === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => onSection(key)}
                  aria-current={current ? 'true' : undefined}
                  className={`fe-tap fe-press z5-topic z5-topic--chip${current ? ' is-active' : ''}`}
                >
                  <span className="z5-topic__name"><span className="min-w-0">{sectionLabel(section)}</span></span>
                  <span className="z5-topic__count" title={indicatorsCountText(section.indicators.length, locale, t)}>{compactCount(section.indicators.length, locale)}</span>
                </button>
              );
            })}
          </div>
        </details>
      </aside>
    </>
  );
}
