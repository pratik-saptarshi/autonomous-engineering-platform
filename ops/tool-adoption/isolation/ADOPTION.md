# Isolation stack adoption record

The adoption record for the isolation instance of the tool-adoption
pattern (playbook: `ops/tool-adoption/README.md`). Adopted shape:
**locally operated confinement mechanisms for one lane type** —
evaluation of external/untrusted repositories and skills. The
installer that reproduces this adoption is `install.sh` in this
directory.

One shape difference from the Plannotator instance, stated plainly:
the composite's launchers and gate are **our own code**, so their
sources are committed here — they are the mechanism, and the next
operator must be able to audit them. Third-party binaries are **not**
committed: `runsc` and the `nsjail` binary are reproduced on each
machine from the pins and recipes below, exactly as the pattern
requires. Nothing in this instance is vendored third-party source.

- Adoption date: 2026-11-14
- Authority: owner ruling 2026-11-14 — adopt the isolation survey's
  top three ranked options simultaneously, with the rank-1 composite
  plus its 2a hardening as the standing boundary for
  untrusted-evaluation lanes.
- Scope: the untrusted-evaluation lane type only. Trusted,
  continuity-dependent lanes are not routed through these boundaries.
- Platform: Linux x86_64, systemd as PID 1 (this runtime class; see
  the prerequisite checks in `install.sh`).

## Evidence base

The verdicts behind this adoption, retained per machine as local
state (not repository content, as with the Plannotator pilot
workspace):

- `~/workspace/plans/isolation-findings-report-2026-11-14/isolation-findings-report.html`
  — the consolidated findings report.
- `~/workspace/plans/isolation-patterns-survey-2026-11-14/` — the
  survey: ranking (composite 4.20, gVisor 3.65, nsjail/Incus tied
  3.35), environment facts, avoid list.
- `~/workspace/plans/ai-software-factory-evaluation-2026-11-14/` —
  Item 2 (ephemeral isolation: ADAPT) and Item 3 (event-triggered
  pipelines: REJECT as built; its 11-point control set is the price
  of admission for any future event-triggered lane).
- Per-component local records: `~/workspace/isolation-pilot/`
  (ADOPTION.md, RESULTS.md, ADOPTION-ADDENDUM.md),
  `~/workspace/gvisor/ADOPTION.md`, `~/workspace/nsjail/ADOPTION.md`,
  `~/workspace/incus/FEASIBILITY.md`.

## Status summary

| Component | Survey rank | Status on the origin runtime |
|---|---|---|
| Rank-1 composite + `sandbox-gate` (2a) | 1 (4.20) | **Adopted and in force** for untrusted-evaluation lanes |
| gVisor / `runsc` (systrap) | 2 (3.65) | **Adopted** as the opt-in boundary for the highest-risk lane type (launcher flag, default off); smoke-test gate passed |
| nsjail profile | 3 (tied, 3.35) | **Adopted** — pinned local build, profile probed, sibling launcher live |
| Incus | 3 (tied, 3.35) | **Adopted-in-pattern, blocked on this runtime** — documented negative case (below); no installer step exists |

## ⚠ Standing warning — this stack is NOT resource-capped on this runtime

Pilot criterion 2 **failed**, and the failure is a substrate fact,
not a defect in the mechanisms: this runtime is delegated a cgroup v2
tree with **no memory or CPU controllers**
(`/sys/fs/cgroup/cgroup.controllers` is empty). Every cgroup-based
ceiling is therefore recorded-but-unenforceable here:

- `systemd-run` accepts `MemoryMax`/`CPUQuota`/`TasksMax` and
  enforces none of them (proven twice: the preserved hog test
  allocated the full 1,536 MiB against a nominal 512 MiB cap, in the
  pilot and again against the hardened launcher);
- nsjail's cgroup v2 mode cannot even be armed — it aborts
  fail-closed trying to enable the `+memory` controller;
- gVisor's in-sandbox cgroups are accounting-only, and no OCI
  resource limit is set.

**Never describe this stack as resource-capped on this runtime.**
The only functioning resource controls are the wall-clock timeout,
`time_limit`, and the rlimit family (nsjail profile). Resource
blast-radius is an infrastructure decision — a host that delegates
cgroup controllers. The preserved hog test (`probes/hog.py`,
`sandbox-run hogtest`) re-runs unchanged if the runtime changes;
criteria 1/3/4 and the 2a layers do not depend on it.

