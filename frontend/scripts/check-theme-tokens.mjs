// Theme guard: dark and light must stay in step.  Run: npm run test:theme
//  1. no colour literal (hex / rgb / hsl) outside the token blocks of src/index.css
//     (a line that holds the marker "theme-ok" is allowed: the white PDF paper, brand marks)
//  2. every var(--x) that is used is defined in index.css or in the file that uses it
//  3. the dark block and the light block of index.css define exactly the same tokens
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const SRC = new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const INDEX = join(SRC, "index.css");
const COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;
const problems = [];

function walk(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : /\.(css|tsx|ts)$/.test(n) ? [p] : [];
  });
}

const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));

// --- blocks of index.css that may hold colours: :root / [data-theme=...] ---
const indexText = readFileSync(INDEX, "utf8");
function blockTokens(selectorRe) {
  const m = new RegExp(selectorRe + "\\s*\\{([^}]*)\\}").exec(stripComments(indexText));
  return m ? [...m[1].matchAll(/(--[a-z0-9-]+)\s*:/g)].map((x) => x[1]) : null;
}
const dark = blockTokens("(?::root,\\s*)?\\[data-theme=\"dark\"\\]");
const light = blockTokens("\\[data-theme=\"light\"\\]");
if (!dark) problems.push('index.css: no [data-theme="dark"] block');
if (!light) problems.push('index.css: no [data-theme="light"] block');
if (dark && light) {
  for (const t of dark) if (!light.includes(t)) problems.push(`index.css: ${t} is in dark but missing in light`);
  for (const t of light) if (!dark.includes(t)) problems.push(`index.css: ${t} is in light but missing in dark`);
}

// --- colour literals outside index.css ---
let literalLines = 0;
for (const file of walk(SRC)) {
  if (file === INDEX || /[\\/]locales[\\/]/.test(file)) continue;
  readFileSync(file, "utf8").split("\n").forEach((line, i) => {
    if (COLOUR.test(line) && !line.includes("theme-ok")) {
      literalLines++;
      if (literalLines <= 15) problems.push(`${relative(SRC, file)}:${i + 1}: colour literal -> use a token`);
    }
  });
}
if (literalLines > 15) problems.push(`... and ${literalLines - 15} more colour literal lines (${literalLines} in all)`);

// --- every var(--x) is defined somewhere ---
const defined = new Set([...(dark ?? []), ...(light ?? [])]);
const colorNames = [...stripComments(indexText).matchAll(/(--[a-z0-9-]+)\s*:/g)].map((x) => x[1]);
// --color-* names live in `@theme inline`: Tailwind inlines them and never emits them as real variables, so var(--color-x) would be empty
colorNames.filter((n) => !n.startsWith("--color-")).forEach((n) => defined.add(n));
for (const file of walk(SRC)) {
  const text = readFileSync(file, "utf8");
  const local = new Set([...text.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((x) => x[1]));
  for (const m of text.matchAll(/var\((--[a-z0-9-]+)/g)) {
    if (!defined.has(m[1]) && !local.has(m[1])) problems.push(`${relative(SRC, file)}: var(${m[1]}) is used but never defined`);
  }
}

if (problems.length) {
  console.error(`theme check FAILED (${problems.length} problems)\n` + [...new Set(problems)].join("\n"));
  process.exit(1);
}
console.log("theme check OK: dark and light define the same tokens, no stray colour literals, no undefined variables");
