#!/usr/bin/env python3
"""2a-layer probes: run INSIDE the sandbox. Prove each hardening layer
fires — Landlock ruleset, seccomp denylist, unprivileged uid — with
discriminating tests (actions that discretionary permissions / normal
unprivileged semantics ALLOW, so only the layer under test can deny).

With --syscalls-only: run just the raw syscall sweep (used for the
host-side baseline, where no gate is installed; landlock/uid checks are
skipped and syscall outcomes are printed for comparison)."""
import ctypes
import errno
import os
import sys

libc = ctypes.CDLL("libc.so.6", use_errno=True)
results = []

def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

def raw_syscall(nr, *args):
    ctypes.set_errno(0)
    ret = libc.syscall(nr, *args)
    return ret, ctypes.get_errno()

# x86_64 syscall numbers exercised below
SYS = dict(mount=165, umount2=166, pivot_root=155, chroot=161, open_tree=428,
           move_mount=429, fsopen=430, fsconfig=431, fsmount=432,
           mount_setattr=442, unshare=272, setns=308, init_module=175,
           finit_module=313, delete_module=176, create_module=174,
           kexec_load=246, kexec_file_load=320, reboot=169, syslog=103,
           _sysctl=156, get_kernel_syms=177, query_module=178,
           nfsservctl=180, quotactl=179, acct=163, ptrace=101,
           process_vm_readv=310, process_vm_writev=311, kcmp=312,
           pidfd_getfd=438, add_key=248, request_key=249, keyctl=250,
           bpf=321, perf_event_open=298, userfaultfd=323,
           io_uring_setup=425, io_uring_enter=426, io_uring_register=427,
           name_to_handle_at=303, open_by_handle_at=304, mknod=133,
           mknodat=259, settimeofday=164, clock_settime=227, adjtimex=159,
           swapon=167, swapoff=168, vhangup=153, personality=135,
           getuid=102)  # x86_64 getuid; 186 is gettid (probe bug, 2a run)

SYSCALLS_ONLY = "--syscalls-only" in sys.argv

if not SYSCALLS_ONLY:
    # ---------- Layer (c): unprivileged uid ----------
    check("payload uid is 65534 (nobody)", os.getuid() == 65534,
          f"uid={os.getuid()}")
    check("payload gid is 65534 (nogroup)", os.getgid() == 65534,
          f"gid={os.getgid()}")
    try:
        with open("/proc/self/status") as f:
            status = f.read()
        capeff = [l for l in status.splitlines() if l.startswith("CapEff")]
        check("payload holds no capabilities", capeff and capeff[0].split()[1] == "0" * 16,
              capeff[0] if capeff else "CapEff unreadable")
        sec = [l for l in status.splitlines() if l.startswith("Seccomp:")]
        nn = [l for l in status.splitlines() if l.startswith("NoNewPrivs:")]
        print(f"INFO  status: {sec} {nn}")
        check("seccomp mode is filter (2)", bool(sec) and sec[0].split()[1] == "2",
              sec[0] if sec else "")
        check("no_new_privs is set", bool(nn) and nn[0].split()[1] == "1",
              nn[0] if nn else "")
    except OSError as e:
        check("/proc/self/status readable", False, str(e))
    try:
        os.setuid(0)
        check("root-only action setuid(0) refused", False, "SETUID(0) SUCCEEDED")
    except PermissionError:
        check("root-only action setuid(0) refused", True, "EPERM")
    except OSError as e:
        check("root-only action setuid(0) refused", False, f"errno {e.errno}")

    # ---------- Layer (a): Landlock ----------
    # /scratch: dir mode 777, secret.txt mode 644, both root-owned.
    # Discretionary permissions ALLOW nobody to read the file and create
    # new files in the dir. Only Landlock can deny these.
    try:
        with open("/scratch/secret.txt", "rb") as f:
            f.read(1)
        check("landlock: read /scratch/secret.txt denied", False, "READ SUCCEEDED")
    except PermissionError:
        check("landlock: read /scratch/secret.txt denied", True, "EACCES")
    except OSError as e:
        check("landlock: read /scratch/secret.txt denied", False,
              f"errno {e.errno} ({errno.errorcode.get(e.errno)})")
    try:
        fd = os.open("/scratch/escape", os.O_CREAT | os.O_WRONLY, 0o644)
        os.close(fd)
        os.unlink("/scratch/escape")
        check("landlock: create /scratch/escape denied", False, "CREATE SUCCEEDED")
    except PermissionError:
        check("landlock: create /scratch/escape denied", True, "EACCES")
    except OSError as e:
        check("landlock: create /scratch/escape denied", False,
              f"errno {e.errno} ({errno.errorcode.get(e.errno)})")
    # Controls: Landlock grants still work (it is a policy, not a wall).
    try:
        with open("/tmp/.landlock-control", "w") as f:
            f.write("ok")
        os.unlink("/tmp/.landlock-control")
        check("landlock control: /tmp write allowed", True)
    except OSError as e:
        check("landlock control: /tmp write allowed", False, str(e))
    try:
        with open("/work/.landlock-control", "w") as f:
            f.write("ok")
        os.unlink("/work/.landlock-control")
        check("landlock control: /work write allowed", True)
    except OSError as e:
        check("landlock control: /work write allowed", False, str(e))

# ---------- Layer (b): seccomp denylist ----------
# Discriminating probes: legal no-ops / unprivileged-allowed calls that
# only an installed filter can turn into EPERM. (Host baseline with
# --syscalls-only shows what these return with NO gate installed.)
ret, err = raw_syscall(SYS["unshare"], 0)  # unshare(0) is a legal no-op
if SYSCALLS_ONLY:
    print(f"INFO  baseline unshare(0): ret={ret} errno={err}")
