# Task 1 / K — Authenticated profiles

Status: K implementation plus round-1 isolation fixes complete; focused regression passed; ready for scoped re-review.
Base: 03e09c9. Worktree: C:/Users/jose_/.codex/worktrees/provider-preflight/proyecto4-ai-swe.
Scope: K plus profile-mode activation. L/M are intentionally deferred to their own tasks.
No external model calls, paid inference, push, tag, primary-checkout edits, trust/policy changes,
or reading/printing the primary .env were performed.

## Behavior

- `crear_app(..., settings: Settings | None = None)` retains legacy mode when disabled.
  With profile_mode true it returns the root authenticated dispatcher, with no shared RunStore.
- `AI_SWE_PROFILE_MODE=true`, launcher `--profiles`, and installed/frozen default activate profiles.
  `AI_SWE_PROFILES_ROOT` overrides the default `<state_db_path.parent>/users`.
- Each UUID owns identity.json, encrypted vault.json, state.sqlite3, logs/, worktrees/, cache/.
  Public `.names/<SHA256(normalized name)>` exclusive claims prevent concurrent duplicate names.
  No user-selected path or user_id field picks an application owner.
- NFKC/trim/casefold normalized names; 12–1024 character passwords; fixed stdlib Scrypt
  N=32768/r=8/p=1, 16-byte salt, 32-byte wrapping key, maxmem64MiB.
  Random256-bit DEK wrapped by AES256GCM; independent random12-byte nonces and version/owner/purpose AAD.
- Passwords/tokens are never returned in validation errors. Generic RequestValidationError
  handler avoids FastAPI/Pydantic input echo. Vault GET exposes only configuration allowlist
  and has_token boolean, never the token or encrypted/key material.
- HttpOnly SameSite=Strict opaque cookie with Max-Age; Secure on HTTPS (loopback HTTP supported).
  Session CSRF header required for writes; Origin and Sec-Fetch-Site checked, including login.
  JSON login/register; no cross-origin CORS allowance. Ten login/register attempts per IP/minute.
  Expiry reaper and logout revoke sessions, draining accepted work before closing a child.
- Direct ASGI child dispatch preserves streaming SSE and existing endpoints. Legacy headers
  cannot bypass the outer cookie boundary. Multiple sessions for a user share one user context.
- All per-profile model credentials/config explicitly replace inherited settings. ProfileSettings
  sources are init-only: no environment, dotenv, global API-key, HF token or Langfuse fallback.
- Profile log ContextVar filter prevents other handlers receiving the record. Worker submission
  copies context into executor threads. Legacy handler receives only legacy-context records.
- Internal profile directories, and any repository ancestor containing them, cannot be registered
  or used in RunOptions.repo_path. Existing source scope protections still apply.
- React ProfileRoot checks /auth/status before mounting App/private-data reads. Register/login,
  logout, vault token/config/budget form, session expiry, and truthful own-profile Session UI.
  Legacy selectors and API-key mode preserved. CSRF only in memory; cookie HttpOnly; SSE uses cookie.

## Public Python interfaces for L/M

`ai_swe.security.vault`:
- `seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes` returns nonce+ciphertext+tag.
- `open_sealed(key, envelope, aad) -> bytes`; authentication/format failure raises VaultError.
- `wrap_key(owner: str, password: str, key: bytes) -> dict` public version/owner/salt/wrapped_key header.
- `unwrap_key(owner, password, header) -> bytes` works on a new machine, no DPAPI dependency.
- `create_vault(owner,password,data) -> (envelope,DEK)`;
  `unlock_vault(owner,password,envelope) -> (DEK,data)`;
  `save_vault(owner,DEK,header,data) -> envelope` gives fresh nonce per save.
- VERSION=1. Vault JSON plaintext cap1MiB. Generic envelope cap256MiB+1MiB;
  M must enforce its own256MiB content budget. Use distinct authenticated AAD for backups.

`ai_swe.state.profiles`:
- `ProfileStore(users: Path).create(name,password)` / `.unlock(name,password)` -> UnlockedProfile.
- `UnlockedProfile.user_id`, `.name`, `.paths`, `.key` (DEK), `.header` (public wrapping header),
  `.data` (decrypted dict). Sensitive members excluded from dataclass repr.
- `.save(data)` atomically rewrites encrypted vault and updates in-memory data.
- `.settings(base: Settings) -> ProfileSettings`, init-only/environment-free, profile_id set.
- `UserPaths.for_user(users: Path,user_id: canonical UUID)` and `.prepare()`;
  properties root,database,logs,worktrees,cache,vault,identity. Rejects traversal and symlink paths.
- `atomic_json(path,data)` writes a unique temporary file and replaces atomically.

`ai_swe.api.profiles`:
- `create_profile_app(settings) -> FastAPI`;
  `root.state.profiles: ProfileManager`, `root.state.settings`.
