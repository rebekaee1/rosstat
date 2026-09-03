import { StrictMode, useLayoutEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import App from './App.jsx';
import { scheduleSpaReveal } from './lib/spaReveal';

/** Корень SPA: клип SSR-тела только после первого commit (см. spaReveal). */
export default function SpaRoot({ queryClient }) {
  useLayoutEffect(() => {
    const id = scheduleSpaReveal();
    return () => {
      if (id != null) cancelAnimationFrame(id);
    };
  }, []);
  return (
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>
  );
}
