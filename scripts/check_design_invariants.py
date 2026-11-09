#!/usr/bin/env python3
"""Section-aware design invariant checker for PR #133.

Reads the four AEP design documents, binds each assertion to the section that
owns it, and fails closed when a section is missing. The checker is deliberately
structural: run-spec checks read the <pre> block, table checks read the <tr>,
and card checks read the item card. A prose negation elsewhere does not satisfy
or defeat a check.
"""

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = {
    "lld": ROOT / "docs/plan/aep-lld-v1.1.html",
    "hld": ROOT / "docs/plan/aep-hld-v1.1.html",
    "backlog": ROOT / "docs/plan/aep-backlog-v1.1.html",
    "draft": ROOT / "docs/draft-proposal.html",
}

HEADING_RE = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
PRE_RE = re.compile(r"<pre><code>(.*?)</code></pre>", re.I | re.S)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
CARD_RE = re.compile(r'<div class="item-card">', re.I)
AC_RE = re.compile(r'<div class="ac-box">(.*?)</div>', re.I | re.S)


def text_of(fragment):
    return html.unescape(TAG_RE.sub(" ", fragment)).replace("\xa0", " ")


def section(doc, needle):
    """Return the body of the first h2/h3 whose heading contains needle."""
    matches = list(HEADING_RE.finditer(doc))
    for i, match in enumerate(matches):
        title = text_of(match.group(2)).strip()
        if needle.lower() in title.lower():
            end = matches[i + 1].start() if i + 1 < len(matches) else len(doc)
            return doc[match.end():end]
    return ""


def pre_blocks(fragment):
    return [html.unescape(m.group(1)) for m in PRE_RE.finditer(fragment)]


def rows(fragment):
    return [text_of(m.group(1)) for m in ROW_RE.finditer(fragment)]


def row(fragment, needle):
    for candidate in rows(fragment):
        if needle.lower() in candidate.lower():
            return candidate
    return ""


