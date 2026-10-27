// Tests for scripts/audit/check_verifier_distinctness.cjs (Task A3).
// Run: node --test scripts/audit/test/check_verifier_distinctness.test.cjs
//
// Fixtures are small four-artifact run sets (findings + coverage ledger +
// attestation sidecar + dispatch log, plus run-metadata.json for the
// profile) constructed here and materialised into a temporary run
// directory per test. The clean fixture's freshness hashes are computed
// over the exact findings/ledger bytes written, so they genuinely match.

"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const checkerPath = path.join(__dirname, "..", "check_verifier_distinctness.cjs");
const { canonicalCoverageId } = require(path.join(
  __dirname,
  "..",
  "..",
  "..",
  "reference",
  "security-audit-skill",
  "skills",
  "security-audit",
  "validate-coverage-ledger.cjs"
));

const FP_ONE = "fp-candidate-one";
const FP_TWO = "fp-candidate-two";

function source(kind = "entrypoint", file = "src/handler.c", line = 10) {
  return { kind, file, line, scope: "handle", description: "Attacker data reaches the operation." };
}

function evidence(file = "src/handler.c", line = 10) {
  return { file, line, description: "The source performs the operation without the required check." };
}

function confirmedFinding() {
  return {
    verdict: "confirmed",
    fingerprint: FP_ONE,
    title: "Missing ownership check",
    description: "An attacker can reach an operation without the intended ownership check.",
    root_cause: "handle omits the ownership check before changing the object.",
    intended_behavior: "Only the object's owner can change it.",
    trace: [source("entrypoint"), source("propagation", "src/model.c", 20), source("sink", "src/store.c", 30)],
    evidence: [evidence()],
    conditions: [],
    execution: {
      attacker_perspective: "An unprivileged remote user with their own account.",
      payloads: ["An object identifier owned by another user."],
      instructions: ["Submit the identifier through the public operation."],
      observed_result: "The other user's object changes.",
    },
    remediation: { strategy: "Check ownership before the state change." },
    severity: {
      likelihood: { score: "medium", reason: "The operation is directly reachable." },
      impact: { score: "medium", reason: "The attacker changes one protected object." },
      overall_severity: "medium",
    },
    confidence: { score: "high", reason: "The source path and result were reproduced." },
  };
}

function needsValidationFinding() {
  return {
    verdict: "needs_validation",
    fingerprint: FP_TWO,
    title: "Unchecked parsed size",
    description: "A parsed size may reach an allocation without a limit.",
    claimed_root_cause: "parse_size may pass an unbounded value to allocate.",
    trace: [source()],
    evidence: [evidence()],
    blockers: ["no network-namespace isolation on this VM; target code would share host loopback"],
    validation_plan: {
      local: "Generate the parser and submit the smallest input that exceeds the documented limit.",
    },
  };
}

function sourceCheck(agentId) {
  return {
    agent_id: agentId,
    reviewed_paths: ["src/router.ts"],
    invariant: "The route checks object ownership.",
    method: "source",
    result: "The owner check applies before the update.",
    artifact: null,
  };
}

function candidateUnit(kind, fingerprint, hunterId) {
  const variants = {
    one: {
      canonicalRefs: {
        surface: "src/a.ts#one",
        boundary: "src/authz.ts#requireOwner",
        subsystem: "packages/api",
        attack_class: "ATTACK-CLASSES.md#Access control",
      },
      surface: "Update-user route",
      boundary: "Object ownership",
      subsystem: "API",
      attack_class: "Access control",
      starting_paths: ["src/router.ts", "src/authz.ts"],
      ordinary_attack_class_block: "ATTACK-CLASSES.md#Access control",
    },
    two: {
      canonicalRefs: {
        surface: "src/b.ts#two",
        boundary: "src/limits.ts#requireBound",
        subsystem: "packages/parser",
        attack_class: "ATTACK-CLASSES.md#Resource exhaustion",
      },
      surface: "Parser allocation",
      boundary: "Input length bound",
      subsystem: "Parser",
      attack_class: "Resource exhaustion",
      starting_paths: ["src/parser.ts", "src/limits.ts"],
      ordinary_attack_class_block: "ATTACK-CLASSES.md#Resource exhaustion",
    },
  };
  const variant = variants[kind];
  const canonicalRefs = variant.canonicalRefs;
  return {
    coverage_id: canonicalCoverageId(canonicalRefs),
    canonical_refs: canonicalRefs,
    surface: variant.surface,
    boundary: variant.boundary,
    subsystem: variant.subsystem,
    attack_class: variant.attack_class,
    starting_paths: variant.starting_paths,
    ordinary_attack_class_block: variant.ordinary_attack_class_block,
    selected_companion_blocks: [],
    excluded_blocks: [],
    prior_status: "new",
    attempts: [],
    wave: 1,
    status: "candidate",
    agent_id: hunterId,
    reviewed_paths: ["src/router.ts"],
    local_checks: [sourceCheck(hunterId)],
    result_fingerprints: [fingerprint],
    unresolved: [],
  };
}

