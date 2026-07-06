import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // React plugin нужен, чтобы юнит-тесты могли импортировать модули
  // с JSX-литералами (например, `lib/cpiViewModeContent.jsx`).
  plugins: [react()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.{js,jsx}'],
    // Т-13: component-тесты (testing-library) живут в jsdom; юнит-тесты lib/
    // остаются в быстром node-окружении.
    environmentMatchGlobs: [['src/**/*.component.test.jsx', 'jsdom']],
    setupFiles: ['src/test/setup.js'],
  },
});