## Component 1 — rank-1 composite + sandbox-gate (2a hardening)

The default boundary. `sandbox-run` is the only entry point:
fresh clone dir per run → `systemd-run` system scope → `unshare`
mount/PID/net namespaces → a hand-built chroot root (tmpfs; only the
declared binds exist inside) → **`sandbox-gate`** runs first inside
the chroot and, before exec'ing the payload:

1. applies a **Landlock** ruleset built from the declared path
   policy (runtime-queried ABI **8** on the origin kernel,
   7.0.0-44-generic; handled FS mask covers access types through
   ABI 5 — any type introduced later is unhandled until the gate's
   mask is extended);
2. **drops the payload to uid/gid 65534** (setgroups → setgid →
   setuid, self-verified; CapEff 0) — closing the pilot's recorded
   root-in-namespace residual for the payload;
3. sets `no_new_privs` and installs a **seccomp denylist**
   (hand-built classic BPF via raw `prctl`, no libseccomp
   dependency): **51 syscalls → EPERM**, grouped as
   mount/namespace manipulation, kernel-module and kernel control,
   cross-process introspection, kernel keyring, eBPF/perf/
   userfaultfd, the io_uring family, file-handle bypass, device-node
   creation, and clock/swap/personality hardening. It is a denylist,
   not an allowlist; clone/clone3 stay allowed because the evaluated
   workloads need them.

Kept from the pilot: split-phase egress (a protocol-restricted
`git clone` host-side is the only network step, before any untrusted
code exists; the run phase has **no egress at all**, not even DNS),
allowlist-only scrubbed environment with an explicit
credential-shape assertion, fail-closed launcher (exit 64, payload
never runs), exact exit-code propagation, clean teardown.

### Pins (origin runtime, 2026-11-14)

| Artefact | SHA256 |
|---|---|
| `bin/sandbox-run` (this directory) | `7374076c471053159f8dfb56b9e084b418fe5d9fafd59a50d674c1c1a6f4095d` |
| `bin/inner.sh` | `66de07ba99ad6f50e71c380289ec61dadeed47f8214b746c7cc1558933f63fff` |
| `gate/sandbox-gate.c` (source pin) | `d1a9bdea0480d19280c6def5ac7f2145dfc1de9d4706f5a45e37d087b9d716f1` |
| built `sandbox-gate` binary (origin build, `gcc -O2 -static`) | `0e23eb3bd54e660743cfe1c2f0ccc2e2cad5f8e7bff848c6573ff0470ccd9762` |

Note: the `bin/sandbox-run` pin above moved with the hogtest log-directory and `runsc --log` diagnostic-channel remediations; the remaining rows are the origin runtime's pins, unchanged.

The source is the pin: `install.sh` verifies the source hash, builds
locally, and reports the resulting binary hash (a different toolchain
may produce a different binary hash; that is recorded, not hidden).

### Evidence (run `eval2`, target `more-itertools` @ `ceafee8`)

- Criterion 1, confinement of reads: **24/24 PASS** — memory store,
  other lanes' trees, `~/.ssh`, `~/.config/gh` are *absent paths*
  inside (not merely denied); zero credential-shaped env vars;
  PID namespace shows only the payload tree; no route/DNS.
