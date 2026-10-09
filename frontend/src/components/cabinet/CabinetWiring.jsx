// Круг 11, интеграция: обёртки, которыми страницы получают общие кнопки кабинета.
//  - `CabinetSubjectActions` — для слота `CabinetActionsSlot` (показатели, страны, регионы, рейтинг, календарь):
//    «Сохранить» и «Следить» по предмету страницы (`lib/cabinetSubjects.js`); при `only: 'watch'` только «Следить».
//  - `CompareSaveButton` — «Сохранить» в ряду действий под графиком сравнения (`ComparePage` → `renderSave`).
// Когда кабинет выключен на сервере (`GET /cabinet/config` → disabled) или ответа нет, кнопки ничего не рисуют.
import { useT } from '../../i18n';
import { comparisonSaveProps } from '../../lib/cabinetWiring';
import SaveButton from './SaveButton';
import WatchButton from './WatchButton';

export function CabinetSubjectActions({ subject }) {
  if (!subject) return null;
  const watch = subject.watch?.subjectKey ? (
    <WatchButton subjectKind={subject.watch.subjectKind} subjectKey={subject.watch.subjectKey} title={subject.title || undefined} />
  ) : null;
  if (subject.only === 'watch') return watch;
  return (
    <>
      <SaveButton kind={subject.kind} itemKey={subject.itemKey} title={subject.title} payload={subject.payload} />
      {watch}
    </>
  );
}

export function CompareSaveButton({ spec }) {
  const t = useT();
  const props = comparisonSaveProps(spec);
  if (!props) return null;
  return <SaveButton {...props} variant="button" label={t('c11i.compare.save')} />;
}
