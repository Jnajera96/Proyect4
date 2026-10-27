# Productization v0.1.0 Implementation Plan

> **For agentic workers:** Execute inline against the approved user specification;
> use verification-before-completion and tests for each implementation checkpoint.

**Goal:** Convert the frozen local candidate into a reproducible Windows local product.
**Architecture:** External Model Lab recommends configuration to the existing gateway;
the installed FastAPI/React runtime does not import Jupyter or require cloud notebooks.
**Tech Stack:** Existing Python/Pydantic/httpx/LangGraph, React/Vite; optional lab GPU
dependencies; later PyInstaller onedir and a Windows installer.

## Global constraints

- No push or remote configuration. Preserve delivery-rc1 at 2d35a59.
- Branch productization/v0.1.0; small local commits with tests and evidence.
- Never serialize tokens; secret input belongs in external environment or ignored .env.
- No quota-consuming inference until credential and economic authorization gates pass.
- Offline suite remains independent of credentials, Jupyter, GPUs and remote providers.
- No MCP, Graphify, Knowledge Graph, Langfuse, TTS, production/multiuser/TD-02 work.
- Continue D through J automatically except at indispensable human gates.

## D — External model laboratory

- [x] Verify baseline, tag and branch; inspect existing adapter and contracts.
- [x] Read official HF discovery, routing, authentication, structured output, tools,
  usage, pricing and rate-limit documentation; record URLs in MODEL-LAB-REPORT.md.
- [ ] Create tools/model_lab_cases.py: actual TaskInterpretation, RunPlan,
  CodeProposal and ReviewVerdict cases with semantic checks, not only JSON validity.
- [ ] Create tests/test_model_lab.py first: discovery unknowns, live-only selection,
  quality gating, secret-free exports, budget reservation and gateway wire/error cases.
- [ ] Implement tools/model_lab.py: public dynamic discovery, bounded benchmarks,
  per-attempt metrics and explicit paid-call gate, deterministic evidence-based ranking.
- [ ] Create notebook notebooks/01_HF_AGENT_MODEL_LAB.ipynb with no stored outputs,
  reusable Python imports, remote mode and optional lazy cloud-GPU mode.
- [ ] Run discovery without inference; write var/model_lab_results.json with real
  metadata and empty measurements until actual inference is authorized and executed.
- [ ] Execute offline tests and full suite; inspect diff and notebook outputs for secrets.
- [ ] Immediately before first inference, check only whether HF_TOKEN is configured.
  Stop for missing credential; otherwise determine quota/cost and request a bounded
  grant if charges cannot be excluded. Never infer a free account balance from pricing.
- [ ] Execute bounded real benchmarks, select routing only from successful semantic
  trials, document live compatibility or demonstrated gap; commit completed D as
  feat(ai): add Hugging Face agent model laboratory.

## E — Progressive real routing

- [ ] Extend typed settings/registry and node gateway selection for Analyst, then
  Supervisor, Coder and Reviewer, using measured D recommendation. Researcher stays
  deterministic. Test each integration with MockTransport before real opt-in calls.
- [ ] Reuse and extend tests/test_model_gateway.py and real opt-in tests for valid/
  invalid/truncated JSON, timeout, 429, 5xx, auth and budget; no live tests by default.
- [ ] Run a real-model flow against a disposable repository, with both human gates,
  real tests and byte-verified promotion; document REAL-MODEL-VALIDATION.md.
- [ ] Commit feat(ai): enable validated real model routing only after evidence passes.

## F — Real speech

- [ ] Detect GPU/driver/VRAM and actually test CUDA availability. Inspect existing
  FasterWhisperAdapter; use lazy loading and CPU fallback where supported.
- [ ] Install declared voice extra locally; choose a small hardware-appropriate model
  and measure a real audio file before microphone. Downloads above ~2 GB require gate.
- [ ] At physical microphone permission/speech gate request the exact user action;
  verify editable transcript and explicit confirmation without automatic run creation.
- [ ] Record device/model/compute/audio and transcription duration in
  REAL-STT-VALIDATION.md; commit feat(voice): validate real local speech transcription.

## G — Installed product configuration

- [x] Separate data/log/cache/config under LOCALAPPDATA/AISWESystem, source assets in
  application bundle, secrets external; add focused path/settings regression tests.
- [x] Add explicit first-run provider-not-configured state without breaking local
  features. Commit feat(runtime): prepare Windows product configuration.

## H — Launcher and executable

- [x] Implement src/ai_swe/launcher.py: directory/config setup, port selection,
  loopback-only server, health wait, real URL opening, readable errors and shutdown.
- [x] Test port conflicts, missing assets, invalid configuration and startup failure.
- [x] Fresh frontend build; PyInstaller onedir spec with required assets/imports only.
- [x] Run bundled EXE smoke: health/frontend/DB/project/auth/run/shutdown. Document
  PACKAGING-REPORT.md; commit build(windows): add executable application packaging.

## I — Reduced environment and installer

- [x] Run bundle with reduced PATH, no development interpreter/Node/venv dependency.
- [ ] Detect available Sandbox/VM; configure only if possible without admin/reboot;
  otherwise stop at human gate. Verify persistence, promotion and clean restart there.
- [ ] After onedir passes, build user-friendly installer with shortcuts, no services;
  stop only for unavoidable UAC. Commit build(windows): add local installer and
  clean-machine validation after evidence supports that description.

## J — Final product release

- [ ] Run complete Python/frontend/browser/offline/real-model/real-STT/promotion/
  packaged/clean-machine matrix, preserving explicit omissions rather than false PASS.
- [ ] Write PRODUCT-v0.1.0.md, INSTALLATION-WINDOWS.md and
  KNOWN-LIMITATIONS-v0.1.0.md, update README/snapshot and coherent version 0.1.0.
- [ ] Only if the required matrix is green, create local v0.1.0 tag and report
  executable/installer locations, startup instructions and separate readiness verdicts.