- `manager.store: ProfileStore`; `manager.contexts[uid]: ProfileContext`;
  `manager.sessions[token]: Session`; `manager.lock: asyncio.Lock`.
- `ProfileContext.profile`, `.app`, `.lifetime`, `.requests` (active dispatched HTTP leases).
- `Session.token`, `.csrf`, `.user_id`, `.expires` (monotonic seconds, process-only).
- `manager.session(HTTPConnection) -> Session|None`; `async login(profile) -> Session`;
  `async open_context(profile)`, `close_context(uid)`, `prune()`, `shutdown()`.
  open/close_context are called while manager.lock is held; they do not acquire it themselves.
- Child `app.state.profile`, `.settings`, `.store`, `.engine`, `.worker`, `.ledger`.
  Register future continuity root endpoints before fallback mount('/'); authenticate + CSRF
  and acquire the manager lock/session again before mutations. Never export sessions.
- `RunWorker.active` reports queued/running accepted jobs; worker shutdown waits for completion.
  Check it and context.requests before replacing/exporting an app, but M must also inspect
  graph states/checkpoints for its stronger consistent-cut requirements.
- `runtime_logging.profile_log_context` tags own-profile operations; use/reset around any new
  background task that does not originate inside dispatched request context.

`ai_swe.state.budget_ledger`:
- `BudgetLedger(profile_database)` creates additive tables in that user's SQLite.
- `.set_limit(amount)` refuses a lower limit than consumed+reserved.
- `.reserve(run_id,amount,run_limit=...) -> reservation_id` is transactional.
- `.reserve_call(run_id,run_limit=...,estimate=...)` reserves all remaining allowance
  for that run before each adapter attempt. Retries do not escape reservations.
- `.settle(reservation_id,cost)` records declared actual cost; None retains reservation.
- `.summary()` returns limit,consumed,reserved,available. Currency restricted to USD in vault API.
- Profile ModelGateway constructs this ledger from Settings.profile_id/state_db_path.
  Every adapter invocation needs known tariff, explicit bounded output and run budget.
  UTF8 bytes+structural overhead provide the local input estimate. Missing usage or an
  ambiguous transport failure keeps allowance reserved, so subsequent calls fail closed.
  Costs above estimate are still recorded honestly and prevent further spending.

## HTTP API

- GET /auth/status: profile_mode,authenticated; own user{id,name},csrf_token when authenticated.
- POST /auth/register and /auth/login: JSON{name,password}; register201/login200 + cookie.
- POST /auth/logout: cookie + X-CSRF-Token; revoked200 and cookie deletion.
- GET /auth/vault: own safe config,has_token,ledger summary.
- PUT /auth/vault: cookie+CSRF. hf_token null preserves, empty clears. model_name,
  reviewer_model,model_provider(openai_compatible),model_base_url(HTTPS),remote_model_roles
  (coder/reviewer),model_pricing(JSON string),budget_limit,max_cost_per_run.
  Requires tariffs+token+positive budget before enabling remote roles. Returns saved/has_token.
  Busy child returns409; config validated before saving/rebuilding child.
- GET /health unauthenticated is only status/profile_mode for launcher readiness.
  Authenticated /health dispatches to user's normal child health and own counts.
- All existing private routes and SSE pass only to the session's child.

## Verification evidence

1. Initial tests failed at collection because security.vault did not exist (expected red phase).
2. Pinned cryptography==50.0.2 declared (already locked); local uv sync --extra dev --extra voice
   --extra packaging succeeded. Actual AESGCM/scrypt operations loaded/executed under current
   Windows environment without policy changes or custom launchers.
3. Focused `pytest tests/test_profiles.py -q`:13 passed, including wrong password/owner/tamper,
   traversal, global token fallback, atomic budget race, unknown usage retention, cookie flags,
   CSRF/origin/expiry/logout, login rate limit, safe422, separate SQLite/projects/runs/SSE,
   log filtering and worker propagation, internal-storage repo exclusion, cross-store uniqueness, and deterministic ledger connection closure on success/rollback.
4. Earlier full `pytest -q`: passed with exit0 (803 tests at collection,3 skips, no failures).
   Three added hardening tests thereafter passed in focused suite; exact-final-source full
   regression passed:803 passed,3 skipped in172.12s. The only subsequent backend source change
   was the explicit connection-lifetime cleanup, covered by the focused13-test run.
5. `npm --prefix frontend run build`: TypeScript+Vite passed.
6. `npm --prefix frontend test`:24/24 passed, rerun after final Session UI changes.
7. `python tools/verify_profiles.py`: Chromium against active profile API,7 milestones passed:
   no private pre-login fetch, registration, real run+cookie SSE, encrypted vault/no token echo,
   logout revocation, second-user isolation (including direct foreign run404), login restoration.
