import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/** Только дамп cpi-methodology-combinations.temp.txt — не входит в check-all. */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    include: ['src/lib/dump-cpi-methodology-temp.test.js'],
  },
});
