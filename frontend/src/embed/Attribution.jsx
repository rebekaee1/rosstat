import { ExternalLink } from 'lucide-react';

export default function Attribution({ code, dark = false }) {
  return (
    <a
      href={`https://forecasteconomy.com/indicator/${code || ''}`}
      target="_blank"
      rel="noopener"
      className="flex items-center justify-end gap-1 px-3 py-1.5 no-underline transition-opacity hover:opacity-80"
      style={{
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontSize: 10,
        color: dark ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.3)',
        lineHeight: 1,
      }}
    >
      <span>Данные: Forecast Economy</span>
      <ExternalLink size={9} strokeWidth={2} />
    </a>
  );
}
