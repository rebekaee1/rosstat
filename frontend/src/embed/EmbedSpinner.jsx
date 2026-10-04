/**
 * Единое кольцо ожидания для встраиваемых виджетов. В iframe нет Tailwind и общих стилей сайта,
 * поэтому внешний вид — инлайн-стилем, а ключевые кадры — собственным <style> (одинаковый у всех
 * экземпляров, повтор безвреден). Цвета берутся из палитры виджета (`colors`).
 * При prefers-reduced-motion кольцо не вращается и остаётся видимым.
 */
const CSS = '@keyframes fe-embed-spin{to{transform:rotate(360deg)}}'
  + '.fe-embed-spinner{animation:fe-embed-spin .7s linear infinite}'
  + '@media(prefers-reduced-motion:reduce){.fe-embed-spinner{animation:none}}';

export default function EmbedSpinner({ colors, size = 20, label }) {
  return (
    <>
      <span
        className="fe-embed-spinner"
        role={label ? 'status' : undefined}
        aria-label={label || undefined}
        aria-hidden={label ? undefined : 'true'}
        style={{
          display: 'inline-block',
          flexShrink: 0,
          width: size,
          height: size,
          boxSizing: 'border-box',
          borderRadius: '50%',
          border: `2px solid ${colors?.border || 'rgba(0,0,0,.12)'}`,
          borderTopColor: colors?.textTertiary || '#697587',
        }}
      />
      <style>{CSS}</style>
    </>
  );
}
