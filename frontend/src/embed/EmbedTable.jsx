import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { formatValueWithUnit, formatDate, formatChange, isCpiIndex } from '../lib/format';
import { useEmbedParams, useEmbedImpression, useEmbedAutoHeight, THEME_COLORS } from './useEmbedParams';
import Attribution from './Attribution';

export default function EmbedTable() {
  const { code } = useParams();
  const { theme, limit, showTitle } = useEmbedParams();
  const colors = THEME_COLORS[theme];

  useEmbedImpression(code, 'table');
  useEmbedAutoHeight();

  const { data: meta } = useIndicator(code);
  const { data: dataResp, isLoading, isError } = useIndicatorData(code);

  const rows = useMemo(() => {
    const pts = dataResp?.data || [];
    const recent = pts.slice(-limit).reverse();
    return recent.map((p, i) => {
      const next = i < recent.length - 1 ? recent[i + 1] : null;
      const change = next ? p.value - next.value : null;
      return { ...p, change };
    });
  }, [dataResp, limit]);

  const unit = meta?.unit || '%';
  const isCpi = isCpiIndex(code);
  const font = 'system-ui, -apple-system, sans-serif';
  const mono = 'ui-monospace, monospace';

  return (
    <div style={{ background: colors.bg, fontFamily: font, overflow: 'hidden' }}>
      {showTitle && meta && (
        <div style={{ padding: '12px 16px 8px', fontSize: 13, fontWeight: 600, color: colors.text }}>
          {meta.name}
        </div>
      )}

      {isLoading ? (
        <div style={{ padding: 24, textAlign: 'center', color: colors.textTertiary, fontSize: 13 }}>
          Загрузка…
        </div>
      ) : isError ? (
        <div style={{ padding: 24, textAlign: 'center', color: colors.textTertiary, fontSize: 13 }}>
          Ошибка загрузки данных
        </div>
      ) : rows.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', color: colors.textTertiary, fontSize: 13 }}>
          Нет данных
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
              <th style={{ padding: '6px 16px', textAlign: 'left', fontWeight: 500, color: colors.textTertiary, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Дата
              </th>
              <th style={{ padding: '6px 16px', textAlign: 'right', fontWeight: 500, color: colors.textTertiary, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Значение
              </th>
              <th style={{ padding: '6px 16px', textAlign: 'right', fontWeight: 500, color: colors.textTertiary, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Изм.
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const displayVal = isCpi ? +(r.value - 100).toFixed(2) : r.value;
              const chg = r.change != null ? (isCpi ? +(r.change).toFixed(2) : r.change) : null;
              return (
                <tr key={r.date} style={{
                  borderBottom: i < rows.length - 1 ? `1px solid ${colors.border}` : 'none',
                  transition: 'background 0.15s',
                }}>
                  <td style={{ padding: '8px 16px', fontFamily: mono, color: colors.textSecondary, fontSize: 11 }}>
                    {formatDate(r.date, 'full')}
                  </td>
                  <td style={{ padding: '8px 16px', textAlign: 'right', fontFamily: mono, fontWeight: 600, color: colors.text }}>
                    {formatValueWithUnit(displayVal, unit)}
                  </td>
                  <td style={{ padding: '8px 16px', textAlign: 'right', fontFamily: mono, fontWeight: 500, fontSize: 11, color: chg > 0 ? '#16a34a' : chg < 0 ? '#dc2626' : colors.textTertiary }}>
                    {chg != null ? formatChange(chg) : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '4px 8px', borderTop: `1px solid ${colors.border}` }}>
        <Attribution code={code} dark={theme === 'dark'} />
      </div>
    </div>
  );
}
