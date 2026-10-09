import { createContext } from 'react';

/**
 * Кнопки кабинета для страниц данных (круг 11, F). Значение: функция `(subject) => ReactNode`, которая рисует «В избранное» и
 * «Следить» для предмета страницы (описание предметов — `lib/cabinetSubjects.js`). Провайдер ставит зона кабинета одной обёрткой
 * у корня приложения; без провайдера слоты на страницах пусты.
 */
export const CabinetActionsContext = createContext(null);
