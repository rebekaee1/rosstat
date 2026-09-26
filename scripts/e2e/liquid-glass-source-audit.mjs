/** Read-only source/runtime inventory. Run after the final backend rebuild. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const python = path.join(root, 'backend/.venv/bin/python');
const inspect = String.raw`
import ast, hashlib, json, pathlib
root = pathlib.Path.cwd()
files = ['backend/app/services/og_image.py', 'backend/app/api/sitemap.py',
 'backend/app/services/seo_renderer.py', 'backend/app/services/seo_world.py',
 'backend/app/services/seo_regional.py', 'backend/app/services/seo_world_subnational.py',
 'backend/app/services/site_urls.py', 'backend/app/services/site_paths.py',
 'backend/app/api/seo_pages.py', 'frontend/nginx.conf']
out = {'fileHashes': {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files},
 'renderers': [], 'routes': []}
for rel,key,prefix in [(files[0],'renderers','render_'),(files[1],'routes','og_image_')]:
 tree = ast.parse((root/rel).read_text())
 for n in tree.body:
  if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) or not n.name.startswith(prefix): continue
  if key == 'renderers' and not n.name.endswith('_og'): continue
  names = {v.id for v in ast.walk(n) if isinstance(v,ast.Name)}
  item = {'function': n.name, 'line': n.lineno,
   'portrait': 'portrait' in [a.arg for a in n.args.args+n.args.kwonlyargs]}
  if key == 'renderers':
   item['sharedPearlBase'] = '_pearl_base' in names
   item['portraitHelpers'] = sorted(x for x in names if 'portrait' in x and x != 'portrait')
  else:
   item['renderers'] = sorted(x for x in names if x.startswith('render_') and x.endswith('_og'))
   item['paths'] = [d.args[0].value for d in n.decorator_list if isinstance(d,ast.Call) and d.args and isinstance(d.args[0],ast.Constant) and isinstance(d.args[0].value,str)]
  out[key].append(item)
out['counts'] = {'rendererFunctions': len(out['renderers']), 'ogHandlers': len(out['routes']),
 'portraitRenderers': sum(r['portrait'] for r in out['renderers']),
 'portraitHandlers': sum(r['portrait'] for r in out['routes'])}
print(json.dumps(out))
`;
const report = JSON.parse(execFileSync(python, ['-c', inspect], { cwd: root, encoding: 'utf8' }));
report.at = new Date().toISOString();
report.status = 'final_local_source_and_runtime_snapshot';
report.baseline = 'docs/design/local-acceptance/source-audit.json';
const runtimePaths = Object.keys(report.fileHashes).filter(p => p.startsWith('backend/')).map(p => '/app/' + p.replace(/^backend\//, ''));
const runtimeCode = `import hashlib,json,pathlib; print(json.dumps({p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in ${JSON.stringify(runtimePaths)}}))`;
const backendHashes = JSON.parse(execFileSync('docker', ['compose', 'exec', '-T', 'backend', 'python', '-c', runtimeCode], { cwd: root, encoding: 'utf8', timeout: 15000 }));
report.runtimeHashes = Object.fromEntries(Object.entries(backendHashes).map(([p, h]) => ['backend/' + p.replace(/^\/app\//, ''), h]));
report.runtimeHashes['frontend/nginx.conf'] = execFileSync('docker', ['compose', 'exec', '-T', 'frontend', 'sha256sum', '/etc/nginx/conf.d/default.conf'], { cwd: root, encoding: 'utf8', timeout: 15000 }).trim().split(/\s+/)[0];
report.sourceMatchesRuntime = Object.fromEntries(Object.entries(report.runtimeHashes).map(([p, h]) => [p, h === report.fileHashes[p]]));
report.containerImages = {};
for (const service of ['backend', 'frontend']) {
  const id = execFileSync('docker', ['compose', 'ps', '-q', service], { cwd: root, encoding: 'utf8' }).trim();
  report.containerImages[service] = execFileSync('docker', ['inspect', '--format', '{{.Image}}', id], { cwd: root, encoding: 'utf8' }).trim();
}
report.acceptanceArtifacts = [];
for (const relative of ['final/all.json', 'final-narrow/http.json', 'final-narrow/browser.json', 'final-us-images-before.json', 'final-us-images-after.json']) {
  const file = path.join(root, 'docs/design/local-acceptance', relative);
  if (!fs.existsSync(file)) continue;
  const evidence = JSON.parse(fs.readFileSync(file));
  report.acceptanceArtifacts.push({ file: path.relative(root, file), at: evidence.at, completedAt: evidence.completedAt,
    http: evidence.http?.length, browser: evidence.browser?.length, images: evidence.images?.length,
    hashes: [...(evidence.http || []).map(x => ({ id: x.id, locale: x.locale, url: x.url, sha256: x.sha256 })),
      ...(evidence.images || []).map(x => ({ id: x.id, locale: x.locale, url: x.url, sha256: x.sha256 }))] });
}
report.limitations = ['Local compose snapshot, no production deployment or verification.',
 'AST counts describe actual renderer entry points, not an inferred count of all possible chart modes.',
 'Family sampling and source inspection do not establish that every published URL was crawled.',
 'Non-data fallback OG and map-as-ranking use are documented coverage choices, not geographical renderers.'];
const file = path.join(root, 'docs/design/local-acceptance/final-source-audit.json');
fs.writeFileSync(file, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ file, counts: report.counts, sourceMatchesRuntime: report.sourceMatchesRuntime }));
