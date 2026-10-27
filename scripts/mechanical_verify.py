#!/usr/bin/env python3
"""Allowlist mechanical verifier.

Discovers verification commands from a fixed allowlist of project markers,
then runs them bounded (per-command timeout, tail-capped output) and
budgeted (overall wall-clock budget, memory preflight), stopping at the
first failure. Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import configparser
import ctypes
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_CAP_BYTES = 65536
SCAN_CHARS = 65536
MIN_MEMORY_KB = 524288  # 512 MiB
TERM_GRACE_SECONDS = 0.75
SWEEP_BOUND_SECONDS = 2.0

MARKDOWNLINT_ARGV = (
    "markdownlint-cli2",
    "**/*.md",
    "!reference/esf/**/*.md",
    "!reference/neurostrata/**/*.md",
    "!skills/archify/**/*.md",
)

# pytest verbosity is an additive counter across the project's
# addopts and the command line. The old -q spent one quiet level
# here, and a project with `addopts = -q` stacked to -qq, which
# suppresses the terminal summary entirely: a passing run printed
# only `. [100%]`, parsed to zero collected, and was rejected
# (Codex P2, round 5). -v nets +1, so project addopts down to -qq
# still leave the summary alive. The collected count no longer
# depends on that summary alone (issue #53): run_verification
# takes it from the run's junitxml report — written outside the
# tree, independent of verbosity — and the summary remains as the
# cross-check the report is judged against whenever verbosity
# left one (see _pytest_collected_count).
PYTEST_ARGV = ("python3", "-m", "pytest", "-v")


@dataclass(frozen=True)
class VerificationCommand:
    id: str
    label: str
    argv: tuple[str, ...]
    # A leg that exists only through classification uncertainty
    # (an unresolved class base, a star-import-open module) is
    # marked speculative at discovery: run_all judges its clean
    # zero collection against the union of the run instead of
    # letting it veto a run another Python leg passed
    # (issue #51). Deterministic legs leave this False.
    speculative: bool = False


@dataclass(frozen=True)
class VerificationResult:
    command: VerificationCommand
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: str
    stderr: str
    output_truncated: bool
    survivors_killed: tuple[int, ...] = ()
    survivors_remaining: bool = False
    tests_collected: int | None = None
    # The raw capped bytes behind stdout/stderr, exactly as captured
    # (issue #38). Receipts hash these, never the lossy decode above.
    # None only for hand-built results that never went through
    # run_verification; append_receipt then falls back to encoding
    # the text, which is byte-identical for valid UTF-8 output.
    stdout_bytes: bytes | None = None
    stderr_bytes: bytes | None = None

    @property
    def passed(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.survivors_remaining
            and self.tests_collected != 0
            # A Python leg whose collected count is unproven
            # (None — e.g. a pytest run whose junitxml report
            # channel produced nothing, issue #53 round 2) fails
            # the gate exactly like a proven zero: the gate's
            # question is whether the leg PROVED it collected
            # tests, and an absent proof is not a pass. For
            # non-Python commands the count never applies —
            # _count_collected returns None for them by design.
            and not (
                self.command.id in _PYTHON_LEG_IDS
                and self.tests_collected is None
            )
        )


# Assignment values that are provably NOT callables: literal data
# displays. An assignment binding a pytest-collectable name to
# anything else (a name, a lambda, a call result, ...) may have put
# a pytest-collectable function or class in the module namespace.
_NON_CALLABLE_VALUE_TYPES = (
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.JoinedStr,
)


def _assignment_target_names(target: ast.expr) -> list[str]:
    """Names bound by one assignment target (plain or unpacked)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_assignment_target_names(element))
        return names
    return []


def _binds_pytest_collectable(
    name: str, value_is_testcase: bool
) -> bool:
    """Whether binding `name` to a possibly-callable value is pytest
    evidence: pytest collects `test_*` functions and `Test*` classes
    from the module namespace, however they were bound. A `Test*`
    name bound to a value that provably denotes TestCase denotes
    unittest's own class instead — the binding is a TestCase alias,
    not a pytest-only class."""
    if name.startswith("test_"):
        return True
    return name.startswith("Test") and not value_is_testcase


def _value_denotes_testcase(
    value: ast.expr, testcase_names: set[str]
) -> bool:
    """Whether an assignment value provably denotes unittest's
    TestCase: its dotted name ends in `TestCase`, or it is a name
    already recorded as a TestCase alias."""
    value_name = _dotted_name(value)
    return value_name is not None and (
        value_name.rsplit(".", 1)[-1] == "TestCase"
        or value_name in testcase_names
    )


def _assignment_target_triggers(
    target: ast.expr, value: ast.expr, testcase_names: set[str]
) -> bool:
    """Whether binding `target` to `value` puts a pytest-collectable
    name in the module namespace.

    A plain name target is judged against the whole value (the
    round 7/9 rule: the name triggers unless the value is provably
    non-callable literal data). An unpacking target — a tuple or
    list of names — whose value is a tuple or list is judged by
    `_unpacking_triggers` (per element where correspondence is
    determinate; issue #52). Where the value is not a sequence
    display there is no per-element correspondence, and the
    level's names fall back to the whole-value rule against that
    value.
    """
    if isinstance(target, ast.Name):
        return not isinstance(
            value, _NON_CALLABLE_VALUE_TYPES
        ) and _binds_pytest_collectable(
            target.id, _value_denotes_testcase(value, testcase_names)
        )
    if isinstance(target, (ast.Tuple, ast.List)):
        if isinstance(value, (ast.Tuple, ast.List)):
            return _unpacking_triggers(
                target.elts, value.elts, testcase_names
            )
        if isinstance(value, _NON_CALLABLE_VALUE_TYPES):
            return False
        value_is_testcase = _value_denotes_testcase(
            value, testcase_names
        )
        return any(
            _binds_pytest_collectable(name, value_is_testcase)
            for name in _assignment_target_names(target)
        )
    return False


def _unpacking_triggers(
    target_elts: list[ast.expr],
    value_elts: list[ast.expr],
    testcase_names: set[str],
) -> bool:
    """Whether one unpacking level (sequence target, sequence
    value) binds a pytest-collectable name.

    Ruling (issue #52, superseding round 9's whole-value
    fallback for sequence values): judge per element. Each
    plainly-bound target element is judged against its
    corresponding value element — the prefix elements pair
    left-aligned with the leading value elements and the suffix
    elements pair right-aligned with the trailing ones, so
    determinate pairings survive an arity mismatch and a
    starred element alike; a target element with no
    corresponding value element triggers nothing by itself.
    Determinate value elements are those outside a value-side
    spread: elements before it sit at fixed leading positions
    and elements after it at fixed trailing ones.

    The starred target binds a LIST of the remaining values.
    It triggers only if at least one remaining value denotes a
    TestCase; if the remainder's contents are statically
    unknowable (a value-side spread feeds it), it does not
    trigger by itself.
    """
    target_star = next(
        (
            index
            for index, element in enumerate(target_elts)
            if isinstance(element, ast.Starred)
        ),
        None,
    )
    value_star = next(
        (
            index
            for index, element in enumerate(value_elts)
            if isinstance(element, ast.Starred)
        ),
        None,
    )
    if target_star is None:
        target_prefix = target_elts
        target_suffix: list[ast.expr] = []
        starred: ast.expr | None = None
    else:
        target_prefix = target_elts[:target_star]
        target_suffix = target_elts[target_star + 1 :]
        starred = target_elts[target_star]
    if value_star is None:
        # Every value position is fixed: the prefix pairs from
        # the head of the list, reserving the tail for the
        # suffix targets; the two segments never overlap.
        lead = value_elts[
            : max(0, len(value_elts) - len(target_suffix))
        ]
        trail = (
            value_elts[len(value_elts) - len(target_suffix) :]
            if target_suffix
            else []
        )
    else:
        lead = value_elts[:value_star]
        trail = value_elts[value_star + 1 :]

    triggers = False
    prefix_pairs = list(zip(target_prefix, lead))
    suffix_pairs = list(
        zip(reversed(target_suffix), reversed(trail))
    )
    for element, element_value in prefix_pairs + suffix_pairs:
        if _assignment_target_triggers(
            element, element_value, testcase_names
        ):
            triggers = True

    if starred is not None and value_star is None:
        inner = starred.value
        if isinstance(inner, ast.Name) and (
            inner.id.startswith("test_")
            or inner.id.startswith("Test")
        ):
            remainder = value_elts[
                len(prefix_pairs) : len(value_elts)
                - len(suffix_pairs)
            ]
            if any(
                _value_denotes_testcase(
                    element_value, testcase_names
                )
                for element_value in remainder
            ):
                triggers = True
    return triggers


