#!/usr/bin/env node
// Network posture: none — this validator performs no network I/O; it reads
// only the local profile schema, the vendored validator module, and the
// findings file named on the command line.
//
// AEP-owned profile validator for the audit lane. The vendored validator
// (reference/security-audit-skill/skills/security-audit/validate-findings.cjs)
// hardcodes its load of the vendored report-schema.json and can therefore
// never validate the AEP profile. This validator loads the profile schema
// (docs/security-audit-schema-profile.json) instead and validates a findings
// file the same way the vendored validator does (top-level array), reusing
// the vendored validator's exported document validation so schema
// interpretation and the finding-level semantic checks stay identical.
//
// The one semantic adjustment is profile delta P3 (see
// docs/security-audit-protocol.md): a trace entry of kind "composition" is
// a profile trace entry, so vendored trace-ordering errors that name a
// "composition" entry as the offending kind are not profile errors. Every
// other vendored error is reported unchanged.
//
// Usage: node scripts/audit/validate_findings_profile.cjs <path-to-findings.json>
// Exit 0 on PASS, nonzero on FAIL, with each violation named on stderr.

"use strict";

const fs = require("fs");
const path = require("path");

const PROFILE_SCHEMA_PATH = path.join(
  __dirname,
  "..",
  "..",
  "docs",
  "security-audit-schema-profile.json"
);
const VENDORED_VALIDATOR_PATH = path.join(
  __dirname,
  "..",
  "..",
  "reference",
  "security-audit-skill",
  "skills",
  "security-audit",
  "validate-findings.cjs"
);
const INPUT_LIMIT_BYTES = 5 * 1024 * 1024;

function traceKindAt(findings, errorMessage) {
  const match = /^\$\[(\d+)\]\.trace\[(\d+)\]\.kind:/.exec(errorMessage);
  if (!match) return null;
  const finding = findings[Number(match[1])];
  if (!finding || !Array.isArray(finding.trace)) return null;
  const entry = finding.trace[Number(match[2])];
  return entry && typeof entry.kind === "string" ? entry.kind : null;
}

function isProfileCompositionTraceError(findings, errorMessage) {
  // Delta P3 only: vendored ordering/one-entry errors whose offending trace
  // kind is "composition" (a kind the vendored schema does not know). The
  // schema-level enum error for "composition" cannot occur under the
  // profile schema, because the profile enum admits it.
  if (!errorMessage.includes(".trace[")) return false;
  return traceKindAt(findings, errorMessage) === "composition";
}

function run(file) {
  if (!file) {
    console.error(
      "Usage: node scripts/audit/validate_findings_profile.cjs <path-to-findings.json>"
    );
    return 1;
  }

  let vendored;
  try {
    vendored = require(VENDORED_VALIDATOR_PATH);
  } catch (error) {
    console.error("Failed to load vendored validator:", error.message);
    return 1;
  }

  let schema;
  try {
    schema = JSON.parse(fs.readFileSync(PROFILE_SCHEMA_PATH, "utf8"));
  } catch (error) {
    console.error("Failed to load profile schema:", error.message);
    return 1;
  }

  let findings;
  try {
    const stat = fs.statSync(file);
    if (!stat.isFile()) throw new Error("input must be a regular file");
    if (stat.size > INPUT_LIMIT_BYTES) {
      throw new Error(`input exceeds ${INPUT_LIMIT_BYTES} byte limit`);
    }
    findings = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    console.error("Failed to read or parse findings JSON:", error.message);
    return 1;
  }
  if (!Array.isArray(findings)) {
    console.error("ERROR: $: findings must be a top-level array");
    console.error("FAIL: 1 validation error(s)");
    return 1;
  }

  let errors;
  try {
    errors = vendored.validateDocument(findings, schema);
  } catch (error) {
    console.error("Failed to validate findings JSON:", error.message);
    return 1;
  }
  const profileErrors = errors.filter(
    (message) => !isProfileCompositionTraceError(findings, message)
  );

  for (const message of profileErrors) console.error("ERROR:", message);
  if (profileErrors.length > 0) {
    console.error(`FAIL: ${profileErrors.length} validation error(s)`);
    return 1;
  }
  console.log(`PASS: ${findings.length} findings valid (AEP profile)`);
  return 0;
}

if (require.main === module) process.exit(run(process.argv[2]));

module.exports = { isProfileCompositionTraceError };
