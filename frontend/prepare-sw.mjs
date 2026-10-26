// Embed this exact build's HTML/assets so Render's loading page is never cached.
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const html = await readFile(new URL('./dist/index.html', import.meta.url), 'utf8');
const assets = (await readdir(new URL('./dist/assets/', import.meta.url))).map(name => '/assets/' + name);
assets.push('/icon-192.png', '/icon-512.png', '/apple-touch-icon.png', '/manifest.json');
const template = await readFile(new URL('./public/sw.js', import.meta.url), 'utf8');
const digest = createHash('sha256').update(html + template);
for (const asset of assets) digest.update(await readFile(new URL('./dist' + asset, import.meta.url)));
const version = digest.digest('hex').slice(0, 16);
const script = template.replace('"__BUILD_VERSION__"', JSON.stringify(version))
  .replace('"__BUILD_HTML__"', JSON.stringify(html))
  .replace('["__BUILD_ASSETS__"]', JSON.stringify(assets));
await writeFile(new URL('./dist/sw.js', import.meta.url), script);