def _dotted_name(node: ast.expr) -> str | None:
    """Dotted name for a Name/Attribute chain (`unittest.TestCase`),
    else None (calls, subscripts, and other expressions have none)."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _classify_test_module(
    text: str, truncated: bool = False
) -> tuple[bool, bool]:
    """(has_unittest_leg, triggers_pytest) for one test module.

    The pair-only view of _classify_module, kept for callers
    (and tests) that do not judge speculativeness.
    """
    has_unittest, triggers_pytest, _, _ = _classify_module(
        text, truncated
    )
    return has_unittest, triggers_pytest


def _classify_module(
    text: str, truncated: bool = False
) -> tuple[bool, bool, bool, bool]:
    """(has_unittest_leg, triggers_pytest, unittest_speculative,
    pytest_speculative) for one test module.

    A leg is SPECULATIVE when every signal that scheduled it is
    classification uncertainty — an unresolved class base the
    loader must decide, or a star import opening the module's
    binding set — rather than positive evidence the runner will
    collect something. run_all composes speculative legs'
    results against the union of the run (issue #51); a leg
    with any deterministic signal is not speculative.

    Classification follows the runners' collection semantics, by AST:

    - unittest leg iff the module defines a class whose bases include
      a dotted name ending in `TestCase`, a name imported as an alias
      of `unittest.TestCase`, or a module-local TestCase subclass
      (transitively — the unittest loader collects them all). Imports
      alone never create the leg: `import unittest.mock` defines
      nothing the unittest loader could collect. A module-level
      `load_tests` hook also selects the leg: the hook is the
      module's suite under unittest's loading protocol, and pytest
      never executes it.
    - pytest trigger iff the module defines module-level (or async)
      `test_*` functions, OR an import binds a `test_*` name (pytest
      collects test functions from the module namespace, imported
      ones included — the bound name is the evidence), OR an
      import binds a `Test*` name that does not denote TestCase
      in this module (an imported class's definition lives
      elsewhere, so it cannot be resolved as a TestCase subclass
      here; pytest collects Test* classes from the namespace,
      imported ones included — a dotted import's alias,
      `import shared.TestImported as TestImported`, binds its
      name the same explicit way), OR an
      assignment binds a pytest-collectable name (`test_*` or
      `Test*`) to a value that is not provably non-callable data (a
      literal display — `test_failure = failure` binds a collectable
      function and `TestGenerated = Helper` a collectable class;
      `test_cases = [...]` and `TestData = {...}` bind tables and do
      not; a `Test*` name bound to TestCase itself denotes
      unittest's class, recorded as an alias, not a pytest class;
      an unpacking assignment with a sequence value is judged
      per element wherever correspondence is determinate —
      `TestA, TestB = Helper, Other` binds two collectable
      classes, `test_a, test_b = 1, 2` binds none, determinate
      pairings survive an arity mismatch or a starred element,
      and the starred remainder triggers only when a remaining
      value denotes a TestCase — while a sequence target bound
      to a non-sequence value falls back to the whole-value
      rule for its names),
      OR a `Test*`
      class that is NOT resolved as a TestCase subclass (its test
      methods may be inherited from a local helper or written
      pytest-style, so its own body is not the evidence), OR the
      module is OPEN beside a statically known TestCase-denoting
      class — a `from X import *` star import makes the module's
      binding set open (the names it binds are statically
      unknowable and the classifier never executes imports), so
      pytest-collectable test_* functions it brings in are
      invisible to every name-based rule above; the pytest leg
      it gains is speculative, routed through the same
      uncertainty channel as an unresolved class base, and a
      star import beside NO known test marker changes nothing —
      OR the module has no leg at all (default). A module whose only
      collectable content is TestCase subclasses does NOT by itself
      trigger the pytest
      command (RC2 — pure-unittest trees keep byte-identical argv);
      when the bare pytest command exists for other reasons it
      collects those modules too.
    - Definitions are collected at module namespace at ANY compound
      depth (`if True:` / `try:` blocks execute at module level, and
      both runners collect what they define); definitions nested in a
      class or function are not module-level collectables.
    - UNCERTAINTY ROUTES TO MORE EXECUTION, NEVER LESS (panel
      CLASS-P1): a truncated scan (content past the cap may hide
      either runner's shapes), an unparseable module, or a class
      whose base cannot be resolved inside the module — e.g. a
      TestCase subclass imported from a shared base module — routes
      the module to the unittest leg by explicit name (the loader
      decides collectability at runtime) and, where pytest-collectable
      shapes may also hide (a `Test*` class with an unresolved base,
      truncation, unparseable), triggers the pytest leg too. A bare
      builtin base (`object`, `Exception`, ...) is NOT uncertainty:
      no builtin is a TestCase, so it resolves determinately.
    """
    if truncated:
        # Pure uncertainty: both legs on suspicion alone, so
        # both are speculative.
        return True, True, True, True
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return True, True, True, True

    # Module-namespace pass: TestCase-denoting names (direct imports,
    # import aliases, assignment aliases), every imported name, every
    # module-level class, and module-level test_* functions.
    testcase_names: set[str] = set()
    imported_names: set[str] = set()
    classes: list[ast.ClassDef] = []
    triggers_pytest = False
    has_load_tests = False
    has_star_import = False

    def visit(node: ast.AST, in_class: bool, in_func: bool) -> None:
        nonlocal triggers_pytest, has_load_tests, has_star_import
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                if not in_class and not in_func:
                    classes.append(child)
                visit(child, True, in_func)
            elif isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                if not in_class and not in_func:
                    if child.name.startswith("test_"):
                        triggers_pytest = True
                    elif child.name == "load_tests":
                        # unittest's loading protocol: the hook IS
                        # the module's suite, and only the unittest
                        # loader executes it (pytest never calls
                        # it). Without the leg, a suite the hook
                        # builds — e.g. FunctionTestCases, with no
                        # TestCase subclass declared — is silently
                        # omitted (Codex P2).
                        has_load_tests = True
                visit(child, in_class, True)
            else:
                if not in_class and not in_func:
                    if isinstance(child, ast.ImportFrom):
                        if any(
                            alias.name == "*" for alias in child.names
                        ):
                            # A star import makes the module's
                            # binding set OPEN (issue #51): the
                            # names it binds are statically
                            # unknowable, so no name-based channel
                            # below can see what it brings in.
                            # Recorded here; judged after class
                            # resolution, where the module's known
                            # test markers are settled.
                            has_star_import = True
                        if child.module == "unittest" or (
                            child.module is not None
                            and child.module.startswith("unittest.")
                        ):
                            for alias in child.names:
                                if alias.name == "TestCase":
                                    testcase_names.add(
                                        alias.asname or alias.name
                                    )
                        for alias in child.names:
                            bound = alias.asname or alias.name
                            imported_names.add(bound)
                            if bound.startswith("test_"):
                                # pytest collects test_* functions
                                # from the module namespace, imported
                                # ones included — an import binding a
                                # test_* name IS pytest evidence.
                                # Recording the name without the
                                # trigger let a sibling TestCase class
                                # suppress the leg and silently omit
                                # the imported tests (Codex P2).
                                triggers_pytest = True
                            elif (
                                bound.startswith("Test")
                                and bound != "TestCase"
                                and bound not in testcase_names
                            ):
                                # pytest collects Test* CLASSES from
                                # the module namespace, imported ones
                                # included. An imported Test* name
                                # cannot be resolved as a TestCase
                                # subclass from this module — its
                                # definition lives elsewhere — so,
                                # like a locally unresolved Test*
                                # class, it is positive evidence for
                                # pytest; recording the name without
                                # the trigger let a sibling TestCase
                                # class suppress the leg and silently
                                # omit the imported class (Codex P2).
                                # TestCase-denoting imports are
                                # excluded: `TestCase` itself, and
                                # names recorded above as its
                                # aliases, are unittest's own class.
                                triggers_pytest = True
                    elif isinstance(child, ast.Import):
                        for alias in child.names:
                            imported_names.add(
                                alias.asname
                                or alias.name.split(".")[0]
                            )
                            if (
                                alias.asname is not None
                                and alias.asname.startswith("Test")
                                and alias.asname != "TestCase"
                                and alias.asname not in testcase_names
                            ):
                                # A dotted import with an alias —
                                # `import shared.TestImported as
                                # TestImported` — binds its Test*
                                # name in the module namespace
                                # explicitly, exactly as the
                                # ImportFrom form round 8 covers;
                                # recording it without the trigger
                                # left the same silent omission
                                # behind a sibling TestCase class.
                                # What the alias denotes (class or
                                # module) is unresolved from this
                                # module, and unresolved Test*
                                # bindings keep the pytest leg.
                                # Without an alias, only the
                                # top-level package name is bound —
                                # no Test* name enters the namespace
                                # — so there is nothing to trigger
                                # on. TestCase-denoting aliases are
                                # excluded as in the ImportFrom
                                # branch.
                                triggers_pytest = True
                    elif isinstance(child, ast.Assign):
                        value_is_testcase = _value_denotes_testcase(
                            child.value, testcase_names
                        )
                        if value_is_testcase:
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    testcase_names.add(target.id)
                        for target in child.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "load_tests"
                            ):
                                # `load_tests = <callable>` binds the
                                # same module attribute the unittest
                                # loader invokes.
                                has_load_tests = True
                        for target in child.targets:
                            if _assignment_target_triggers(
                                target, child.value, testcase_names
                            ):
                                # pytest collects test_* functions
                                # and Test* classes from the module
                                # namespace, however they were bound
                                # — `test_failure = failure`,
                                # `TestGenerated = Helper`, and the
                                # unpacking form `TestA, TestB =
                                # Helper, Other` included (the
                                # last judged per element: the
                                # whole-value rule saw one Tuple
                                # value — a literal display in the
                                # non-callable set — and triggered
                                # for neither name). Checking
                                # assignment targets only for
                                # TestCase aliases and load_tests let
                                # a sibling TestCase class suppress
                                # the leg and silently omit the
                                # assigned tests (Codex P2, rounds
                                # 7 and 9). Only provably-data
                                # values (literal displays) are not
                                # evidence, and a Test* name bound
                                # to TestCase itself denotes
                                # unittest's class (recorded above
                                # as an alias), not a pytest class.
                                triggers_pytest = True
                    elif isinstance(child, ast.AnnAssign):
                        # `test_failure: Callable = failure` and
                        # `TestGenerated: type = Helper` bind the
                        # same module attributes as the plain
                        # assignments above; an annotation without a
                        # value binds nothing.
                        if (
                            child.value is not None
                            and isinstance(child.target, ast.Name)
                            and not isinstance(
                                child.value,
                                _NON_CALLABLE_VALUE_TYPES,
                            )
                        ):
                            ann_value_is_testcase = (
                                _value_denotes_testcase(
                                    child.value, testcase_names
                                )
                            )
                            if _binds_pytest_collectable(
                                child.target.id,
                                ann_value_is_testcase,
                            ):
                                triggers_pytest = True
                visit(child, in_class, in_func)

    visit(tree, False, False)

    # Resolve each module-level class against its bases, to a
    # fixpoint (module-local subclasses resolve transitively).
    local_names = {cls.name for cls in classes}
    resolved: dict[str, bool] = {}
    uncertain: set[str] = set()
    pending = list(classes)
    while pending:
        deferred: list[ast.ClassDef] = []
        progressed = False
        for cls in pending:
            is_testcase = False
            is_uncertain = False
            waiting = False
            for base in cls.bases:
                dotted = _dotted_name(base)
                if dotted is None:
                    is_uncertain = True
                    continue
                if (
                    dotted.rsplit(".", 1)[-1] == "TestCase"
                    or dotted in testcase_names
                ):
                    is_testcase = True
                    continue
                root = dotted.split(".")[0]
                if (
                    "." not in dotted
                    and root not in imported_names
                    and root not in local_names
                    and isinstance(getattr(builtins, root, None), type)
                ):
                    # A bare builtin base (object, Exception, ...):
                    # builtins are concrete classes the interpreter
                    # itself resolves, and none of them is a
                    # TestCase — the base is KNOWN non-TestCase, not
                    # an uncertainty. Routing it to a speculative
                    # unittest leg made that leg collect zero and
                    # veto passing pytest suites (Codex P2).
                    continue
                if dotted in resolved:
                    if resolved[dotted]:
                        is_testcase = True
                elif root in local_names and "." not in dotted:
                    waiting = True
                elif root in imported_names or root not in local_names:
                    # A base defined outside this module (or nowhere
                    # visible): it may be a TestCase subclass defined
                    # in a shared base module — the loader decides.
                    is_uncertain = True
            if waiting and not is_testcase:
                deferred.append(cls)
                continue
            resolved[cls.name] = is_testcase
            if is_uncertain and not is_testcase:
                uncertain.add(cls.name)
            if is_testcase:
                testcase_names.add(cls.name)
            progressed = True
        if not progressed:
            # Circular local bases: the loader will error at import;
            # route to the unittest leg and let it decide.
            for cls in deferred:
                resolved[cls.name] = False
                uncertain.add(cls.name)
            break
        pending = deferred

    # Every trigger the visitor set is positive evidence found
    # in the module's own bindings (a test_* def, an imported
    # test_*/Test* name, a collectable assignment) — deterministic.
    # Only the post-resolution rules below can add a SPECULATIVE
    # trigger, and they record that they did.
    visitor_triggers_pytest = triggers_pytest
    pytest_speculative_trigger = False
    pytest_deterministic_trigger = False
    has_unittest = has_load_tests
    for cls in classes:
        if resolved.get(cls.name):
            has_unittest = True
        elif cls.name in uncertain:
            # Unresolved base: the class may be a TestCase subclass
            # (unittest leg by name — the loader decides); a Test*
            # name may instead be a plain pytest class.
            has_unittest = True
            if cls.name.startswith("Test"):
                triggers_pytest = True
                pytest_speculative_trigger = True
        elif cls.name.startswith("Test"):
            # Resolved as NOT a TestCase subclass — but pytest
            # collects Test* classes, and their test methods may be
            # inherited from a local helper class, invisible in this
            # class's own body. Suppressing the leg for want of
            # literal test_* methods silently omitted inherited
            # tests whenever a sibling class selected the unittest
            # leg (Codex P2). The leg may be suppressed only on
            # positive evidence there is nothing for pytest to
            # collect; a Test* name on a non-TestCase class is the
            # opposite of that evidence, so it keeps the leg.
            triggers_pytest = True
            pytest_deterministic_trigger = True
    if (
        has_star_import
        and not triggers_pytest
        and any(resolved.get(cls.name) for cls in classes)
    ):
        # Issue #51: an OPEN module (star import — see the
        # ImportFrom branch) beside a statically known
        # TestCase-denoting class must not classify as
        # unittest-only. The star import may bring
        # pytest-collectable test_* functions into the module
        # namespace that no name-based channel can see, and
        # the classifier never executes imports to find out.
        # The module gains a SPECULATIVE pytest leg through
        # the same uncertainty channel as an unresolved class
        # base above: both legs are scheduled, and the leg is
        # marked speculative on its command, so run_all judges
        # a clean zero collection from it against the union of
        # the run — it never vetoes a run another Python leg
        # passed, in any leg position, but standing alone with
        # zero collected it fails closed like any genuinely
        # empty discovery. FALSE-TRIGGER BOUND: the leg
        # fires only when a TestCase-denoting class is
        # statically known in the module — a star import
        # beside no known test marker changes nothing, and a
        # closed module (no star import) is completely
        # unaffected — so a module that star-imports non-test
        # helpers gains a leg only when it already carries
        # unittest content of its own.
        triggers_pytest = True
        pytest_speculative_trigger = True
    if not has_unittest and not triggers_pytest:
        triggers_pytest = True  # no leg at all: the pytest default
    unittest_speculative = (
        has_unittest
        and not has_load_tests
        and not any(resolved.get(cls.name) for cls in classes)
    )
    pytest_speculative = (
        triggers_pytest
        and pytest_speculative_trigger
        and not visitor_triggers_pytest
        and not pytest_deterministic_trigger
    )
    return (
        has_unittest,
        triggers_pytest,
        unittest_speculative,
        pytest_speculative,
    )


def _is_real_file(path: Path) -> bool:
    """True for a regular file that is not a symlink. See the
    symlink policy at discover_verification_commands."""
    return not path.is_symlink() and path.is_file()


# pytest's inifile candidates, in the precedence order of
# _pytest.config.findpaths.locate_config (pytest 9.0.3).
_PYTEST_CONFIG_CANDIDATES = (
    "pytest.toml",
    ".pytest.toml",
    "pytest.ini",
    ".pytest.ini",
    "pyproject.toml",
    "tox.ini",
    "setup.cfg",
)

# Candidates pytest treats as a config source on existence
# alone (findpaths.load_config_dict_from_file): only
# pytest.ini/.pytest.ini, which are sources even when empty.
# pytest.toml/.pytest.toml are sources with any content — even
# without a [pytest] table — but the file must still parse as
# TOML (pytest aborts on an unparseable candidate). The
# remaining candidates qualify only with content: pyproject.toml
# needs a [tool.pytest] table with keys of its own or a
# [tool.pytest.ini_options] table, tox.ini a [pytest] section,
# setup.cfg a [tool:pytest] section. Every content condition is
# evaluated on the PARSED structure (tomllib for the .toml
# family, configparser for the .ini names) — never on raw text:
# a section name appearing in a comment or a string value is
# not a section (round-3 finding F2).
_PYTEST_CONFIG_ALWAYS = frozenset(("pytest.ini", ".pytest.ini"))


def _parse_toml(text: str) -> dict | None:
    """The TOML document in *text*, or None when it does not
    parse. Real pytest raises UsageError on an unparseable
    candidate (it aborts rather than skipping the file); the
    walk treats it as non-qualifying and moves on — see the
    divergences named in _pytest_config_selected."""
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def _pyproject_config_qualifies(text: str) -> bool:
    """Whether a pyproject.toml makes it pytest's inifile,
    judged on the parsed document exactly as
    findpaths.load_config_dict_from_file judges it: a
    [tool.pytest] table carrying at least one key of its own
    (anything but ini_options), or a [tool.pytest.ini_options]
    table (present even when empty). An empty [tool.pytest]
    table — no keys, no ini_options — does not qualify, and a
    header appearing only in a comment or a string value is
    not a table. The [tool] pytest = {...} inline-table form
    parses to the same structure and qualifies, as in pytest."""
    config = _parse_toml(text)
    if config is None:
        return False
    tool = config.get("tool")
    if not isinstance(tool, dict):
        return False
    pytest_table = tool.get("pytest")
    if not isinstance(pytest_table, dict):
        return False
    if "ini_options" in pytest_table:
        return True
    return any(key != "ini_options" for key in pytest_table)


def _ini_config_has_section(text: str, section: str) -> bool:
    """Whether INI *text* contains a real *section*, judged on
    the parsed structure: comment lines, string values, and
    indented continuation lines are not sections. An
    unparseable file has no sections (real pytest aborts on
    it; see _parse_toml for why the walk may move on)."""
    parser = configparser.ConfigParser(
        interpolation=None, allow_no_value=True, strict=False
    )
    try:
        parser.read_string(text)
    except configparser.Error:
        return False
    return parser.has_section(section)


def _pytest_config_qualifies(name: str, text: str) -> bool:
    """Whether the real file *name* with contents *text* is a
    config source for pytest, per the per-name content
    conditions of findpaths.load_config_dict_from_file."""
    if name in ("pytest.toml", ".pytest.toml"):
        # A dedicated .toml is always a source once it parses,
        # even without a [pytest] table.
        return _parse_toml(text) is not None
    if name == "pyproject.toml":
        return _pyproject_config_qualifies(text)
    if name == "tox.ini":
        return _ini_config_has_section(text, "pytest")
    if name == "setup.cfg":
        return _ini_config_has_section(text, "tool:pytest")
    return name in _PYTEST_CONFIG_ALWAYS


def _pytest_config_selected(root: Path) -> Path | None:
    """The config file the bare pytest leg reads at *root*,
    following the inifile precedence of
    _pytest.config.findpaths.locate_config (pytest 9) —
    pytest.toml, .pytest.toml, pytest.ini, .pytest.ini,
    pyproject.toml, tox.ini, setup.cfg — with pytest's per-name
    content conditions (see _PYTEST_CONFIG_ALWAYS and
    _pytest_config_qualifies), or None when no candidate
    qualifies. Only real files are read: a symlink candidate
    is reported at its precedence position without being read.
    That is deliberately conservative — whether pytest would
    honour the link depends on the unbound target's contents,
    so the walk treats the link as the selected config and the
    leg is insulated (see _pytest_argv); over-insulation is
    the safe direction.

    The judgement is root-scoped, and since Task 15 (paperthin
    validation 5) it is true of the run BY CONSTRUCTION: left
    to itself, pytest's search does not stop at the root — an
    ancestor's inifile becomes the run's config, an ancestor's
    non-qualifying pyproject.toml anchors rootdir by fallback,
    and ancestor conftest.py files execute. The leg's argv
    therefore pins -c to this walk's selection (or os.devnull)
    and rootdir/confcutdir to the root itself (see
    _pytest_argv), so pytest never performs its own search and
    no ancestor file can be selected, anchor, or load. The
    two divergences the walk once carried against pytest's
    search are inert under the pin: (1) pytest's
    found_pyproject_toml fallback, which selects a
    non-qualifying pyproject.toml as an EMPTY config, never
    engages — with -c pinned, pytest reads only the named
    file, and when the walk selects nothing the named file is
    os.devnull, so the fallback cannot anchor rootdir at an
    ancestor's pyproject either. (2) The walk's parsers and
    pytest's do not judge every candidate alike (an
    unparseable candidate makes real pytest abort with
    UsageError rather than skip it; configparser strict=False
    qualifies a few files iniconfig rejects) — under the pin
    those candidates are never pytest's to judge: a
    walk-selected candidate pytest rejects aborts the run
    honestly, exactly as its own search would have, and a
    candidate the walk skipped is never read at all."""
    for name in _PYTEST_CONFIG_CANDIDATES:
        candidate = root / name
        if not candidate.is_file():
            continue
        if candidate.is_symlink():
            return candidate
        if name in _PYTEST_CONFIG_ALWAYS:
            return candidate
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            return candidate
        except UnicodeDecodeError:
            continue
        if _pytest_config_qualifies(name, text):
            return candidate
    return None


def _pytest_argv(root: Path) -> tuple[str, ...]:
    """The bare-pytest command for *root*, pinned so the run's
    resolution is a function of the root alone (Task 15,
    paperthin validation 5). Unpinned, pytest resolves ACROSS
    the root: with no qualifying inifile inside, its search
    ascends and an ancestor's config steers the run, an
    ancestor's pyproject.toml anchors rootdir by fallback, and
    ancestor conftest.py files execute — content no binding
    attests. The pin has three elements, each load-bearing
    against the installed pytest (9.0.3, probed):

    - -c names the config the gates judged — the selected
      real in-tree file (see _pytest_config_selected) — or
      os.devnull when there is none or it is a symlink, so the
      unbound file's addopts/testpaths define nothing (issue
      #64) and no ancestor inifile can be selected instead.
    - --rootdir names the root itself: rootdir otherwise
      derives from the -c file's directory — /dev for
      os.devnull — and confcutdir follows rootdir, so the
      config pin alone leaves conftest collection unbounded
      (a /dev rootdir let collection wander the filesystem).
    - --confcutdir names the root itself: conftest ascent
      stops at the attested boundary even if rootdir's
      derivation ever changes under it.

    Defence in depth lives in run_verification: a run whose
    transcript names a rootdir other than this root has its
    collected count treated as unproven (see
    _pytest_rootdir_escapes)."""
    resolved = root.resolve()
    selected = _pytest_config_selected(root)
    if selected is not None and not selected.is_symlink():
        config = str(resolved / selected.name)
    else:
        config = os.devnull
    return PYTEST_ARGV + (
        "-c",
        config,
        "--rootdir",
        str(resolved),
        "--confcutdir",
        str(resolved),
    )


def _pytest_config_raw_values(
    config: Path, keys: tuple[str, ...]
) -> list[object]:
    """The raw values of *keys* in a REAL pytest config file,
    read with the same parsers the qualification walk uses —
    tomllib for the .toml family (pytest.toml's [pytest]
    table; pyproject.toml's [tool.pytest] keys and its
    [tool.pytest.ini_options] table), configparser for the .ini
    names ([pytest], or [tool:pytest] for setup.cfg). An
    unreadable or unparseable file yields no values: real
    pytest aborts on such a config, so its aims never steer a
    run that could seal."""
    name = config.name
    try:
        text = config.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    values: list[object] = []
    if name in ("pytest.toml", ".pytest.toml", "pyproject.toml"):
        parsed = _parse_toml(text)
        if not isinstance(parsed, dict):
            return []
        if name == "pyproject.toml":
            tool = parsed.get("tool")
            table = (
                tool.get("pytest") if isinstance(tool, dict) else None
            )
            if not isinstance(table, dict):
                return []
            for key in keys:
                values.append(table.get(key))
            ini_options = table.get("ini_options")
            if isinstance(ini_options, dict):
                for key in keys:
                    values.append(ini_options.get(key))
        else:
            table = parsed.get("pytest")
            if not isinstance(table, dict):
                return []
            for key in keys:
                values.append(table.get(key))
    else:
        section = "tool:pytest" if name == "setup.cfg" else "pytest"
        parser = configparser.ConfigParser(
            interpolation=None, allow_no_value=True, strict=False
        )
        try:
            parser.read_string(text)
        except configparser.Error:
            return []
        if not parser.has_section(section):
            return []
        for key in keys:
            if parser.has_option(section, key):
                values.append(parser.get(section, key))
    return values


def _pytest_config_path_entries(config: Path) -> list[str]:
    """The `testpaths` and `pythonpath` entries of a REAL pytest
    config file. Values in TOML may be a list or a single
    string; INI values are whitespace-separated, as pytest's
    own ini types split them."""
    entries: list[str] = []
    for value in _pytest_config_raw_values(
        config, ("testpaths", "pythonpath")
    ):
        if isinstance(value, str):
            entries.extend(value.split())
        elif isinstance(value, list):
            entries.extend(
                item for item in value if isinstance(item, str)
            )
    return entries


def _pytest_config_addopts(config: Path) -> list[str]:
    """The `addopts` tokens of a REAL pytest config file.
    pytest prepends addopts to its argv, so the tokens are
    read with the same parsers as the path entries and split
    the way pytest splits them (shlex). A TOML list contributes
    its items, each item shlex-split like a string; an
    unparseable addopts yields no tokens — real pytest aborts
    on it the same way, so nothing it names can steer a run
    that could seal."""
    tokens: list[str] = []
    for value in _pytest_config_raw_values(config, ("addopts",)):
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = [item for item in value if isinstance(item, str)]
        else:
            continue
        for item in items:
            try:
                tokens.extend(shlex.split(item))
            except ValueError:
                continue
    return tokens


# Options of pytest 9's core parser that consume the FOLLOWING
# token as their REQUIRED value — introspected from
# _pytest.config's parser (every registered option whose
# action takes exactly one value: store/append with nargs
# None), so an addopts value (a -k expression, a --basetemp
# directory, a --junit-xml report path) is never mistaken for
# a positional collection aim or an armed option spelling.
# Options whose value is OPTIONAL (nargs="?") are excluded —
# there are exactly two in the core parser, --debug and
# --cache-show: the parser takes the following token as the
# value only when it does not look like an option, so in
# _addopts_token_stream the token after one of them keeps
# both of its readings (`--debug --lf` arms --lf against the
# raw binary — an optional-value option in this set would
# swallow the spelling). A pin test (AddoptsGrammarTests)
# re-derives this set from the installed parser, so a future
# pytest that changes either side of it fails loudly.
# Plugin-registered options are unknowable here; a plugin
# option's space-separated value, when it names a path, is
# judged as an aim like any bare token — over-refusal of the
# leg, in the fail-closed direction, never a missed aim of
# pytest's own surface.
_PYTEST_VALUE_OPTIONS = frozenset(
    {
        "-W", "-c", "-k", "-m", "-o", "-p", "-r",
        "--assert", "--basetemp", "--capture", "--code-highlight",
        "--color", "--confcutdir", "--config-file",
        "--deselect", "--doctest-glob", "--doctest-report",
        "--durations", "--durations-min", "--ignore",
        "--ignore-glob", "--import-mode", "--junit-prefix",
        "--junit-xml", "--junitprefix", "--junitxml",
        "--last-failed-no-failures", "--lfnf", "--log-auto-indent",
        "--log-cli-date-format", "--log-cli-format",
        "--log-cli-level", "--log-date-format", "--log-disable",
        "--log-file", "--log-file-date-format", "--log-file-format",
        "--log-file-level", "--log-file-mode", "--log-format",
        "--log-level", "--maxfail", "--override-ini", "--pastebin",
        "--pdbcls", "--pythonwarnings", "--rootdir",
        "--show-capture", "--tb", "--verbosity",
    }
)


def _addopts_token_stream(
    tokens: list[str],
) -> Iterator[tuple[str, str, str | None]]:
    """The addopts *tokens* judged the way pytest 9's parser
    can read them — ("option", name, value) and
    ("aim", token, None) judgements in stream order. The one
    tokenization every addopts consumer shares.

    The grammar is the parser's, not getopt's: pytest parses
    its argv in two passes (argparse's intermixed parsing;
    on pre-3.12.8 Pythons a fallback that splits the
    leftovers the same way) — the first pass consumes a `--`
    separator and the second re-reads the remainder as a
    fresh stream, so a registered option spelling arms
    WHEREVER it appears: before, between, or after
    positionals, and after one `--` as surely as before it
    (Task 13 review, finding F1; every spelling behaviour
    stated here was proven against the raw binary). The
    separator therefore terminates nothing for the scanners:
    it is skipped, and every other token is judged under
    BOTH readings the parser could give it — an option
    spelling as an option, a bare token as a positional aim.
    (After two separators the parser gives a spelling the
    positional reading instead and errors on it as a path;
    judging it as an option too is the fail-closed side of
    that divergence.) A known value-taking option consumes
    the token that follows it verbatim, separators and
    spellings included: where the parser accepts the stream
    it consumes that token the same way, and where the
    scanner's reading is one the parser rejects (`-k -- x`,
    `-c --lf` — proven rc 4, "expected one argument") the
    run errors, so the scanner's silence about the swallowed
    token cannot seal. Options whose value is OPTIONAL are
    not in _PYTEST_VALUE_OPTIONS and never consume here (see
    its comment): the token after --debug or --cache-show
    keeps both readings."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token == "--":
            continue
        if token.startswith("-") and token != "-":
            name, sep, attached = token.partition("=")
            value = attached if sep else None
            if (
                value is None
                and name in _PYTEST_VALUE_OPTIONS
                and index < len(tokens)
            ):
                value = tokens[index]
                index += 1
            yield ("option", name, value)
            continue
        yield ("aim", token, None)


def _addopts_aims(tokens: list[str]) -> tuple[list[str], bool]:
    """(positional aims, uses_pyargs) in addopts *tokens*.

    The aims are the bare tokens of _addopts_token_stream —
    the tokens pytest's parser can read as positional
    collection aims (a path or nodeid it will collect),
    wherever they sit in the stream; a token consumed as a
    known value-taking option's value is neither an aim nor
    an option. --pyargs is reported separately rather than
    returned as an aim: it retargets collection at installed
    packages, outside the bound set by construction."""
    aims: list[str] = []
    pyargs = False
    for kind, text, _value in _addopts_token_stream(tokens):
        if kind == "option":
            if text == "--pyargs":
                pyargs = True
        else:
            aims.append(text)
    return aims, pyargs


# The cache-SELECTION flags of pytest 9's cacheprovider and
# stepwise plugins — enumerated from their registrations
# (_pytest/cacheprovider.py: --lf/--last-failed;
# _pytest/stepwise.py: --sw/--stepwise and --sw-skip/
# --stepwise-skip), not from memory. Each makes the executed
# set of a run a function of the cache tools' state files
# (v/cache/lastfailed, v/cache/stepwise) — state the binding
# deliberately excludes (see FS_RESIDUE_DIRS), so a bound
# config arming one lets unbound bytes choose which tests an
# attested run executes: a subset PASS for a tree whose full
# suite fails (paperthin validation 4, breach B-B). The
# flags are CLI/addopts-only — cacheprovider registers
# exactly one ini key (cache_dir) and stepwise registers
# none — so addopts is the whole surface to scan. Adjudicated
# NOT selection, from the plugins' source and from probes
# against the installed pytest, and therefore absent here:
# --ff/--failed-first (reorders only — LFPlugin concatenates
# its previously-failed and previously-passed partitions, so
# every collected test still runs, and with -x the run still
# stops ON a failure, never before one; its one narrowing
# combination, --ff with --last-failed-no-failures=none on
# an empty cache, deselects everything and exits 5, never a
# PASS); --lfnf/--last-failed-no-failures (a modifier of
# --lf's empty-cache behaviour, inert unless --lf or --ff is
# armed); --sw-reset/--stepwise-reset (DISCARDS the stepwise
# state before selection, so a PASS under it is a full-set
# PASS); --nf/--new-first (reorders by cache/nodeids, selects
# nothing); --cache-clear (clears the state — the write
# side); --cache-show (performs no run at all, so the
# collected-count gates refuse it like any zero-test leg).
_PYTEST_CACHE_SELECTION_OPTIONS = frozenset(
    {
        "--lf",
        "--last-failed",
        "--sw",
        "--stepwise",
        "--sw-skip",
        "--stepwise-skip",
    }
)


