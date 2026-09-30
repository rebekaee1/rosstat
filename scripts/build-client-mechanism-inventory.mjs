#!/usr/bin/env node
/** Independent source inventory; no application execution and no review stamps. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
const files = tracked.filter(p => /\.(jsx?|mjs|tsx?)$/.test(p) && (p.startsWith('frontend/') || p.startsWith('mcp/'))).sort();
const owned = new Set(tracked);
const inventory = { schema_version: 1, scope: 'Git tracked client sources, including tests/build/MCP; source-only Babel traversal',
  limits: ['Expressions are preserved, not evaluated. A declaration is not proof of mounting, execution or UI acceptance.',
    'Anonymous callbacks have enclosing source anchors; semantic review remains in the source ledger.',
    'Hook/state/HTTP/storage/event/JSX call sites are syntactic inventories, not a runtime dependency graph.'], files: {}, totals: {} };

function functionName(p) {
  const n = p.node;
  return n.id?.name || (p.parentPath?.isVariableDeclarator() ? p.parentPath.node.id?.name : null)
    || (p.isObjectMethod() || p.isClassMethod() ? n.key?.name || n.key?.value : null);
}

function owner(p) {
  const names = [];
  for (let q = p.parentPath; q; q = q.parentPath) {
    if (q.isFunction()) names.unshift(functionName(q) || `<callback@${q.node.loc.start.line}>`);
  }
  return names.join('.') || '<module>';
}

function resolveImport(file, spec) {
  if (!spec.startsWith('.')) return { category: 'external_package', target: spec };
  const base = path.posix.normalize(path.posix.join(path.posix.dirname(file), spec));
  const matches = [base, ...['.js', '.jsx', '.mjs', '.ts', '.tsx', '.json'].map(s => base + s),
    ...['index.js', 'index.jsx', 'index.ts', 'index.tsx'].map(s => base + '/' + s)].filter(x => owned.has(x));
  return { category: matches.length === 1 ? 'owned_source' : matches.length ? 'ambiguous' : 'unresolved_local', targets: matches };
}

for (const file of files) {
  const raw = fs.readFileSync(path.join(root, file)), source = raw.toString('utf8');
  const row = { sha256: createHash('sha256').update(raw).digest('hex'), imports: [], routes: [], functions: [],
    hooks: [], http: [], storage: [], events: [], jsx_handlers: [], registries: [], mcp_tools: [] };
  const expr = n => n ? source.slice(n.start, n.end) : null;
  const anchor = (p, extra = {}) => ({ line: p.node.loc.start.line, end_line: p.node.loc.end.line, owner: owner(p), ...extra });
  try {
    traverse(parser.parse(source, { sourceType: 'unambiguous', plugins: ['jsx', ...(/\.tsx?$/.test(file) ? ['typescript'] : [])] }), {
      ImportDeclaration(p) { row.imports.push(anchor(p, { specifier: p.node.source.value, ...resolveImport(file, p.node.source.value), bindings: p.node.specifiers.map(s => s.local.name) })); },
      ExportNamedDeclaration(p) { if (p.node.source) row.imports.push(anchor(p, { specifier: p.node.source.value, ...resolveImport(file, p.node.source.value), re_export: true })); },
      Function(p) { row.functions.push(anchor(p, { name: functionName(p), kind: p.node.type, callback_context: expr(p.parentPath?.node?.callee) })); },
      JSXOpeningElement(p) {
        const name = expr(p.node.name);
        const attrs = Object.fromEntries(p.node.attributes.filter(a => a.type === 'JSXAttribute').map(a => [a.name.name, expr(a.value)]));
        if (name === 'Route') row.routes.push(anchor(p, { attributes: attrs }));
        for (const [event, value] of Object.entries(attrs)) if (/^on[A-Z]/.test(event)) row.jsx_handlers.push(anchor(p, { component: name, event, expression: value }));
      },
      VariableDeclarator(p) {
        if (p.node.id.type === 'Identifier' && /^(?:[A-Z][A-Z\d_]+|.*(?:Defs|Registry|Families|Routes|Variants|Options))$/.test(p.node.id.name)
          && ['ObjectExpression', 'ArrayExpression', 'CallExpression'].includes(p.node.init?.type))
          row.registries.push(anchor(p, { name: p.node.id.name, kind: p.node.init.type,
            entries: p.node.init.properties?.map(v => expr(v.key)) || p.node.init.elements?.map(v => expr(v)) || [], initializer: p.node.init.type === 'CallExpression' ? expr(p.node.init.callee) : null }));
      },
      CallExpression(p) {
        const callee = expr(p.node.callee), args = p.node.arguments.map(expr);
        if (/(?:registerTool|\.tool)$/.test(callee)) row.mcp_tools.push(anchor(p, { callee, name: expr(p.node.arguments[0]), schema: expr(p.node.arguments[1]), handler_line: p.node.arguments.at(-1)?.loc?.start.line }));
        if (/^(?:use[A-Z]|React\.use[A-Z])/.test(callee)) row.hooks.push(anchor(p, { callee, arguments: args }));
        if (callee === 'fetch' || /(?:^|\.)(?:get|post|put|patch|delete|head|options)$/.test(callee)
          && /^(?:api|axios|client|http|fetchClient|authApi)\b/.test(callee)) row.http.push(anchor(p, { callee, arguments: args }));
        if (/(?:localStorage|sessionStorage)\.(?:getItem|setItem|removeItem|clear)$/.test(callee)) row.storage.push(anchor(p, { callee, arguments: args }));
        if (/(?:addEventListener|removeEventListener|dispatchEvent|sendBeacon|postMessage)$/.test(callee)) row.events.push(anchor(p, { callee, arguments: args }));
        if (p.node.callee.type === 'Import' && p.node.arguments[0]?.type === 'StringLiteral') row.imports.push(anchor(p, { dynamic: true, specifier: p.node.arguments[0].value, ...resolveImport(file, p.node.arguments[0].value) }));
      },
    });
  } catch (error) { row.parse_error = error.message; }
  inventory.files[file] = row;
}
for (const kind of ['imports', 'routes', 'functions', 'hooks', 'http', 'storage', 'events', 'jsx_handlers', 'registries', 'mcp_tools'])
  inventory.totals[kind] = Object.values(inventory.files).reduce((n, v) => n + v[kind].length, 0);
inventory.totals.files = files.length;
inventory.totals.parse_errors = Object.values(inventory.files).filter(v => v.parse_error).length;
const json = JSON.stringify(inventory, null, 2) + '\n';
const lines = ['# Независимый инвентарь клиента', '', 'Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.', '',
  ...Object.entries(inventory.totals).map(([k, v]) => `- ${k}: ${v}`), '',
  'Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.', '',
  '## Объявления маршрутов', '', '| Источник | path / index | element |', '|---|---|---|',
  ...Object.entries(inventory.files).flatMap(([f, r]) => r.routes.map(v => `| [${f}:${v.line}](../${f}#L${v.line}) | ${v.attributes.path || (v.attributes.index !== undefined ? 'index' : '(group)')} | ${(v.attributes.element || '').replaceAll('|', '&#124;')} |`)), '',
  '## Границы', '', ...inventory.limits.map(v => '- ' + v), ''];
const outputs = { 'docs/client-mechanism-inventory.json': json, 'docs/client-mechanism-inventory.md': lines.join('\n') };
for (const [file, body] of Object.entries(outputs)) {
  const target = path.join(root, file);
  if (process.argv.includes('--check')) {
    if (!fs.existsSync(target) || fs.readFileSync(target, 'utf8') !== body) { console.error('Stale: ' + file); process.exitCode = 1; }
  } else fs.writeFileSync(target, body);
}
if (inventory.totals.parse_errors) process.exitCode = 1;
console.log(JSON.stringify(inventory.totals));
