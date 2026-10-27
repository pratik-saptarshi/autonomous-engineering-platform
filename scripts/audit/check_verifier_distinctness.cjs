#!/usr/bin/env node
// Network posture: none — this checker performs no network I/O; it reads
// only the local run artifacts named on the command line.
//
// AEP-owned checker for Task A3 of the audit lane. It consumes a run's
// findings file, coverage ledger, attestation sidecar
// (verification-attestations.json), and dispatch log
// (dispatch-log.json), and checks the dispatch-recorded finder != verifier
// distinctness contract of docs/security-audit-protocol.md and
// scripts/audit/verification-attestations.schema.md. It reads the four
// artifacts, compares identities, anchors, hashes, and dispatch ordering,
// and reports; it does not edit artifacts and does not judge finding
// truth.
//
// Usage:
//   node scripts/audit/check_verifier_distinctness.cjs <run-dir>
//   node scripts/audit/check_verifier_distinctness.cjs <findings.json>
//     <coverage-ledger.json> <verification-attestations.json>
//     <dispatch-log.json> [--profile quick|standard|deep]
//
// In run-dir form the four artifacts are read from the directory and
// the profile comes only from the run's run-metadata.json, which is
// the artifact of record; --profile is reserved for the four-file form
// and is ignored in run-dir form. In four-file form the profile comes
// from --profile, else from a run-metadata.json beside the findings
// file. There is no default profile: when no valid profile is
// available, or the available value is not a known profile, the
// checker fails closed (nonzero exit, run_status: incomplete).
//
// Exit 0 iff every confirmed / needs_validation record satisfies all
// rules; nonzero names the offending fingerprints, and the run is
// reported as run_status: incomplete (its findings are not publishable
// as verified).

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const AGENT_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const PROFILES = new Set(["quick", "standard", "deep"]);
const VERDICT_RANK = { rejected: 0, needs_validation: 1, confirmed: 2 };
const SEVERITY_RANK = {
  informational: 0,
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};
const ROLE_BY_FIELD = [
  ["hunter_agent_id", "hunter"],
  ["phase3_verifier_agent_id", "phase3_verifier"],
  ["phase5_verifier_agent_id", "phase5_verifier"],
  ["replacement_verifier_agent_id", "replacement_verifier"],
];
// The sidecar contract (verification-attestations.schema.md): each
// entry carries exactly these fields — all present, no extras.
const SIDECAR_FIELDS = [
  "hunter_agent_id",
  "phase3_verifier_agent_id",
  "phase5_verifier_agent_id",
  "replacement_verifier_agent_id",
  "confirmation_basis",
  "superseded_verdict",
  "superseded_severity",
  "static_rewalk",
  "findings_sha256",
  "ledger_sha256",
];
const INPUT_LIMIT_BYTES = 5 * 1024 * 1024;

function hasRank(table, value) {
  return Object.prototype.hasOwnProperty.call(table, value);
}

function sha256Hex(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function readArtifact(file) {
  const stat = fs.statSync(file);
  if (!stat.isFile()) throw new Error("input must be a regular file");
  if (stat.size > INPUT_LIMIT_BYTES) {
    throw new Error(`input exceeds ${INPUT_LIMIT_BYTES} byte limit`);
  }
  return fs.readFileSync(file);
}

function isUnderExamples(file) {
  return path.resolve(file).split(path.sep).includes("examples");
}

function parseArgs(argv) {
  const positional = [];
  let profile = null;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--profile") {
      profile = argv[i + 1] || null;
      i += 1;
    } else {
      positional.push(argv[i]);
    }
  }
  return { positional, profile };
}

// The profile of record in run-metadata.json. An absent, unreadable,
// profile-less, or unknown-profile metadata file is malformed input,
// not a cue to default: this throws and the caller fails closed.
function profileFromMetadata(dir) {
  const metadataPath = path.join(dir, "run-metadata.json");
  let raw;
  try {
    raw = fs.readFileSync(metadataPath, "utf8");
  } catch {
    throw new Error(
      `no valid profile: run-metadata.json is missing or unreadable in ${dir}`
    );
  }
  let metadata;
  try {
    metadata = JSON.parse(raw);
  } catch {
    throw new Error(
      `no valid profile: run-metadata.json in ${dir} is not valid JSON`
    );
  }
  if (
    !metadata ||
    typeof metadata.profile !== "string" ||
    !PROFILES.has(metadata.profile)
  ) {
    throw new Error(
      `no valid profile: run-metadata.json in ${dir} does not carry a known profile (quick, standard, or deep)`
    );
  }
  return metadata.profile;
}

