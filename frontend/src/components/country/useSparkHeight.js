// Высота мини-графика крупной цифры: на телефоне ниже, чтобы карточка не вытягивалась в экран.
import { useEffect, useState } from 'react';

const WIDE = '(min-width: 640px)';

export default function useSparkHeight(wideHeight = 88, narrowHeight = 52) {
  const [wide, setWide] = useState(
    () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(WIDE).matches : true),
  );
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia(WIDE);
    const onChange = () => setWide(mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);
  return wide ? wideHeight : narrowHeight;
}
