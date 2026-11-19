// Commit the generated assets with the existing CSS/JS build output: Vercel's
// legacy static builder serves these files without running the npm build.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync, existsSync } from "node:fs";
import { dirname, basename, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { transformSync } from "esbuild";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../static");
const output = resolve(root, "versioned");
mkdirSync(output, { recursive: true });
const manifest = {};

function writeIfChanged(path, data) {
  const bytes = Buffer.from(data);
  if (!existsSync(path) || !readFileSync(path).equals(bytes)) writeFileSync(path, bytes);
}

function emit(filename, data = readFileSync(resolve(root, filename))) {
  const hash = createHash("sha256").update(data).digest("hex").slice(0, 16);
  const ext = extname(filename);
  const target = `versioned/${basename(filename, ext)}.${hash}${ext}`;
  writeIfChanged(resolve(root, target), data);
  manifest[filename] = target;
}

for (const name of readdirSync(resolve(root, "fonts")).sort()) {
  if (name.endsWith(".woff2")) emit(`fonts/${name}`);
}
let css = readFileSync(resolve(root, "css/output.css"), "utf8");
for (const [source, target] of Object.entries(manifest)) {
  css = css.replaceAll(`../${source}`, `/static/${target}`);
}
emit("css/output.css", transformSync(css, { loader: "css", minify: true }).code);
for (const name of readdirSync(resolve(root, "js")).sort()) {
  if (name.endsWith(".js")) emit(`js/${name}`);
}

const current = new Set(Object.values(manifest));
for (const name of readdirSync(output)) {
  if (/\.[a-f0-9]{16}\.(css|js|woff2)$/.test(name) && !current.has(`versioned/${name}`)) {
    unlinkSync(resolve(output, name));
  }
}
writeIfChanged(resolve(root, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
