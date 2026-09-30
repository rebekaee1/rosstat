/** Source-level DOM checks for the local terrain viewer; no browser or network. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { JSDOM } = require('jsdom');
const fixture = {
  extractor: 'fixture', baseline_commit: '0123456789abcdef',
  files: [
    { path: 'backend/app/main.py', layer: 'model', kind: 'code', extraction: 'nodes', bytes: 10, lines: 2, nodes: 1, sha256: 'a' },
    { path: 'frontend/src/App.jsx', layer: 'browser', kind: 'code', extraction: 'nodes', bytes: 20, lines: 3, nodes: 2, sha256: 'b' },
  ],
  edges: [{ source: 'frontend/src/App.jsx', target: 'backend/app/main.py', relation: 'imports', confidence: 'INFERRED', count: 1, evidence: [] }],
  stats: { files: 2, file_edges: 1 },
  overview: {
    semantic_files: 0, semantic_stale: [],
    layers: [{ id: 'model', label: 'Backend', files: 1, with_nodes: 1, semantic_evidence: 0 }, { id: 'browser', label: 'Frontend', files: 1, with_nodes: 1, semantic_evidence: 0 }],
    links: [{ source: 'browser', target: 'model', file_relations: 1 }],
  },
  code_review: {
    available: true, current_now: 1, counts: { files: 2, definitions: 1, annotated_definitions: 1 },
    files: { 'backend/app/main.py': { status: 'reviewed', current: true, summary: '<img src=x onerror=alert(1)>', contracts: ['Request lifecycle'], elements: [{ name: 'lifespan', purpose: 'Register background tasks', verification: 'body_reviewed', line: 1, end_line: 2 }] } },
  },
  mechanisms: {'frontend/src/App.jsx': { current: true, records: [
    { inventory_kind: 'functions', kind: 'ArrowFunctionExpression', name: null, owner: 'App', line: 2, end_line: 3 },
    { inventory_kind: 'jsx_handlers', event: 'onClick', expression: '<img src=x onerror=alert(1)>', line: 2, end_line: 2 },
  ]}},
};
const template = fs.readFileSync(path.join(root, 'scripts/project-terrain-template.html'), 'utf8');
const html = template.replace('__TERRAIN_DATA__', JSON.stringify(fixture).replaceAll('<', '\\u003c'));
const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'https://terrain.invalid/' });
const { document, Event } = dom.window;
dom.window.HTMLElement.prototype.scrollIntoView = () => {};
const set = (id, value) => { const node = document.getElementById(id); node.value = value; node.dispatchEvent(new Event('input')); };
const count = () => document.querySelectorAll('#files .file').length;
assert.equal(count(), 2);
assert.match(document.getElementById('detail').textContent, /Register background tasks/);
assert.equal(document.querySelector('#detail img'), null, 'Review text must not become HTML');
set('search', 'lifespan'); assert.equal(count(), 1);
set('search', ''); set('review-filter', 'attention'); assert.equal(count(), 1);
document.querySelector('[data-layer="model"]').click();
assert.equal(document.getElementById('review-filter').value, '', 'Layer selection resets review filter');
assert.equal(count(), 1);
set('review-filter', 'attention');
document.querySelector('.matrix button:not(:disabled)').click();
assert.equal(document.getElementById('review-filter').value, '', 'Matrix selection resets review filter');
assert.equal(count(), 2);
document.querySelector('[data-path="frontend/src/App.jsx"]').click();
assert.match(document.getElementById('detail').textContent, /ещё нет содержательной рецензии/);
assert.match(document.getElementById('detail').textContent, /Независимые элементы: 2/);
assert.match(document.getElementById('detail').textContent, /ArrowFunctionExpression/);
assert.equal(document.querySelector('#detail img'), null, 'Mechanism expressions must remain text');
dom.window.close();
console.log('Terrain DOM: search, review filters, drilldown reset, missing review and text escaping passed');
