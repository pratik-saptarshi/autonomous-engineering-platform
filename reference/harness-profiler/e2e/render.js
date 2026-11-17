#!/usr/bin/env node
'use strict';
// Renders e2e/<harness>/output/trace.jsonl into tree.txt, tree-verbose.txt
// and trace.html beside it. With --png it also screenshots the page twice
// (calls only, and every tool call except for the toy) so GitHub can show it; that needs
// Playwright, a dev-only dependency.
const fs = require('fs');
const path = require('path');
const { renderTree, renderHtml } = require('../plugin/libexec/hp.js');

function readRecords(file) {
  return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

function outputs(dir) {
  // collect.js stores transcript paths relative to the output directory.
  const records = readRecords(path.join(dir, 'trace.jsonl'))
    .map((r) => (r.transcript && !path.isAbsolute(r.transcript) ? { ...r, transcript: path.join(dir, r.transcript) } : r));
  const id = records.find((r) => r.session).session;
  return {
    'tree.txt': renderTree(records) + '\n',
    'tree-verbose.txt': renderTree(records, { verbose: true }) + '\n',
    'trace.html': renderHtml({ id, records }),
  };
}

async function screenshot(dir, allCalls) {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2, colorScheme: 'light' });
    await page.goto(`file://${path.join(dir, 'trace.html')}`);
    // The diagram scrolls sideways when its lifelines don't fit; a screenshot can't, so widen the page.
    const overflow = await page.evaluate(() => { const p = document.querySelector('.panel'); return p.scrollWidth - p.clientWidth; });
    if (overflow > 0) await page.setViewportSize({ width: 1280 + overflow + 8, height: 800 });
    await page.screenshot({ path: path.join(dir, 'trace.png'), fullPage: true });
    if (!allCalls) return;
    await page.check('#all');
    await page.screenshot({ path: path.join(dir, 'trace-all-calls.png'), fullPage: true });
  } finally {
    await browser.close();
  }
}

async function main(argv) {
  const png = argv.includes('--png');
  const harnesses = argv.filter((a) => !a.startsWith('--'));
  for (const harness of harnesses.length ? harnesses : ['claude', 'toy']) {
    const dir = path.join(__dirname, harness, 'output');
    for (const [name, text] of Object.entries(outputs(dir))) fs.writeFileSync(path.join(dir, name), text);
    if (png) await screenshot(dir, harness !== 'toy');
    console.log(`Rendered ${path.relative(process.cwd(), dir)}`);
  }
}

module.exports = { outputs };
if (require.main === module) main(process.argv.slice(2)).catch((e) => { console.error(e); process.exitCode = 1; });
