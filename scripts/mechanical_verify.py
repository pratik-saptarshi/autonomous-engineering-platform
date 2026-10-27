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
import ctypes
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
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
# addopts and the command line, and the count parser reads the
# terminal summary — so the discovered invocation must guarantee
# that summary is emitted. The old -q spent one quiet level here,
# and a project with `addopts = -q` stacked to -qq, which
# suppresses the summary entirely: a passing run printed only
# `. [100%]`, parsed to zero collected, and was rejected (Codex
# P2, round 5). -v nets +1, so project addopts down to -qq still
# leave the summary alive.
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


def _pytest_config_selected(root: Path) -> Path | None:
    """The config file pytest would read at *root*, following
    pytest's inifile precedence — pytest.ini, then pyproject.toml
    holding [tool.pytest.ini_options], then setup.cfg holding
    [tool:pytest] — or None when no candidate qualifies. Only
    real files are read: a symlink candidate is reported at its
    precedence position without being read, because whether
    pytest would honour it depends on the unbound target's
    contents."""
    pytest_ini = root / "pytest.ini"
    if pytest_ini.is_file():
        return pytest_ini
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        if pyproject.is_symlink():
            return pyproject
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return pyproject
        if "[tool.pytest.ini_options]" in text:
            return pyproject
    setup_cfg = root / "setup.cfg"
    if setup_cfg.is_file():
        if setup_cfg.is_symlink():
            return setup_cfg
        try:
            text = setup_cfg.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return setup_cfg
        if "[tool:pytest]" in text:
            return setup_cfg
    return None


def _pytest_argv(root: Path) -> tuple[str, ...]:
    """The bare-pytest command for *root*. When the config pytest
    would read is a symlink, the argv pins an empty config
    (-c os.devnull) so collection follows only in-tree defaults
    and the unbound file's addopts/testpaths define nothing
    (issue #64)."""
    selected = _pytest_config_selected(root)
    if selected is not None and selected.is_symlink():
        return PYTEST_ARGV + ("-c", os.devnull)
    return PYTEST_ARGV


