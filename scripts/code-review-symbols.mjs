#!/usr/bin/env node
/** Static symbol inventory. This script never marks source as reviewed. */
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
const output = path.join(root, 'docs/code-review/javascript-symbols.json');
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
const paths = [...new Set([...git('ls-files', '-z'), ...git('ls-files', '--others', '--exclude-standard', '-z')])]
  .filter(name => /\.(js|jsx|mjs|ts|tsx)$/.test(name) && !name.startsWith('docs/code-review/')).sort();

function keyName(node) {
  if (node?.type === 'PrivateName') return '#' + node.id.name;
  return node?.name || (typeof node?.value === 'string' ? node.value : null);
}

function functionName(p) {
  const n = p.node;
  if (n.id?.name) return n.id.name;
  if (p.isObjectMethod() || p.isClassMethod() || p.isClassPrivateMethod()) return keyName(n.key);
  const parent = p.parentPath?.node;
  if (parent?.type === 'VariableDeclarator') return keyName(parent.id);
  if (parent?.type === 'ObjectProperty' || parent?.type === 'ClassProperty') return keyName(parent.key);
  if (parent?.type === 'AssignmentExpression') {
    return keyName(parent.left) || keyName(parent.left?.property);
  }
  return null;
}

function qualifiedName(p, name) {
  const ancestors = [];
  for (let cursor = p.parentPath; cursor; cursor = cursor.parentPath) {
    if (cursor.isFunction()) {
      const parentName = functionName(cursor);
      if (parentName) ancestors.unshift(parentName);
    } else if (cursor.isClassDeclaration() || cursor.isClassExpression()) {
      if (cursor.node.id?.name) ancestors.unshift(cursor.node.id.name);
    }
  }
  return [...ancestors, name].join('.');
}

const inventory = {};
for (const name of paths) {
  const filename = path.join(root, name);
  if (!fs.existsSync(filename) || fs.lstatSync(filename).isSymbolicLink()) continue;
  const raw = fs.readFileSync(filename);
  const row = { sha256: createHash('sha256').update(raw).digest('hex'), definitions: [], imports: [], exports: [], anonymous_functions: 0 };
  try {
    const ast = parser.parse(raw.toString('utf8'), {
      sourceType: 'unambiguous', plugins: ['jsx', ...(/\.tsx?$/.test(name) ? ['typescript'] : [])],
    });
    traverse(ast, {
      Function(p) {
        const symbol = functionName(p);
        if (!symbol) { row.anonymous_functions += 1; return; }
        // VariableDeclarator includes the name on the line used by reviewers.
        const location = p.parentPath?.isVariableDeclarator() ? p.parentPath.node.loc : p.node.loc;
        row.definitions.push({ name: qualifiedName(p, symbol), line: location.start.line, end_line: p.node.loc.end.line, kind: p.node.type });
      },
      Class(p) {
        const symbol = p.node.id?.name || keyName(p.parentPath?.node?.id);
        if (symbol) row.definitions.push({ name: qualifiedName(p, symbol), line: p.node.loc.start.line, end_line: p.node.loc.end.line, kind: p.node.type });
      },
      ImportDeclaration(p) { row.imports.push({ source: p.node.source.value, line: p.node.loc.start.line }); },
      ExportNamedDeclaration(p) {
        const d = p.node.declaration;
        const names = d?.id?.name ? [d.id.name] : d?.declarations?.map(x => keyName(x.id)).filter(Boolean)
          || p.node.specifiers.map(x => keyName(x.exported)).filter(Boolean);
        row.exports.push({ names, line: p.node.loc.start.line });
      },
      ExportDefaultDeclaration(p) { row.exports.push({ names: ['default'], line: p.node.loc.start.line }); },
    });
    row.definitions.sort((a, b) => a.line - b.line || a.name.localeCompare(b.name));
  } catch (error) { row.error = error.message; }
  inventory[name] = row;
}
const serialized = JSON.stringify(inventory, null, 2) + '\n';
const failed = Object.values(inventory).filter(row => row.error).length;
if (process.argv.includes('--check')) {
  if (!fs.existsSync(output) || fs.readFileSync(output, 'utf8') !== serialized) {
    console.error('JavaScript symbol inventory is stale'); process.exitCode = 1;
  }
} else {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, serialized);
}
if (failed) process.exitCode = 1;
console.log(JSON.stringify({ files: Object.keys(inventory).length, definitions: Object.values(inventory).reduce((n, row) => n + row.definitions.length, 0), parse_errors: failed }));
