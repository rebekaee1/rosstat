/** Keep server-rendered content visible until its full stylesheet is ready. */
export function mountWhenCssReady(mount, { doc = document, timeoutMs = 2500 } = {}) {
  let mounted = false;
  const mountOnce = () => {
    if (mounted) return;
    mounted = true;
    mount();
  };

  const pending = Array.from(doc.querySelectorAll('link[data-fe-css]'))
    .filter((link) => !(link.sheet || link.media === 'all'));
  if (!pending.length) {
    mountOnce();
    return;
  }

  let remaining = pending.length;
  for (const link of pending) {
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      remaining -= 1;
      if (remaining === 0) mountOnce();
    };
    link.addEventListener('load', done, { once: true });
    link.addEventListener('error', done, { once: true });
    // A stylesheet can finish between the initial scan and listener setup.
    if (link.sheet) link.media = 'all';
    if (link.sheet || link.media === 'all') done();
  }
  setTimeout(mountOnce, timeoutMs);
}