def card(doc, key):
    starts = [m.start() for m in CARD_RE.finditer(doc)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(doc)
        candidate = doc[start:end]
        if key.lower() in text_of(candidate).lower():
            return candidate
    return ""


def ac_box(fragment):
    match = AC_RE.search(fragment)
    return match.group(1) if match else ""


def add(errors, check, message):
    errors.append(f"{check}: {message}")


def need(errors, check, label, text, pattern):
    if not re.search(pattern, text, re.I | re.S):
        add(errors, check, f"missing {label}")


def forbid(errors, check, label, text, pattern):
    if re.search(pattern, text, re.I | re.S):
        add(errors, check, f"forbidden {label}")


def check_c9_1(docs, errors):
    lld41 = section(docs["lld"], "4.1")
    lld49 = section(docs["lld"], "4.9")
    if not lld41:
        add(errors, "C9-1", "missing LLD §4.1")
        return
    if not lld49:
        add(errors, "C9-1", "missing LLD §4.9")
        return
    need(errors, "C9-1", "Backend struct", lld41, r"type\s+Backend\s+struct")
    need(errors, "C9-1", "Requirement struct", lld41, r"type\s+Requirement\s+struct")
    need(errors, "C9-1", "NoFloor", lld41, r"func\s+NoFloor\s*\(")
    need(errors, "C9-1", "AtLeast requirement", lld41, r"func\s+AtLeast\s*\(")
    need(errors, "C9-1", "Requirement.MetBy", lld41, r"func\s*\(r\s+Requirement\)\s+MetBy")
    need(errors, "C9-1", "Tier2Supported method", lld41, r"func\s*\(p\s+Profile\)\s+Tier2Supported\s*\(")
    need(errors, "C9-1", "KVMProbe", lld41, r"KVMProbe")
    forbid(errors, "C9-1", "stored Tier2Supported bool", lld41, r"Tier2Supported\s+bool")
    need(errors, "C9-1", "BackendKind", lld49, r"BackendKind")
    need(errors, "C9-1", "NewBackend", lld49, r"func\s+NewBackend\s*\(")
    forbid(errors, "C9-1", "duplicate SandboxBackend enum", lld49, r"type\s+SandboxBackend\s+string")


def check_c9_2(docs, errors):
    hld9 = section(docs["hld"], "9. Governance")
    hld11 = section(docs["hld"], "11. Risks")
    if not hld9:
        add(errors, "C9-2", "missing HLD §9")
    if not hld11:
        add(errors, "C9-2", "missing HLD §11")
    combined = hld9 + hld11
    need(errors, "C9-2", "KVMProbe", combined, r"KVMProbe")
    need(errors, "C9-2", "derived Tier2Supported", combined, r"Tier2Supported\s*\(\s*\)|Tier2Supported[^.]{0,80}(derived|from\s+Backend)")
    forbid(errors, "C9-2", "Tier2Supported from KVM probe", combined, r"set\s+`?Tier2Supported`?\s+from\s+the\s+result")


def check_c6(docs, errors):
    lld6 = section(docs["lld"], "6. Admission")
    if not lld6:
        add(errors, "C6", "missing LLD §6")
        return
    pre = "\n".join(pre_blocks(lld6))
    if not pre:
        add(errors, "C6", "missing admission pseudocode")
        return
    forbid(errors, "C6", "unsigned subtraction", pre, r"host\s*-\s*req\.MemMiB\s*\*\s*MiB\s*<")
    need(errors, "C6", "checked host comparison", pre, r"host\s*<\s*reqBytes")
    need(errors, "C6", "overflow error", pre, r"err\s*!=\s*nil")
    need(errors, "C6", "zero request rejection", pre, r"req\.MemMiB\s*==\s*0")


def check_c7(docs, errors):
    lld93 = section(docs["lld"], "9.3")
    pre = "\n".join(pre_blocks(lld93))
    if not pre:
        add(errors, "C7", "missing LLD §9.3 run spec")
    else:
        need(errors, "C7", "exec.sock", pre, r"exec\.sock")
        need(errors, "C7", "AEP_EXEC_SOCKET", pre, r"AEP_EXEC_SOCKET")
        forbid(errors, "C7", "model.sock in lane", pre, r"model\.sock")
        forbid(errors, "C7", "provider key", pre, r"ANTHROPIC_API_KEY|OPENAI_API_KEY|GITHUB_TOKEN")
    hld4 = section(docs["hld"], "4. System architecture")
    hld52 = section(docs["hld"], "5.2")
    combined = hld4 + hld52
    need(errors, "C7", "host harness", combined, r"host\s+harness")
    need(errors, "C7", "model outside lane", combined, r"model\s+inference[^.]{0,120}(outside|host)")
    forbid(errors, "C7", "lane engine harness", combined, r"Engine:\s*opencode2")


def check_c10(docs, errors):
    lld93 = section(docs["lld"], "9.3")
    pre = "\n".join(pre_blocks(lld93))
    if not pre:
        add(errors, "C10", "missing LLD §9.3 run spec")
    else:
        need(errors, "C10", "git.sock", pre, r"git\.sock")
        need(errors, "C10", "AEP_GIT_SOCKET", pre, r"AEP_GIT_SOCKET")
        need(errors, "C10", "workspace .git mask", pre, r"/workspace/\.git")
        forbid(errors, "C10", "host .git mount", pre, r"-v\s+\"?\$?(?:AEP_)?REPO/\.git")
    cap1 = card(docs["backlog"], "CAP-01")
    if not cap1:
        add(errors, "C10", "missing backlog CAP-01")
    else:
        need(errors, "C10", "exec.sock AC", cap1, r"exec\.sock")
        need(errors, "C10", "git.sock AC", cap1, r"git\.sock")
        forbid(errors, "C10", "lane-local index", cap1, r"GIT_INDEX_FILE")


def check_c11(docs, errors):
    cap7 = card(docs["backlog"], "CAP-07")
    if not cap7:
        add(errors, "C11", "missing backlog CAP-07")
        return
    ac = ac_box(cap7)
    need(errors, "C11", "total RAM floor", ac, r"TotalRAM\s*(?:&gt;=|>=)\s*7\.5\s*GiB")
    need(errors, "C11", "busy-host AC", ac, r"AC-07\.3")
    need(errors, "C11", "available memory admission", ac, r"available\s+(?:RAM|memory)|AvailableBytes")
    forbid(errors, "C11", "minimum against available RAM", ac, r"less\s+than\s+8\s*GB\s+available")


def check_c12(docs, errors):
    pr11b = row(docs["backlog"], "PR-11b")
    hld9 = section(docs["hld"], "9. Governance")
    lld3 = section(docs["lld"], "3. As-built")
    lld11 = section(docs["lld"], "11. Test plan")
    draft = docs["draft"]
    combined = pr11b + hld9 + lld3 + lld11
    if not pr11b:
        add(errors, "C12", "missing backlog PR-11b")
    need(errors, "C12", "StdoutSha", combined, r"StdoutSha|stdout_sha")
    need(errors, "C12", "StderrSha", combined, r"StderrSha|stderr_sha")
    need(errors, "C12", "Nonce", combined, r"Nonce")
    need(errors, "C12", "LedgerSeq", combined, r"LedgerSeq")
    need(errors, "C12", "Signature", combined, r"Signature|Ed25519")
    forbid(errors, "C12", "tail-only digest claim", draft, r"tail\s+digest")
    need(errors, "C12", "full-stream digest", draft, r"full[-\s]?stream\s+digest")


def check_c8(docs, errors):
    hld8 = section(docs["hld"], "8. Dispatch")
    hld9 = section(docs["hld"], "9. Governance")
    lld12 = section(docs["lld"], "12. Implementation")
    draft_card = section(docs["draft"], "Sandboxed Re-Verification")
    combined = hld8 + hld9 + lld12 + draft_card
    need(errors, "C8", "Requirement floor", combined, r"Requirement|MinIsolation")
    forbid(errors, "C8", "unconditional hardware microVM reverify", hld9, r"must\s+execute\s+inside\s+a\s+fresh\s+hardware-isolated\s+microVM")
    forbid(errors, "C8", "unconditional microVM reverify in dispatch", hld8, r"fresh,\s+disposable\s+Tier-2\s+microVM\s+sandbox")
    need(errors, "C8", "C4 draft floor", draft_card, r"Requirement|MinIsolation")


def check_c5(docs, errors):
    hld6 = section(docs["hld"], "6. Scalable")
    nano = row(hld6, "nano-8g")
    if not nano:
        add(errors, "C5", "missing HLD nano row")
    else:
        need(errors, "C5", "substrate 2560 MiB", nano, r"2560\s*MiB")
        need(errors, "C5", "tier1 3584 MiB", nano, r"3584\s*MiB")
        need(errors, "C5", "tier2 1536 MiB", nano, r"1536\s*MiB")
        forbid(errors, "C5", "nano Tier 2 disabled", nano, r"Tier\s*2\s+(?:disabled|off)")
    lld41 = section(docs["lld"], "4.1")
    need(errors, "C5", "nano max tier1 lanes", lld41, r"MaxTier1Lanes[^\n]*1\s*\(nano\)")
    need(errors, "C5", "nano tier1 budget", lld41, r"Tier1BudgetMiB[^\n]*3584")
    need(errors, "C5", "nano tier2 budget", lld41, r"Tier2BudgetMiB[^\n]*1536")
    need(errors, "C5", "nano max tier2 lanes", lld41, r"MaxTier2Lanes[^\n]*1\s*\(nano\)")
    forbid(errors, "C5", "Tier 2 off in profile", lld41, r"Tier\s*2\s+off")
    need(errors, "C5", "budget sum", lld41 + hld6, r"7680")
    draft_nano = row(docs["draft"], "nano-8g")
    need(errors, "C5", "draft nano tier1", draft_nano, r"3584\s*MiB")
    need(errors, "C5", "draft nano tier2", draft_nano, r"1536\s*MiB")
    forbid(errors, "C5", "draft nano disabled", docs["draft"], r"Tier\s*2\s+disabled")


def check_c1(docs, errors):
    lld49 = section(docs["lld"], "4.9")
    need(errors, "C1", "VerifyEgressProbe digest", lld49, r"VerifyEgressProbe[^.]{0,160}SHA-256\s+digest")


def check_c2(docs, errors):
    hld9 = section(docs["hld"], "9. Governance")
    lld7 = section(docs["lld"], "7. Dispatch")
    lld82 = section(docs["lld"], "8.2")
    draft_c2 = card(docs["draft"], "C2")
    combined = hld9 + lld7 + draft_c2
    need(errors, "C2", "override", combined, r"override")
    need(errors, "C2", "decision record", lld82, r"decision record|Decision record")
    need(errors, "C2", "operator identity", lld82, r"operator|actor")


def check_c3(docs, errors):
    lld44 = section(docs["lld"], "4.4")
    lld45 = section(docs["lld"], "4.5")
    lld92 = section(docs["lld"], "9.2")
    combined = lld44 + lld45 + lld92
    need(errors, "C3", "relay.Handler", combined, r"relay\.Handler")
    need(errors, "C3", "memory.sock", combined, r"memory\.sock")
    need(errors, "C3", "ghg.sock", combined, r"ghg\.sock")


CHECKS = [
    ("C9-1", check_c9_1),
    ("C9-2", check_c9_2),
    ("C6", check_c6),
    ("C7", check_c7),
    ("C10", check_c10),
    ("C11", check_c11),
    ("C12", check_c12),
    ("C8", check_c8),
    ("C5", check_c5),
    ("C1", check_c1),
    ("C2", check_c2),
    ("C3", check_c3),
]


def run_check(docs):
    errors = []
    for _name, fn in CHECKS:
        fn(docs, errors)
    return errors


def load_docs():
    missing = [str(path) for path in DOCS.values() if not path.exists()]
    if missing:
        return None, missing
    return {name: path.read_text(encoding="utf-8") for name, path in DOCS.items()}, []


# Each mutation must make the named check fail. This is the negative fixture
# corpus: a check that still passes after its load-bearing token is removed is
# not a guard.
MUTATIONS = {
    "C9-1": [("lld", "func (r Requirement) MetBy", "func (r Requirement) NotMet")],
    "C9-2": [("hld", "KVMProbe", "ProbeOnly")],
    "C6": [("lld", "host &lt; reqBytes", "host &gt; reqBytes")],
    "C7": [("lld", "exec.sock", "exec_socket")],
    "C10": [("lld", "git.sock", "git_socket")],
    "C11": [("backlog", "AC-07.3", "AC-07.9")],
    "C12": [
        ("backlog", "Signature", "SigRemoved"),
        ("backlog", "signature", "sigremoved"),
        ("backlog", "Ed25519", "EdRemoved"),
        ("hld", "Signature", "SigRemoved"),
        ("hld", "signature", "sigremoved"),
        ("hld", "Ed25519", "EdRemoved"),
        ("lld", "signature", "sigremoved"),
    ],
    "C8": [
        ("hld", "Requirement", "ReqFloor"),
        ("hld", "MinIsolation", "IsolationFloor"),
        ("lld", "Requirement", "ReqFloor"),
        ("lld", "MinIsolation", "IsolationFloor"),
        ("draft", "Requirement", "ReqFloor"),
        ("draft", "MinIsolation", "IsolationFloor"),
    ],
    "C5": [("hld", "3584 MiB", "4096 MiB")],
    "C1": [("lld", "SHA-256 digest", "SHA-256")],
    "C2": [("lld", "decision record", "decision")],
    "C3": [("lld", "relay.Handler", "relay.Protocol")],
}


def self_test():
    """Test primitives and the negative mutation corpus."""
    sample = """
    <h2>4. System architecture</h2>
    <p>host harness runs model inference outside the lane</p>
    <h2>5. Components</h2>
    <h3>5.2 Execution lanes</h3>
    <p>host harness</p>
    """
    ok = True
    if "host harness" not in section(sample, "5.2"):
        print("self-test: section extraction failed")
        ok = False
    if section(sample, "missing"):
        print("self-test: missing section did not return empty")
        ok = False
    errors = []
    need(errors, "self", "token", "no matching token here", r"model\.sock")
    if not errors:
        print("self-test: missing-token detection failed")
        ok = False
    errors = []
    forbid(errors, "self", "token", "we do not use model.sock", r"model\.sock")
    if not errors:
        print("self-test: forbidden-token detection failed")
        ok = False

    docs, missing = load_docs()
    if missing:
        print("self-test: cannot load docs:", ", ".join(missing))
        return 1
    baseline = run_check(docs)
    if baseline:
        print("self-test: docs are not clean; cannot run mutation corpus")
        for error in baseline:
            print(" -", error)
        return 1
    for check, replacements in MUTATIONS.items():
        mutated = dict(docs)
        for doc_key, old, new in replacements:
            if old not in mutated[doc_key]:
                print(f"self-test: mutation token missing for {check}: {old!r}")
                ok = False
                break
            mutated[doc_key] = mutated[doc_key].replace(old, new)
        else:
            errors = run_check(mutated)
            if not any(error.startswith(check + ":") for error in errors):
                print(f"self-test: mutation did not trip {check}")
                ok = False
    if ok:
        print("self-test: OK")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    docs, missing = load_docs()
    if missing:
        print("missing documents:")
        for path in missing:
            print(" -", path)
        return 2
    errors = run_check(docs)
    if errors:
        print(f"{len(errors)} design invariant violation(s):")
        for error in errors:
            print(" -", error)
        return 1
    print("design invariants: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
