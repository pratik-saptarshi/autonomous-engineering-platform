# Integration Patterns Across T3 Code, Herdr, and Orca (v1.2)

**Status:** Immutable Versioned Architecture Artifact · **Version:** v1.2 · **Date:** 2026-11-09  
**Repository:** `autonomous-engineering-platform` · **Branch:** `docs/dual-lane-governance-proposal`  
**PR:** #133 · **Companion Docs:** `aep-architecture-diagrams-v1.2.html`, `aep-hld-v1.2.html`, `aep-lld-v1.2.html`

---

## 1. Executive Overview & The Triad

The Autonomous Engineering Platform (AEP) substrate operates inside a host virtualization boundary (e.g. macOS Apple Silicon `vz` or Linux `cgroups v2`). Above and alongside this substrate, the developer experience and autonomous agent execution are governed by three complementary host systems:

1. **T3 Code (Developer Harness & Orchestration Control Plane):**
   - The primary AI-assisted coding environment, top-level thread orchestrator (`t3_thread_launch`, `create_threads`, `delegate_task`), and preview server (`preview_*`, `html_render`, `html_preview`).
   - Manages isolated Git worktrees via `workspaceStrategy: "worktree"` and links completed branches to GitHub pull requests (`link_pull_request`, `watch_pull_request`).

2. **Herdr (GPUI Agent Workspace & Terminal Multiplexer):**
   - A GPU-accelerated desktop application built on `gpui-kit` managing parallel agent terminal panes, editor layouts, and operator attention.
   - Watches worktree folders (`watchFolder`) for instant filesystem events via `virtiofs`, raises notifications/toasts (`notify`) when human-in-the-loop decisions are required, and maintains reactive shared mod state (`shared`, `setShared`).

3. **Orca (Agent Lifecycle, Telemetry & Supervision Protocol):**
   - A background protocol daemon (`com.stablyai.orca`) and plugin system (`orca-opencode-status.js`, `orca-agent-view.json`) governing agent execution state machines.
   - Formalizes turn lifecycles: `SessionStart` → `SessionBusy` → `SessionWaiting` (Permission / Form) → `SessionIdle` (or `SessionError`).
   - Relays agent prompts and streaming assistant messages, enforces zero-token leakage, tracks E2EE keypairs, and synchronizes status badges to Herdr and T3 Code.

---

## 2. Architecture Topology Diagram