- 2a layer probes: **16/16 PASS** plus a 47-entry syscall sweep, all
  EPERM. The Landlock proof is discriminating: a fixture directory
  whose discretionary permissions fully allow the payload (dir 777,
  file 644) denies with EACCES — only Landlock produces that denial.
  Seccomp attribution rests on same-uid host-baseline discriminators
  (calls legal for an unprivileged process return EPERM only inside).
  One attribution note: `io_uring_setup` is also EPERM on the host
  baseline (the agent runtime's own inherited filter denies it); the
  gate denies it independently, so the guarantee holds regardless.
- Criterion 3, no behaviour change: **PASS** — inspection output
  byte-identical to the host baseline; the target's full suite
  in-sandbox: **935 tests OK** (42.4 s vs pilot's 40.4 s — the 2a
  layers cost no meaningful time).
- Criterion 4, clean teardown: **PASS**, independently verified.
- Criterion 2: **FAIL — re-confirmed** (see the standing warning).

### Deviations (environment-forced, recorded)

1. **No chown on the workspace filesystem** (btrfs subvolume behind
   an overlay, `nouserxattr`; chown returns EPERM from this user
   namespace even with CAP_CHOWN). Fallback shipped: the launcher
   widens modes (`a+rwX`) on the per-run scratch dirs only, with
   git's `safe.directory=*` plumbed through the environment. The
   per-run worktree is therefore world-writable *inside this
   runtime's user namespace* for the run's lifetime; cleanup deletes
   it. On a chown-capable filesystem, restore the chown.
2. **The skill tree is staged, not bound**: its files carry a group
   id unmapped in this user namespace, so the payload uid can never
   satisfy group permissions on a bind. `inner.sh` stages a tmpfs
   snapshot (size-capped, remounted read-only, Landlock ro rule on
   top). The sandbox sees the tree as of run start — a behaviour
   difference from the pilot's live bind, recorded as such.
3. Setup (`inner.sh`, fetch phase) still runs as namespace-root;
   only the payload is gated — by design, since the gate must be
   built before it can be enforced.

## Component 2 — gVisor / runsc (opt-in boundary)

For the highest-risk runs of the same lane type: the user-space
kernel removes the workload's direct shared-kernel exposure, which
is precisely the composite's largest residual. Wired into
`sandbox-run` as `exec-runsc` / `probe-runsc`, **default off**; the
launcher enforces the pin at runtime (refuses unless
`runsc --version` equals the pin).

### Pin and verification (before first execution)

| Item | Value |
|---|---|
| Release pin | **release-20261109.0** |
| Artifact | `gvisor.tar.bz2`, 84,532,987 bytes, from `https://storage.googleapis.com/gvisor/releases/release/20261109.0/x86_64/` |
| SHA-512 (artifact) | `1a6b8f74c37b4931ef473f67ec1f601690855bedc52ac709f2fac965c69677aa0426ef44598d8eee1aed72cfdb9df87a2a5f352cb3348880fc61a7732bc10f2a` |
| SHA-256 (artifact) | `0846228061b05eb936a96ed2ea205cbd8ddf6936c946f8a390b699cff3b5c138` |
| `runsc` binary SHA-256 | `c58f1dc2a3855487bf3bedc2edf074123ad433f1d98fb7f451f56790e87b5c9f` |

Verification followed upstream's published method: the artifact and
its `.sha512` sidecar were downloaded and `sha512sum -c` returned OK
**before extraction and before any execution**. Second channel: the
GitHub release `SHA512SUMS` entry for the same artifact is the
identical SHA-512. The `.tar.bz2` variant was chosen because `zstd`
is not installed on this runtime (upstream's install doc names the
`.bz2` for exactly that case). No system install: no `runsc install`,
no container-runtime registration; `runsc` runs from
`~/workspace/gvisor/bin/` against per-run OCI bundles.

### Posture and smoke-test evidence

- Platform pinned to **systrap** (`--platform=systrap`); the KVM
  platform is impossible here (no `/dev/kvm`) and systrap is
  upstream's recommended platform inside a VM.
- `--network=none`; the same env allowlist as the composite;
  `--ignore-cgroups` is **mandatory** on this runtime — without it
  every start fails in cgroup setup, the same controller-less
  delegation as the standing warning.
- Smoke gate **PASSED** on the pilot workload: 935 tests OK under
  runsc; inspection output byte-identical to the host baseline;
  criterion-1 probes 24/24 under the runsc boundary; zero payload
  syscall/ABI failures.
- **Overhead: ≈ +72% internal time** vs a same-window host baseline
  (68.3 s vs 39.6 s on the unittest suite). The tax is
  workload-shaped: re-measure before pointing a build-heavy lane at
  this boundary.
- The hog test under runsc allocated the full 1,536 MiB:
  **gVisor enforces no memory cap here either** (see the standing
  warning). Its contribution is the kernel boundary, not limits.
- Frictions recorded: bind-mount writes need the same `a+rwX`
  scratch widening as the composite (gofer uid mapping); a transient
  pre-start gofer creation failure (2 of 13 starts, always
  fail-closed) is retried at most 3 times by the launcher, for that
  exact failure only — retried, not root-caused.

## Component 3 — nsjail profile

An additional profile for the same lane type, carrying namespaces +
Kafel seccomp + rlimits/time limits in one config. Sibling launcher
`sandbox-run-nsjail` (same fail-closed contract; chosen over a flag
on `sandbox-run` because the rank-1 and rank-2 lanes were editing
that file in parallel — zero contention risk).

### Route and pin

- **Build route: Homebrew.** The owner first authorized an `apt`
  install of the build packages, then superseded that ruling with
  the Homebrew route before any install ran. **The apt authorization
  went unused — no system packages were installed by any route.**
  The only system-level change in this adoption is one unprivileged
  user (`linuxbrew`, uid 1000) owning `/home/linuxbrew/.linuxbrew`;
  Homebrew **7.0.13-132-gcbd3ae6**, invoked only as that user
  (brew refuses to run as root; this shell is uid 0).
- Dependencies, all poured from x86_64-linux bottles: protobuf
  **36.2**, libnl **3.12.0**, flex **2.6.11**, bison **3.8.2**,
  autoconf **2.73**, automake **1.20**, libtool **2.6.2**, pkgconf
  **3.0.10**. nsjail itself has no Homebrew formula; it builds from
  the pinned source, wired via `PATH`, `PKG_CONFIG_PATH`, and an
  `LDFLAGS` rpath into the brew prefix (build record in the local
  ADOPTION.md).
- Source pin: `https://github.com/google/nsjail`, tag **3.6** =
  commit `f78475530b46d0186111a9096b30725f816b55fe`; Kafel submodule
  at `76d0f41bf3eb5c4008713d64b9767b461a9129a3`.
- Built binary: SHA256
  `52a8cf999849b3e47dac089fe6227942980aeb7faf003ce05d9591dc843e285d`,
  RUNPATH `/home/linuxbrew/.linuxbrew/lib`. Residual: a future
  `brew upgrade`/cleanup of protobuf/abseil/libnl can break the
  binary until relinked; the Cellar versions above are the
  reproduction record.

### Profile posture and probe evidence

Profile template: `nsjail/eval-lane.cfg.tmpl` (SHA256
`ed4204a87ed53e0cc6f478b298dce30e94f362bd6609c2473c7a0690fad99f04`),
rendered per run. Posture mirrors the composite: fresh worktree rw
at `/work`, skills ro at `/skills`, outputs rw at `/out`, host home
occluded by tmpfs overlays, `/etc` never bound wholesale (only
`ld.so.cache`, `passwd`, `group`), **no network in the run phase**
(`clone_newnet`, no loopback), six-variable env allowlist plus a
scrubbed launcher environment, `time_limit` 600 s, rlimits
(AS 4096 MiB default, core 0, fsize 1024 MiB, nofile/nproc 1024).

- Criterion-1 battery: **24/24 PASS** (sensitive paths absent, env
  exactly the allowlist, one visible PID, no egress).
- Kafel seccomp proof: **PASS** — `ptrace` and `mount` return EPERM.
  Measured Kafel facts that shaped the profile: `DENY` compiles to
  `SECCOMP_RET_KILL` (the payload dies with SIGSYS) — the EPERM
  action is spelled `ERRNO(1)`; this Kafel build's syscall table
  has no `umount2` identifier, so the denylist carries `mount` only.
- Time-limit proof: **PASS** (payload killed at the limit, 3 s test).
- Rlimit proof: **PASS** — the hog stopped at 992 MiB under a
  1024 MiB `rlimit_as` ("RLIMIT FIRED"). Note the contrast: the
  rlimit family is a *working* memory bound in this profile.
- Workload: **PASS** — 935 tests OK inside the profile.
- Launcher fail-closed: **PASS** (missing binary → exit 64, payload
  never ran).

### Residual — `clone_newuser: false`

Forced by the substrate, recorded: mounting procfs inside a nested
user namespace is refused on this runtime (measured), and nsjail's
default `clone_newuser: true` dies at the `/proc` mount. The payload
therefore runs as **uid 0 in the runtime user namespace** —
confinement rests on the mount/pid/net namespaces, the tmpfs
occlusion, seccomp, and rlimits, with no uid-mapping layer.
(Pilot Stage-1 parity; the rank-1 composite's gate *does* drop uid,
which is one reason the composite remains the default.) Cgroup v2
is **off** in the default profile: armed, it cannot be enabled at
all here (standing warning); the `--cgroup-variant` honesty test
exists to re-prove that if the runtime changes.

## Component 4 — Incus: adopted-in-pattern, blocked on this runtime

The documented negative case. Feasibility was audited first-hand
(full record: `~/workspace/incus/FEASIBILITY.md`); **five
independent blockers, any one sufficient**, all properties of this
runtime's delegation rather than of configuration:

1. **Namespace root, not host root** — `uid_map 0 → 131072`, range
   65,536; Incus's privileged-daemon model presumes real host root.
2. **No CAP_NET_ADMIN / CAP_NET_RAW** — the managed bridge (and the
   network ACLs that are Incus's headline advantage) cannot be
   created; `dnsmasq` absent, `ip_forward = 0`.
3. **No cgroup controllers** — Incus lists cgroup support as
   mandatory; its daemon and project-aggregate limits would be
   accepted-and-unenforced here (the standing warning, one layer up).
4. **Idmap range impossible** — upstream requires a contiguous root
   subuid range ≥ 10M; `/etc/subuid` is empty and the entire
   identity range here is 65,536 uids.
5. **No within-authority install route** — upstream release assets
   carry the client only; the daemon ships via system packages or a
   source build whose prerequisites are themselves system packages.

The daemon-socket caveat, answered: on this runtime every lane runs
as the same uid 0, so socket-group discipline is void — anything
reaching the socket is already root, and restricted projects do not
bind a daemon admin. Incus would be protected *by* the rank-1
composite (never bind-mounting its socket), not protect anything
itself.

**Owner ruling (§7(a) of the feasibility record): Incus is accepted
as adopted-in-pattern, blocked on this runtime.** The on-a-real-host
adoption shape in that record (package install approved on that
host, verified subuid range, one restricted project with aggregate
limits, ACL'd bridge, probe battery + hog test inside a container,
socket never exposed to lanes) is the standing plan that activates
on a qualifying host. There is deliberately **no Incus step in
`install.sh`**.

## What enforces, and what does not (summary)

| Mechanism | Composite | gVisor mode | nsjail profile |
|---|---|---|---|
| Mount/pid/net confinement, host paths absent | Enforces | Enforces | Enforces |
| Env allowlist / credential scrub | Enforces | Enforces | Enforces |
| Landlock ruleset / uid 65534 drop | Enforces | n/a (sentry boundary instead) | Not applied (uid-0 residual) |
| Seccomp denylist | Enforces (51, EPERM) | Sentry's own | Enforces (Kafel, EPERM form) |
| Wall-clock / `time_limit` | Enforces | Enforces | Enforces |
| Rlimits | — | — | Enforce (AS proven) |
| **Cgroup memory/CPU caps** | **Do not enforce** | **Do not enforce** | **Cannot be armed** |
| Shared-kernel exposure | Residual (narrowed) | **Removed for the workload** (sentry remains on the host kernel) | Residual |

## Accepted residuals (cross-component)

- **Shared kernel** for the namespace mechanisms (composite,
  nsjail). gVisor removes it for the workload; the sentry itself
  still runs on this kernel.
- **No resource ceilings** on this runtime (standing warning).
  Wall-clock timeout is the only universal resource control.
- **Judgment lives host-side.** The boundaries confine *execution*,
  not persuasion: an orchestrator acting on malicious repo *content*
  (READMEs, comments) host-side is outside every component here.
- **The fetch step is host-side.** The clone executes no target code
  and is protocol-restricted, but it is the one moment
  target-controlled data touches the host outside a boundary.
- **Landlock mask currency** (ABI 5 types handled; runtime ABI 8)
  and **denylist-not-allowlist** posture, as recorded for
  component 1.
- **Build-from-source audit surface** for nsjail + Kafel (the
  survey's stated cost for rank 3); the pin and this record are the
  controls.

## Wrapper skills

None. This instance adds no skills: the policies are carried by the
launchers, this record, and the playbook entry, and the lane type is
invoked deliberately per evaluation rather than wrapped. (Pattern
step 5 applies when a tool needs per-lane judgement encoded; here
the judgement is the owner's per-lane direction.)

## Current state

All three runnable components are installed and proven on the origin
runtime through their launchers; Incus is closed as
adopted-in-pattern. `install.sh` reproduces the stack on a fresh VM
of this runtime class and fails loudly where the substrate does not
match the assumptions recorded here — most importantly, it prints
the criterion-2 warning whenever the cgroup-controller delegation
is absent.