else:
    check("seccomp: unshare(0) no-op denied", ret == -1 and err == errno.EPERM,
          f"ret={ret} errno={err}")
ret, err = raw_syscall(SYS["ptrace"], 0, 0, 0, 0)  # PTRACE_TRACEME on self
if SYSCALLS_ONLY:
    print(f"INFO  baseline ptrace(TRACEME): ret={ret} errno={err}")
else:
    check("seccomp: ptrace(TRACEME) denied", ret == -1 and err == errno.EPERM,
          f"ret={ret} errno={err}")
    if ret == 0:
        raw_syscall(101, 17, 0, 0, 0)  # PTRACE_DETACH if it somehow traced
ret, err = raw_syscall(SYS["keyctl"], 1, 0, 0, 0, 0)  # JOIN_SESSION_KEYRING, NULL name
if SYSCALLS_ONLY:
    print(f"INFO  baseline keyctl(JOIN_SESSION_KEYRING): ret={ret} errno={err}")
else:
    check("seccomp: keyctl(JOIN_SESSION_KEYRING) denied",
          ret == -1 and err == errno.EPERM, f"ret={ret} errno={err}")
ret, err = raw_syscall(SYS["io_uring_setup"], 8, None)
if SYSCALLS_ONLY:
    print(f"INFO  baseline io_uring_setup(8): ret={ret} errno={err}")
else:
    check("seccomp: io_uring_setup denied", ret == -1 and err == errno.EPERM,
          f"ret={ret} errno={err}")
    if ret >= 0:
        os.close(ret)

# Full denylist sweep: every denied syscall must fail (never succeed).
# Benign/zero arguments; for syscalls an unprivileged process would be
# refused anyway, the outcome is recorded as-is — mechanism attribution
# rests on the discriminating probes + Seccomp status above.
SWEEP_ARGS = {
    "mount": (b"none", b"/tmp", b"tmpfs", 0, None), "umount2": (b"/nonexistent", 0),
    "pivot_root": (b"/tmp", b"/tmp"), "chroot": (b"/tmp",),
    "open_tree": (-100, b"/tmp", 0), "move_mount": (-100, b"", -100, b"", 0),
    "fsopen": (b"tmpfs", 0), "fsconfig": (0, 0, None, None, 0),
    "fsmount": (0, 0, 0), "mount_setattr": (-100, b"/tmp", 0, None, 0),
    "setns": (-1, 0), "init_module": (None, 0, None),
    "finit_module": (-1, None, 0), "delete_module": (b"nonexistent", 0),
    "create_module": (b"nonexistent", 0), "kexec_load": (0, 0, None, None),
    "kexec_file_load": (-1, -1, 0, None, 0), "reboot": (0, 0, 0, None),
    "syslog": (0, None, 0), "_sysctl": (None,), "get_kernel_syms": (None,),
    "query_module": (None, 0, 0, None, None), "nfsservctl": (0, None, None),
    "quotactl": (0, None, 0, 0), "acct": (None,),
    "process_vm_readv": (1, None, 0, None, 0, 0),
    "process_vm_writev": (1, None, 0, None, 0, 0),
    "kcmp": (1, 1, 0, 0, 0), "pidfd_getfd": (-1, 0, 0),
    "add_key": (b"user", b"probe", None, 0, -3),
    "request_key": (b"user", b"probe", None, -3),
    "bpf": (0, None, 0), "perf_event_open": (None, 0, -1, -1, 0),
    "userfaultfd": (0,), "io_uring_enter": (-1, 0, 0, 0, None, 0),
    "io_uring_register": (-1, 0, None, 0),
    "name_to_handle_at": (-100, b"/tmp", None, None, 0),
    "open_by_handle_at": (-100, None, 0),
    "mknod": (b"/tmp/.probe-node", 0o600 | 0o2000, 0),
    "mknodat": (-100, b".probe-node", 0o600 | 0o2000, 0),
    "settimeofday": (None, None), "clock_settime": (0, None),
    "adjtimex": (None,), "swapon": (b"/nonexistent", 0),
    "swapoff": (b"/nonexistent",), "vhangup": (), "personality": (0xFFFFFFFF,),
}
sweep_bad = []
for name in sorted(SWEEP_ARGS):
    nr = SYS[name]
    args = SWEEP_ARGS[name]
    ret, err = raw_syscall(nr, *args)
    ok = ret == -1 and err in (errno.EPERM, errno.ENOSYS, errno.EACCES)
    print(f"{'INFO ' if SYSCALLS_ONLY else ('PASS ' if ok else 'FAIL ')} "
          f"sweep {name}: ret={ret} errno={err} ({errno.errorcode.get(err, '?')})")
    if not SYSCALLS_ONLY and not ok:
        sweep_bad.append(name)
    if name == "mknod":
        try:
            os.unlink("/tmp/.probe-node")
        except OSError:
            pass
if not SYSCALLS_ONLY:
    check("seccomp sweep: no denied syscall succeeded", not sweep_bad,
          f"succeeded={sweep_bad}")
    # Selectivity control: an allowed syscall still works.
    ret, err = raw_syscall(SYS["getuid"])
    check("seccomp control: getuid allowed", ret == 65534, f"ret={ret}")

if SYSCALLS_ONLY:
    print("BASELINE SWEEP DONE")
    sys.exit(0)
fails = [n for n, ok in results if not ok]
print(f"LAYER PROBE SUMMARY: {len(results) - len(fails)}/{len(results)} passed; failures: {fails}")
sys.exit(1 if fails else 0)