def _addopts_cache_selection(tokens: list[str]) -> bool:
    """Whether addopts *tokens* arm a cache-selection flag
    (see _PYTEST_CACHE_SELECTION_OPTIONS). Judged over the
    shared token stream (_addopts_token_stream): a spelling
    arms anywhere in the stream — after a `--` separator
    included, because the separator does NOT end option
    processing in pytest's parser (Task 13 review,
    finding F1) — and a token consumed as a known
    value-taking option's value is not an option. A spelling
    carried as `--flag=value` is judged by its name — real
    pytest rejects that form for these store-true flags, so
    judging it armed is the fail-closed direction."""
    return any(
        kind == "option" and text in _PYTEST_CACHE_SELECTION_OPTIONS
        for kind, text, _value in _addopts_token_stream(tokens)
    )


def _pytest_config_key_entries(
    config: Path, key: str
) -> list[str] | None:
    """The effective entries of one "args"-typed ini key
    (*key*: norecursedirs, python_files) in a REAL pytest
    config, or None when the config does not set the key.
    pytest's _getini coerces an "args" value with
    shlex.split; a TOML list stands as its items. The raw
    reader can yield several values for one key (pyproject's
    [tool.pytest] table and its ini_options table); the LAST
    non-None value wins, matching the reader's precedence.
    A single value still applies when its list is empty: an
    explicitly emptied key is a set key."""
    values = [
        value
        for value in _pytest_config_raw_values(config, (key,))
        if value is not None
    ]
    if not values:
        return None
    value = values[-1]
    if isinstance(value, str):
        try:
            return shlex.split(value)
        except ValueError:
            return value.split()
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _fnmatch_ex(pattern: str, path: str) -> bool:
    """pytest's fnmatch_ex (_pytest.pathlib), ported: a
    pattern containing no path separator is matched against
    the path's basename; a pattern with one is matched
    against the whole path, with "*<sep>" prepended when the
    path is absolute and the pattern is not."""
    if os.sep not in pattern:
        name = Path(path).name
    else:
        name = path
        if os.path.isabs(path) and not os.path.isabs(pattern):
            pattern = "*" + os.sep + pattern
    return fnmatch.fnmatch(name, pattern)


# The residue names pytest's traversal must be kept out of.
# __pycache__ is NOT among them: _pytest.main's
# pytest_ignore_collect returns True for a directory of that
# name unconditionally, before the norecursedirs check, so
# no config value can reopen it (pinned behaviourally in
# TraversalGateTests). The other three are excluded only by
# pytest's default norecursedirs — ["*.egg", ".*", "_darcs",
# "build", "CVS", "dist", "node_modules", "venv", "{arch}"]
# (registered in _pytest.main's pytest_addoption, pytest
# 9.0.3) — whose `.*` entry the gate's pin test re-judges
# against the installed pytest on every run.
_TRAVERSAL_RESIDUE_NAMES = (".git", ".pytest_cache", ".mypy_cache")


def _norecursedirs_excludes(patterns: list[str], name: str) -> bool:
    """Whether pytest traversal under norecursedirs
    *patterns* is kept out of a directory named *name*,
    judged the way _pytest.main's pytest_ignore_collect
    judges it: fnmatch_ex per pattern, on the directory's
    path. A slash-free pattern fnmatches the basename and so
    covers the name at every depth. A pattern with a
    separator is credited only when it matches the name at
    EVERY depth probed (one, two, and three components below
    a placeholder root): `*/.git` covers `.git` wherever it
    sits, while `sub/.git` covers exactly one location and
    leaves every other `.git` enterable — not coverage."""
    for pattern in patterns:
        if os.sep not in pattern:
            if fnmatch.fnmatch(name, pattern):
                return True
        else:
            probes = (
                f"/probe/{name}",
                f"/probe/sub/{name}",
                f"/probe/sub/deep/{name}",
            )
            if all(_fnmatch_ex(pattern, probe) for probe in probes):
                return True
    return False


def _selected_config_traversal_enters_residue(root: Path) -> bool:
    """Whether the REAL config pytest would read at *root*
    sets a norecursedirs under which collection traversal
    can enter a residue directory (paperthin validation 3,
    breach B-NEW).

    norecursedirs REPLACES pytest's default list: a bound
    config setting `norecursedirs = *.egg` drops the
    default's `.*`, and the default traversal — no aim, no
    testpaths — then descends into .git, where a bound
    conftest's custom collector can execute a planted file
    outside the .git bind set. The judgement is scoped to
    what traversal alone reaches: the residue directories
    themselves (aims INTO them, and below them, are the aim
    gate's). When the config does not set the key, pytest's
    default applies and excludes all three names — the pin
    test re-judges the installed pytest's registered default
    so a future pytest changing it fails loudly. A symlinked
    selected config is never read: _pytest_argv pins it to
    an empty config (issue #64)."""
    selected = _pytest_config_selected(root)
    if selected is None or selected.is_symlink():
        return False
    patterns = _pytest_config_key_entries(selected, "norecursedirs")
    if patterns is None:
        return False
    return any(
        not _norecursedirs_excludes(patterns, name)
        for name in _TRAVERSAL_RESIDUE_NAMES
    )


_PYTEST_DEFAULT_PYTHON_FILES = ("test_*.py", "*_test.py")
_PYTEST_DEFAULT_DOCTEST_GLOBS = ("test*.txt",)


def _addopts_doctest_globs(tokens: list[str]) -> list[str]:
    """The --doctest-glob values among addopts *tokens*.

    --doctest-glob is the doctest plugin's append option:
    when a run carries any, they REPLACE its built-in
    default (test*.txt) as the fnmatch_ex globs
    _pytest.doctest applies to non-.py files. Judged over
    the shared token stream (_addopts_token_stream), so a
    glob spelled after a `--` separator — which the raw
    parser arms like any other registered option — is read
    too, and a glob-looking token swallowed as another
    option's value is not misread as one."""
    return [
        value
        for kind, text, value in _addopts_token_stream(tokens)
        if kind == "option"
        and text == "--doctest-glob"
        and value is not None
    ]


def _pytest_collection_patterns(
    root: Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The (python_files patterns, doctest globs) the bare
    run at *root* collects under — the EFFECTIVE patterns
    the scope walk judges symlinked files by.

    The defaults when no config is selected, and when the
    selected config is a symlink: the pinned run reads an
    empty config (issue #64), so no config value can widen
    anything, and the walk pins that interaction by judging
    exactly what the pinned run would use. Otherwise the
    selected real config's python_files when it sets the
    key, and the --doctest-glob values of its addopts when
    it carries any; each unset piece stays at its default."""
    selected = _pytest_config_selected(root)
    if selected is None or selected.is_symlink():
        return _PYTEST_DEFAULT_PYTHON_FILES, _PYTEST_DEFAULT_DOCTEST_GLOBS
    python_files = _pytest_config_key_entries(selected, "python_files")
    globs = _addopts_doctest_globs(_pytest_config_addopts(selected))
    return (
        tuple(python_files)
        if python_files is not None
        else _PYTEST_DEFAULT_PYTHON_FILES,
        tuple(globs) if globs else _PYTEST_DEFAULT_DOCTEST_GLOBS,
    )


def _path_crosses_symlink(root: Path, target: str) -> bool:
    """Whether the normalized absolute *target* — inside
    *root* — is reached through a symlink below the root:
    the final component itself, or any directory component
    above it, is a link. The binding records a link's target
    string, never its content, so content an aim reaches
    through a link is attested nowhere — whatever the aimed
    file's name, and wherever the link points: the link is
    the policy object, not its target (the posture of the
    scope walk in _bare_pytest_scope_has_symlink). A
    component that does not exist is not a link: an aim at
    nothing collects nothing."""
    relative = os.path.relpath(
        target, os.path.normpath(str(root))
    )
    current = str(root)
    for part in relative.split(os.sep):
        if part in ("", "."):
            continue
        current = os.path.join(current, part)
        if os.path.islink(current):
            return True
    return False


def _entry_aims_unattested(root: Path, entry: str) -> bool:
    """Whether one aim *entry* — a testpaths or pythonpath
    entry, or a positional addopts token — steers the bare
    leg at content the seal does not attest: a path with a
    residue-named component, a path resolving outside
    *root*, or a path at or through a symlink.

    The path part of a nodeid (before "::") is judged.
    Residue is judged as written, so `.mypy_cache/collected`
    and `pkg/.pytest_cache/x` are caught, and again after
    normalization against *root*, so `pkg/../.mypy_cache/x`
    is caught too — while `.mypy_cache/../tests`, which
    normalizes to bound content, is not. Outside-the-root is
    judged on the normalized join: `../outside` and absolute
    paths land outside the tree the seal describes, and
    content there is bound nowhere (Task 11 review, finding
    F3). A bare token naming no path (a test name) normalizes
    to an in-tree path and passes. The symlink judgement
    (Task 11 re-review §4) closes the composition seam the
    textual checks cannot see: an aim at a symlinked file
    whose name falls outside the scope walk's patterns
    resolves textually inside the root, yet executes the
    link target's content — as does an aim through a
    symlinked directory at a file the walk's name rule
    would pass."""
    path_part = entry.split("::", 1)[0]
    if not path_part:
        return False
    for candidate in (path_part, os.path.join(root, path_part)):
        normalized = os.path.normpath(candidate)
        if any(
            part in FS_RESIDUE_DIRS
            for part in normalized.split(os.sep)
        ):
            return True
    if os.path.isabs(path_part):
        target = os.path.normpath(path_part)
    else:
        target = os.path.normpath(os.path.join(root, path_part))
    root_norm = os.path.normpath(str(root))
    if target != root_norm and not target.startswith(
        root_norm + os.sep
    ):
        return True
    return _path_crosses_symlink(root, target)


def _selected_config_aims_unattested(root: Path) -> bool:
    """Whether the REAL config pytest would read at *root*
    steers the bare leg at unattested content, over the
    config's full steering surface: its testpaths and
    pythonpath entries, the positional tokens of its
    addopts, --pyargs, its cache-selection flags, and its
    norecursedirs — judged for whether default collection
    traversal can still enter a residue directory (see
    _selected_config_traversal_enters_residue).

    The collected .py files under a residue name are bound
    in the tree digest (see _fs_residue_entries), so a
    residue aim is not an audit hole for them; it is refused
    anyway, in the fail-closed posture of
    _bare_pytest_scope_has_symlink, because collection aimed
    into a residue directory can execute shapes no extension
    set enumerates — a bound conftest registering a custom
    pytest_collect_file hook executes non-.py files from
    there (paperthin validation 2, probe B2's family) — and
    a pythonpath entry makes the directory the import
    machinery's home. addopts positionals are the same aims
    carried by a key the two-key gate never read (Task 11
    review, finding F2), and an aim resolving outside the
    root collects or imports content the seal does not
    describe at all (finding F3). A cache-selection flag in
    addopts is refused on the same principle one level down:
    it aims collection at no place — it lets the cache
    tools' unbound state files choose which collected tests
    execute (see _addopts_cache_selection; paperthin
    validation 4, breach B-B). An aim at or through a
    symlink is refused on the same principle (Task 11
    re-review §4): the binding attests a link's target
    string, never its content. The traversal key is the one
    steering surface that is not an aim at all: it widens
    where the DEFAULT walk descends (paperthin validation
    3, breach B-NEW). A symlinked selected
    config is never read here: _pytest_argv already pins it
    to an empty config, so its entries define nothing
    (issue #64)."""
    selected = _pytest_config_selected(root)
    if selected is None or selected.is_symlink():
        return False
    if _selected_config_traversal_enters_residue(root):
        return True
    addopts = _pytest_config_addopts(selected)
    if _addopts_cache_selection(addopts):
        return True
    aims, pyargs = _addopts_aims(addopts)
    if pyargs:
        return True
    return any(
        _entry_aims_unattested(root, entry)
        for entry in (*_pytest_config_path_entries(selected), *aims)
    )


def _pytest_collectable_file(
    path: Path,
    python_files: tuple[str, ...],
    doctest_globs: tuple[str, ...],
) -> bool:
    """Whether pytest's own collection machinery executes
    the file at *path*, under the EFFECTIVE patterns (see
    _pytest_collection_patterns): conftest.py, which pytest
    imports from every directory it collects in and whose
    hooks can steer collection; a name matching an effective
    python_files pattern — core collection imports only .py
    files, but a pattern naming another suffix is the
    config's own declaration of what it treats as a test
    module, and the gate does not prove a negative about
    the hooks and plugins that declaration steers; or a
    name matching an effective doctest glob — the doctest
    plugin collects textfiles under its globs and executes
    their doctests, under the default test*.txt no less
    than under a widened --doctest-glob (the default-glob
    route is the one the pre-Task-12 default-pattern set
    missed entirely)."""
    name = path.name
    if name == "conftest.py":
        return True
    return any(
        _fnmatch_ex(pattern, str(path))
        for pattern in (*python_files, *doctest_globs)
    )


def _pytest_scope_link_file(
    path: Path,
    python_files: tuple[str, ...],
    doctest_globs: tuple[str, ...],
) -> bool:
    """Whether a symlinked file at *path* in the bare
    leg's collection scope disqualifies the leg: any `.py`
    name — collection executes an aimed .py file under any
    name, and a collected module imports a .py module by
    name from a sys.path directory the same way — or a
    name pytest's own machinery executes under the
    effective patterns (see _pytest_collectable_file). A
    name matching no pattern — a data file, a README — is
    never executed by collection itself, so a symlink
    under it disqualifies nothing; a bound conftest
    choosing to execute it is bound code acting in-tree,
    the disclosed family, not this gate's."""
    return path.name.endswith(".py") or _pytest_collectable_file(
        path, python_files, doctest_globs
    )


def _bare_pytest_scope_has_symlink(root: Path) -> bool:
    """Whether the bare pytest leg's collection scope at *root*
    reaches content through a symlink (issue #62).

    The bare leg runs pytest with no path arguments, so
    collection walks the tree below root, steered only by the
    config the leg's pinned argv selects — the in-tree config
    the gates judged, or the empty config — with rootdir and
    confcutdir pinned to the root itself (see _pytest_argv),
    so no ancestor config or conftest can steer it either.
    Collection traverses symlinked directories and executes
    symlinked collectable files, while the tree binding records
    only a link's target *string* — content reached through a
    link is bound nowhere, and mutating the target after
    sealing leaves a stale PASS standing. The scope therefore
    disqualifies the leg when it contains:

    - any symlinked DIRECTORY below root, at any depth — the
      conservative form: config can widen collection
      (testpaths, norecursedirs overrides), so no directory
      below root is provably outside the scope; or
    - any symlinked FILE pytest would execute, judged
      against the EFFECTIVE collection patterns (see
      _pytest_scope_link_file and
      _pytest_collection_patterns): every `.py` name, plus
      the names the effective python_files patterns and
      doctest globs name. The .py rule is deliberately
      wider than the name patterns collection uses by
      default: a config aim executes a .py file under ANY
      name (Task 11 re-review §4), and prepend import mode
      puts every collected test's directory on sys.path,
      where a .py module is importable by name — so no .py
      name is provably outside the execution scope. The
      boundary that remains is a non-.py name no effective
      pattern names: a symlinked data file is never
      executed by collection itself, so it disqualifies
      nothing.

    The walk prunes only .git — the VCS's own subtree, which
    the binding likewise never attests as project content. The
    caller-selected root itself may be a symlink: it is the
    boundary the binding canonicalizes, and only entries below
    it are judged. The walk never follows links, and any walk
    error disqualifies the leg (fail closed): a scope that
    cannot be inventoried cannot be attested symlink-free.
    """
    python_files, doctest_globs = _pytest_collection_patterns(root)
    errors: list[OSError] = []
    for dirpath, dirnames, filenames in os.walk(
        root, followlinks=False, onerror=errors.append
    ):
        current = Path(dirpath)
        descend: list[str] = []
        for name in dirnames:
            if name == ".git":
                continue
            if (current / name).is_symlink():
                return True
            descend.append(name)
        dirnames[:] = descend
        for name in filenames:
            if _pytest_scope_link_file(
                current / name, python_files, doctest_globs
            ) and (current / name).is_symlink():
                return True
    return bool(errors)


def _ancestor_dirs(root: Path) -> tuple[Path, ...]:
    """The directories a runner's upward resolution can reach
    from *root*: its ancestors, nearest first, up to the
    filesystem root. The binding attests the root's interior
    only, so anything found in these directories is unbound
    by construction (Task 15, paperthin validation 5)."""
    return tuple(root.resolve().parents)


def _ancestor_node_modules(root: Path) -> Path | None:
    """The nearest ancestor of *root* carrying a node_modules
    directory, else None. Node's module resolution climbs
    parent directories for every unsatisfied require, at any
    depth below the root, and no flag switches the climb
    off — while such an ancestor exists, which code a sealed
    npm run executes is partly a function of unbound
    content, so the leg is disqualified (see
    discover_verification_commands)."""
    for parent in _ancestor_dirs(root):
        if (parent / "node_modules").is_dir():
            return parent
    return None


def _cargo_exclude_matches(pattern: str, rel: str) -> bool:
    """Whether a workspace `exclude` *pattern* covers the
    crate's path *rel* (POSIX separators) below the workspace
    root: an exact path, or a glob judged with fnmatch, whose
    * crosses separators the way cargo's own glob matching
    does. The match is only ever used to ALLOW a leg, on the
    strength of cargo's probed exclude semantics; a missed
    match disqualifies instead (fail closed)."""
    return pattern == rel or fnmatch.fnmatchcase(rel, pattern)


def _cargo_manifest_tables(path: Path) -> dict | None:
    """The parsed tables of the Cargo manifest at *path*, or
    None when it cannot be read or does not parse. Cargo
    aborts on a manifest it cannot parse wherever it must
    read one, so a None here can only ever cost a refusal —
    it cannot hide steering cargo itself would have honoured."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _cargo_ancestor_steers(root: Path) -> bool:
    """Whether state in *root*'s ancestors can steer the
    cargo leg's run across the attested root (Task 15,
    paperthin validation 5) — cargo's two upward channels,
    both probed against the installed cargo:

    - .cargo config discovery: cargo merges
      .cargo/config.toml (or the extensionless .cargo/config)
      from every ancestor into the build's configuration; a
      rustc-wrapper named there EXECUTES during the root's
      build, and the discovery does not stop at the workspace
      boundary — it fires under a self-anchored root. Any
      ancestor carrying either file disqualifies,
      unconditionally.
    - workspace membership: a crate whose manifest carries
      no [workspace] table of its own is claimed by the
      nearest ancestor manifest that carries one, and the
      workspace root's manifest then governs the build (its
      [workspace.dependencies] paths and [patch] table can
      select code from outside the root — probed: mutating
      the ancestor's library flips the member crate's test).
      The claim ends where that manifest's exclude covers
      the crate's relative path (probed standalone) or at
      the crate's own [workspace] table (the self-anchor,
      probed). Membership cannot be settled from the
      members list alone — cargo errors on a plain
      non-member inside a workspace directory, but a path
      dependency of a member auto-enrolls a crate the list
      never names — so ANY ancestor workspace that does not
      exclude the crate disqualifies. A root manifest
      declaring package.workspace names an outside workspace
      as its governor in bound text and disqualifies on its
      own."""
    resolved = root.resolve()
    own = _cargo_manifest_tables(root / "Cargo.toml")
    own_tables = own if isinstance(own, dict) else {}
    package = own_tables.get("package")
    if isinstance(package, dict) and "workspace" in package:
        return True
    self_anchored = isinstance(own_tables.get("workspace"), dict)
    ancestors = _ancestor_dirs(root)
    for parent in ancestors:
        cargo_dir = parent / ".cargo"
        if (cargo_dir / "config.toml").is_file() or (
            cargo_dir / "config"
        ).is_file():
            return True
    if self_anchored:
        return False
    for parent in ancestors:
        manifest = parent / "Cargo.toml"
        if not manifest.is_file():
            continue
        tables = _cargo_manifest_tables(manifest)
        if not isinstance(tables, dict):
            continue
        workspace = tables.get("workspace")
        if not isinstance(workspace, dict):
            continue
        # The nearest workspace-bearing ancestor is the one
        # cargo's ascent judges membership against; parent is
        # an ancestor of resolved by construction, so the
        # relative path always exists.
        rel = resolved.relative_to(parent).as_posix()
        exclude = workspace.get("exclude")
        if isinstance(exclude, list) and any(
            isinstance(entry, str)
            and _cargo_exclude_matches(entry, rel)
            for entry in exclude
        ):
            return False
        return True
    return False


def discover_verification_commands(root: Path) -> tuple[VerificationCommand, ...]:
    # Symlink policy (issues #63, #64): a symlinked marker or
    # config file does not schedule, gate, or steer its leg. The
    # tree binding records a symlink's target *string* (git blob /
    # fs readlink), never the target's contents, so content
    # reached through a link is unbound: a symlinked go.mod,
    # Cargo.toml, package.json, Makefile, or .markdownlint.yaml
    # is treated as absent; a symlinked pytest config cannot
    # trigger the bare pytest leg; and the leg's argv always
    # pins the config the gates judged (or the empty config
    # when that config is a symlink or there is none), its
    # rootdir, and its confcutdir to the root itself, so no
    # ancestor config or conftest can steer the run either
    # (see _pytest_argv; Task 15 — the runners' upward
    # resolution is the same unbound-content shape one
    # directory up, and the cargo and npm legs below are
    # disqualified on their own ancestor channels).
    # The pytest config names are pytest's full inifile candidate
    # set — pytest.toml, .pytest.toml, pytest.ini, .pytest.ini,
    # pyproject.toml, tox.ini, setup.cfg (the precedence order
    # and per-name content conditions of
    # _pytest.config.findpaths in pytest 9; see
    # _PYTEST_CONFIG_CANDIDATES and _pytest_config_selected,
    # whose walk treats a symlink candidate as selected at its
    # position without reading it — deliberately conservative,
    # since over-insulation is the safe direction).
    # Issue #62: the bare pytest leg is additionally disqualified
    # when its collection scope contains a symlink — a symlinked
    # directory, a symlinked .py file of any name, or a
    # symlinked file the effective collection patterns name
    # (see _bare_pytest_scope_has_symlink) — or when the real
    # config pytest would read steers collection or sys.path at
    # unattested content over its full steering surface —
    # testpaths, pythonpath, addopts positionals, --pyargs,
    # cache-selection flags, and norecursedirs judged for
    # whether default traversal can still enter a residue
    # directory;
    # targets: a residue directory, anywhere outside the
    # root, or a path at or through a symlink (see
    # _selected_config_aims_unattested: files under
    # residue names are largely bound in the tree digest, but
    # collection aimed there can execute shapes no extension
    # set enumerates, and content outside the root — or behind
    # a link — is bound nowhere). Excluding links from
    # discovery's own reads cannot help there — the leg runs
    # pytest over the whole tree, and pytest's own traversal is
    # what reaches the linked content — so the leg is not
    # scheduled at all. The check is lazy and memoized: trees
    # that never become pytest candidates pay no walk, and
    # sections 4 and 5 share the one result.
    # The caller-selected root itself may be a symlink — it is
    # the boundary the binding canonicalizes; every check below
    # applies to entries under it.
    commands: list[VerificationCommand] = []
    seen: set[str] = set()

    def add(command: VerificationCommand) -> None:
        if command.id not in seen:
            seen.add(command.id)
            commands.append(command)

    scope_check: list[bool] = []

    def bare_pytest_disqualified() -> bool:
        if not scope_check:
            scope_check.append(
                _bare_pytest_scope_has_symlink(root)
                or _selected_config_aims_unattested(root)
            )
        return scope_check[0]

    # 1. Go (AEP addition). The leg runs with GOWORK=off
    # forced in run_verification, so an ancestor go.work can
    # never put the run in workspace mode (Task 15).
    if _is_real_file(root / "go.mod"):
        add(VerificationCommand("go-test", "Go tests", ("go", "test", "./...")))

    # 2. Rust. Disqualified when ancestor state — a .cargo
    # config, or a workspace that would claim the crate —
    # can steer the build across the root (Task 15; see
    # _cargo_ancestor_steers).
    if _is_real_file(root / "Cargo.toml") and not _cargo_ancestor_steers(
        root
    ):
        add(VerificationCommand("cargo-test", "Rust tests", ("cargo", "test")))

    # 3. Node — only with a real scripts.test string, and
    # only when no ancestor carries a node_modules directory
    # node's upward resolution could climb into (Task 15; see
    # _ancestor_node_modules).
    package_json = root / "package.json"
    if _is_real_file(package_json) and _ancestor_node_modules(root) is None:
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            scripts = data.get("scripts")
            if isinstance(scripts, dict):
                test_script = scripts.get("test")
                if (
                    isinstance(test_script, str)
                    and test_script.strip()
                    and "no test specified" not in test_script.lower()
                ):
                    add(
                        VerificationCommand(
                            "npm-test", "Node tests", ("npm", "test")
                        )
                    )

    # 4. Python markers.
    if (
        any(
            _is_real_file(root / name)
            for name in _PYTEST_CONFIG_CANDIDATES
        )
        or (root / "tests").exists()
    ) and not bare_pytest_disqualified():
        add(
            VerificationCommand("pytest", "Python tests", _pytest_argv(root))
        )

    # 5. Root-level python test files, partitioned by runner
    # collection semantics (Task 4, per-module AST classification —
    # see _classify_test_module): modules defining TestCase
    # subclasses run under the unittest runner (named explicitly —
    # discover's default pattern (test*.py) would silently skip the
    # *_test.py files discovery accepts), and modules that trigger
    # the pytest leg fall to the shared bare pytest command, which
    # collects plain test functions the unittest runner never would.
    # A mixed suite therefore runs BOTH runners; a single-style
    # suite runs exactly the one command it ran before.
    # Issue #61: the partition applies the symlink policy to the
    # test files themselves — entry acceptance is _is_real_file,
    # not is_file, so a symlinked root-level test file is neither
    # classified (its contents are never read here) nor scheduled
    # by either leg: the binding records only the link's target
    # string, so the target's contents are bound nowhere.
    test_files: list[Path] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not _is_real_file(entry) or not entry.name.endswith(".py"):
                continue
            if entry.name.startswith("test_") or entry.name.endswith("_test.py"):
                test_files.append(entry)
    if test_files:
        unittest_modules: list[str] = []
        pytest_triggered = False
        # A shared leg is speculative only when EVERY module
        # that scheduled it did so through classification
        # uncertainty; one module's deterministic evidence makes
        # the leg deterministic (issue #51).
        unittest_speculative = True
        pytest_speculative = True
        for path in test_files:
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(SCAN_CHARS + 1)
            except OSError:
                text = ""
            truncated = len(text) > SCAN_CHARS
            (
                has_unittest,
                triggers_pytest,
                module_unittest_speculative,
                module_pytest_speculative,
            ) = _classify_module(text[:SCAN_CHARS], truncated=truncated)
            if has_unittest:
                unittest_modules.append(path.stem)
                if not module_unittest_speculative:
                    unittest_speculative = False
            if triggers_pytest:
                pytest_triggered = True
                if not module_pytest_speculative:
                    pytest_speculative = False
        if unittest_modules:
            add(
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    ("python3", "-m", "unittest", "-v", *unittest_modules),
                    speculative=unittest_speculative,
                )
            )
        if pytest_triggered and not bare_pytest_disqualified():
            add(
                VerificationCommand(
                    "pytest",
                    "Python tests",
                    _pytest_argv(root),
                    speculative=pytest_speculative,
                )
            )

    # 6. Make (AEP addition).
    makefile = root / "Makefile"
    if _is_real_file(makefile):
        try:
            text = makefile.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if re.search(r"^test:", text, re.MULTILINE):
            add(VerificationCommand("make-test", "Make tests", ("make", "test")))

    # 7. Markdown lint (AEP addition) — binary called directly, never npx.
    if _is_real_file(root / ".markdownlint.yaml") and (
        shutil.which("markdownlint-cli2") is not None
    ):
        add(
            VerificationCommand(
                "markdownlint", "Markdown lint", MARKDOWNLINT_ARGV
            )
        )

    # 8. Scripts test suite (AEP addition) — suites living in
    # scripts/tests, run exactly as CI's script-tests job's
    # unittest-discover step runs them. The caller-selected root may
    # itself be a symlink, but below that boundary both scripts and
    # scripts/tests must be real directories, no entry anywhere in
    # the scripts/tests subtree may be a symlink, and at least one
    # top-level test*.py must be a regular file. The inventory must
    # also be complete: os.walk ignores scandir errors by default,
    # so any part of the subtree that cannot be listed disqualifies
    # the leg (fail closed) instead of silently truncating the
    # inventory. This keeps the leg from attesting a foreign tree's
    # tests while avoiding a vacuous command for an empty or
    # test-less directory.
    scripts_dir = root / "scripts"
    scripts_tests = scripts_dir / "tests"
    scripts_suite_contained = (
        scripts_dir.is_dir()
        and not scripts_dir.is_symlink()
        and scripts_tests.is_dir()
        and not scripts_tests.is_symlink()
    )
    if scripts_suite_contained:
        inventory_errors: list[OSError] = []
        subtree_has_symlink = any(
            Path(dirpath, entry).is_symlink()
            for dirpath, dirnames, filenames in os.walk(
                scripts_tests,
                followlinks=False,
                onerror=inventory_errors.append,
            )
            for entry in (*dirnames, *filenames)
        )
        scripts_suite_contained = (
            not inventory_errors and not subtree_has_symlink
        )
    if scripts_suite_contained and any(
        entry.is_file() and not entry.is_symlink()
        for entry in scripts_tests.glob("test*.py")
    ):
        add(
            VerificationCommand(
                "scripts-unittest",
                "Scripts unittest",
                (
                    "python3",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "scripts/tests",
                    "-v",
                ),
            )
        )

    return tuple(commands)


class _TailBuffer:
    """Byte sink retaining only the last OUTPUT_CAP_BYTES bytes."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.total = 0

    def append(self, chunk: bytes) -> None:
        self.total += len(chunk)
        self._buf.extend(chunk)
        overflow = len(self._buf) - OUTPUT_CAP_BYTES
        if overflow > 0:
            del self._buf[:overflow]

    @property
    def truncated(self) -> bool:
        return self.total > OUTPUT_CAP_BYTES

    @property
    def raw(self) -> bytes:
        """The retained bytes exactly as captured (post-cap tail)."""
        return bytes(self._buf)

    def text(self) -> str:
        return bytes(self._buf).decode("utf-8", errors="replace")


def _drain(stream, buffer: _TailBuffer) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            buffer.append(chunk)
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _read_proc_stat(pid: int) -> tuple[int, int, int, str] | None:
    """(ppid, pgrp, start_time, state) from /proc/<pid>/stat.

    start_time (field 22) identifies a process incarnation: a pid
    whose start_time differs from the one recorded earlier is a
    different process that recycled the pid.
    """
    try:
        text = Path(f"/proc/{pid}/stat").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None
    try:
        rest = text.rsplit(")", 1)[1].split()
        return int(rest[1]), int(rest[2]), int(rest[19]), rest[0]
    except (IndexError, ValueError):
        return None


def _children_start_times() -> dict[int, int]:
    """Map of this process's current child pids to their start times."""
    me = os.getpid()
    children: dict[int, int] = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return children
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        stat = _read_proc_stat(pid)
        if stat is not None and stat[0] == me:
            children[pid] = stat[2]
    return children


def _sweep_survivors(
    leader_pid: int, snapshot: dict[int, int]
) -> tuple[tuple[int, ...], bool]:
    """Kill everything a finished command left behind.

    Targets are (a) this process's children that were NOT in the
    pre-spawn snapshot — adoptees: descendants orphaned when the
    leader exited, reparented here when the subreaper flag is set —
    and (b) remaining members of the leader's process group. A
    `setsid` descendant escapes (b) by construction but lands in (a).
    Processes in the snapshot (bystanders that predate the command)
    are never signalled. Each target's (pid, start_time) identity is
    re-verified immediately before SIGKILL, and killed adoptees are
    reaped per pid. Iterates until no live target remains or the
    sweep bound elapses; returns (killed, exhausted) — exhausted
    means a live survivor outlasted the bound, which the caller must
    surface as a failure, never pass silently.
    """
    me = os.getpid()
    killed: list[int] = []
    deadline = time.monotonic() + SWEEP_BOUND_SECONDS
    while True:
        targets: dict[int, int] = {}
        try:
            entries = list(Path("/proc").iterdir())
        except OSError:
            entries = []
        for entry in entries:
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == me or pid == leader_pid:
                continue
            stat = _read_proc_stat(pid)
            if stat is None:
                continue
            ppid, pgrp, start_time, state = stat
            if state == "Z":
                # Dead awaiting reaping — not a live survivor. If it
                # is ours, collect it so it does not linger as a
                # zombie for the rest of this process's life.
                if ppid == me and snapshot.get(pid) != start_time:
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except OSError:
                        pass
                continue
            if (ppid == me and snapshot.get(pid) != start_time) or (
                pgrp == leader_pid
            ):
                targets[pid] = start_time
        if not targets:
            return tuple(killed), False
        if time.monotonic() >= deadline:
            return tuple(killed), True
        for pid, start_time in targets.items():
            current = _read_proc_stat(pid)
            if current is None or current[2] != start_time:
                continue  # gone, or the pid was recycled — not ours
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                continue
            if pid not in killed:
                killed.append(pid)
            try:
                os.waitpid(pid, os.WNOHANG)
            except OSError:
                pass
        time.sleep(0.05)


def _set_child_subreaper() -> bool:
    """Set PR_SET_CHILD_SUBREAPER on this process (Linux), best-effort.

    With the flag set, descendants orphaned by a verification command
    reparent here instead of to init, so the post-run sweep can find
    and reap them. Set once from main() before append_run_start;
    in-process callers do not set it — the sweep is snapshot-scoped
    and safe either way. Returns whether the flag was set.
    """
    try:
        return ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) == 0
    except Exception:
        return False


