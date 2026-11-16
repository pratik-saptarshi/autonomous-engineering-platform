# PR #7 Remediation Implementation Plan: Direct API & Proxy Support Without API Key

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate and close the three open review findings on PR #7 (`docs-mcp-server`) by threading file-based `app.directApi` configuration through `areCredentialsAvailable` and `DocumentStore` initialization, completing required TSDoc documentation, updating the Ollama quick-start documentation in `README.md`, and validating the complete test suite.

**Architecture:** Extend `areCredentialsAvailable(provider, options?: { directApi?: boolean })` with an optional options object to allow callers like `DocumentStore` to supply file-based configuration without breaking existing call sites. Update `isOpenAiDirectApiOrProxyConfigured` and `createEmbeddingModel` to accept direct API configuration options and document all exported symbols with full TSDoc per AGENTS.md. Update `DocumentStore` to forward `this.config.app.directApi` to credential checks and model creation so vector search initializes properly from config files without environment variables.

**Tech Stack:** TypeScript 5.8, Node.js 22, Vitest 5.1.0, Biome, LangChain Community OpenAI Embeddings.

**Spec:** PR #7 review findings from Codex and Overseer panel comments:
- Codex Comment 1 (P2): Pass `app.directApi` through credential checks and client creation (`EmbeddingFactory.ts:60`)
- Codex Comment 2 (P2): Specify a local embedding model in the Ollama quick start (`README.md:49`)
- Codex Comment 3 (P1): Complete the exported helper's required TSDoc (`EmbeddingFactory.ts:47`)
- AGENTS.md: TSDoc requirements, Conventional Commits, `— Terminator3000-DarkCrouton` signature.

---

## Verified Ground Truth & Review Findings

| Thread ID | Location | Severity | Description | Current Status |
|---|---|---|---|---|
| `PRRT_kwDOVeogIc61eoup` | `src/store/embeddings/EmbeddingFactory.ts:60` | P2 | `app.directApi: true` in config file does not enable vector search because `areCredentialsAvailable` only checks `process.env`. | **RESOLVED** (`c88e7c6`) |
| `PRRT_kwDOVeogIc61eour` | `README.md:49` | P2 | Ollama quick start in `README.md` omits `DOCS_MCP_EMBEDDING_MODEL` and `ollama pull` prerequisite, causing failure against default `text-embedding-3-small`. | **RESOLVED** (`c88e7c6`) |
| `PRRT_kwDOVeogIc61eouw` | `src/store/embeddings/EmbeddingFactory.ts:47` | P1 | Exported helper `isOpenAiDirectApiOrProxyConfigured` lacks `@param` and `@returns` TSDoc tags required by AGENTS.md. | **RESOLVED** (`c88e7c6`) |
| `PRRT_kwDOVeogIc61gIw_` | `src/utils/config.ts:568` | P2 | Register `--direct-api` option with CLI parser so `docs-mcp-server --direct-api` does not fail strict parsing. | **RESOLVED** (`59849fd`) |

---

## Multi-Lens Evaluation Summary

### 1. `receiving-code-review` (Technical Verification)
- **Finding 1:** In `DocumentStore.ts:709, 797, 889`, `areCredentialsAvailable(config.provider)` is called with no configuration. If `process.env.OPENAI_API_KEY` is unset, it returns `false`, aborting vector search.
- **Finding 2:** `README.md` recommends `OPENAI_BASE_URL="http://localhost:11434/v1"` without specifying a model. Since default is `text-embedding-3-small`, Ollama returns 404 because it only hosts pulled models like `nomic-embed-text`.
- **Finding 3:** `isOpenAiDirectApiOrProxyConfigured` in `EmbeddingFactory.ts` has summary doc but lacks `@param` and `@returns`.

### 2. `paperthin` (`factchk`, `hate`, `modelchk`)
- **`factchk`:** Verifying backward compatibility: `options?: { directApi?: boolean }` on `areCredentialsAvailable` is purely additive. All existing calls passing only `provider` continue working identically.
- **`hate`:** What if `app.directApi: true` is enabled without a custom base URL? LangChain client gets placeholder key `"direct-api-proxy"` and fails on OpenAI auth with 401 instead of crashing inside the client constructor. This is fail-closed behavior.
- **`modelchk`:** Sized as `standard` / `thorough` for TypeScript API contract and config propagation.

### 3. `overseer` Panel Synthesis
- Incorporate all 4 criteria identified in the panel comment: Correctness, Architecture, Security, and Documentation.

---

## Global Constraints

- Run on Node 22 ABI.
- Run `npm run lint`, `npm run typecheck`, and `npm test` before pushing.
- No `any` without strict necessity, no non-null assertions (`!`).
- Every exported function and class has TSDoc: summary, `@param`, and `@returns`.
- Conventional Commits: `<type>(<scope>): <subject>`.
- Sign all PR replies and comments as `— Terminator3000-DarkCrouton`.

---

### Task 1: Complete TSDoc on `isOpenAiDirectApiOrProxyConfigured`

**Files:**
- Modify: `src/store/embeddings/EmbeddingFactory.ts:40-60`
- Test: `src/store/embeddings/EmbeddingFactory.test.ts`

**Interfaces:**
- Produces: Exported `isOpenAiDirectApiOrProxyConfigured` with full TSDoc tags.

- [ ] **Step 1: Write/verify TSDoc specification**
  Add summary, `@param runtimeConfig`, and `@returns` documentation to `isOpenAiDirectApiOrProxyConfigured`.