function cleanLedger() {
  return [
    candidateUnit("one", FP_ONE, "hunter-1"),
    candidateUnit("two", FP_TWO, "hunter-1"),
  ].sort((a, b) => (a.coverage_id < b.coverage_id ? -1 : 1));
}

// Sidecar entries without the freshness hashes; materialise() injects the
// real hashes unless a test overrides them afterwards.
function cleanEntries() {
  return {
    [FP_ONE]: {
      hunter_agent_id: "hunter-1",
      phase3_verifier_agent_id: "verifier-1",
      phase5_verifier_agent_id: "verifier-2",
      replacement_verifier_agent_id: "verifier-3",
      confirmation_basis: "static",
      superseded_verdict: "needs_validation",
      superseded_severity: null,
      static_rewalk: "agreed",
    },
    [FP_TWO]: {
      hunter_agent_id: "hunter-1",
      phase3_verifier_agent_id: "verifier-1",
      phase5_verifier_agent_id: "verifier-2",
      replacement_verifier_agent_id: null,
      confirmation_basis: "execution",
      superseded_verdict: null,
      superseded_severity: null,
      static_rewalk: null,
    },
  };
}

function cleanDispatch() {
  return [
    { agent_id: "hunter-1", role: "hunter", session_id: "sess-hunter-1", dispatched_at: "2026-10-26T10:00:00Z" },
    { agent_id: "verifier-1", role: "phase3_verifier", session_id: "sess-verifier-1", dispatched_at: "2026-10-26T11:00:00Z" },
    { agent_id: "verifier-2", role: "phase5_verifier", session_id: "sess-verifier-2", dispatched_at: "2026-10-26T12:00:00Z" },
    { agent_id: "verifier-3", role: "replacement_verifier", session_id: "sess-verifier-3", dispatched_at: "2026-10-26T13:00:00Z" },
  ];
}