_UNITTEST_RAN_RE = re.compile(r"^Ran (\d+) tests?\b", re.MULTILINE)
_PYTEST_ROOTDIR_RE = re.compile(r"^rootdir:\s*(.+?)\s*$", re.MULTILINE)


def _pytest_transcript_rootdir(stdout: str) -> str | None:
    """The rootdir named in a pytest transcript's header, or
    None when the header names none (suppressed verbosity, or
    a transcript whose head the capped capture did not
    retain). The header prints the path absolute; pre-8
    pytest appended ", inifile: ..." to the same line, which
    is not part of the path."""
    match = _PYTEST_ROOTDIR_RE.search(stdout)
    if match is None:
        return None
    value = match.group(1).split(", inifile:", 1)[0].strip()
    return value or None


def _pytest_rootdir_escapes(stdout: str, root: Path) -> bool:
    """Whether the transcript's header names a rootdir other
    than *root* — positive evidence the run attested a
    different tree than the binding covers (Task 15). A
    transcript naming no rootdir makes no claim and never
    fires this: the argv pin (see _pytest_argv) is the
    primary confinement; this is its tripwire."""
    named = _pytest_transcript_rootdir(stdout)
    if named is None:
        return False
    return Path(named).resolve() != root.resolve()


_PYTEST_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|deselected|errors?|xfailed|xpassed)\b"
)
_PYTEST_SUMMARY_TAIL_RE = re.compile(r" in \d+(?:\.\d+)?s\b")
# The collection header pytest prints as collection finishes
# ("collecting ... collected N items"): the transcript's own
# statement of how much collection found, independent of the
# summary line the count parser reads.
_PYTEST_COLLECTED_RE = re.compile(r"collected (\d+) items?\b")


def _pytest_summary_count(stdout: str, stderr: str) -> int | None:
    """The collected count the transcript's terminal summary
    states, or None when the transcript carries no summary line
    at all (verbosity stacked it away — issue #53).

    The count is the sum of the outcome groups in the summary
    line (passed+failed+skipped+errors+xfailed+xpassed)
    EXCLUDING `deselected` — deselected tests were filtered OUT
    by the runner and never collected for execution (panel
    correctness P2-B). Zero collection is recognized only from
    the runner's final summary line itself (`no tests ran
    in …s`): the same phrase in test output (exposed by e.g.
    `addopts = -s`) is a diagnostic, not the summary, and must
    not override it (Codex P2, round 4).
    """
    total: int | None = None
    for line in (stdout + "\n" + stderr).splitlines():
        if not _PYTEST_SUMMARY_TAIL_RE.search(line):
            continue
        groups = _PYTEST_COUNT_RE.findall(line)
        if groups:
            total = sum(
                int(count)
                for count, label in groups
                if label != "deselected"
            )
        elif "no tests ran" in line:
            # The summary line itself reports zero collection.
            # The phrase anywhere else (a test's printed
            # diagnostic) never reaches this branch: it is
            # either not summary-shaped or superseded by the
            # real summary, which pytest prints last.
            total = 0
    return total


def _count_collected(
    command_id: str, stdout: str, stderr: str
) -> int | None:
    """Collected-test count for a Python command; None for other
    commands (the count gate does not apply to them).

    unittest: parse `Ran (\\d+) tests?` from stdout+stderr combined
    (unittest writes it to stderr). The `scripts-unittest` leg
    (rule 8's scripts/tests discovery) is a unittest-discover run
    and is counted by the same rule — without it the leg sealed
    receipts with no collected count and the gate never judged it.
    pytest: the transcript channel — the terminal summary, parsed
    by _pytest_summary_count. This is no longer the count of
    record for a real run: run_verification composes it with the
    run's junitxml report (see _pytest_collected_count), and this
    channel is the cross-check a present report is judged
    against. It never carries the count on its own: when the
    report channel abstains, the composed count is unproven
    (None), not this channel's number (issue #53, round 2).
    A transcript with no summary line at all (dots only, or
    quiet levels stacked past what
    PYTEST_ARGV's net verbosity preserves — Codex P2, round 5)
    parses to 0 here: verbosity-independent evidence was
    deliberately NOT taken from e.g. the progress dots, which
    are not a count.
    Trust level (issue #54, stated where the parser lives):
    this channel reads what the runner's terminal reporter
    printed, and whatever shapes that output sits at the
    parser's trust level — a reporter-replacing plugin (e.g.
    pytest-sugar) that changes or omits the summary line, like
    every plugin loaded into the runner's environment, is
    trusted the way the interpreter itself is trusted. Its
    role in the composed count is cross-check, never carrier:
    since issue #53 a summary that contradicts the run's
    junitxml report yields 0 — both channels present, in
    disagreement, so the run proves nothing — and since the
    #53 round-2 fix a run whose report is absent has an
    unproven count that fails the count gate, so this channel
    is never believed on its own. _pytest_collected_count
    carries the full trust-level statement for the composed
    count.
    An unparseable count is 0 — a Python command
    that cannot prove it collected anything fails the count gate in
    VerificationResult.passed. Skips count as collected (deliberate
    ruling): the guarantee is "routed to a runner that collects the
    test"; whether a collected test skips is the test author's
    signal, not a routing failure.
    """
    if command_id in ("unittest", "scripts-unittest"):
        match = _UNITTEST_RAN_RE.search(stdout + "\n" + stderr)
        return int(match.group(1)) if match is not None else 0
    if command_id == "pytest":
        total = _pytest_summary_count(stdout, stderr)
        return total if total is not None else 0
    return None


# The report channel's read cap: a genuine report is proportional
# to the suite it describes; anything larger is not evidence the
# composition will weigh (it abstains, like an unparseable file).
_JUNITXML_MAX_BYTES = 64 * 1024 * 1024


def _junitxml_count(report_path: Path) -> int | None:
    """The collected count in the junitxml report at
    *report_path*: the number of <testcase> elements it carries,
    or None when the channel abstains (file missing, empty,
    oversized, unparseable, or not a junit report at all).

    Element count, not the testsuite `tests` attributes: the
    elements are the report's items themselves. Collection
    errors appear as a testcase bearing <error>, so the count
    matches the transcript parser's error-group counting on the
    same run. Both report shapes occur (a <testsuites> root, or
    a bare <testsuite> under junit_family=xunit1); anything else
    is not a report. ElementTree never resolves external
    entities, and the byte cap bounds what a run can make the
    verifier parse.
    """
    try:
        if report_path.stat().st_size > _JUNITXML_MAX_BYTES:
            return None
        data = report_path.read_bytes()
    except OSError:
        return None
    if not data:
        return None
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    if root.tag not in ("testsuites", "testsuite"):
        return None
    return len(root.findall(".//testcase"))