def discover_verification_commands(root: Path) -> tuple[VerificationCommand, ...]:
    # Symlink policy (issues #63, #64): a symlinked marker or
    # config file does not schedule, gate, or steer its leg. The
    # tree binding records a symlink's target *string* (git blob /
    # fs readlink), never the target's contents, so content
    # reached through a link is unbound: a symlinked go.mod,
    # Cargo.toml, package.json, Makefile, or .markdownlint.yaml
    # is treated as absent; a symlinked pytest config cannot
    # trigger the bare pytest leg; and when that leg is scheduled
    # by other evidence, its argv pins an empty config if the
    # config pytest would read is a symlink (see _pytest_argv).
    # The caller-selected root itself may be a symlink — it is
    # the boundary the binding canonicalizes; every check below
    # applies to entries under it.
    commands: list[VerificationCommand] = []
    seen: set[str] = set()

    def add(command: VerificationCommand) -> None:
        if command.id not in seen:
            seen.add(command.id)
            commands.append(command)

    # 1. Go (AEP addition).
    if _is_real_file(root / "go.mod"):
        add(VerificationCommand("go-test", "Go tests", ("go", "test", "./...")))

    # 2. Rust.
    if _is_real_file(root / "Cargo.toml"):
        add(VerificationCommand("cargo-test", "Rust tests", ("cargo", "test")))

    # 3. Node — only with a real scripts.test string.
    package_json = root / "package.json"
    if _is_real_file(package_json):
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
        _is_real_file(root / "pytest.ini")
        or _is_real_file(root / "pyproject.toml")
        or _is_real_file(root / "setup.cfg")
        or (root / "tests").exists()
    ):
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
    test_files: list[Path] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not entry.is_file() or not entry.name.endswith(".py"):
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
        if pytest_triggered:
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
_PYTEST_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|deselected|errors?|xfailed|xpassed)\b"
)
_PYTEST_SUMMARY_TAIL_RE = re.compile(r" in \d+(?:\.\d+)?s\b")
# The collection header pytest prints as collection finishes
# ("collecting ... collected N items"): the transcript's own
# statement of how much collection found, independent of the
# summary line the count parser reads.
_PYTEST_COLLECTED_RE = re.compile(r"collected (\d+) items?\b")


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
    pytest: the collected count is
    the sum of the outcome groups in the summary line
    (passed+failed+skipped+errors+xfailed+xpassed) EXCLUDING
    `deselected` — deselected tests were filtered OUT by the runner
    and never collected for execution (panel correctness P2-B).
    Zero collection is recognized only from the runner's final
    summary line itself (`no tests ran in …s`): the same phrase in
    test output (exposed by e.g. `addopts = -s`) is a diagnostic,
    not the summary, and must not override it (Codex P2, round 4).
    The summary itself is guaranteed by the invocation: PYTEST_ARGV
    nets positive verbosity, so project addopts cannot stack quiet
    levels into suppressing it (Codex P2, round 5). A transcript
    with no summary line at all (dots only) still parses to 0 —
    verbosity-independent evidence was deliberately NOT taken from
    e.g. the progress dots, which are not a count.
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
        combined = stdout + "\n" + stderr
        total: int | None = None
        for line in combined.splitlines():
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
        return total if total is not None else 0
    return None


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
    started = time.monotonic()
    # Snapshot this process's children immediately before the spawn:
    # the post-run sweep kills only children that appear after this
    # point (plus the leader's group), so bystanders that predate the
    # command are never signalled.
    snapshot = _children_start_times()
    try:
        proc = subprocess.Popen(
            list(command.argv),
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return VerificationResult(
            command=command,
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
    return VerificationResult(
        command=command,
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
        tests_collected=_count_collected(
            command.id, stdout_text, stderr_text
        ),
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

FS_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "target",
        "node_modules",
        "coverage",
        "htmlcov",
        "dist",
        "build",
        ".tox",
        ".venv",
    }
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        timeout=60,
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


def _fs_tree_digest(root: Path, receipts_path: Path | None = None) -> str:
    """Digest of a non-git tree: sha256 over sorted relative paths of
    `relpath + "\\0" + mode + "\\0" + content + "\\0"`, where mode is
    the entry's git-style mode string (file type + executable bit —
    see `_fs_entry_mode`) and content is the file's sha256 hex
    (symlinks: the target string, never followed). Paths with a
    component in FS_EXCLUDED_DIRS and the receipts file itself are
    excluded.
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
            if name in FS_EXCLUDED_DIRS:
                continue
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
                entries.append(
                    (
                        rel,
                        _fs_entry_mode(path),
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
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


def tree_clean(root: Path, receipts_path: Path | None = None) -> bool:
    """Git-mode cleanliness predicate for the binding gate.

    `git status --porcelain --untracked-files=all` must be empty
    after dropping (i) the
    receipts file itself and UNTRACKED entries under `.superpowers/`
    (the workflow's own bookkeeping — a TRACKED `.superpowers/` entry
    that is modified or staged counts as dirty like any other
    tracked change) and (ii) untracked entries whose path has a
    component in FS_EXCLUDED_DIRS (tool caches the run itself
    creates). Modified or staged tracked entries always count as
    dirty; the exclusions never hide a tracked change.
    """
    resolved = root.resolve()
    top = _git(resolved, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return False
    toplevel = Path(
        top.stdout.decode("utf-8", errors="replace").strip()
    ).resolve()
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
        ):
            continue
        if status == b"??" and any(
            part in FS_EXCLUDED_DIRS for part in path.split("/")
        ):
            continue
        return False
    return True


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
                print(
                    f"RECEIPTS: DIRTY task {task}: "
                    "working tree is not clean"
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
            print(
                "VERIFY: FAIL tree not clean at HEAD "
                "— commit or stash before verifying"
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