- [ ] **Step 2: Implement TSDoc update in `src/store/embeddings/EmbeddingFactory.ts`**
  ```ts
  /**
   * Checks whether an OpenAI proxy or direct API is configured in the environment or runtime configuration,
   * allowing requests to be routed without requiring a real OPENAI_API_KEY.
   *
   * @param runtimeConfig - Optional configuration object that may specify `directApi`.
   * @returns `true` if an OpenAI base URL or direct API flag is present in environment variables or configuration; otherwise `false`.
   */
  export function isOpenAiDirectApiOrProxyConfigured(
    runtimeConfig?: (AppConfig["embeddings"] & { directApi?: boolean }) | { directApi?: boolean },
  ): boolean
  ```

---

### Task 2: Thread `directApi` Through `areCredentialsAvailable` and `createEmbeddingModel`

**Files:**
- Modify: `src/store/embeddings/EmbeddingFactory.ts:60-175`
- Test: `src/store/embeddings/EmbeddingFactory.test.ts`

**Interfaces:**
- Produces: `areCredentialsAvailable(provider: EmbeddingProvider, options?: { directApi?: boolean }): boolean`
- Produces: `createEmbeddingModel(providerAndModel: string, runtime?: { requestTimeoutMs?: number; vectorDimension?: number; config?: AppConfig["embeddings"] & { directApi?: boolean }; directApi?: boolean }): Embeddings`

- [ ] **Step 1: Write failing unit tests in `src/store/embeddings/EmbeddingFactory.test.ts`**
  - Test `areCredentialsAvailable("openai", { directApi: true })` returns `true` when `process.env` is empty.
  - Test `createEmbeddingModel("openai:text-embedding-3-small", { vectorDimension: 1536, directApi: true })` instantiates without `OPENAI_API_KEY`.

- [ ] **Step 2: Run test to verify failure**
  Run: `npx vitest run src/store/embeddings/EmbeddingFactory.test.ts`
  Expected: FAIL (argument count / missing credentials).

- [ ] **Step 3: Implement signature and logic updates in `src/store/embeddings/EmbeddingFactory.ts`**
  - Update `areCredentialsAvailable`:
    ```ts
    export function areCredentialsAvailable(
      provider: EmbeddingProvider,
      options?: { directApi?: boolean },
    ): boolean {
      switch (provider) {
        case "openai":
          return !!process.env.OPENAI_API_KEY || isOpenAiDirectApiOrProxyConfigured(options);
        ...
    ```
  - Update `createEmbeddingModel` runtime parameter to include `directApi?: boolean`.

- [ ] **Step 4: Run test to verify passes**
  Run: `npx vitest run src/store/embeddings/EmbeddingFactory.test.ts`
  Expected: PASS.

---

### Task 3: Forward `app.directApi` from `DocumentStore`

**Files:**
- Modify: `src/store/DocumentStore.ts:705-725, 795-815, 840-860, 885-905`
- Test: `src/store/DocumentStore.test.ts`

**Interfaces:**
- Consumes: `areCredentialsAvailable(provider, options)`, `createEmbeddingModel(modelSpec, runtime)`
- Produces: Vector search enabled when `config.app.directApi: true` even without env credentials.

- [ ] **Step 1: Write failing integration test in `src/store/DocumentStore.test.ts`**
  Test initializing `DocumentStore` with `app.directApi: true` and no `OPENAI_API_KEY`, verifying `isVectorSearchEnabled` is `true`.

- [ ] **Step 2: Run test to verify failure**
  Expected: FAIL (`isVectorSearchEnabled` is false because credentials check skipped).

- [ ] **Step 3: Update `DocumentStore.ts` call sites**
  - In `checkEmbeddingModelChange()`: pass `{ directApi: this.config.app.directApi }` to `areCredentialsAvailable`.
  - In `initializeEmbeddings()`: pass `{ directApi: this.config.app.directApi }` to `areCredentialsAvailable`.
  - In `detectEmbeddingDimension()` / `validateAndSyncDimensions()`: pass `{ directApi: this.config.app.directApi }` to `areCredentialsAvailable`.
  - In `createEmbeddingClient()`: pass `directApi: this.config.app.directApi` to `createEmbeddingModel`.

- [ ] **Step 4: Run test to verify passes**
  Run: `npx vitest run src/store/DocumentStore.test.ts`
  Expected: PASS.

---

### Task 4: Update Ollama Quick Start in `README.md`

**Files:**
- Modify: `README.md:45-55`

**Interfaces:**
- Documentation for quick-start users.

- [ ] **Step 1: Update README.md quick start snippet**
  Specify `DOCS_MCP_EMBEDDING_MODEL="nomic-embed-text:latest"` and note to run `ollama pull nomic-embed-text` first:
  ```bash
  OPENAI_BASE_URL="http://localhost:11434/v1" \
  DOCS_MCP_EMBEDDING_MODEL="nomic-embed-text:latest" \
  npx @arabold/docs-mcp-server@latest
  ```

---

### Task 5: Full Verification & Validation

**Files:**
- All touched files.

- [ ] **Step 1: Run linter**
  Run: `npm run lint`
  Expected: Clean, no errors or warnings.

- [ ] **Step 2: Run typecheck**
  Run: `npm run typecheck`
  Expected: Clean, exit code 0.

- [ ] **Step 3: Run unit and integration tests**
  Run: `npm test`
  Expected: All passing.

---

### Task 6: Commit, Push, and Resolve Review Threads

**Files:**
- Git repository.

- [ ] **Step 1: Commit with Conventional Commit message**
  `fix(embeddings): forward directApi through credential checks and document Ollama model`

- [ ] **Step 2: Push to `feat/direct-api-proxy-support`**

- [ ] **Step 3: Reply to and resolve the 3 GitHub review threads**
  End every reply with: `— Terminator3000-DarkCrouton`.

---