function resolveInputs(positional, profileFlag) {
  if (positional.length === 1) {
    const dir = positional[0];
    if (!fs.statSync(dir).isDirectory()) {
      throw new Error("single argument must be a run directory");
    }
    return {
      findingsFile: path.join(dir, "findings.json"),
      ledgerFile: path.join(dir, "coverage-ledger.json"),
      sidecarFile: path.join(dir, "verification-attestations.json"),
      dispatchFile: path.join(dir, "dispatch-log.json"),
      // The run's recorded profile is the artifact of record: a
      // caller-supplied --profile must not override it in run-dir
      // form, so profileFlag is deliberately not consulted here.
      profile: profileFromMetadata(dir),
    };
  }
  if (positional.length === 4) {
    const [findingsFile, ledgerFile, sidecarFile, dispatchFile] = positional;
    let profile;
    if (profileFlag !== null) {
      if (!PROFILES.has(profileFlag)) {
        throw new Error(
          `no valid profile: --profile ${JSON.stringify(profileFlag)} is not a known profile (quick, standard, or deep)`
        );
      }
      profile = profileFlag;
    } else {
      profile = profileFromMetadata(path.dirname(path.resolve(findingsFile)));
    }
    return {
      findingsFile,
      ledgerFile,
      sidecarFile,
      dispatchFile,
      profile,
    };
  }
  throw new Error(
    "Usage: node scripts/audit/check_verifier_distinctness.cjs <run-dir> | " +
      "<findings.json> <coverage-ledger.json> <verification-attestations.json> " +
      "<dispatch-log.json> [--profile quick|standard|deep]"
  );
}

// The earliest dispatch-log entry for an agent in a role, or null.
function resolveDispatch(dispatch, agentId, role) {
  let best = null;
  let bestTime = Infinity;
  for (const entry of dispatch) {
    if (!entry || entry.agent_id !== agentId || entry.role !== role) continue;
    const time = Date.parse(entry.dispatched_at);
    const key = Number.isNaN(time) ? Infinity : time;
    if (key < bestTime) {
      best = entry;
      bestTime = key;
    }
  }
  return best;
}

