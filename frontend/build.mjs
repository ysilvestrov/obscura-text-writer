import {build} from 'esbuild';
import {createHash} from 'node:crypto';
import {readFile, writeFile, mkdir, readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const frontend = path.join(root, 'frontend');
const output = path.join(root, 'src/storygen/web/static');
const sha = data => createHash('sha256').update(data).digest('hex');
const result = await build({
  absWorkingDir: frontend, entryPoints: ['src/rich-engine.js'],
  outfile: path.join(output, 'rich-editor-engine.js'), bundle: true, format: 'esm',
  platform: 'neutral', mainFields: ['module', 'main'], conditions: ['import'],
  target: ['es2022'], charset: 'utf8', legalComments: 'eof', metafile: true,
});
const sources = {};
for (const name of ['package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'build.mjs', ...(await readdir(path.join(frontend, 'src'))).filter(name => name.endsWith('.js')).map(name => `src/${name}`)]) {
  sources[`frontend/${name}`] = sha((await readFile(path.join(frontend, name), 'utf8')).replaceAll('\r\n', '\n'));
}
const packages = new Map();
for (const input of Object.keys(result.metafile.inputs)) {
  if (!input.includes('node_modules/')) continue;
  let directory = path.dirname(path.resolve(frontend, input));
  while (directory !== path.dirname(directory)) {
    try {
      const info = JSON.parse(await readFile(path.join(directory, 'package.json'), 'utf8'));
      if (info.name && info.version) {packages.set(info.name, {info, directory}); break;}
    } catch (error) {if (error.code !== 'ENOENT') throw error;}
    directory = path.dirname(directory);
  }
}
await mkdir(path.join(output, 'licenses'), {recursive: true});
const licenses = [];
for (const [name, {info, directory}] of [...packages].sort(([a], [b]) => a.localeCompare(b))) {
  const filename = (await readdir(directory)).find(value => /^licen[sc]e(?:\..*)?$/i.test(value));
  if (!filename) throw new Error(`Missing license for ${name}`);
  const bytes = await readFile(path.join(directory, filename));
  const target = `licenses/${name.replaceAll('/', '__').replaceAll('@', '')}.txt`;
  await writeFile(path.join(output, target), bytes);
  licenses.push({name, version: info.version, license: info.license, path: target, sha256: sha(bytes)});
}
const asset = 'rich-editor-engine.js';
const manifest = {version: 1, sources, assets: {[asset]: sha(await readFile(path.join(output, asset)))}, licenses};
await writeFile(path.join(output, 'editor-bundle.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`Built ${asset}; ${licenses.length} bundled dependency licenses`);