```mermaid
flowchart TD
  %% Integration Patterns Across T3 Code, Herdr, and Orca (v1.2)

  subgraph HOST_DESKTOP["Host Developer Environment (macOS / Linux)"]
    subgraph T3_CODE["T3 Code (Harness & Orchestrator)"]
      T3_Thread["Thread Engine\n(Launch / Send / Read / Transfer)"]
      T3_Worktree["Worktree Strategy\n(Branch Isolation)"]
      T3_MCP["T3 MCP Server\n(Previews, Devices, PR Link)"]
      T3_Delegator["Delegate Task\n(Cross-Provider Routing)"]
    end

    subgraph HERDR["Herdr (GPUI Agent Multiplexer)"]
      Herdr_Core["Herdr Core Daemon\n(herdr.d.ts / IPC Socket)"]
      Herdr_UI["GPUI Terminal Panes\n(Multi-Agent Multiplexer)"]
      Herdr_Watcher["Folder Watcher\n(watchFolder API)"]
      Herdr_Toasts["Notification Toasts\n(User Attention Alerts)"]
    end

    subgraph ORCA["Orca (Agent Lifecycle & Supervision)"]
      Orca_Daemon["Orca Protocol Daemon\n(com.stablyai.orca)"]
      Orca_FSM["Session Lifecycle FSM\n(Start -> Busy -> Waiting -> Idle)"]
      Orca_TUI["Orca Status TUI\n(Real-Time Indicators)"]
      Orca_E2EE["Telemetry & E2EE Keys\n(Zero Token Leakage)"]
    end

    subgraph SUBSTRATE["AEP Substrate Core Services"]
      NS_Memory["NeuroStrata Cognitive Memory\n(ladybug.db / Vector / FTS)"]
      Beads_Ledger["Beads Issue Ledger\n(Single Source of Truth)"]
      GHG_Gateway["GHG GitHub Gateway\n(3,500 req/h Cap / Host Token)"]
      AEP_Supervisor["AEP Supervisor & Boot Gate\n(Preflight & Admission Control)"]
    end
  end

  subgraph VIRT_FILESYSTEM["Shared Filesystem & Relays (Virtiofs)"]
    Git_Worktrees["Git Worktree Storage\n(/repo/.worktrees/lane-*)"]
    Unix_Sockets["Supervisor Socket Relays\n(/run/aep/lanes/<laneId>/)"]
  end

  subgraph EXECUTION_TIERS["Dual-Lane Execution Substrate"]
    subgraph TIER1["Tier 1: Ralph-Loop Lanes (Fast Inner Loop)"]
      Ralph_Container["OCI Container (--network none)\nPrivate tmpfs / Read-Only rootfs"]
      Ralph_Agent["Agent Loop (TDD / Plan / Verify)\nHost Model via exec.sock"]
      Ralph_Verifier["aep verify Binary\nFull-stream Stdout/Stderr SHA-256"]
    end

    subgraph TIER2["Tier 2: ESF Factory Pipelines (Outer Factory)"]
      ESF_Temporal["Temporal Durable Workflow\n(esf-beads-<id>)"]
      ESF_Sandbox["Local-First Sandbox\n(Cube/KVM -> libkrun -> gVisor)"]
      ESF_Probe["In-VM EgressProbe\n(Measured Closed Boundary)"]
      ESF_Reverifier["Fresh Disposable Sandbox\n(MinIsolation Rule)"]
    end
  end

  %% Linkages
  T3_Worktree -->|"1. Allocates isolated branch"| Git_Worktrees
  Git_Worktrees -->|"2. Virtiofs event reflection"| Herdr_Watcher
  Herdr_Watcher -->|"3. Instant UI diff refresh"| Herdr_UI

  T3_Thread -->|"Spawns lane task"| AEP_Supervisor
  AEP_Supervisor -->|"Admits & provisions"| Ralph_Container
  AEP_Supervisor -->|"Dispatches factory task"| ESF_Temporal

  Ralph_Agent -->|"Lifecycle events"| Orca_FSM
  ESF_Temporal -->|"Pipeline status"| Orca_FSM
  Orca_FSM -->|"Broadcasts Waiting / Idle"| Orca_Daemon
  Orca_Daemon -->|"IPC socket relay"| Herdr_Core
  Herdr_Core -->|"Fires desktop toast"| Herdr_Toasts
  Herdr_Core -->|"Updates pane status badge"| Herdr_UI
  Orca_Daemon -->|"Syncs thread state"| T3_Thread

  Ralph_Container -->|"Zero direct network"| Unix_Sockets
  ESF_Sandbox -->|"Measured egress proxy"| Unix_Sockets
  Unix_Sockets -->|"Proxy GitHub calls (no token in lane)"| GHG_Gateway
  Unix_Sockets -->|"Memory retrieval / inscription"| NS_Memory

  Ralph_Verifier -->|"Ed25519 CommandReceipt"| Beads_Ledger
  ESF_Reverifier -->|"Verified patch digest"| Beads_Ledger
  Beads_Ledger -->|"Atomic settlement (bd close)"| NS_Memory
  Beads_Ledger -->|"Settled state trigger"| T3_MCP
  T3_MCP -->|"link_pull_request / PR review"| T3_Thread
```

---

## 3. Four Core Integration Patterns

### Pattern A: Workspace Multiplexing & Near-Zero-Latency File Reflection
- **Mechanism:** When a task begins, T3 Code allocates an isolated Git worktree under `.worktrees/lane-<id>`.
- **Virtiofs Bridging:** The worktree directory is mounted into the execution lane container or VM using `virtiofs`.
- **Herdr Event Handling:** Herdr's native folder watcher (`watchFolder`) receives inotify/FSEvents instantly across the mount, keeping terminal panes and diff trees updated in real time without polling loops.

### Pattern B: Agent Lifecycle State Machine & Human-in-the-Loop Supervision
- **FSM Synchronization:** As agents execute turns (via OpenCode, Claude Code, or Pi harnesses), the `orca-opencode-status` plugin captures transitions:
  - `SessionStart`: Clears prior run logs and establishes factory session identity.
  - `SessionBusy`: Active model inference and tool calling.
  - `SessionWaiting`: Raised when an agent encounters an interactive permission request, user prompt hook, or confirmation form.
  - `SessionIdle`: Normal turn completion.
  - `SessionError`: Handled failures, timeouts, or cancellations.
