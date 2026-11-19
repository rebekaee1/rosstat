// 19.11.2026: касание шара — рабочее действие (выбор страны, «данных пока нет», вращение, двойное приближение).
// Холст шара помечен data-interactive, иначе счётчик поведения записывает каждое касание как клик «в пустоту» (dead),
// и Пульс строит из этого гипотезы «шар не отвечает» (309, 318).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const scene = readFileSync(join(here, 'PlanetScene.jsx'), 'utf8');
const behavior = readFileSync(join(here, '..', 'lib', 'behavior.js'), 'utf8');

describe('холст шара для признака dead', () => {
  it('счётчик поведения считает [data-interactive] управлением', () => {
    const selector = behavior.match(/const INTERACTIVE = '([^']+)'/)?.[1] || '';
    expect(selector.split(',')).toContain('[data-interactive]');
  });

  it('холст шара получает data-interactive при создании сцены', () => {
    const created = scene.match(/onCreated=\{\(\{ gl \}\) => \{([\s\S]*?)\n\s*\}\}/)?.[1] || '';
    expect(created).toMatch(/gl\.domElement\.setAttribute\('data-interactive', ''\)/);
  });
});
