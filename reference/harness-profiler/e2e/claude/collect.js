'use strict';
// Copies a recorded session into output/ so it renders the same on any machine:
//   output/trace.jsonl                                    the trace, temp path -> /work/fixture
//   output/transcripts/<session>.jsonl                    main's model calls
//   output/transcripts/<session>/subagents/agent-<id>.jsonl
// hp reads context sizes and spend from Claude Code's transcripts. Those hold
// the whole conversation, so only what hp reads is kept: per model call the
// message id, the token usage and the ids of its tool calls.
// Usage: node collect.js <trace.jsonl> <work dir> <output dir>
const fs = require('fs');
const path = require('path');
const { fillContextTokens } = require('../../plugin/libexec/hp.js');

const [trace, work, out] = process.argv.slice(2);
const USAGE_KEYS = ['input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens'];

function reduce(text) {
  const kept = [];
  for (const line of text.split('\n')) {
    let entry;
    try { entry = JSON.parse(line); } catch { continue; }
    const message = entry && entry.type === 'assistant' && entry.message;
    if (!message || !message.usage) continue;
    const usage = Object.fromEntries(USAGE_KEYS.filter((k) => k in message.usage).map((k) => [k, message.usage[k]]));
    const content = (message.content || []).filter((c) => c && c.type === 'tool_use').map((c) => ({ type: 'tool_use', id: c.id }));
    kept.push(JSON.stringify({ type: 'assistant', message: { id: message.id, usage, content } }));
  }
  return kept.length ? kept.join('\n') + '\n' : '';
}

function copyTranscript(from, to) {
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.writeFileSync(to, reduce(fs.readFileSync(from, 'utf8')));
  const subagents = path.join(from.replace(/\.jsonl$/, ''), 'subagents');
  if (!fs.existsSync(subagents)) return;
  for (const f of fs.readdirSync(subagents).filter((n) => /^agent-.+\.jsonl$/.test(n))) {
    copyTranscript(path.join(subagents, f), path.join(to.replace(/\.jsonl$/, ''), 'subagents', f));
  }
}

const records = fillContextTokens(fs.readFileSync(trace, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)));
fs.rmSync(path.join(out, 'transcripts'), { recursive: true, force: true });
const lines = records.map((r) => {
  if (!r.transcript) return r;
  const local = path.join('transcripts', path.basename(r.transcript));
  if (fs.existsSync(r.transcript)) copyTranscript(r.transcript, path.join(out, local));
  return { ...r, transcript: local };
}).map((r) => JSON.stringify(r).split(work).join('/work/fixture'));
fs.writeFileSync(path.join(out, 'trace.jsonl'), lines.join('\n') + '\n');
