import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Состояние ожидания для кнопки или чипа (круг 11, G, U31): человек нажал, а ответ придёт через секунду-две, и на самой кнопке должно
 * быть видно, что нажатие принято.
 *
 *   const { pending, run } = usePending();
 *   <Chip pending={pending} onClick={() => run(() => switchMode('yoy'))}>Год к году</Chip>
 *   <Button pending={pending} onClick={() => run(addRussia)}>Добавить Россию</Button>
 *
 * `run(fn)` ставит ожидание, вызывает `fn` (она может вернуть обещание), снимает ожидание по окончании (в том числе при ошибке: ошибка
 * не глотается, уходит дальше). Пока ожидание идёт, повторный `run` возвращает то же обещание и функцию второй раз не зовёт.
 * После размонтирования состояние не обновляется. Для переходов по ссылке этот хук не нужен: `PageProgress` сам ставит метку на нажатую ссылку.
 */
export function usePending() {
  const [pending, setPending] = useState(false);
  const live = useRef(true);
  const inflight = useRef(null);

  useEffect(() => {
    live.current = true;
    return () => { live.current = false; };
  }, []);

  const run = useCallback((fn) => {
    if (inflight.current) return inflight.current;
    setPending(true);
    const done = () => {
      inflight.current = null;
      if (live.current) setPending(false);
    };
    let result;
    try {
      result = fn();
    } catch (error) {
      done();
      throw error;
    }
    if (result && typeof result.then === 'function') {
      inflight.current = Promise.resolve(result).finally(done);
      return inflight.current;
    }
    done();
    return result;
  }, []);

  return { pending, run };
}