function sha256(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

// Build a run set, apply the test's mutation to the in-memory artifacts,
// write the run directory, and run the checker over it. By default the
// checker runs in run-dir form; data.form = "files" selects the
// four-file form, data.extraArgs appends CLI arguments (e.g. a
// --profile flag), data.omitMetadata drops run-metadata.json, and
// data.metadataProfile = null writes metadata with no profile key.
function runChecker(mutate) {
  const data = {
    profile: "standard",
    findings: [confirmedFinding(), needsValidationFinding()],
    ledger: cleanLedger(),
    entries: cleanEntries(),
    dispatch: cleanDispatch(),
    sidecarMutate: null,
    form: "dir",
    extraArgs: [],
    omitMetadata: false,
    metadataProfile: undefined,
  };
  if (mutate) mutate(data);

  const findingsText = JSON.stringify(data.findings, null, 2);
  const ledgerText = JSON.stringify(data.ledger, null, 2);
  for (const entry of Object.values(data.entries)) {
    entry.findings_sha256 = sha256(findingsText);
    entry.ledger_sha256 = sha256(ledgerText);
  }
  if (data.sidecarMutate) data.sidecarMutate(data.entries);

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "a3-run-"));
  try {
    fs.writeFileSync(path.join(dir, "findings.json"), findingsText);
    fs.writeFileSync(path.join(dir, "coverage-ledger.json"), ledgerText);
    fs.writeFileSync(
      path.join(dir, "verification-attestations.json"),
      JSON.stringify(data.entries, null, 2)
    );
    fs.writeFileSync(path.join(dir, "dispatch-log.json"), JSON.stringify(data.dispatch, null, 2));
    if (!data.omitMetadata) {
      const metadata = { run_id: "a3-fixture", run_status: "complete" };
      const metadataProfile =
        data.metadataProfile === undefined ? data.profile : data.metadataProfile;
      if (metadataProfile !== null) metadata.profile = metadataProfile;
      fs.writeFileSync(
        path.join(dir, "run-metadata.json"),
        JSON.stringify(metadata, null, 2)
      );
    }
    const args =
      data.form === "files"
        ? [
            checkerPath,
            path.join(dir, "findings.json"),
            path.join(dir, "coverage-ledger.json"),
            path.join(dir, "verification-attestations.json"),
            path.join(dir, "dispatch-log.json"),
            ...data.extraArgs,
          ]
        : [checkerPath, dir, ...data.extraArgs];
    const result = spawnSync(process.execPath, args, { encoding: "utf8" });
    return { status: result.status, output: `${result.stdout}${result.stderr}` };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function assertFailsNaming(result, fingerprint) {
  assert.notEqual(result.status, 0, `expected nonzero exit, got 0: ${result.output}`);
  assert.ok(
    result.output.includes(fingerprint),
    `expected failure output to name ${fingerprint}, got: ${result.output}`
  );
}

test("(a) hunter == phase3 verifier fails naming the fingerprint", () => {
  const result = runChecker((data) => {
    data.entries[FP_ONE].phase3_verifier_agent_id = "hunter-1";
  });
  assertFailsNaming(result, FP_ONE);
});

test("(b) hunter anchor missing fails", () => {
  const result = runChecker((data) => {
    // No ledger unit carrying FP_ONE is owned by / checked by hunter-1.
    data.ledger = data.ledger.map((unit) =>
      unit.result_fingerprints.includes(FP_ONE)
        ? { ...unit, agent_id: "hunter-9", local_checks: [sourceCheck("hunter-9")] }
        : unit
    );
  });
  assertFailsNaming(result, FP_ONE);
});

test("(b2) unit-owner-only hunter match does not anchor the hunter", () => {
  const result = runChecker((data) => {
    // The unit carrying FP_ONE keeps agent_id == hunter-1 (the unit
    // owner), but no check on that unit carries the hunter's agent_id:
    // the anchor is check-level only, so this must fail.
    data.ledger = data.ledger.map((unit) =>
      unit.result_fingerprints.includes(FP_ONE)
        ? { ...unit, local_checks: [sourceCheck("hunter-9")] }
        : unit
    );
  });
  assertFailsNaming(result, FP_ONE);
});

test("(c) material strengthening with only two distinct agents fails", () => {
  const result = runChecker((data) => {
    // FP_ONE is material (superseded needs_validation -> confirmed), but
    // the replacement verifier is the Phase 3 verifier: the only distinct
    // agents are hunter-1 and verifier-1, and there is no Phase 5 record.
    data.entries[FP_ONE].phase5_verifier_agent_id = null;
    data.entries[FP_ONE].replacement_verifier_agent_id = "verifier-1";
  });
  assertFailsNaming(result, FP_ONE);
});

test("(c2) material strengthening with replacement_verifier_agent_id null fails", () => {
  const result = runChecker((data) => {
    // FP_ONE is material on its own (superseded needs_validation ->
    // confirmed) and every other rule is satisfied by distinct agents,
    // so only the material-presence rule can fail this fixture:
    // deleting that rule would turn it green.
    data.entries[FP_ONE].replacement_verifier_agent_id = null;
  });
  assertFailsNaming(result, FP_ONE);
});

test("(d) clean two-candidate run passes", () => {
  const result = runChecker(null);
  assert.equal(result.status, 0, result.output);
  assert.match(result.output, /PASS/);
});

test("(e) record with no sidecar entry fails", () => {
  const result = runChecker((data) => {
    delete data.entries[FP_TWO];
  });
  assertFailsNaming(result, FP_TWO);
});

test("(f) example-* ID in a run directory not under examples/ fails", () => {
  const result = runChecker((data) => {
    data.entries[FP_ONE].phase3_verifier_agent_id = "example-verifier-1";
    data.dispatch.push({
      agent_id: "example-verifier-1",
      role: "phase3_verifier",
      session_id: "sess-example-1",
      dispatched_at: "2026-10-26T11:30:00Z",
    });
  });
  assertFailsNaming(result, FP_ONE);
});

test("(g) static-basis confirmed without static_rewalk agreed fails", () => {
  const result = runChecker((data) => {
    data.entries[FP_ONE].static_rewalk = null;
  });
  assertFailsNaming(result, FP_ONE);
});

test("(h) quick profile with phase3 == phase5 and distinct hunter passes", () => {
  const result = runChecker((data) => {
    data.profile = "quick";
    for (const entry of Object.values(data.entries)) {
      entry.phase5_verifier_agent_id = entry.phase3_verifier_agent_id;
    }
    // The merged Phase 3+5 pass is dispatched to the same agent in the
    // same session as its Phase 3 dispatch.
    data.dispatch.push({
      agent_id: "verifier-1",
      role: "phase5_verifier",
      session_id: "sess-verifier-1",
      dispatched_at: "2026-10-26T12:00:00Z",
    });
  });
  assert.equal(result.status, 0, result.output);
  assert.match(result.output, /PASS/);
});

test("(i) freshness hash mismatch fails", () => {
  const result = runChecker((data) => {
    data.sidecarMutate = (entries) => {
      entries[FP_ONE].findings_sha256 = "0".repeat(64);
    };
  });
  assertFailsNaming(result, FP_ONE);
});

test("(j) verifier dispatched before the hunter fails", () => {
  const result = runChecker((data) => {
    for (const entry of data.dispatch) {
      if (entry.agent_id === "verifier-1" && entry.role === "phase3_verifier") {
        entry.dispatched_at = "2026-10-26T09:00:00Z";
      }
    }
  });
  assertFailsNaming(result, FP_ONE);
});

test("(k) run-dir --profile cannot override the run's recorded standard profile", () => {
  const result = runChecker((data) => {
    // Standard profile of record, but phase3 == phase5 for FP_ONE: a
    // fail under standard. Re-invoking with --profile quick must not
    // turn it into a pass; the metadata profile governs run-dir form.
    data.entries[FP_ONE].phase5_verifier_agent_id =
      data.entries[FP_ONE].phase3_verifier_agent_id;
    // Give the merged pass a dispatch record too, so that if --profile
    // quick were (wrongly) honoured every quick rule would pass and
    // only the recorded standard profile can fail this fixture.
    data.dispatch.push({
      agent_id: "verifier-1",
      role: "phase5_verifier",
      session_id: "sess-verifier-1",
      dispatched_at: "2026-10-26T12:30:00Z",
    });
    data.extraArgs = ["--profile", "quick"];
  });
  assertFailsNaming(result, FP_ONE);
});

test("(l) run-dir with missing run-metadata.json fails closed", () => {
  const result = runChecker((data) => {
    data.omitMetadata = true;
  });
  assert.notEqual(result.status, 0, `expected nonzero exit, got 0: ${result.output}`);
  assert.ok(
    result.output.includes("run_status: incomplete"),
    `expected run_status: incomplete in output, got: ${result.output}`
  );
});

test("(m) run-dir with profile-less run-metadata.json fails closed", () => {
  const result = runChecker((data) => {
    data.metadataProfile = null;
  });
  assert.notEqual(result.status, 0, `expected nonzero exit, got 0: ${result.output}`);
  assert.ok(
    result.output.includes("run_status: incomplete"),
    `expected run_status: incomplete in output, got: ${result.output}`
  );
});

test("(n) four-file form with no profile from --profile or metadata fails closed", () => {
  const result = runChecker((data) => {
    data.form = "files";
    data.omitMetadata = true;
  });
  assert.notEqual(result.status, 0, `expected nonzero exit, got 0: ${result.output}`);
  assert.ok(
    result.output.includes("run_status: incomplete"),
    `expected run_status: incomplete in output, got: ${result.output}`
  );
});

test("(o) sidecar entry missing a contract field fails naming the fingerprint", () => {
  const result = runChecker((data) => {
    // Omitting superseded_verdict must not read as "replaced nothing":
    // field presence is required, distinct from an explicit null.
    data.sidecarMutate = (entries) => {
      delete entries[FP_ONE].superseded_verdict;
    };
  });
  assertFailsNaming(result, FP_ONE);
});

test("(p) sidecar entry with an unknown extra field fails naming the fingerprint", () => {
  const result = runChecker((data) => {
    data.sidecarMutate = (entries) => {
      entries[FP_ONE].extra_field = "verifier-9";
    };
  });
  assertFailsNaming(result, FP_ONE);
});

test("(q) sidecar entry with an unknown superseded_verdict rank fails", () => {
  const result = runChecker((data) => {
    data.entries[FP_ONE].superseded_verdict = "bogus";
  });
  assertFailsNaming(result, FP_ONE);
});