def _pytest_collected_count(
    report_count: int | None, stdout: str, stderr: str
) -> int | None:
    """The pytest leg's collected count of record (issue #53),
    composed from the run's two evidence channels:

    - the junitxml report the same run wrote to a tempfile
      outside the tree (*report_count*, None when the report
      channel abstains — the file is missing, empty, oversized,
      unparseable, or not a junit report), and
    - the transcript summary (_pytest_summary_count, None when
      verbosity suppressed it).

    The composition, by which channels the run produced:

    - Report present: its count is the count — verbosity cannot
      stack it away, and passive project config cannot redirect
      or inflate it (the verifier's --junitxml is a
      command-line option: it beats the same option in addopts,
      which are prepended). When a summary survived verbosity
      it must AGREE with the report: the two channels describe
      the same run, and a contradiction means at least one was
      written by something other than the runner's own
      accounting, so the count is 0 and the leg fails closed.
      The report stands alone only when no summary exists —
      exactly the stacked-quiet case whose absence of evidence
      was the defect.
    - Report absent: the count is UNPROVEN (None) and the leg
      fails the count gate (round 2) — the transcript is never
      believed on its own. A completed pytest session writes
      its report unconditionally, zero-collection sessions
      included, so an absent report after a completed run
      means the tree's own bound config switched the evidence
      channel off (a passive `addopts = -p no:junitxml` line
      suffices) or in-tree code interfered with it; either way
      the run produced none of the evidence the verifier chose,
      and a channel the tree can switch off cannot be replaced
      by the transcript, whose summary line in-tree code can
      print verbatim (the fd-2 forgery). Suppression is
      self-defeating: it buys a failed gate, never a pass.
      Runs the exit status already fails are unaffected in
      outcome — a spawn error produced no run at all, and a
      killed or usage-error run wrote no report either; for
      those, the absent report is not what fails them.

    Trust level, stated plainly: both channels are produced
    inside the runner process, and in-tree code running there
    sits at the interpreter's own trust level (issue #54's
    family; the forging code is digest-bound in the sealed
    tree). When both channels are present, defeating the count
    requires forging both to the same number in the same run.
    In the report-alone case (a quiet tree) the count rests on
    the report channel by itself, and a tree whose own code
    overwrites that report defeats it — the same exposure
    class as a conftest monkeypatching assertions. No same-run
    channel can do better, and the composition claims nothing
    stronger.
    """
    summary = _pytest_summary_count(stdout, stderr)
    if report_count is None:
        return None
    if summary is not None and summary != report_count:
        return 0
    return report_count


# CPython ≥3.12's unittest CLI exit code for a run that collected
# zero tests (unittest.main's _NO_TESTS_EXITCODE). Older versions
# exit 0 for the identical "Ran 0 tests" transcript.
_UNITTEST_NO_TESTS_EXIT_CODE = 5


def _clean_zero_collection(
    command: VerificationCommand, result: VerificationResult
) -> bool:
    """Whether a leg's failure is solely a clean zero collection.

    Exit 0 is the historic presentation. A unittest leg on CPython
    ≥3.12 instead exits _UNITTEST_NO_TESTS_EXIT_CODE for the same
    transcript — the loader ran, collected nothing, nothing errored
    (issue #56) — and that presentation is the same routing signal,
    so it defers exactly as exit 0 does. The signal is the PAIR
    (parsed count, exit code), never the exit code alone, and for
    exit 5 the parsed zero must come from a genuine "Ran 0 tests"
    line: the count parser also reports 0 when no summary line
    exists at all (a runner that died before printing one), and a
    fallback zero is not evidence of a clean zero collection. A
    broken leg never presents this way — unittest's loader
    fabricates a _FailedTest for an unimportable module, which
    runs and reports "Ran 1 test" with exit 1.
    """
    if result.tests_collected != 0:
        return False
    if result.exit_code == 0:
        return True
    if (
        command.id != "unittest"
        or result.exit_code != _UNITTEST_NO_TESTS_EXIT_CODE
    ):
        return False
    match = _UNITTEST_RAN_RE.search(result.stdout + "\n" + result.stderr)
    return match is not None and int(match.group(1)) == 0


def _speculative_zero_pair(tests_collected, exit_code) -> bool:
    """The (parsed count, exit code) pair a speculative clean
    zero must present — the part of the predicate the runtime
    and the audit acceptor share. A parsed zero, and either
    exit 0 (the historic presentation) or the runners' no-tests
    exit code 5. The pair is necessary, never sufficient: each
    side adds the evidence its shape allows (the transcript at
    runtime, the segment at audit).
    """
    return tests_collected == 0 and exit_code in (
        0,
        _UNITTEST_NO_TESTS_EXIT_CODE,
    )


def _pytest_reports_zero_collection(
    result: VerificationResult,
) -> bool:
    """Whether a pytest transcript positively reports that
    collection found nothing: at least one "collected N items"
    header line, and every such line reports zero. A line
    reporting more — wherever in the transcript it appears —
    contradicts the zero the summary parsed to, and the
    benefit of the doubt goes to the contradiction (a genuine
    zero's only collected line reports zero).
    """
    counts = [
        int(n)
        for n in _PYTEST_COLLECTED_RE.findall(
            result.stdout + "\n" + result.stderr
        )
    ]
    return bool(counts) and all(n == 0 for n in counts)


def _speculative_clean_zero(
    command: VerificationCommand, result: VerificationResult
) -> bool:
    """Whether a speculative leg's failure is solely a clean zero
    collection, judged by the pair (parsed count, exit code)
    plus the transcript evidence each runner can produce.

    Exit 0 with a parsed zero is the historic presentation for
    unittest (older CPython exits 0 over the same "Ran 0 tests"
    transcript). The no-tests exit code 5 is not
    self-evidencing for either runner, and each proves a clean
    zero against its own transcript:

    - unittest must present the genuine "Ran 0 tests" line,
      exactly as _clean_zero_collection pins for the deferral,
      so a runner that died before printing a summary — whose
      count parses to a fallback zero — is not mistaken for a
      clean zero.
    - pytest must positively report zero collection: a
      "collected 0 items" header line and no collected line
      reporting more. Exit 5 alone would also accept a
      MANUFACTURED pair: a tree-supplied conftest whose
      pytest_collection_modifyitems calls
      pytest.exit(returncode=5) after collection printed
      "collected 2 items" leaves a summary that parses to zero
      beside exit 5, while the routed tests never ran. The
      collection line sits in the same transcript and
      contradicts the zero, so such a leg is judged on its
      merits. (A hook that could suppress the header entirely
      would operate at the transcript's trust level — issue
      #54's family; absent the positive line, the zero is
      simply not clean either way.)
    """
    if not _speculative_zero_pair(
        result.tests_collected, result.exit_code
    ):
        return False
    if command.id == "pytest":
        return _pytest_reports_zero_collection(result)
    if result.exit_code == 0:
        return True
    return _clean_zero_collection(command, result)


def _policy_path() -> Path:
    """Resolve the launch-policy file: $AEP_POLICY_DATA when set, else
    the policy.data beside this script — the same rule lane-coord.sh's
    load_policy applies."""
    override = os.environ.get("AEP_POLICY_DATA")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "policy.data"


class PolicyError(ValueError):
    """An existing policy file cannot be honored. Raised by the
    policy reader under the same fail-closed grammar lane-coord.sh's
    load_policy enforces; a MISSING file is not an error (it yields
    no fragments, and the record says so)."""


