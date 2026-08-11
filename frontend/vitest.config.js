import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // React plugin нужен, чтобы юнит-тесты могли импортировать модули
  // с JSX-литералами (например, `lib/cpiViewModeContent.jsx`).
  plugins: [react()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.{js,jsx}'],
    // Ограничиваем параллелизм: десятки Vite-трансформаций и jsdom-страниц
    // одновременно перегружали локальный CI и давали ложные timeout'ы.
    maxWorkers: 4,
    // Полные React-страницы под jsdom на загруженной CI-машине иногда
    // переходят стандартный порог 5 с, хотя отдельный прогон стабильно зелёный.
    testTimeout: 10_000,
    // Т-13: component-тесты (testing-library) живут в jsdom; юнит-тесты lib/
    // остаются в быстром node-окружении.
    environmentMatchGlobs: [['src/**/*.component.test.jsx', 'jsdom']],
    setupFiles: ['src/test/setup.js'],
  },
});