function checkRun({ findings, ledger, sidecar, dispatch, profile, findingsSha, ledgerSha, examplesRun }) {
  const failures = [];
  const fail = (fingerprint, message) => failures.push({ fingerprint, message });

  if (!PROFILES.has(profile)) {
    fail("<run>", `unknown profile ${JSON.stringify(profile)}`);
    return failures;
  }

  const qualifying = findings.filter(
    (record) =>
      record &&
      (record.verdict === "confirmed" || record.verdict === "needs_validation")
  );

  // Completeness: exactly one sidecar entry per qualifying fingerprint,
  // and no sidecar entries for anything else.
  const qualifyingFingerprints = new Set();
  for (const record of qualifying) {
    if (typeof record.fingerprint === "string") {
      qualifyingFingerprints.add(record.fingerprint);
    }
  }
  for (const key of Object.keys(sidecar)) {
    if (!qualifyingFingerprints.has(key)) {
      fail(key, "sidecar entry has no confirmed/needs_validation finding");
    }
  }

  for (const record of qualifying) {
    const fp = record.fingerprint;
    if (typeof fp !== "string" || fp.length === 0) {
      fail("<unknown>", "qualifying record has no fingerprint");
      continue;
    }
    const entry = sidecar[fp];
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      fail(fp, "no attestation sidecar entry (absence is a fail)");
      continue;
    }

    // Field shape: every contract field must be present as an own
    // property (an absent field is not the same as an explicit null),
    // and no unknown fields may appear.
    for (const field of SIDECAR_FIELDS) {
      if (!Object.prototype.hasOwnProperty.call(entry, field)) {
        fail(fp, `sidecar ${field} is missing (field presence is required)`);
      }
    }
    for (const key of Object.keys(entry)) {
      if (!SIDECAR_FIELDS.includes(key)) {
        fail(fp, `sidecar entry has unknown field ${JSON.stringify(key)}`);
      }
    }
    const hunter = entry.hunter_agent_id;
    const phase3 = entry.phase3_verifier_agent_id;
    const phase5 = entry.phase5_verifier_agent_id;
    const replacement = entry.replacement_verifier_agent_id;
    if (typeof hunter !== "string" || hunter.length === 0) {
      fail(fp, "sidecar hunter_agent_id is missing or not a string");
    }
    if (typeof phase3 !== "string" || phase3.length === 0) {
      fail(fp, "sidecar phase3_verifier_agent_id is missing or not a string");
    }
    for (const [field, value] of [
      ["phase5_verifier_agent_id", phase5],
      ["replacement_verifier_agent_id", replacement],
      ["superseded_verdict", entry.superseded_verdict],
      ["superseded_severity", entry.superseded_severity],
    ]) {
      if (value !== null && typeof value !== "string") {
        fail(fp, `sidecar ${field} must be a string or null`);
      }
    }
    if (entry.confirmation_basis !== "static" && entry.confirmation_basis !== "execution") {
      fail(fp, 'sidecar confirmation_basis must be "static" or "execution"');
    }
    if (
      entry.static_rewalk !== null &&
      entry.static_rewalk !== "agreed" &&
      entry.static_rewalk !== "rebutted"
    ) {
      fail(fp, 'sidecar static_rewalk must be "agreed", "rebutted", or null');
    }

    // ID pattern and the reserved example-* prefix.
    const ids = [hunter, phase3, phase5, replacement].filter(
      (value) => typeof value === "string"
    );
    for (const id of ids) {
      if (!AGENT_ID_PATTERN.test(id)) {
        fail(fp, `agent ID ${JSON.stringify(id)} does not match the canonical ID pattern`);
      }
      if (!examplesRun && id.startsWith("example-")) {
        fail(fp, `agent ID ${JSON.stringify(id)} uses the reserved example-* prefix in a real run`);
      }
    }

    // Freshness binding.
    if (entry.findings_sha256 !== findingsSha) {
      fail(fp, "sidecar findings_sha256 does not match the findings file as checked");
    }
    if (entry.ledger_sha256 !== ledgerSha) {
      fail(fp, "sidecar ledger_sha256 does not match the ledger file as checked");
    }

    // Hunter anchor: the attested hunter owns a check on a ledger unit
    // whose result_fingerprints contain this fingerprint (protocol
    // §7.7). The anchor is check-level only: the unit's own agent_id
    // does not anchor the hunter.
    if (typeof hunter === "string") {
      const anchored = ledger.some((unit) => {
        if (!unit || !Array.isArray(unit.result_fingerprints)) return false;
        if (!unit.result_fingerprints.includes(fp)) return false;
        return (
          Array.isArray(unit.local_checks) &&
          unit.local_checks.some((check) => check && check.agent_id === hunter)
        );
      });
      if (!anchored) {
        fail(fp, "hunter anchor missing: no ledger unit carrying this fingerprint is owned by the attested hunter");
      }
    }

    // Distinctness (profile-aware).
    if (typeof hunter === "string" && typeof phase3 === "string" && hunter === phase3) {
      fail(fp, "hunter and Phase 3 verifier are the same agent");
    }
    if (typeof hunter === "string" && typeof phase5 === "string" && hunter === phase5) {
      fail(fp, "hunter and Phase 5 verifier are the same agent");
    }
    if (profile === "quick") {
      if (typeof phase5 !== "string" || phase5 !== phase3) {
        fail(fp, "quick profile requires phase5_verifier_agent_id == phase3_verifier_agent_id (merged Phase 3+5)");
      }
    } else if (typeof phase5 === "string" && phase5 === phase3) {
      fail(fp, "Phase 3 and Phase 5 verifiers are the same agent outside the quick profile");
    }

    // Materiality (mechanical, from recorded inputs): movement toward
    // confirmed, or a severity increase, between the sidecar's superseded
    // fields and the finding's current verdict/severity.
    let material = false;
    const supersededVerdict = entry.superseded_verdict;
    if (typeof supersededVerdict === "string") {
      if (!hasRank(VERDICT_RANK, supersededVerdict) || !hasRank(VERDICT_RANK, record.verdict)) {
        fail(fp, "superseded_verdict or current verdict is not a known verdict");
      } else if (VERDICT_RANK[record.verdict] > VERDICT_RANK[supersededVerdict]) {
        material = true;
      }
    }
    const supersededSeverity = entry.superseded_severity;
    const currentSeverity =
      record.severity && typeof record.severity === "object"
        ? record.severity.overall_severity
        : null;
    if (typeof supersededSeverity === "string") {
      if (!hasRank(SEVERITY_RANK, supersededSeverity)) {
        fail(fp, "superseded_severity is not a known severity");
      } else if (
        typeof currentSeverity === "string" &&
        hasRank(SEVERITY_RANK, currentSeverity) &&
        SEVERITY_RANK[currentSeverity] > SEVERITY_RANK[supersededSeverity]
      ) {
        material = true;
      }
    }
    if (material && (typeof replacement !== "string" || replacement.length === 0)) {
      fail(fp, "material replacement has no replacement_verifier_agent_id (a third verifier is required)");
    }
    if (typeof replacement === "string" && replacement.length > 0) {
      // The replacement's proposer is the Phase 5 verifier; the third
      // verifier must differ from the hunter, both phase verifiers, and
      // therefore from the proposer.
      for (const [label, other] of [
        ["hunter", hunter],
        ["Phase 3 verifier", phase3],
        ["Phase 5 verifier (the replacement's proposer)", phase5],
      ]) {
        if (replacement === other) {
          fail(fp, `replacement verifier is the same agent as the ${label}`);
        }
      }
    }

    // Static re-walk.
    if (
      record.verdict === "confirmed" &&
      entry.confirmation_basis === "static" &&
      entry.static_rewalk !== "agreed"
    ) {
      fail(fp, 'static-basis confirmed record requires static_rewalk "agreed"');
    }

    // Dispatch resolution, session distinctness, and ordering.
    const resolved = [];
    for (const [field, role] of ROLE_BY_FIELD) {
      const agentId = entry[field];
      if (typeof agentId !== "string" || agentId.length === 0) continue;
      const dispatchEntry = resolveDispatch(dispatch, agentId, role);
      if (!dispatchEntry) {
        fail(fp, `sidecar ${field} ${JSON.stringify(agentId)} has no dispatch-log entry with role ${JSON.stringify(role)}`);
        continue;
      }
      if (typeof dispatchEntry.session_id !== "string" || dispatchEntry.session_id.length === 0) {
        fail(fp, `dispatch entry for ${JSON.stringify(agentId)} (${role}) has no session_id`);
      }
      if (Number.isNaN(Date.parse(dispatchEntry.dispatched_at))) {
        fail(fp, `dispatch entry for ${JSON.stringify(agentId)} (${role}) has no valid dispatched_at`);
      }
      resolved.push({ field, role, agentId, dispatchEntry });
    }
    // Roles carried by different agents must carry distinct sessions.
    for (let i = 0; i < resolved.length; i += 1) {
      for (let j = i + 1; j < resolved.length; j += 1) {
        const a = resolved[i];
        const b = resolved[j];
        if (a.agentId === b.agentId) continue;
        if (
          a.dispatchEntry.session_id &&
          a.dispatchEntry.session_id === b.dispatchEntry.session_id
        ) {
          fail(fp, `roles ${a.role} and ${b.role} carry the same session_id for different agents`);
        }
      }
    }
    // Each verifier's dispatch postdates the hunter's dispatch.
    const hunterResolved = resolved.find((item) => item.role === "hunter");
    if (hunterResolved) {
      const hunterTime = Date.parse(hunterResolved.dispatchEntry.dispatched_at);
      for (const item of resolved) {
        if (item.role === "hunter") continue;
        const time = Date.parse(item.dispatchEntry.dispatched_at);
        if (!Number.isNaN(time) && !Number.isNaN(hunterTime) && time <= hunterTime) {
          fail(fp, `${item.role} was dispatched before (or at) the hunter's dispatch for this fingerprint`);
        }
      }
    }
  }

  return failures;
}