def _load_policy_fragments(policy_path) -> tuple[str, ...] | None:
    """The [env-scrub] fragments of a policy file, strictly parsed.

    Returns None when the file does not exist. Raises PolicyError for
    an existing file lane-coord's grammar refuses: unreadable, an
    unknown or misspelled section header, content before any section
    header, an entry containing whitespace, or either section
    ([sensitive-paths] / [env-scrub]) missing or empty — an emptied
    [env-scrub] section is exactly the fragmentless-policy hole the
    panel reproduced (full environment, record claiming 'scrubbed').
    """
    path = Path(policy_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise PolicyError(f"cannot read {path}: {exc}") from exc
    sections: dict[str, list[str]] = {
        "sensitive-paths": [],
        "env-scrub": [],
    }
    section: str | None = None
    for num, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if line in ("[sensitive-paths]", "[env-scrub]"):
                section = line[1:-1]
                continue
            raise PolicyError(
                f"line {num}: unknown section header {line!r} in {path}"
            )
        if section is None:
            raise PolicyError(
                f"line {num}: content before any section header "
                f"in {path}"
            )
        if any(ch.isspace() for ch in line):
            raise PolicyError(
                f"line {num}: entry contains whitespace in {path}"
            )
        sections[section].append(line)
    for name, entries in sections.items():
        if not entries:
            raise PolicyError(f"section [{name}] is empty in {path}")
    return tuple(sections["env-scrub"])


def policy_env_scrub(policy_path) -> tuple[str, ...]:
    """Read the [env-scrub] fragments from a policy.data file.

    A missing file yields no fragments. An existing file is parsed
    under lane-coord.sh's fail-closed grammar (see
    _load_policy_fragments) and raises PolicyError when it cannot be
    honored — the reader never silently returns an empty list for a
    file that is present but broken.
    """
    fragments = _load_policy_fragments(policy_path)
    return fragments if fragments is not None else ()


def _auth_occurrence_is_sensitive(upper: str) -> bool:
    """True if an (already uppercased) name has an AUTH occurrence that
    is NOT boundary-exempt — a port of lane-coord.sh's
    auth_occurrence_is_sensitive. An occurrence is exempt when
    immediately preceded by SSH_ (spares SSH_AUTH_SOCK) or immediately
    followed by OR + ('_' or end-of-name) (spares GIT_AUTHOR_NAME,
    ...AUTHOR / ...AUTHOR_ names). AUTHORITY is not exempt: its AUTH
    is followed by ORI..., not OR_/end.
    """
    start = 0
    while True:
        i = upper.find("AUTH", start)
        if i < 0:
            return False
        if i >= 4 and upper[i - 4 : i] == "SSH_":
            start = i + 1
            continue
        after = upper[i + 4 :]
        if after == "OR" or after.startswith("OR_"):
            start = i + 1
            continue
        return True


def _name_is_sensitive(name: str, fragments) -> bool:
    """Port of lane-coord.sh's name_is_sensitive: a name is sensitive
    when it contains any [env-scrub] fragment as a case-insensitive
    substring (the AUTH fragment applies its boundary exemptions;
    other fragments have none)."""
    upper = name.upper()
    for fragment in fragments:
        frag_upper = fragment.upper()
        if frag_upper == "AUTH":
            if _auth_occurrence_is_sensitive(upper):
                return True
        elif frag_upper and frag_upper in upper:
            return True
    return False


def build_run_env(policy_path) -> dict:
    """The environment verification commands run with: os.environ
    minus every name the policy's [env-scrub] fragments mark sensitive.

    AEP_VERIFY_FULL_ENV=1 opts out (mirroring lane-coord's
    AEP_LANE_FULL_ENV) and the full environment passes through. With
    no fragments — a missing policy file — nothing is scrubbed. An
    existing-but-invalid policy file raises PolicyError (fail
    closed): it is never silently treated as "no fragments".
    """
    env = dict(os.environ)
    if os.environ.get("AEP_VERIFY_FULL_ENV") == "1":
        return env
    fragments = policy_env_scrub(policy_path)
    if not fragments:
        return env
    return {
        name: value
        for name, value in env.items()
        if not _name_is_sensitive(name, fragments)
    }


def run_env_mode(policy_path) -> str:
    """The env mode stated on the run-start record, derived from the
    fragments actually applied — never from the file's mere
    existence. A missing policy file is 'unscrubbed (no policy)';
    the explicit opt-out is 'full (AEP_VERIFY_FULL_ENV)'; 'scrubbed'
    is stated only when a non-empty fragment list was extracted (and
    is what build_run_env applies). An existing-but-invalid file
    raises PolicyError: no honest mode string exists for it, and the
    run refuses before any command executes."""
    if os.environ.get("AEP_VERIFY_FULL_ENV") == "1":
        return "full (AEP_VERIFY_FULL_ENV)"
    if not Path(policy_path).exists():
        return "unscrubbed (no policy)"
    fragments = policy_env_scrub(policy_path)
    if not fragments:
        return "unscrubbed (no fragments)"
    return "scrubbed"


def run_verification(
    root: Path,
    command: VerificationCommand,
    timeout_seconds: float = 300,
) -> VerificationResult:
    env = build_run_env(_policy_path())
    env["CI"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    if command.id == "go-test":
        # Task 15 (paperthin validation 5): the go leg runs in
        # module mode, always. An ancestor go.work would
        # otherwise put the run in workspace mode and resolve
        # the root module's imports from modules outside the
        # attested root. GOFLAGS cannot carry workspace mode
        # (probed), but a caller-supplied GOWORK could
        # re-enable it, so the value is assigned here — after
        # build_run_env has composed the caller's environment —
        # where nothing later overrides it (the posture of CI
        # above, holding under AEP_VERIFY_FULL_ENV for the
        # same reason). An in-tree go.work does not govern the
        # leg either: the leg attests the root module in
        # module mode, and a tree that needs its workspace
        # fails honestly rather than sealing a workspace run.
        env["GOWORK"] = "off"
    # Issue #53: the pytest leg's collected count is read from a
    # junitxml report the same run writes — never from inside the
    # verified tree, where the artifact would collide with the
    # binding and tree-clean checks (the round-5 objection), but
    # to a tempfile in the system temp dir. The executed command
    # carries the flag, so the result — and therefore the sealed
    # receipt — records the argv that actually ran, evidence
    # channel included. The tempfile is consumed and removed
    # below, on every return path.
    executed = command
    report_path: Path | None = None
    if command.id == "pytest":
        fd, report_name = tempfile.mkstemp(
            prefix="mechanical-verify-junitxml-", suffix=".xml"
        )
        os.close(fd)
        report_path = Path(report_name)
        executed = VerificationCommand(
            command.id,
            command.label,
            command.argv + (f"--junitxml={report_path}",),
            command.speculative,
        )
    started = time.monotonic()
    # Snapshot this process's children immediately before the spawn:
    # the post-run sweep kills only children that appear after this
    # point (plus the leader's group), so bystanders that predate the
    # command are never signalled.
    snapshot = _children_start_times()
    try:
        proc = subprocess.Popen(
            list(executed.argv),
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        if report_path is not None:
            report_path.unlink(missing_ok=True)
        return VerificationResult(
            command=executed,
            exit_code=None,
            timed_out=False,
            duration_ms=int((time.monotonic() - started) * 1000),
            stdout="",
            stderr=str(exc),
            output_truncated=False,
            stdout_bytes=b"",
            stderr_bytes=str(exc).encode("utf-8"),
        )

    stdout_buf = _TailBuffer()
    stderr_buf = _TailBuffer()
    threads = [
        threading.Thread(target=_drain, args=(proc.stdout, stdout_buf), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, stderr_buf), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            proc.wait(timeout=TERM_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        # Escalate even when the leader already exited: a descendant
        # that ignored SIGTERM can outlive it while still holding the
        # process group (and the worktree). SIGKILL whatever remains.
        try:
            os.killpg(proc.pid, 0)
        except OSError:
            pass
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        if proc.returncode is None:
            proc.wait()
    # The leader has been waited on every path above — only now may
    # the sweep run. Reaping concurrently with a live Popen would let
    # a stray waitpid consume the leader's exit status and corrupt
    # its reported exit code.
    survivors_killed, survivors_remaining = _sweep_survivors(
        proc.pid, snapshot
    )
    for thread in threads:
        thread.join(timeout=5)

    stdout_text = stdout_buf.text()
    stderr_text = stderr_buf.text()
    tests_collected = _count_collected(
        command.id, stdout_text, stderr_text
    )
    if report_path is not None:
        # Read only now — after the leader was waited on and the
        # survivor sweep ran, no writer of the report remains.
        tests_collected = _pytest_collected_count(
            _junitxml_count(report_path), stdout_text, stderr_text
        )
        if _pytest_rootdir_escapes(stdout_text, root):
            # Defence in depth behind the argv pin (Task 15):
            # the run's own header names a rootdir other than
            # the attested root, so whatever it collected, it
            # attested a different tree — its count is unproven
            # and the leg fails the count gate (see
            # VerificationResult.passed). The header sits at
            # the start of the transcript and the capture is a
            # capped tail, so a transcript too long to retain
            # it makes no claim either way; the pin is the
            # confinement, this fires only on positive evidence
            # of escape.
            tests_collected = None
        report_path.unlink(missing_ok=True)
    return VerificationResult(
        command=executed,
        exit_code=proc.returncode,
        timed_out=timed_out,
        duration_ms=int((time.monotonic() - started) * 1000),
        stdout=stdout_text,
        stderr=stderr_text,
        stdout_bytes=stdout_buf.raw,
        stderr_bytes=stderr_buf.raw,
        output_truncated=stdout_buf.truncated or stderr_buf.truncated,
        survivors_killed=survivors_killed,
        survivors_remaining=survivors_remaining,
        tests_collected=tests_collected,
    )


def available_memory_kb() -> int | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^MemAvailable:\s+(\d+)\s*kB", text, re.MULTILINE)
    if match is None:
        return None
    return int(match.group(1))


# The Python test legs whose collected counts the count gate
# judges (see _count_collected). At most one of each is ever
# scheduled (discovery dedupes by command id).
_PYTHON_LEG_IDS = frozenset({"unittest", "pytest"})


def run_all(
    root,
    commands,
    *,
    timeout_seconds=300,
    budget_seconds=600,
    mem_available_kb=available_memory_kb,
    on_result=None,
    between_commands=None,
) -> int:
    mem_kb = mem_available_kb() if mem_available_kb is not None else None
    if mem_kb is not None and mem_kb < MIN_MEMORY_KB:
        print(
            "VERIFY: insufficient memory available "
            f"({mem_kb // 1024} MiB < 512 MiB); refusing to run"
        )
        return 3

    if not commands:
        return 2

    started = time.monotonic()
    executed = 0
    python_leg_passed = False
    for idx, command in enumerate(commands):
        elapsed = time.monotonic() - started
        if elapsed >= budget_seconds:
            remaining = len(commands) - idx
            print(
                f"VERIFY: budget exhausted ({budget_seconds}s); "
                f"{remaining} command(s) not run"
            )
            return 1
        effective_timeout = min(timeout_seconds, budget_seconds - elapsed)
        result = run_verification(root, command, timeout_seconds=effective_timeout)
        executed += 1
        if on_result is not None:
            on_result(result)
        # Count-gate deferral (Codex P2 on the A2 fix): a Python leg
        # whose ONLY failure is a zero collected count, while
        # another Python leg remains to run, does not fail the run.
        # Classification uncertainty schedules speculative legs (A2:
        # uncertainty routes to more execution), and the runner the
        # module actually belongs to may not have run yet — its leg
        # collecting zero is expected, not a vacuity signal. The
        # gate instead judges the union of the legs that ran: every
        # leg executes first, and a leg with no Python leg after it
        # fails on a zero count exactly as before, so a tree where
        # NO leg collects anything still fails. A clean zero
        # collection presents as exit 0, or — for a unittest leg on
        # CPython ≥3.12 — as the no-tests exit code 5 over the same
        # "Ran 0 tests" transcript (issue #56; _clean_zero_collection
        # pins the pair, so a broken leg cannot defer on it).
        defer_zero = (
            not result.passed
            and command.id in _PYTHON_LEG_IDS
            and _clean_zero_collection(command, result)
            and not result.timed_out
            and not result.survivors_remaining
            and any(
                c.id in _PYTHON_LEG_IDS for c in commands[idx + 1 :]
            )
        )
        # Speculative-leg non-veto (issue #51, round 2): the
        # deferral above is directional — it rescues a zero leg
        # only when another Python leg runs AFTER it, and its
        # exit-5 branch is unittest-only — so a speculative leg
        # scheduled on suspicion (its command is marked at
        # discovery) could still veto from last position with a
        # literal zero (e.g. a pytest leg exiting 5 over
        # `__test__ = False`). The non-veto is therefore a
        # property of the leg, judged against the union of the
        # run: a speculative leg whose only failure is a clean
        # zero collection defers when a Python leg remains, and
        # is excused outright when a Python leg already passed.
        # Standing alone with zero collected it excuses
        # nothing — no Python leg passed and none remains — so
        # a genuinely empty discovery still fails closed, and a
        # speculative leg collecting >0 is judged on its merits.
        speculative_zero = (
            not result.passed
            and command.speculative
            and command.id in _PYTHON_LEG_IDS
            and _speculative_clean_zero(command, result)
            and not result.timed_out
            and not result.survivors_remaining
        )
        defer_speculative = speculative_zero and any(
            c.id in _PYTHON_LEG_IDS for c in commands[idx + 1 :]
        )
        excuse_speculative = speculative_zero and python_leg_passed
        non_veto_speculative = (
            excuse_speculative and not defer_zero and not defer_speculative
        )
        if (
            not result.passed
            and not defer_zero
            and not defer_speculative
            and not excuse_speculative
        ):
            exit_repr = (
                "spawn-error" if result.exit_code is None else str(result.exit_code)
            )
            print(
                f"VERIFY: {command.id} FAIL exit={exit_repr} "
                f"duration_ms={result.duration_ms}"
            )
            if result.survivors_remaining:
                print("VERIFY: survivors remain after reap bound")
            if result.tests_collected == 0:
                print("VERIFY: zero tests collected")
            if (
                result.tests_collected is None
                and command.id in _PYTHON_LEG_IDS
            ):
                print("VERIFY: collected count unproven")
            print(f"VERIFY: stopped at first failure ({command.id})")
            return 1
        if between_commands is not None:
            # In-run binding revalidation (panel SEC-P0-1): the hook
            # returns a description when the tree moved during this
            # command. Abort BEFORE the next command runs — a later
            # command must never execute against a substituted tree,
            # and no completion record may seal the segment.
            excursion = between_commands()
            if excursion is not None:
                print(
                    f"VERIFY: FAIL tree binding changed during the "
                    f"run: {excursion} — aborting without a "
                    f"completion record"
                )
                return 1
        if result.passed:
            print(f"VERIFY: {command.id} PASS")
            if command.id in _PYTHON_LEG_IDS:
                python_leg_passed = True
        elif non_veto_speculative:
            print(
                f"VERIFY: {command.id} collected zero tests — "
                f"speculative leg does not veto the Python leg(s) "
                f"already passed"
            )
        else:
            print(
                f"VERIFY: {command.id} collected zero tests — "
                f"count gate deferred to the remaining Python leg(s)"
            )
    return 0 if executed else 1


GENESIS_CHAIN = "0" * 64

RECEIPT_FIELDS = (
    "ts",
    "task",
    "command_id",
    "argv",
    "exit_code",
    "timed_out",
    "duration_ms",
    "stdout_sha256",
    "stderr_sha256",
    "chain_sha256",
)

COMPLETION_KIND = "run-complete"

COMPLETION_FIELDS = (
    "ts",
    "task",
    "kind",
    "run_id",
    "command_count",
    "commands_sha256",
    "chain_sha256",
)

RUN_START_KIND = "run-start"

RUN_START_FIELDS = (
    "ts",
    "task",
    "kind",
    "run_id",
    "chain_sha256",
)

# Strict field types for the records of the SELECTED segment (Task 8,
# R7 — panel EXP5 / P3-1). A JSON bool wearing an int's clothes fails
# open under `==` checks (False == 0, True == 1), so validation uses
# `type(v) is ...` semantics, never isinstance (bool subclasses int).
# The map covers every field the writers can emit across the three
# record kinds — the base fields above plus the Task 1/2/4/5
# extensions (binding, subreaper, env, survivors_killed,
# tests_collected, speculative). exit_code alone may also be null: a spawn-error
# receipt legitimately records it. Fields absent from the map are
# ignored — the schema must not freeze against follow-ups (issue #38,
# P2-2). Element types are pinned for the two list fields.
SEGMENT_FIELD_TYPES: dict[str, tuple[type, ...]] = {
    "ts": (str,),
    "task": (str,),
    "kind": (str,),
    "run_id": (str,),
    "command_id": (str,),
    "argv": (list,),
    "exit_code": (int, type(None)),
    "timed_out": (bool,),
    "duration_ms": (int,),
    "stdout_sha256": (str,),
    "stderr_sha256": (str,),
    "chain_sha256": (str,),
    "command_count": (int,),
    "commands_sha256": (str,),
    "binding": (dict,),
    "subreaper": (bool,),
    "env": (str,),
    "survivors_killed": (list,),
    "tests_collected": (int,),
    "speculative": (bool,),
}

SEGMENT_LIST_ELEMENT_TYPES: dict[str, type] = {
    "argv": str,
    "survivors_killed": int,
}


def _segment_field_type_error(record: dict) -> str | None:
    """The first field of `record` whose value violates
    SEGMENT_FIELD_TYPES, else None. Unknown fields are ignored."""
    for field, value in record.items():
        allowed = SEGMENT_FIELD_TYPES.get(field)
        if allowed is None:
            continue
        if type(value) not in allowed:
            return field
        element = SEGMENT_LIST_ELEMENT_TYPES.get(field)
        if element is not None and any(
            type(item) is not element for item in value
        ):
            return field
    return None


def _receipts_file_tracked(root: Path, receipts_path: Path) -> bool:
    """True when the receipts file is tracked by git in root's repo.

    Path computation (N2): resolve the receipts path absolutely, take
    its path relative to the git toplevel of the root, and ask
    `git -C <toplevel> ls-files --error-unmatch` — correct for
    root-as-repo, root-as-subdirectory, and symlinked receipts paths.
    A root outside any git worktree tracks nothing: no rule applies.
    """
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return False
    toplevel = Path(
        top.stdout.decode("utf-8", errors="replace").strip()
    ).resolve()
    try:
        rel = receipts_path.resolve().relative_to(toplevel)
    except ValueError:
        return False
    proc = _git(
        toplevel, "ls-files", "--error-unmatch", "--", rel.as_posix()
    )
    return proc.returncode == 0


def _commands_digest(command_ids) -> str:
    canonical = json.dumps(list(command_ids), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Tree binding (overseer remediation R1): a receipts segment records the
# tree it describes, so a sealed PASS can be re-validated against that
# tree later — never against whatever the working tree holds then.

# The only directory names whose TOOL STATE the tree binding
# does not cover, at any depth. PR #42 excluded twelve names
# here; the paperthin validation of this batch (probes
# P-01..P-05) showed that eight of them are content directories
# — dependency, virtualenv, and build-output trees
# (node_modules, .venv, .tox, target, build, dist, coverage,
# htmlcov) whose code a sealed run can import or collect while
# the binding saw nothing, the #62 stale-PASS class through
# the digest's exclusion door. Those eight are bound like any
# other directory now. The second validation then found plain
# SOURCE under the four remaining names equally invisible
# (probes B1a/B1b/B1c, B2): the exclusion the four names carry
# is of their tool state, not of anything planted in them.
# The verifier's own legs regenerate that tool state during
# the run itself (a pytest leg creates .pytest_cache and
# __pycache__ from cold; git updates .git on every status), so
# binding it would make the run's own residue abort every
# seal. The binding under a residue name therefore excludes
# exactly the owning tool's state files and nothing else —
# under the three cache names every other file binds (see
# _residue_file_binds), an untracked file that would bind
# blocks git-mode sealing like untracked content anywhere
# (see tree_clean), and config aiming collection or sys.path
# into a residue directory — or anywhere outside the root —
# refuses the bare pytest leg (see
# _selected_config_aims_unattested). What remains unbound
# under a residue name is the tools' own state files
# themselves (bytes planted under those exact names take
# effect only through the tool — whose reads of them can
# also SELECT what a run executes, the read side a bound
# config arms only through the cache-selection flags
# discovery refuses, see _addopts_cache_selection — or
# through bound code that chooses to load them — the
# explicit-path family), the
# files under .git outside its enumerated bind set (an
# archive under an arbitrary name among them), and the one
# residual that needs no planted aiming: a bytecode-cache
# entry actively forged to match its source's recorded
# stat. See the Tree binding section of
# docs/deepcode-mechanisms.md for the exact bound set.
FS_RESIDUE_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
    }
)

# The file suffixes the binding treats as code wherever they
# live: Python source (.py) and native extension modules (.so,
# .pyd — the suffixes importlib accepts for extension modules;
# versioned names like .cpython-312-x86_64-linux-gnu.so still
# END in .so, so an exact-suffix test catches them). Judged on
# the name's final suffix, case-sensitively. Bytecode (.pyc)
# is deliberately NOT in the set — it is the tool state the
# residue exclusion exists for (the run regenerates it), and
# its residual is the disclosed one (a cache entry actively
# forged to match its source's recorded stat; see
# FS_RESIDUE_DIRS above and the Tree binding section of
# docs/deepcode-mechanisms.md). The suffix test decides
# binding only under .git (see _residue_file_binds): under
# the three cache names the rule is inverted and no suffix
# test decides anything, because a runtime also loads
# modules by name from ARCHIVES — and zipimport accepts an
# archive under any filename (Task 11 review, finding F1).
_FS_CODE_SUFFIXES = (".py", ".so", ".pyd")

# The archive suffixes importlib loads modules from by name
# (zipimport and the loaders registered for these formats).
# Part of the bind set under .git only, for the reason above.
_FS_ARCHIVE_SUFFIXES = (".zip", ".egg", ".whl")


def _is_code_file(name: str) -> bool:
    """Whether the file *name* is code a runtime loads by name
    (see _FS_CODE_SUFFIXES). Used to decide what binds — and,
    in git mode, what counts as dirty — under a residue
    directory, where tool state and planted code share a tree."""
    return name.endswith(_FS_CODE_SUFFIXES)


def _is_code_shaped(name: str) -> bool:
    """Whether the file *name* is content a runtime loads by
    name — code (see _is_code_file) or a module archive (see
    _FS_ARCHIVE_SUFFIXES). The union is the filename half of
    the enumerated .git bind set, and it is also the shape the
    git-mode cleanliness gate conditions the `.superpowers/`
    drop on (see tree_clean): under both names the question
    is the same — could this file's bytes be executed by a
    run the seal attests?"""
    return _is_code_file(name) or name.endswith(_FS_ARCHIVE_SUFFIXES)


# The tool-state files of the cache residue directories: the
# files the owning tool itself writes there, enumerated from
# the tools' real output — pytest 9's cache (its top-level
# CACHEDIR.TAG / README.md / .gitignore and the data files of
# v/cache/, the shape of an actual .pytest_cache in this
# repo), mypy's cache (its JSON data — every *.json, which
# covers .data.json and .meta.json — its cache databases, and
# its own .gitignore / CACHEDIR.TAG / missing_stubs marker),
# and CPython's bytecode cache (the *.pyc the interpreter
# writes). The run regenerates exactly these files mid-run,
# so excluding them — and only them — is what keeps the
# run's own residue from aborting the seal under the inverted
# rule of _residue_file_binds.
_PYTEST_CACHE_TOP_FILES = frozenset(
    (".gitignore", "CACHEDIR.TAG", "README.md")
)
_PYTEST_CACHE_DATA_FILES = frozenset(
    ("lastfailed", "nodeids", "stepwise")
)
_MYPY_CACHE_STATE_FILES = frozenset(
    (".gitignore", "CACHEDIR.TAG", "missing_stubs")
)
_MYPY_CACHE_STATE_SUFFIXES = (".json", ".db", ".sqlite", ".sqlite3")


def _is_tool_state_file(
    residue_name: str, inside: tuple[str, ...]
) -> bool:
    """Whether the file at *inside* — the path below a residue
    directory named *residue_name*, filename last — is that
    tool's own state (see the enumeration above). Never true
    for .git: git's state is not a file set that can be
    enumerated this way, so .git files are judged by the bind
    set in _residue_file_binds instead."""
    base = inside[-1]
    if residue_name == "__pycache__":
        return base.endswith(".pyc")
    if residue_name == ".pytest_cache":
        if len(inside) == 1:
            return base in _PYTEST_CACHE_TOP_FILES
        return (
            inside[:2] == ("v", "cache")
            and base in _PYTEST_CACHE_DATA_FILES
        )
    if residue_name == ".mypy_cache":
        return base in _MYPY_CACHE_STATE_FILES or base.endswith(
            _MYPY_CACHE_STATE_SUFFIXES
        )
    return False


def _residue_file_binds(
    active: str, inside: tuple[str, ...]
) -> bool:
    """Whether a file inside a residue directory binds in the
    tree digest. *active* is the innermost residue name
    containing the file; *inside* is the path below that
    directory, filename last.

    Under the three cache names the rule is inverted: every
    file binds except the owning tool's own state (see
    _is_tool_state_file). A planted archive of any filename,
    an extensionless script, a collectable data file — all are
    content a sealed run can load by name, so all are content
    the seal attests (Task 11 review, finding F1). Under .git
    the rule cannot invert — git rewrites its control files
    under ordinary operations between seal and audit — so the
    bind set is enumerated instead: code files, module
    archives (see _FS_ARCHIVE_SUFFIXES), and everything under
    hooks/ (git's own hook scripts — code the tree's operator
    runs by name). A file under .git outside that set, an
    archive under an arbitrary name among them, is unbound;
    it has effect only through bound code loading it by
    explicit path — the disclosed explicit-path family — or
    through pytest collection traversal entering .git, which
    requires a bound config whose norecursedirs admits it
    and is refused at discovery for the bare leg (see
    _selected_config_traversal_enters_residue)."""
    if active == ".git":
        return inside[0] == "hooks" or _is_code_shaped(inside[-1])
    return not _is_tool_state_file(active, inside)


def _residue_context(
    parts: tuple[str, ...], root_name: str
) -> tuple[str, tuple[str, ...]]:
    """(active residue name, path inside it) for a file whose
    path below a residue directory named *root_name* is
    *parts*: a nested residue name restarts the context, so a
    __pycache__ inside a planted .pytest_cache subtree is
    judged by the bytecode rule, not the cache rule."""
    active = root_name
    start = 0
    for index, part in enumerate(parts[:-1]):
        if part in FS_RESIDUE_DIRS:
            active = part
            start = index + 1
    return active, parts[start:]


def _path_binds_under_residue(parts: list[str]) -> bool | None:
    """Whether a repo-relative path (*parts*, filename last)
    would bind in the fs digest by virtue of sitting under a
    residue directory — None when it sits under none. The
    git-mode cleanliness gate uses this for parity: an
    untracked file the fs binding would cover must block
    sealing in git mode too (see tree_clean)."""
    active: str | None = None
    start = 0
    for index, part in enumerate(parts[:-1]):
        if part in FS_RESIDUE_DIRS:
            active = part
            start = index + 1
    if active is None:
        return None
    return _residue_file_binds(active, tuple(parts[start:]))


# Command-line configuration pinned on every git invocation the
# verifier makes. Repo-local git configuration is unbound state
# delivered WITH a filesystem-copied checkout (an archive, an
# rsync, a prebuilt worktree image), not operator environment, yet
# it steers the answers the verifier borrows from git — above all
# `git status`, whose cleanliness judgement the git-mode binding
# rests on. A `-c` assignment on the argv is applied after ALL
# file config — the system and global files, the repo file, any
# include.path / includeIf chain it names, and the
# extensions.worktreeConfig file — so one pin covers the whole
# chain wherever the setting actually lives (paperthin
# validation 6, breach B-A). Each pin restores the instrument's
# platform-default judgement against a repo-local claim:
#
# - core.fsmonitor / core.untrackedCache: off. Both delegate or
#   accelerate status's answer with state the checkout supplies —
#   fsmonitor wholesale, to a helper PROGRAM the config names,
#   whose primed token lineage makes a modified tracked file
#   invisible (the breach); the untracked cache is the same
#   borrowed answer for the untracked half.
# - core.hooksPath: the null device, so no hook (a
#   post-index-change hook fires when status refreshes the
#   index) executes a repo-named program during a verifier call.
# - core.attributesFile / core.excludesFile: the null device, so
#   a repo-local pointer cannot move the attributes or excludes
#   git honours to files outside the tree — an outside
#   attributes file selecting a constant clean filter masks a
#   tracked modification outright; an outside excludes file
#   hides untracked code. (The in-tree .gitignore and
#   .git/info/exclude are untouched: ignored content is git
#   mode's stated limit, not this pin's subject.)
# - core.fileMode / core.checkStat / core.trustctime /
#   core.ignoreCase / core.symlinks / core.autocrlf: the
#   comparison's width and the filesystem's real properties,
#   restored — a repo-local fileMode=false masks a mode change,
#   a narrowed checkStat / distrusted ctime thins the stat
#   comparison a forged timestamp must survive, and conversion
#   is not the repo's to enable against a binding made of raw
#   blob bytes.
# - status.showUntrackedFiles: all, the call site's flag
#   restated at the _git level so every status invocation
#   enumerates untracked files individually.
#
# Two setup-level keys a -c pin cannot retake. core.worktree IS
# honoured from the file over the argv (setup consumes it before
# -c applies), so _git overrides it with --work-tree derived
# from the filesystem layout instead (see _filesystem_worktree_top).
# core.bare is REFUSED, not pinned: the restated argv
# (--git-dir/--work-tree) overrides bareness exactly as it
# overrides core.worktree, so a checkout declaring core.bare=true
# would otherwise be judged as an ordinary worktree (Task 16
# review, finding F1 — the original adjudication here claimed
# the opposite). A bare declaration in a delivered worktree
# checkout is anomalous, so tree_clean refuses it outright via
# _repo_local_config_refusal, which also refuses repo-local
# filter drivers (program-naming config of the fsmonitor kind).
_GIT_CONFIG_PINS = (
    "core.fsmonitor=false",
    "core.untrackedCache=false",
    "core.hooksPath=" + os.devnull,
    "core.attributesFile=" + os.devnull,
    "core.excludesFile=" + os.devnull,
    "core.fileMode=true",
    "core.checkStat=default",
    "core.trustctime=true",
    "core.ignoreCase=false",
    "core.symlinks=true",
    "core.autocrlf=false",
    "status.showUntrackedFiles=all",
)


def _filesystem_worktree_top(root: Path) -> Path | None:
    """The worktree top for *root* by filesystem layout alone:
    the nearest ancestor (root itself first) carrying a `.git`
    entry — git's own discovery rule, re-derived without asking
    git, because the answer git gives is one repo-local config
    (core.worktree) can redirect to a different tree entirely.
    None when no ancestor carries one (a bare repo directory, a
    separate-git-dir layout): the plain invocation stands."""
    try:
        start = root.resolve()
    except OSError:
        return None
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _layout_git_dir(top: Path) -> str | None:
    """The git dir a `.git` entry at *top* names: the directory
    itself, or the target of a `.git` file's `gitdir:` line
    (linked worktrees, submodules), resolved against *top*.
    None when the entry cannot be read in either form."""
    dot = top / ".git"
    try:
        if dot.is_dir():
            return str(dot)
        text = dot.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("gitdir:"):
            target = Path(line[len("gitdir:"):].strip())
            if not target.is_absolute():
                target = top / target
            return str(target.resolve())
    return None


def _git_env() -> dict:
    """Environment for the verifier's git invocations: the
    caller's, plus GIT_NO_REPLACE_OBJECTS=1. Replace refs
    (.git/refs/replace/<sha>) are delivered checkout state like
    .git/config: a planted ref makes ls-tree, cat-file, and
    status read substituted objects, so a seal could attest a
    tree that is not HEAD's (Task 16 review, finding F2's
    family). The env opt-out applies to every invocation
    uniformly, with no argv-ordering constraint."""
    env = dict(os.environ)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return env


def _absolute_git_dir(root: Path) -> str | None:
    """Fallback for exotic layouts: ask git where the git dir
    is. The answer is a path derivation repo-local config was
    probed not to steer (core.worktree redirects
    --show-toplevel, never --absolute-git-dir)."""
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
        capture_output=True,
        timeout=60,
        env=_git_env(),
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").strip() or None


def _git_argv(root: Path, *args: str) -> list[str]:
    argv = ["git", "-C", str(root)]
    top = _filesystem_worktree_top(root)
    if top is not None:
        git_dir = _layout_git_dir(top) or _absolute_git_dir(root)
        if git_dir is not None:
            # --work-tree/--git-dir on the argv are the only
            # override core.worktree honours: setup consumes the
            # file value before -c config applies (probed), so
            # the worktree is restated from the filesystem
            # layout and the borrowed answers describe the tree
            # under attestation, not a tree config names.
            argv += ["--git-dir", git_dir, "--work-tree", str(top)]
    for pin in _GIT_CONFIG_PINS:
        argv += ["-c", pin]
    argv += list(args)
    return argv


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        _git_argv(root, *args),
        capture_output=True,
        timeout=60,
        env=_git_env(),
    )


def _git_head(root: Path) -> str | None:
    proc = _git(root, "rev-parse", "HEAD")
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").strip() or None


def _git_tree_digest(root: Path, head: str) -> str | None:
    """Digest of the tree at `head`, computed from git objects only.

    For each entry of `git ls-tree -r -z <head>` (NUL-terminated, raw
    path bytes), hash `mode + " " + blob_sha + " " + path + "\n"` in
    ls-tree's own order. Working-tree content is never read, so the
    digest is reproducible at any later time while the commit exists;
    None when the commit is unreadable.
    """
    proc = _git(root, "ls-tree", "-r", "-z", head)
    if proc.returncode != 0:
        return None
    digest = hashlib.sha256()
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        parts = meta.split(b" ")
        if len(parts) != 3:
            return None
        digest.update(parts[0] + b" " + parts[2] + b" " + path + b"\n")
    return digest.hexdigest()


_FILTER_DRIVER_KEY = re.compile(r"^filter\..+\.(clean|smudge|process)$")

_DELIVERED_CONFIG_SCOPES = ("local", "worktree")


def _config_bool(value: str | None) -> bool:
    """Git's boolean reading of one config value: a valueless
    key is true, the empty string is false, and the named and
    numeric forms follow git's own rules."""
    if value is None:
        return True
    text = value.strip().lower()
    if text in ("true", "yes", "on"):
        return True
    if text in ("false", "no", "off", ""):
        return False
    try:
        return int(text) != 0
    except ValueError:
        return False


def _repo_local_config_refusal(root: Path) -> str | None:
    """Why git mode refuses this checkout's own configuration,
    or None. Only the DELIVERED scopes are judged — `local`
    (.git/config, including anything its include.path chain
    pulls in, which git reports under the including scope) and
    `worktree` (config.worktree under extensions.worktreeConfig)
    — never the operator's system/global config, which is
    operator environment, nor the verifier's own -c pins
    (command scope). Two refusals:

    - Any filter.*.clean / .smudge / .process key: filter
      drivers are program-naming config delivered with the
      checkout, the fsmonitor kind. Content-exact cleanliness
      (see _tracked_content_matches_head) compares raw bytes
      precisely so that no repo-named program stands between
      the worktree and the blob; a checkout carrying the keys
      is refused whether or not an attribute selects a driver.
    - core.bare=true (the effective delivered value, last in
      precedence order): the verifier's restated argv overrides
      bareness, so the flag would otherwise be silently
      neutralized while the checkout declares itself not a
      worktree at all. The declaration is anomalous in a
      delivered worktree checkout; refusing costs nothing
      legitimate (Task 16 review, finding F1).
    """
    names = _git(root, "config", "--name-only", "--list", "--show-scope")
    if names.returncode != 0:
        return "repo-local git config is not readable"
    for line in names.stdout.decode("utf-8", errors="replace").splitlines():
        scope, sep, key = line.partition("\t")
        if not sep or scope not in _DELIVERED_CONFIG_SCOPES:
            continue
        if _FILTER_DRIVER_KEY.match(key.strip().lower()):
            return (
                "repo-local git config defines a filter driver "
                f"({key.strip()}); filter drivers are programs the "
                "checkout names, and git mode refuses them"
            )
    values = _git(root, "config", "--list", "--show-scope")
    if values.returncode != 0:
        return "repo-local git config is not readable"
    bare_seen = False
    bare_value: str | None = None
    for line in values.stdout.decode("utf-8", errors="replace").splitlines():
        scope, sep, rest = line.partition("\t")
        if not sep or scope not in _DELIVERED_CONFIG_SCOPES:
            continue
        key, eq, value = rest.partition("=")
        if key.strip().lower() != "core.bare":
            continue
        bare_seen = True
        bare_value = value if eq else None
    if bare_seen and _config_bool(bare_value):
        return (
            "repo-local git config sets core.bare=true; a "
            "delivered worktree checkout declaring itself bare "
            "is refused rather than silently overridden"
        )
    return None


def _tracked_content_matches_head(root: Path, toplevel: Path) -> bool:
    """Content-exact tracked cleanliness: for every blob entry
    of `git ls-tree -r HEAD`, the worktree entry at the same
    path carries the same git mode and bytes identical to the
    blob's. Gitlink (submodule) entries are skipped — their
    state is the submodule's own HEAD, which the status half
    of tree_clean judges.

    This replaces the index's stat cache as the tracked half's
    authority. `git status` believes an index entry whose stat
    fields match the worktree file WITHOUT reading content —
    the cache working as designed — and the index travels with
    a filesystem-delivered checkout exactly as .git/config
    does: a byte-forged entry (HEAD's blob SHA over the
    modified file's genuine stat, trailer checksum recomputed)
    makes a modified tracked file invisible to status and to
    every -c pin, because no pin governs the cache (Task 16
    review, finding F2). Comparing bytes directly consults no
    cache and executes no program: blob bytes come from one
    `git cat-file --batch` over the object store (replace
    objects disabled, see _git_env), worktree bytes are read
    raw. `git hash-object` was probed and rejected as the
    per-file instrument: it EXECUTES the entry's clean filter
    (a sentinel-writing driver ran), standing a repo-named
    program inside the verifier's own call — the hooks class
    the pins exist to exclude.

    The price, stated as git mode's limit in the docs: the
    comparison is byte-exact, so a tree whose checked-out bytes
    legitimately differ from its blob bytes — attribute-driven
    EOL/text conversion, a clean/smudge filter, Git LFS —
    cannot seal in git mode. No normalization is applied,
    because every normalization available is either git's own
    borrowed answer or a repo-named program.
    """
    proc = _git(root, "ls-tree", "-r", "-z", "HEAD")
    if proc.returncode != 0:
        return False
    blobs: list[tuple[str, str, str]] = []
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        meta, _, raw_path = entry.partition(b"\t")
        parts = meta.split(b" ")
        if len(parts) != 3:
            return False
        if parts[1] != b"blob":
            continue
        blobs.append(
            (
                parts[0].decode("ascii", errors="replace"),
                parts[2].decode("ascii", errors="replace"),
                raw_path.decode("utf-8", errors="surrogateescape"),
            )
        )
    if not blobs:
        return True
    try:
        batch = subprocess.Popen(
            _git_argv(root, "cat-file", "--batch"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=_git_env(),
        )
    except OSError:
        return False
    try:
        assert batch.stdin is not None and batch.stdout is not None
        for mode, sha, rel in blobs:
            target = toplevel / rel
            try:
                st = os.lstat(target)
            except OSError:
                return False
            if _fs_entry_mode(target) != mode:
                return False
            batch.stdin.write((sha + "\n").encode("ascii"))
            batch.stdin.flush()
            header = (
                batch.stdout.readline().decode("ascii", errors="replace")
            ).split()
            if len(header) != 3 or header[1] != "blob":
                return False
            try:
                size = int(header[2])
            except ValueError:
                return False
            content = batch.stdout.read(size)
            if len(content) != size or batch.stdout.read(1) != b"\n":
                return False
            if stat.S_ISLNK(st.st_mode):
                actual = os.readlink(target).encode(
                    "utf-8", errors="surrogateescape"
                )
                if actual != content:
                    return False
            elif _fs_entry_content(target) != hashlib.sha256(
                content
            ).hexdigest():
                return False
        return True
    except (OSError, ValueError):
        return False
    finally:
        try:
            if batch.stdin is not None:
                batch.stdin.close()
        except OSError:
            pass
        try:
            batch.wait(timeout=10)
        except Exception:
            batch.kill()


def _fs_entry_mode(path: Path) -> str:
    """Git-style mode string for one filesystem entry: the file TYPE
    plus, for regular files, the executable bit — `100755` vs
    `100644`; symlinks are `120000` whatever they point at; other
    types keep their raw type bits. Mirrors what the git-mode digest
    already captures from ls-tree, so an execution-relevant
    permission change moves the fs digest exactly as it moves the
    git one. Non-executable permission bits (read/write) are not
    execution evidence and stay out, matching git.
    """
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        return "120000"
    if stat.S_ISREG(st.st_mode):
        return "100755" if st.st_mode & 0o111 else "100644"
    return format(stat.S_IFMT(st.st_mode), "06o")


_NON_REGULAR_CONTENT = "non-regular"


def _fs_entry_content(path: Path) -> str:
    """The content component of one fs-digest entry: a
    regular file's sha256 hex; a symlink's target string
    (never followed); for any other entry type — FIFO,
    socket, device — a fixed marker, so the entry binds the
    file's presence and type (its mode string, see
    _fs_entry_mode) WITHOUT opening it: opening a FIFO
    blocks until a writer appears, so a tree containing one
    hung verify and check_receipts, which recomputes the
    digest, forever (paperthin validation 3, note N4). Git
    mode needs no such rule: its digest comes from git
    object metadata and never opens a working-tree file."""
    if path.is_symlink():
        return os.readlink(path)
    if stat.S_ISREG(os.lstat(path).st_mode):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return _NON_REGULAR_CONTENT


def _fs_residue_entries(
    residue_root: Path,
    resolved: Path,
    receipts_resolved: Path | None,
) -> list[tuple[str, str, str]]:
    """Digest entries from inside one residue directory.

    The walk descends (never following symlinks) and binds the
    files whose post-seal mutation must move the digest, per
    _residue_file_binds: under the three cache names, every
    file except the owning tool's own state; under .git, the
    enumerated bind set (code files, module archives, hooks).
    Bound files digest by content hash, symlinks by target
    string, and non-regular files by presence (see
    _fs_entry_content) — exactly as the main walk binds them
    everywhere else. The excluded remainder — cache indexes,
    bytecode, git's other internals — contributes nothing, so
    the run's own cache generation cannot change the digest
    mid-run and abort the seal. Planted content is not tool
    state: what a runtime can load by name binds wherever it
    sits, so content a sealed run imports or collects from a
    residue directory is content the seal attests (paperthin
    validation 2, probes B1a/B1b/B1c; Task 11 review, finding
    F1).
    """
    entries: list[tuple[str, str, str]] = []
    for dirpath, dirnames, filenames in os.walk(
        residue_root, followlinks=False
    ):
        current = Path(dirpath)
        descend: list[str] = []
        for name in dirnames:
            path = current / name
            if path.is_symlink():
                entries.append(
                    (
                        path.relative_to(resolved).as_posix(),
                        _fs_entry_mode(path),
                        os.readlink(path),
                    )
                )
            else:
                descend.append(name)
        dirnames[:] = descend
        for name in filenames:
            path = current / name
            if (
                receipts_resolved is not None
                and path.resolve() == receipts_resolved
            ):
                continue
            rel = path.relative_to(resolved).as_posix()
            if path.is_symlink():
                entries.append(
                    (rel, _fs_entry_mode(path), os.readlink(path))
                )
            else:
                active, inside = _residue_context(
                    path.relative_to(residue_root).parts,
                    residue_root.name,
                )
                if _residue_file_binds(active, inside):
                    entries.append(
                        (
                            rel,
                            _fs_entry_mode(path),
                            _fs_entry_content(path),
                        )
                    )
    return entries


def _fs_tree_digest(root: Path, receipts_path: Path | None = None) -> str:
    """Digest of a non-git tree: sha256 over sorted relative paths of
    `relpath + "\\0" + mode + "\\0" + content + "\\0"`, where mode is
    the entry's git-style mode string (file type + executable bit —
    see `_fs_entry_mode`) and content is the file's sha256 hex
    (symlinks: the target string, never followed; non-regular
    files: a presence marker, never opened — see
    _fs_entry_content). The receipts
    file itself is excluded. A directory named in
    FS_RESIDUE_DIRS contributes the files _residue_file_binds
    selects and its symlinks (see _fs_residue_entries); the
    tools' own state files under the cache names, and git's
    other control files, are not bound. Every other directory
    — dependency, virtualenv, and build-output trees included
    — is bound in full: content a run can execute from them
    is content the seal attests.
    """
    resolved = root.resolve()
    receipts_resolved = (
        receipts_path.resolve() if receipts_path is not None else None
    )
    entries: list[tuple[str, str, str]] = []
    for dirpath, dirnames, filenames in os.walk(resolved, followlinks=False):
        current = Path(dirpath)
        descend: list[str] = []
        for name in dirnames:
            path = current / name
            if name in FS_RESIDUE_DIRS:
                if path.is_symlink():
                    entries.append(
                        (
                            path.relative_to(resolved).as_posix(),
                            _fs_entry_mode(path),
                            os.readlink(path),
                        )
                    )
                else:
                    entries.extend(
                        _fs_residue_entries(
                            path, resolved, receipts_resolved
                        )
                    )
                continue
            if path.is_symlink():
                entries.append(
                    (
                        path.relative_to(resolved).as_posix(),
                        _fs_entry_mode(path),
                        os.readlink(path),
                    )
                )
            else:
                descend.append(name)
        dirnames[:] = descend
        for name in filenames:
            path = current / name
            if (
                receipts_resolved is not None
                and path.resolve() == receipts_resolved
            ):
                continue
            rel = path.relative_to(resolved).as_posix()
            entries.append(
                (rel, _fs_entry_mode(path), _fs_entry_content(path))
            )
    entries.sort()
    digest = hashlib.sha256()
    for rel, mode, content in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(mode.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def tree_binding(
    root: Path, receipts_path: Path | None = None
) -> dict:
    """The binding a run records for the tree it verifies.

    git mode (root inside a git worktree): head + the ls-tree digest
    at that head. fs mode: head None + the live-tree digest. Root is
    canonicalized with Path.resolve(). Raises ValueError when a git
    root has no readable HEAD/tree to bind to.
    """
    resolved = root.resolve()
    if _git(resolved, "rev-parse", "--git-dir").returncode == 0:
        head = _git_head(resolved)
        digest = (
            _git_tree_digest(resolved, head) if head is not None else None
        )
        if head is None or digest is None:
            raise ValueError(
                f"git root {resolved} has no readable HEAD to bind to"
            )
        return {
            "root": str(resolved),
            "head": head,
            "tree_digest": digest,
            "mode": "git",
        }
    return {
        "root": str(resolved),
        "head": None,
        "tree_digest": _fs_tree_digest(resolved, receipts_path),
        "mode": "fs",
    }


def _entry_is_symlink(toplevel: Path, rel: str) -> bool:
    """Whether the git-status entry at repo-relative *rel* is
    a symlink in the working tree. git status reports a
    symlink as a single entry and never enumerates through
    it, so the entry's on-disk type is the only place its
    nature is visible to the cleanliness gate. A path that
    cannot be lstat'd (it vanished between the status and
    this check) reads as not-a-symlink, and the name rules
    decide it, as they did before entry types were judged."""
    try:
        return (toplevel / rel).is_symlink()
    except OSError:
        return False


def tree_clean(root: Path, receipts_path: Path | None = None) -> bool:
    """Git-mode cleanliness predicate for the binding gate.

    `git status --porcelain --untracked-files=all` must be empty
    after dropping (i) the
    receipts file itself and UNTRACKED entries under `.superpowers/`
    whose names are not code-shaped (see _is_code_shaped) — the
    workflow's own bookkeeping: ledgers, briefs, record files.
    The drop is conditioned, not blanket (paperthin validation 4,
    breach B-A): an untracked code-shaped file under
    `.superpowers/` — source, a native extension, a module
    archive — counts as dirty like untracked content anywhere
    else, because committed code can import or collect it and
    it would then execute under the seal bound nowhere; it
    must be committed (which binds it via ls-tree) or removed.
    A TRACKED `.superpowers/` entry that is modified or staged
    counts as dirty like any other tracked change. And
    (ii) untracked entries under a residue
    name that the fs binding would NOT cover (see
    _path_binds_under_residue: the cache tools' own state
    files, and files under .git outside its bind set). An
    untracked file under a residue name that the fs binding
    WOULD cover counts as dirty like untracked content
    anywhere else — under the cache names that is everything
    but the tools' own state, planted archives included —
    and git mode's parity is to refuse the seal until the
    file is committed (which binds it via ls-tree) or
    removed.
    Both drops judge the entry's TYPE as well as its name
    (Task 13 review, finding F2): an untracked SYMLINK entry
    is dropped by neither. A name says nothing about what a
    run executes through a link, and the fs binding attests
    a link's target string wherever the link sits — under
    `.superpowers/`, and under the residue names even at
    paths the name rules exclude (a tool-state name, a
    non-bind name under .git) — so parity counts an
    untracked link as dirty until it is committed, when
    ls-tree binds its target string exactly as it binds
    code. Waved through on its name, a git-mode seal would
    be blind even to the link's retargeting — the one event
    the symlink contract promises always registers.
    Untracked content
    under any other directory name —
    a dependency, virtualenv, or build-output tree included —
    counts as dirty like untracked content anywhere else: git
    mode binds committed content, and an untracked file a run
    could execute must be committed or removed before the tree
    can seal. Modified or staged tracked entries always count
    as dirty; the exclusions never hide a tracked change.
    That contract rests on pinned instruments (see
    _GIT_CONFIG_PINS): every git invocation carries command-line
    pins for the repo-local keys that could steer its answer —
    repo-local git configuration is unbound state delivered
    with the checkout, and an unpinned `git status` asks the
    checkout's own configuration whether the checkout is clean
    (a primed core.fsmonitor helper answers for it wholesale;
    paperthin validation 6, breach B-A). Replace objects are
    disabled on every invocation (see _git_env): a planted
    replace ref would substitute the objects themselves.
    The checkout's own configuration is also REFUSED, not
    merely pinned, in two cases (see _repo_local_config_refusal):
    a filter driver definition (program-naming config of the
    fsmonitor kind), and core.bare=true. And the index itself
    is judged after status: a tracked file carrying the
    skip-worktree or assume-unchanged bit is one status has
    been told not to look at — it reports the file clean BY
    DESIGN while its bytes differ from HEAD — so a tree
    carrying either bit on any tracked file is not clean here.
    Finally, the tracked half of the contract is content-exact
    (see _tracked_content_matches_head): status consults the
    index's stat cache, which a byte-forged index entry defeats
    wholesale — HEAD's blob SHA over the modified file's
    genuine stat is believed without a content read, and no
    -c pin governs the cache — so worktree bytes for every
    tracked path are compared against HEAD's blob bytes
    directly. The status loop above still judges the untracked
    half, staged/index divergence, and mode state; the content
    comparison is the tracked half's authority.
    """
    resolved = root.resolve()
    top = _git(resolved, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return False
    toplevel = Path(
        top.stdout.decode("utf-8", errors="replace").strip()
    ).resolve()
    if _repo_local_config_refusal(resolved) is not None:
        return False
    receipts_rel: str | None = None
    if receipts_path is not None:
        try:
            receipts_rel = (
                receipts_path.resolve().relative_to(toplevel).as_posix()
            )
        except ValueError:
            receipts_rel = None
    # --untracked-files=all: enumerate untracked files individually.
    # Git's default collapses a wholly untracked directory into one
    # `?? dir/` entry, which never equals the receipts file's exact
    # path — a receipts file in a fresh directory (e.g. evidence/)
    # would defeat exclusion (i) and fail the gate spuriously
    # (Codex P2). Per-file entries keep the exclusion exact: the
    # receipts file is dropped, its untracked siblings are not.
    proc = _git(
        resolved, "status", "--porcelain", "-z", "--untracked-files=all"
    )
    if proc.returncode != 0:
        return False
    fields = proc.stdout.split(b"\0")
    idx = 0
    while idx < len(fields):
        entry = fields[idx]
        idx += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        if status[:1] in (b"R", b"C"):
            idx += 1  # rename/copy: the source path field follows
        if receipts_rel is not None and path == receipts_rel:
            continue
        if status == b"??" and (
            path == ".superpowers" or path.startswith(".superpowers/")
        ) and not _is_code_shaped(path.rsplit("/", 1)[-1]) \
                and not _entry_is_symlink(toplevel, path):
            continue
        if status == b"??" and (
            _path_binds_under_residue(path.split("/")) is False
        ) and not _entry_is_symlink(toplevel, path):
            continue
        return False
    # Index mask bits: `git ls-files -v` exposes them in the
    # entry tag — lowercase for assume-unchanged, S for
    # skip-worktree. Either bit means the pinned status above
    # was instructed not to compare that file's worktree bytes
    # against the index at all, so its silence about the file is
    # not evidence; the bits have no legitimate place in a
    # checkout whose cleanliness is being attested.
    proc = _git(resolved, "ls-files", "-v", "-z")
    if proc.returncode != 0:
        return False
    for entry in proc.stdout.split(b"\0"):
        if entry and (entry[:1].islower() or entry[:1] == b"S"):
            return False
    # Content-exact tracked half: the stat cache status just
    # consulted is delivered state and forgeable (see the
    # docstring); compare the bytes themselves.
    return _tracked_content_matches_head(resolved, toplevel)


def binding_excursion(
    root: Path, binding: dict, receipts_path: Path | None = None
) -> str | None:
    """Describe how the live tree has moved from `binding`, or None
    when it still matches. Git mode only (fs mode returns None; its
    seal recomputes the whole-tree digest instead).

    Head and digest are compared independently: a reset to a
    different commit with identical tree content moves the head
    while the digest stands still, and the segment's claim is about
    the recorded commit, not merely its content. The working tree
    must also still be clean — an uncommitted excursion is movement
    even when HEAD never changes. This observes the tree BETWEEN
    commands; a single command that swaps and restores entirely
    within its own execution is not observable this way (that needs
    an execution sandbox, outside the same-uid threat model).
    """
    if binding.get("mode") != "git":
        return None
    try:
        current = tree_binding(root, receipts_path)
    except (OSError, ValueError) as exc:
        return f"tree binding no longer readable ({exc})"
    if current["head"] != binding["head"]:
        return (
            f"HEAD moved {binding['head']} -> {current['head']}"
        )
    if current["tree_digest"] != binding["tree_digest"]:
        return "tree digest changed at the recorded HEAD"
    if not tree_clean(root, receipts_path):
        return "working tree no longer clean"
    return None


def _chain_sha256(body: dict, prev_chain: str) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev_chain + canonical).encode("utf-8")).hexdigest()


def _receipt_lines(receipts_path: Path) -> list[str]:
    try:
        text = receipts_path.read_text(encoding="utf-8")
    except OSError:
        return []
    return text.splitlines()


def _last_chain(receipts_path: Path) -> str:
    """Chain hash of the file's last line; genesis for an empty file.

    Raises ValueError when the last line is malformed (not a JSON object
    carrying a string chain_sha256) — a torn receipts file is never
    appended to blindly.
    """
    lines = _receipt_lines(receipts_path)
    if not lines:
        return GENESIS_CHAIN
    try:
        parsed = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"malformed last receipt line {len(lines)} in {receipts_path}"
        ) from exc
    if not isinstance(parsed, dict) or not isinstance(
        parsed.get("chain_sha256"), str
    ):
        raise ValueError(
            f"malformed last receipt line {len(lines)} in {receipts_path}"
        )
    return parsed["chain_sha256"]


def _append_record(receipts_path: Path, body: dict) -> None:
    """Append one hash-chained record under an exclusive flock.

    The append lands as a single os.write, so concurrent runs cannot
    interleave a line.
    """
    fd = os.open(receipts_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        record = dict(body)
        record["chain_sha256"] = _chain_sha256(body, _last_chain(receipts_path))
        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def append_receipt(
    receipts_path: Path,
    task: str,
    result: VerificationResult,
    run_id: str | None = None,
) -> None:
    """Append one hash-chained receipt for a result the verifier produced.

    Only hashes of the capped output are recorded — never output text.
    When run_id is given, the receipt carries it so check_receipts can
    attribute the receipt to its run segment.
    """
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "command_id": result.command.id,
        "argv": list(result.command.argv),
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "duration_ms": result.duration_ms,
        # Issue #38: hash the raw capped bytes the runner retained.
        # The decoded text is lossy on non-UTF-8 output (every invalid
        # sequence became U+FFFD), so hashing it never covered the
        # bytes the command actually emitted. The fallback covers
        # hand-built results without captured bytes; it is identical
        # whenever the text is valid UTF-8.
        "stdout_sha256": hashlib.sha256(
            result.stdout_bytes
            if result.stdout_bytes is not None
            else result.stdout.encode("utf-8")
        ).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            result.stderr_bytes
            if result.stderr_bytes is not None
            else result.stderr.encode("utf-8")
        ).hexdigest(),
    }
    if run_id is not None:
        body["run_id"] = run_id
    if result.survivors_killed:
        body["survivors_killed"] = list(result.survivors_killed)
    if result.tests_collected is not None:
        body["tests_collected"] = result.tests_collected
    if result.command.speculative:
        # Issue #51, round 3: the leg's speculative mark,
        # recorded at seal time (and covered by the chain) so
        # check_receipts can mirror run_all's speculative-zero
        # excuse from the segment itself — see
        # _speculative_zero_receipt. Recorded only when true,
        # in the style of the other optional fields: absence
        # means deterministic, so receipts sealed before this
        # field existed default to deterministic at audit and
        # stay fail-closed, and omitting the mark can only make
        # the audit stricter, never looser.
        body["speculative"] = True
    _append_record(receipts_path, body)


def append_run_start(
    receipts_path: Path,
    task: str,
    run_id: str,
    binding: dict | None = None,
    subreaper: bool | None = None,
    env: str | None = None,
) -> None:
    """Append the run-boundary record that opens a run segment.

    Written before a verify run executes any command; the run's
    receipts and its completion record carry the same run_id, so
    check_receipts can validate the latest run independently of any
    earlier (possibly interrupted) segments in the same file. When a
    tree binding is given it is recorded here (and on the completion
    record) as an EXTRA field — the required-field tuples deliberately
    do not include it, so its absence routes to the UNBOUND verdict
    rather than a corruption verdict (RC3). `subreaper`, when given,
    records whether main() set PR_SET_CHILD_SUBREAPER for the run —
    likewise an extra field. `env`, when given, states the run's env
    mode (see run_env_mode) — an extra field in the same style.
    """
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "kind": RUN_START_KIND,
        "run_id": run_id,
    }
    if binding is not None:
        body["binding"] = binding
    if subreaper is not None:
        body["subreaper"] = subreaper
    if env is not None:
        body["env"] = env
    _append_record(receipts_path, body)


def append_completion(
    receipts_path: Path,
    task: str,
    commands,
    run_id: str | None = None,
    binding: dict | None = None,
) -> None:
    """Append the run-completion record for a fully successful run.

    Written only when every discovered command executed and passed; it
    carries the expected command count and a digest of the ordered
    command set, so check_receipts can reject the partial receipt set
    of a run that stopped early. `binding`, when given, is the tree
    binding computed at run start (see append_run_start).
    """
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "kind": COMPLETION_KIND,
        "command_count": len(commands),
        "commands_sha256": _commands_digest([c.id for c in commands]),
    }
    if run_id is not None:
        body["run_id"] = run_id
    if binding is not None:
        body["binding"] = binding
    _append_record(receipts_path, body)