8. `python tools/verify_frontend.py --auth`: existing legacy real-browser24 checks passed.
9. Focused ruff check on new/modified security/worker/gateway/test/probe modules passed;
   git diff --check passed. Existing entire-repository lint debt not claimed fixed.

## Review notes and limits

- Source frozen for independent review before final commit. Report/docs may still update.
- Deterministic ledger connection cleanup was identified before reviewer dispatch and fixed with
  an explicit contextmanager (commit/rollback plus finally.close), authorized by parent. All13
  focused tests then passed, including connections closed on success and rollback. Final full
  regression was already in flight; no third full suite is required solely for this lifetime fix.
  Source frozen again after this cleanup; independent review uses the resulting commit.
- Isolation is API/profile-state separation inside one OS account, not defense against an admin
  or arbitrary code with that account's filesystem access. Repo/database plaintext remains as spec.
- Scrypt/AEAD do not recover lost passwords; no reset bypass. Python strings are not forensically
  erased. In-flight accepted work drains on logout; not immediate cancellation of provider calls.
- Ledger is a local conservative guard, not a third-party invoice guarantee. Unknown-cost
  reservations persist. Remote config changes can be refused while a request/SSE/job is active.
- Legacy user data is not migrated/assigned. Installed v0.2 package and L/M acceptance are pending
  parent tasks; this K report does not claim v0.2 release closure or a new distribution artifact.

## Final handoff

Full regression:803 passed,3 skipped. Focused profiles after connection cleanup:13 passed.
Source frozen. Commit identifier is supplied in the agent handoff (this report is part of it).


## Round 1 — focused isolation review fixes

Review base: ef73156; findings: task-1-review.md (two Important findings).
Both were reproduced by seven new failing regression cases before the source fix.

- Added invocation-local `bind_settings_node(node, settings)` using the existing
  ContextVar boundary. Workflow binds sandbox and test-runner nodes, as well as
  deterministic model nodes. Workspace root and allowed test targets now use the
  supplied child Settings. Profile settings override legacy global injection hooks;
  those hooks remain supported outside profile mode. Profile model roles are bound
  even when empty, so a legacy injected gateway/reviewer model cannot bleed across.
  Default gateway construction also consults the bound settings before global load.
- Inspected every load_settings read in graph nodes. Reviewer settings share the
  same bound configuration; promotion/finalize/abort continue using persisted paths
  and were not refactored.
- `FasterWhisperAdapter` accepts optional `use_auth_token: str | bool | None`.
  Profile factory explicitly passes False to Whisper, which forwards it to Hub.
  Speech downloads are deliberately anonymous for all profiles, even if the owner
  has a vault token for remote inference. No credential is implicitly repurposed.
  Legacy adapters retain None/omitted auth and their existing Hub resolution behavior.
  Production code never changes process environment variables.

Focused validation (no models downloaded, network/paid calls, frontend changes or full-suite rerun):

1. New `tests/test_profile_execution_isolation.py`: original 7 cases failed before
   the fix and passed after it. Final module, including 2 explicit legacy cases:
   9 passed. Real temporary Git worktrees for two profiles remain under each UUID;
   another authenticated profile gets403 for both project registration and run repo
   access. Different target allowlists reach the runner independently, with and
   without remote roles. Source repo remains unchanged. No Git config is modified.
2. Offline speech cases use installed faster_whisper.download_model and Hub header
   generation, replacing only model construction, snapshot I/O and the credential
   resolver with synthetic sentinels. Both fake environment and cached credentials
   are excluded; the implicit resolver is never called for profiles. Same boundary
   confirms legacy behavior still resolves the synthetic credential. Empty and
   nonempty owner vault tokens both retain anonymous speech; environment unchanged.
3. Focused selection: test_profile_execution_isolation, test_profiles,
   test_hybrid_routing, test_workflow, test_f7_sandbox, test_f8_test_runner,
   test_f9_reviewer, test_f13_stt, test_stt_settings, with real_stt/real_provider
   excluded:187 selected tests executed,186 passed,1 skipped, exit0. This selection
   included the original7 new cases; the final9-case module then passed separately.
   Final collection is189 selected plus1 real-STT deselected (two legacy cases added).
4. Ruff passes for model_routing.py, workflow.py and the new regression module.
   Existing nodes.py18 and stt/base.py1 lint findings were compared by code/message
   against git HEAD baseline and are identical; no unrelated lint cleanup.
5. Self-review and git diff --check completed. Changes are limited to the two review
   findings and their settings-isolation boundary. No L/M, SAC/trust/policy changes,
   push, source-repository destructive operations, or frontend rerun.

Interfaces for follow-on work are unchanged except the additive optional adapter
argument and internal invocation binder above. Prior full-suite evidence remains
historical evidence from before this focused correction, not a claimed rerun.
