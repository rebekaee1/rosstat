// «Как считаем»: короткое объяснение простыми словами в раскрывающемся блоке.
// Формул и обозначений на виду нет — эксперту достаточно раскрыть блок.
import { ChevronDown } from 'lucide-react';
import { useT } from '../i18n';
import '../styles/w5-tools.css';

export default function CalcMethod({ paragraphs, children, dataBlock }) {
  const t = useT();
  return (
    <details data-block={dataBlock} className="w5-method">
      <summary className="w5-method__summary">
        <span>{t('w5.calc.how.title')}</span>
        <ChevronDown className="w5-method__chev" aria-hidden="true" />
      </summary>
      <div className="w5-method__body">
        {paragraphs.map((text) => <p key={text}>{text}</p>)}
        {children}
      </div>
    </details>
  );
}