function run(argv) {
  let inputs;
  try {
    const { positional, profile } = parseArgs(argv);
    inputs = resolveInputs(positional, profile);
  } catch (error) {
    console.error("ERROR:", error.message);
    console.error("run_status: incomplete");
    return 1;
  }

  let findingsBuffer;
  let ledgerBuffer;
  let findings;
  let ledger;
  let sidecar;
  let dispatch;
  try {
    findingsBuffer = readArtifact(inputs.findingsFile);
    ledgerBuffer = readArtifact(inputs.ledgerFile);
    findings = JSON.parse(findingsBuffer.toString("utf8"));
    ledger = JSON.parse(ledgerBuffer.toString("utf8"));
    sidecar = JSON.parse(readArtifact(inputs.sidecarFile).toString("utf8"));
    dispatch = JSON.parse(readArtifact(inputs.dispatchFile).toString("utf8"));
  } catch (error) {
    console.error("Failed to read or parse run artifacts:", error.message);
    return 1;
  }
  if (!Array.isArray(findings)) {
    console.error("ERROR: findings must be a top-level array");
    return 1;
  }
  if (!Array.isArray(ledger)) {
    console.error("ERROR: coverage ledger must be a top-level array");
    return 1;
  }
  if (!sidecar || typeof sidecar !== "object" || Array.isArray(sidecar)) {
    console.error("ERROR: attestation sidecar must be a top-level object keyed by fingerprint");
    return 1;
  }
  if (!Array.isArray(dispatch)) {
    console.error("ERROR: dispatch log must be a top-level array");
    return 1;
  }

  const failures = checkRun({
    findings,
    ledger,
    sidecar,
    dispatch,
    profile: inputs.profile,
    findingsSha: sha256Hex(findingsBuffer),
    ledgerSha: sha256Hex(ledgerBuffer),
    examplesRun: isUnderExamples(inputs.findingsFile),
  });

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(`ERROR: ${failure.fingerprint}: ${failure.message}`);
    }
    console.error(`FAIL: ${failures.length} distinctness error(s)`);
    console.error("run_status: incomplete");
    return 1;
  }
  const count = findings.filter(
    (record) => record && (record.verdict === "confirmed" || record.verdict === "needs_validation")
  ).length;
  console.log(`PASS: ${count} verified record(s) satisfy finder/verifier distinctness`);
  return 0;
}

if (require.main === module) process.exit(run(process.argv.slice(2)));

module.exports = { checkRun };
