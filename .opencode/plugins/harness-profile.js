// Thin opencode 2.3 entry point. All decisions live in
// tools/harness-profile/handle.js (CommonJS, tested by handle.test.js); this
// file only subscribes once and forwards events, exactly the shape the 2.3
// loader accepts (plain ESM default object with id + setup + disposer).
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const handle = require(path.join(root, 'tools', 'harness-profile', 'handle.js'));

// A capture refusal (no git root, an unverifiable exclusion, a malformed .git)
// is recorded in `state.warnings` instead of failing the session, so without
// this line the trace is simply absent and the reason is unreadable from
// outside the long-lived process. One line per distinct warning per process:
// the server log keeps the diagnosis, and a stream of events cannot flood it.
const reported = new Set();

function reportWarnings(state) {
  for (const warning of state.warnings) {
    if (reported.has(warning)) continue;
    reported.add(warning);
    try {
      process.stderr.write(`[aep-harness-profile] ${warning}\n`);
    } catch {
      // Logging cannot fail a session either.
    }
  }
}

function directoryOf(ctx) {
  if (typeof ctx?.directory === 'string' && ctx.directory) return ctx.directory;
  if (typeof ctx?.location?.directory === 'string' && ctx.location.directory) return ctx.location.directory;
  return process.cwd();
}

export default {
  id: 'aep-harness-profile',
  async setup(ctx) {
    if (typeof ctx?.event?.subscribe !== 'function') return () => {};
    const controller = new AbortController();
    const state = handle.createState({
      cwd: directoryOf(ctx),
      env: process.env,
      sessionGet: typeof ctx?.session?.get === 'function'
        ? (sessionID) => ctx.session.get({ sessionID })
        : undefined,
    });
    const consuming = (async () => {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        await handle.handleEvent(event, state);
        reportWarnings(state);
      }
    })().catch(() => {});
    return async () => {
      controller.abort();
      await consuming;
    };
  },
};
