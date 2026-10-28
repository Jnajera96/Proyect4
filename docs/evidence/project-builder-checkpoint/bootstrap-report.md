# Offline Git project bootstrap

Implemented POST /projects `create_if_missing: StrictBool = False` and explicit Nuevo proyecto Git modes in both project forms. Creation authorizes an absolute local empty directory, README.md, Git initialization and an initial HEAD. Existing registration sends false and retains its prior behavior. Successful responses select the project through the existing App setProjectId hook. Project/ProjectRequest and endpoint metadata are exported in frontend/contracts.json.

Safety: validates authorized roots and private profile, worktree, state database parent, log, cache and STT roots before any mkdir; rejects URL/relative/UNC/traversal and symlink/reparse ancestors. Parent must already exist. Missing Git fails before creating anything. Directory claim prevents concurrent creations sharing the path. Existing nonempty folders (including Git repos) are untouched. Git has a whitelist environment, disabled global/system configuration and templates/hooks, command-local identity, no shell/stdin interaction, 30-second timeout per command. Failed Git leaves partial output for inspection and only removes its own empty claim. No global config, dependencies, remote, paid calls, commits to the working repository, or sweeping deletion.

Validation:
- `.venv/Scripts/python.exe -m pytest tests/test_project_bootstrap.py tests/test_f10_api.py -q`: passed, with one real symlink privilege skip on Windows. Deterministic reparse test passes.
- New bootstrap suite covers initial HEAD/README for new and empty folders, existing registration compatibility, nonempty preservation, invalid/unauthorized/private paths, cookie/CSRF and per-profile registry isolation, reparse ancestor, concurrent claim, clean Git environment, partial failure retention, missing Git, strict JSON boolean consent.
- Ruff check helper/contracts/tests passed.
- Frontend `npm run build`: passed; `npm test`: 32 passed.
- `node tools/verify_project_bootstrap.cjs`: 6 Chromium checks passed; `_tmp/project-bootstrap-browser/report.json` and screenshot.

Limitations: parent directories are deliberately not auto-created. Authorization is rechecked after acquiring the directory claim; hostile external filesystem mutation is not an OS-level sandbox. Real symlink creation was unavailable under Windows privileges, so deterministic reparse validation supplements the skipped real symlink case.

Owned files: src/ai_swe/projects.py; project route in src/ai_swe/api/app.py; ProjectRequest in src/ai_swe/contracts/api.py; frontend/src/{App.tsx,components/Compositor.tsx,views/VistaProyectos.tsx,lib/api.ts,lib/contracts.ts}; frontend/contracts.json; tools/export_contracts.py; tools/verify_project_bootstrap.cjs; tests/test_project_bootstrap.py.

Final safety edge: any .git path component is rejected case-insensitively before mkdir/Git. Targeted git_metadata tests: 2 passed, proving existing HEAD/refs unchanged and zero Git calls for .git and .GiT components. Helper/test Ruff passes. Scope frozen again.

Windows alias hardening: rejects .git components after trimming trailing dots/spaces (and checks resolved components). Rejects any nonanchor component with trailing dots/spaces or colons (ADS) before mutation. Targeted metadata/ambiguous component checks: 7 passed; Ruff passes. Ordinary .gitignore names remain accepted by the guard. Frozen.
