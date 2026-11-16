#!/usr/bin/env python3
"""Criterion-1 probe: run INSIDE the sandbox. Every check prints PASS/FAIL.
PASS means the confinement held (target absent/unreadable) or a positive
control behaved as designed."""
import os
import socket
import sys

results = []

def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

def default_routes(table_text):
    """Default-route rows of a /proc/net/route dump.

    The table is a header line plus one whitespace-separated row per
    route; the second field of a row is the destination in network byte
    order as hex, and "00000000" is the catch-all.
    """
    rows = []
    for line in table_text.splitlines()[1:]:
        fields = line.split()
        if len(fields) > 1 and fields[1] == "00000000":
            rows.append(fields)
    return rows


def must_not_read(path):
    try:
        if os.path.isdir(path):
            os.listdir(path)
            return False, "directory LISTABLE"
        with open(path, "rb") as f:
            f.read(16)
        return False, "file READABLE"
    except FileNotFoundError:
        return True, "absent"
    except PermissionError:
        return True, "permission denied"
    except OSError as e:
        return True, f"oserror {e.errno}"

HOME = "@OPERATOR_HOME@"
# 1a. Memory store and durable memory files
for p in [f"{HOME}/.config/NeuroStrata", f"{HOME}/MEMORY.md", f"{HOME}/memory"]:
    ok, d = must_not_read(p)
    check(f"unreadable: {p}", ok, d)
# 1b. Other lanes' trees
for p in [f"{HOME}/workspace/neurostrata-pr184-remediation",
          f"{HOME}/workspace/custom-skills",
          f"{HOME}/workspace"]:
    ok, d = must_not_read(p)
    check(f"unreadable: {p}", ok, d)
# 1c. Credential locations
for p in [f"{HOME}/.ssh", f"{HOME}/.config/gh/hosts.yml", f"{HOME}/.aws",
          f"{HOME}/.gnupg", f"{HOME}/.netrc"]:
    ok, d = must_not_read(p)
    check(f"unreadable: {p}", ok, d)
# 1d. Host home should not even exist as a path
ok, d = must_not_read(HOME)
check(f"unreadable: {HOME} (whole home)", ok, d)

# 1e. Environment: no credential-shaped variables.
# Refinement (2a run, recorded in ADOPTION-ADDENDUM.md): GIT_CONFIG_KEY_<n>
# is git's config-plumbing naming — its VALUE is a public config key name
# (here the literal "safe.directory"), not key material. The naive
# substring scan false-positived on it. The property under test is "no
# credential material in env", so GIT_CONFIG_KEY_* is exempted BY NAME
# PATTERN; every other KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL-named
# variable still fails the probe.
bad = [k for k in os.environ
       if any(s in k.upper() for s in ("TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL"))
       and not (k.startswith("GIT_CONFIG_KEY_") and k.rsplit("_", 1)[-1].isdigit())]
check("env carries no credential variables", not bad, f"found={bad}")
print("INFO  env keys present:", sorted(os.environ.keys()))

# 1f. PID namespace: only sandbox processes visible
pids = [d for d in os.listdir("/proc") if d.isdigit()]
check("pid namespace hides host processes", len(pids) <= 25, f"visible pids={len(pids)}")
try:
    with open("/proc/1/cmdline", "rb") as f:
        c1 = f.read().replace(b"\0", b" ").decode(errors="replace").strip()
except OSError:
    c1 = "<unreadable>"
print(f"INFO  /proc/1 cmdline: {c1}")
check("pid 1 is not host systemd session tree", "systemd --system" not in c1, "")

# 1g. Network namespace: no egress, no DNS
try:
    s = socket.create_connection(("1.1.1.1", 443), timeout=3)
    s.close()
    check("no direct egress (1.1.1.1:443)", False, "CONNECT SUCCEEDED")
except OSError as e:
    check("no direct egress (1.1.1.1:443)", True, type(e).__name__)
try:
    socket.getaddrinfo("github.com", 443)
    check("no DNS resolution", False, "RESOLVED")
except OSError as e:
    check("no DNS resolution", True, type(e).__name__)
try:
    with open("/proc/net/route") as f:
        routes = default_routes(f.read())
    check("no default route", not routes, f"default routes={len(routes)}")
except OSError as e:
    check("no default route", False, f"route table unreadable: {e}")

# 1h. Positive controls: the declared mounts behave as designed
try:
    with open("/work/.probe-write-test", "w") as f:
        f.write("ok")
    os.unlink("/work/.probe-write-test")
    check("control: /work writable", True)
except OSError as e:
    check("control: /work writable", False, str(e))
try:
    entries = os.listdir("/skills")
    check("control: /skills readable", len(entries) > 0, f"{len(entries)} entries")
except OSError as e:
    check("control: /skills readable", False, str(e))
try:
    with open("/skills/.probe-write-test", "w") as f:
        f.write("x")
    os.unlink("/skills/.probe-write-test")
    check("control: /skills NOT writable (ro bind)", False, "WRITE SUCCEEDED")
except OSError:
    check("control: /skills NOT writable (ro bind)", True)
try:
    with open("/out/.probe-write-test", "w") as f:
        f.write("ok")
    os.unlink("/out/.probe-write-test")
    check("control: /out writable", True)
except OSError as e:
    check("control: /out writable", False, str(e))

# 1i. Root listing: only the constructed root should exist
print("INFO  / contains:", sorted(os.listdir("/")))
check("no /home in sandbox root", not os.path.exists("/home"))
check("no /root in sandbox root", not os.path.exists("/root"))

fails = [n for n, ok in results if not ok]
print(f"PROBE SUMMARY: {len(results) - len(fails)}/{len(results)} passed; failures: {fails}")
sys.exit(1 if fails else 0)