def _deferred_zero_receipt(
    receipts: list[dict], idx: int, receipt: dict
) -> bool:
    """Whether a non-zero receipt is a count-gate-deferred clean
    zero (issue #56), acceptable at audit time.

    run_all defers a unittest leg whose only failure is a clean
    zero collection — exit _UNITTEST_NO_TESTS_EXIT_CODE over a
    "Ran 0 tests" transcript — to a remaining Python leg, and the
    deferred leg's receipt is sealed with that exit code. The
    audit accepts the presentation only when the segment itself
    proves the deferral was sound, mirroring the runtime gate:
    this receipt is the unittest leg, collected zero, and a
    Python leg AFTER it collected tests and exited 0 un-timed-out
    — the union the gate judged. Any other non-zero receipt
    remains a failed receipt, exactly as before.
    """
    if (
        receipt.get("command_id") != "unittest"
        or receipt.get("exit_code") != _UNITTEST_NO_TESTS_EXIT_CODE
        or receipt.get("tests_collected") != 0
    ):
        return False
    return any(
        later.get("command_id") in _PYTHON_LEG_IDS
        and later.get("exit_code") == 0
        and not later.get("timed_out")
        and (later.get("tests_collected") or 0) > 0
        for later in receipts[idx + 1 :]
    )


def _speculative_zero_receipt(
    receipts: list[dict], idx: int, receipt: dict
) -> bool:
    """Whether a non-zero receipt is a speculative leg's excused
    clean zero (issue #51), acceptable at audit time.

    run_all excuses a speculative leg whose only failure is a
    clean zero collection when another Python leg passed — in
    either position (round 2) — and seals the excused leg's
    receipt with its exit code and the mark append_receipt
    recorded from its command (speculativeness is taken from
    that record, never re-derived: the record is what the
    verifier sealed, chain-covered like the exit code itself,
    while re-classifying a bound tree at audit would answer a
    different question about a possibly changed tree). The
    audit accepts the presentation only when the segment itself
    proves the excuse was sound, mirroring the runtime
    predicate over the shapes a receipt carries: the receipt
    is marked speculative (absent → deterministic, so
    pre-mark receipts stay fail-closed), it presents the shared
    (count, exit) pair (_speculative_zero_pair), and some
    Python leg in the segment collected tests and exited 0
    un-timed-out — the union the excuse judged, in any
    position. The transcript evidence the runtime predicate
    additionally demands cannot be re-seen here (receipts
    record only output hashes); that check is necessarily
    runtime-only, exactly as the deferred-zero acceptor above
    cannot re-see the "Ran 0 tests" line. Any other non-zero
    receipt remains a failed receipt.
    """
    if receipt.get("speculative") is not True:
        return False
    if receipt.get("command_id") not in _PYTHON_LEG_IDS:
        return False
    if not _speculative_zero_pair(
        receipt.get("tests_collected"), receipt.get("exit_code")
    ):
        return False
    return any(
        other.get("command_id") in _PYTHON_LEG_IDS
        and other.get("exit_code") == 0
        and not other.get("timed_out")
        and (other.get("tests_collected") or 0) > 0
        for other in receipts
    )


