// «Бюджет» мини-графиков в списке показателей: ряды грузятся только для увиденных строк и не больше лимита за визит.
import { createContext } from 'react';

export const SparkBudgetContext = createContext(null);

export function createSparkBudget(limit) {
  const state = { used: 0 };
  return {
    claim() {
      if (state.used >= limit) return false;
      state.used += 1;
      return true;
    },
  };
}