- **Herdr Attention Routing:** Orca emits waiting events over the local IPC domain socket (`/Users/neo/.config/herdr-app/herdr-app.sock`). Herdr intercepts the event, raises an interactive desktop notification toast (`notify`), and autofocuses the specific agent pane for operator response.

### Pattern C: Supervisor-Mediated Socket Relays (Zero Token Leakage)
- **Container Network Posture:** Both Ralph OCI lanes and ESF sandboxes execute with strict zero-egress policies (`--network none` or measured in-VM `EgressProbe`).
- **Secret Isolation:** Provider API keys (OpenAI, Anthropic, Gemini) and GitHub Personal Access Tokens (PATs) reside exclusively in host memory and the host `ghg` gateway.
- **Domain Sockets:** Containers communicate solely through host supervisor UNIX domain sockets mounted at `/run/aep/lanes/<laneId>/`:
  - `memory.sock` → Relays hybrid vector / FTS searches to NeuroStrata (`ladybug.db`).
  - `ghg.sock` → Proxies GitHub API requests under a hard 3,500 req/h budget.
  - `git.sock` → Commits verified changes using host SSH/GPG identities.
  - `exec.sock` → Relays tool execution commands from the host-hosted model harness.

### Pattern D: Verifiable Settlement & Ledger Synchronization
- **Receipt Generation:** All lane test executions run through the compiled static Go binary `aep verify`, capturing full-stream `StdoutSha` and `StderrSha` into an RFC 8785 canonical JSON receipt signed with Ed25519.
- **Single Source of Truth:** Beads (`bd list --limit 0`) acts as the single task ledger. Issues cannot close without verified receipt attachment.
- **Continuous Learning:** Upon issue closure (`bd close <issueId>`), root causes, fix diffs, and test failure patterns inscribe into NeuroStrata cognitive memory.
- **PR Linking:** T3 Code's MCP harness intercepts the closure, auto-generates or verifies the pull request, and registers it with `link_pull_request`.

---

## 4. Interaction Sequence Diagram

```mermaid
sequenceDiagram
  autonumber
  actor User as Developer / Operator
  participant T3 as T3 Code
  participant Herdr as Herdr Multiplexer
  participant Orca as Orca Daemon
  participant AEP as AEP Supervisor & Lanes
  participant Substrate as Substrate (Beads & Memory)

  User->>T3: Launch engineering task (Thread / Goal)
  T3->>T3: Allocate Git worktree (workspaceStrategy: "worktree")
  T3->>AEP: Dispatch task to Lane (Tier 1 Ralph or Tier 2 ESF)
  AEP->>Orca: Agent session started (SessionStart)
  Orca->>Herdr: Post status: Lane Busy (SessionBusy)
  Herdr->>Herdr: Render active spinner in agent pane

  rect rgb(240, 248, 255)
    note over AEP,Substrate: Execution inside --network none sandbox
    AEP->>AEP: Run agent loop & execute code changes
    AEP->>Substrate: Relayed tool/memory query via supervisor socket
    AEP->>T3: File writes reflected via virtiofs
    Herdr->>Herdr: watchFolder detects changes (instant UI reflection)
  end

  alt Agent requires operator input / approval
    AEP->>Orca: Form / permission requested
    Orca->>Orca: Transition FSM to SessionWaiting
    Orca->>Herdr: Broadcast waiting state over IPC socket
    Herdr->>User: Fire notification toast & focus agent pane
    User->>Herdr: Review diff & submit approval
    Herdr->>AEP: Pass input back via exec.sock
  end

  rect rgb(245, 243, 255)
    note over AEP,Substrate: Deterministic Verification & Settlement
    AEP->>AEP: Run aep verify (full StdoutSha / StderrSha)
    AEP->>AEP: Sign CommandReceipt with Ed25519
    AEP->>Substrate: Settle issue (bd close <id>) & inscribe NeuroStrata
  end

  AEP->>Orca: Session completed (SessionIdle)
  Orca->>Herdr: Update terminal badge to green checkmark
  Orca->>T3: Report thread turn completion
  T3->>T3: Call link_pull_request with verified branch PR
  T3->>User: Display completed task summary & rendered deliverables
```