def check_receipts(
    receipts_path: Path,
    task: str,
    root: Path,
    historical: bool = False,
) -> int:
    lines = _receipt_lines(receipts_path)
    records: list[dict] = []
    for number, line in enumerate(lines, start=1):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        if not isinstance(parsed, dict):
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        if parsed.get("kind") == COMPLETION_KIND:
            required = COMPLETION_FIELDS
        elif parsed.get("kind") == RUN_START_KIND:
            required = RUN_START_FIELDS
        else:
            required = RECEIPT_FIELDS
        if any(field not in parsed for field in required):
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        records.append(parsed)

    prev_chain = GENESIS_CHAIN
    for number, receipt in enumerate(records, start=1):
        body = {k: v for k, v in receipt.items() if k != "chain_sha256"}
        if _chain_sha256(body, prev_chain) != receipt["chain_sha256"]:
            print(f"RECEIPTS: chain broken at line {number}")
            return 1
        prev_chain = receipt["chain_sha256"]

    task_records = [r for r in records if r["task"] == task]
    if not task_records:
        print(f"RECEIPTS: FAIL task {task}: no receipts")
        return 1

    # Segment selection. A verify run opens with a run-start record
    # and its receipts and completion carry that run_id; only the
    # task's LATEST segment is evidence — an interrupted earlier run
    # must not poison a successful retry, and earlier segments remain
    # audit history under the whole-file chain validation above. A
    # file with no run-start record for the task predates segments and
    # keeps the original whole-history semantics.
    start_idx = None
    for idx, record in enumerate(task_records):
        if record.get("kind") == RUN_START_KIND:
            start_idx = idx
    if start_idx is None:
        segment = list(task_records)
        segment_run_id = None
        start_record = None
    else:
        start_record = task_records[start_idx]
        segment_run_id = start_record["run_id"]
        segment = [
            r
            for r in task_records[start_idx + 1 :]
            if r.get("run_id") == segment_run_id
        ]

    # Strict field types (R7), scoped to the SELECTED segment only —
    # an oddity in a superseded segment is audit history and must not
    # poison this validation. This runs before any value comparison:
    # under `==`, a bool exit_code/duration/command_count would
    # otherwise impersonate 0/1 and fail open (panel EXP5).
    selected = (
        segment if start_record is None else [start_record, *segment]
    )
    for record in selected:
        bad_field = _segment_field_type_error(record)
        if bad_field is not None:
            expected = " or ".join(
                "null" if t is type(None) else t.__name__
                for t in SEGMENT_FIELD_TYPES[bad_field]
            )
            print(
                f"RECEIPTS: corrupt: field '{bad_field}' in the "
                f"selected segment has type "
                f"{type(record[bad_field]).__name__}, expected "
                f"{expected}"
            )
            return 1

    mine = [r for r in segment if r.get("kind") != COMPLETION_KIND]
    if not mine and segment_run_id is None:
        print(f"RECEIPTS: FAIL task {task}: no receipts")
        return 1
    for idx, receipt in enumerate(mine):
        if receipt["timed_out"] or (
            receipt["exit_code"] != 0
            and not _deferred_zero_receipt(mine, idx, receipt)
            and not _speculative_zero_receipt(mine, idx, receipt)
        ):
            print(
                f"RECEIPTS: FAIL task {task}: "
                f"receipt failed: {receipt['command_id']}"
            )
            return 1

    # The task's latest run must be proven complete: the task's records
    # must end with a run-completion record for that run whose count
    # and command-set digest match the run's command receipts. Without
    # one, the receipts may be all that a stopped-early run managed to
    # write.
    if task_records[-1].get("kind") != COMPLETION_KIND or (
        segment_run_id is not None
        and task_records[-1].get("run_id") != segment_run_id
    ):
        print(
            f"RECEIPTS: FAIL task {task}: "
            "incomplete run: no completion record"
        )
        return 1
    completion = task_records[-1]
    if segment_run_id is None:
        run_receipts: list[dict] = []
        for record in reversed(task_records[:-1]):
            if record.get("kind") == COMPLETION_KIND:
                break
            run_receipts.append(record)
        run_receipts.reverse()
    else:
        run_receipts = mine
    if len(run_receipts) != completion["command_count"] or _commands_digest(
        [r["command_id"] for r in run_receipts]
    ) != completion["commands_sha256"]:
        print(
            f"RECEIPTS: FAIL task {task}: "
            "completion record does not match run receipts"
        )
        return 1

    # Tree binding (R1): the segment must describe a tree. `binding`
    # is read directly — it is deliberately absent from the required
    # field tuples, so a pre-binding (legacy) segment reaches this
    # branch and is refused as UNBOUND, never misread as corrupt and
    # never silently validated (RC3).
    binding = completion.get("binding")
    start_binding = (
        start_record.get("binding") if start_record is not None else None
    )
    if binding is not None and start_binding is not None:
        if binding != start_binding:
            print(
                f"RECEIPTS: STALE task {task}: "
                "run-start and completion bindings disagree"
            )
            return 1
    if binding is None:
        binding = start_binding
    if (
        not isinstance(binding, dict)
        or binding.get("mode") not in ("git", "fs")
        or not isinstance(binding.get("tree_digest"), str)
        or not isinstance(binding.get("root"), str)
    ):
        print(
            f"RECEIPTS: UNBOUND task {task}: "
            "segment carries no tree binding"
        )
        return 2
    resolved_root = root.resolve()
    if binding["root"] != str(resolved_root):
        print(
            f"RECEIPTS: FAIL task {task}: segment is bound to root "
            f"{binding['root']}, not {resolved_root}"
        )
        return 1
    if binding["mode"] == "git":
        recorded_head = binding.get("head")
        digest = (
            _git_tree_digest(resolved_root, recorded_head)
            if isinstance(recorded_head, str)
            else None
        )
        if digest is None:
            print(
                f"RECEIPTS: UNVERIFIABLE task {task}: recorded commit "
                f"{recorded_head} is not readable"
            )
            return 2
        if digest != binding["tree_digest"]:
            print(
                f"RECEIPTS: STALE task {task}: tree digest does not "
                "match the recorded head"
            )
            return 1
        if not historical:
            current_head = _git_head(resolved_root)
            if current_head != recorded_head:
                print(
                    f"RECEIPTS: HEAD-MOVED task {task}: HEAD is "
                    f"{current_head}, segment bound to {recorded_head}"
                )
                return 1
            if not tree_clean(resolved_root, receipts_path):
                refusal = _repo_local_config_refusal(resolved_root)
                detail = f" ({refusal})" if refusal else ""
                print(
                    f"RECEIPTS: DIRTY task {task}: "
                    f"working tree is not clean{detail}"
                )
                return 1
    else:
        try:
            live_digest = _fs_tree_digest(resolved_root, receipts_path)
        except OSError:
            print(
                f"RECEIPTS: UNVERIFIABLE task {task}: "
                "live tree cannot be read"
            )
            return 2
        if live_digest != binding["tree_digest"]:
            print(
                f"RECEIPTS: STALE task {task}: live tree digest does "
                "not match the segment"
            )
            return 1
    print(f"RECEIPTS: PASS task {task}: {len(mine)} receipts, chain valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mechanical_verify.py")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--task", required=True)
    verify.add_argument("--timeout", type=int, default=300)
    verify.add_argument("--budget", type=int, default=600)
    verify.add_argument("--receipts", default=None)
    check_cmd = subparsers.add_parser("check-receipts")
    check_cmd.add_argument("--receipts", required=True)
    check_cmd.add_argument("--task", required=True)
    check_cmd.add_argument("--root", required=True)
    check_cmd.add_argument("--historical", action="store_true")
    args = parser.parse_args(argv)

    if args.subcommand == "check-receipts":
        return check_receipts(
            Path(args.receipts),
            args.task,
            Path(args.root),
            historical=args.historical,
        )

    # Every verify run sets the child-subreaper flag, receipts or
    # not: orphaned descendants of the run's commands reparent to
    # this process (PR_SET_CHILD_SUBREAPER) so run_verification's
    # post-run sweep can find and reap them. (check-receipts runs no
    # commands and needs no flag.)
    subreaper = _set_child_subreaper()

    if os.environ.get("AEP_VERIFY_FULL_ENV") == "1":
        # The env-scrub opt-out is loud, never silent (mirrors
        # lane-coord's AEP_LANE_FULL_ENV warning): stderr on every
        # run, and the run-start record states the mode.
        print(
            "VERIFY: warning AEP_VERIFY_FULL_ENV=1: commands receive "
            "the full environment (credential scrub disabled)",
            file=sys.stderr,
        )

    if os.environ.get("AEP_VERIFY_FULL_ENV") != "1":
        # Fail closed on an existing-but-invalid policy BEFORE any
        # command executes (panel ENV-P1): a policy that cannot be
        # honored must never degrade to an unscrubbed run wearing a
        # 'scrubbed' record. A missing policy is valid (unscrubbed,
        # and the record says so); the FULL_ENV opt-out skips the
        # check because the policy is not applied at all.
        try:
            policy_env_scrub(_policy_path())
        except PolicyError as exc:
            print(f"VERIFY: FAIL policy data invalid: {exc}")
            return 1

    receipts_path = Path(args.receipts) if args.receipts is not None else None
    if receipts_path is not None:
        # The verifier creates the receipts FILE on first append but
        # never its parent directories: a --receipts path into a
        # nonexistent directory is a caller error, refused here —
        # fail closed before running anything — rather than dying
        # with a FileNotFoundError traceback at the first append.
        if not receipts_path.parent.is_dir():
            print(
                f"VERIFY: FAIL receipts directory "
                f"{receipts_path.parent} does not exist "
                "— create it or point --receipts elsewhere"
            )
            return 1
        # Fail closed before running anything: never append to a receipts
        # file whose last line is malformed.
        lines = _receipt_lines(receipts_path)
        if lines:
            try:
                _last_chain(receipts_path)
            except ValueError:
                print(
                    f"RECEIPTS: corrupt at line {len(lines)} "
                    f"in {args.receipts}"
                )
                return 1

    root = Path(args.root)
    if receipts_path is not None and _receipts_file_tracked(
        root, receipts_path
    ):
        # Evidence must not be part of the artifact (P2-1 residue):
        # a receipts file tracked by git inside the root would be
        # sealed into the very tree it describes. Untracked receipts
        # inside the root — the SDD layout — are explicitly allowed.
        print(
            f"VERIFY: FAIL receipts file {receipts_path} is tracked "
            f"by git inside {root} — point --receipts at an "
            "untracked path"
        )
        return 2
    commands = discover_verification_commands(root)
    markdownlint_skipped = _is_real_file(root / ".markdownlint.yaml") and all(
        c.id != "markdownlint" for c in commands
    )
    if not commands:
        print(
            f"VERIFY: no verification commands discovered at {root} "
            "— no mechanical evidence available"
        )
        if markdownlint_skipped:
            print(
                "VERIFY: markdownlint SKIPPED tool missing "
                "(markdownlint-cli2 not on PATH)"
            )
        return 2
    if markdownlint_skipped:
        print(
            "VERIFY: markdownlint SKIPPED tool missing "
            "(markdownlint-cli2 not on PATH)"
        )
    run_id: str | None = None
    binding: dict | None = None
    on_result = None
    if receipts_path is not None:
        task = args.task
        run_id = uuid.uuid4().hex
        # subreaper was set at the top of the verify path (every run,
        # not only evidence runs); the run-start record states
        # whether the flag was actually set.
        # Tree binding (R1): an evidence run binds to the tree before
        # its first command. Git mode refuses a dirty tree outright —
        # a segment sealed over uncommitted state could never be
        # re-validated against its recorded HEAD.
        try:
            binding = tree_binding(root, receipts_path)
        except (OSError, ValueError) as exc:
            print(
                f"VERIFY: cannot bind receipts to the tree "
                f"at {root}: {exc}"
            )
            return 1
        append_run_start(
            receipts_path,
            task,
            run_id,
            binding=binding,
            subreaper=subreaper,
            env=run_env_mode(_policy_path()),
        )
        if binding["mode"] == "git" and not tree_clean(root, receipts_path):
            refusal = _repo_local_config_refusal(root)
            detail = f" ({refusal})" if refusal else ""
            print(
                "VERIFY: FAIL tree not clean at HEAD "
                f"— commit or stash before verifying{detail}"
            )
            return 1

        def on_result(result: VerificationResult) -> None:
            append_receipt(receipts_path, task, result, run_id=run_id)

    between_commands = None
    if binding is not None and binding["mode"] == "git":
        # Close the bind -> first-command gap as well: revalidate
        # once immediately before the first command runs.
        excursion = binding_excursion(root, binding, receipts_path)
        if excursion is not None:
            print(
                f"VERIFY: FAIL tree binding changed during the "
                f"run: {excursion} — aborting without a "
                f"completion record"
            )
            return 1

        def between_commands() -> str | None:
            return binding_excursion(root, binding, receipts_path)

    rc = run_all(
        root,
        commands,
        timeout_seconds=args.timeout,
        budget_seconds=args.budget,
        mem_available_kb=available_memory_kb,
        on_result=on_result,
        between_commands=between_commands,
    )
    if rc == 0 and receipts_path is not None:
        # run_all returns 0 only when every command executed and
        # passed; seal the run so check_receipts can reject a partial
        # receipt set — but only if the tree is still the tree the run
        # bound to. Dirtied during the run (git) or changed (fs): no
        # completion record; the incomplete segment is the verdict.
        if binding is not None and binding["mode"] == "git":
            seal = tree_clean(root, receipts_path)
        elif binding is not None:
            try:
                seal = (
                    tree_binding(root, receipts_path)["tree_digest"]
                    == binding["tree_digest"]
                )
            except (OSError, ValueError):
                seal = False
        else:
            seal = True
        if not seal:
            print(
                "VERIFY: FAIL tree changed during the run "
                "— no completion record written"
            )
            return 1
        append_completion(
            receipts_path, task, commands, run_id=run_id, binding=binding
        )
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
