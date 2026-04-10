---
name: post-edit-diagnostics
description: >-
  Clears editor red/yellow squiggles after code changes by reading IDE diagnostics
  and running lightweight Python checks (compileall, imports). Use after modifying
  any Python or config files in this repo, when the user asks for a diagnostic pass,
  lint check, or to fix Problems panel issues.
---

# Post-edit diagnostics (nocode)

## When to apply

Run this workflow **after every batch of edits** that touches project source or tooling, unless the user explicitly says to skip checks.

## Steps (in order)

1. **IDE diagnostics (primary)**  
   Call `read_lints` on the paths you edited (files or folders). This mirrors what the user sees as red/yellow underlines in Cursor (Pylance, Ruff extension, etc.).

2. **Fix issues**  
   - Resolve **errors** before **warnings**.  
   - Prefer the smallest change that matches existing style in the file.  
   - Do not silence problems with broad `except` or `# type: ignore` unless unavoidable; if used, one line and a short reason.

3. **CLI sanity checks (from repo root)**  
   Run:

   ```bash
   uv run python -m compileall -q src
   ```

   If you changed imports or package layout, verify imports still work, e.g.:

   ```bash
   uv run python -c "import nocode"
   ```

4. **Re-check**  
   Run `read_lints` again on the same paths. Repeat fix → read_lints until clean or until remaining items are clearly environmental (missing optional dependency, stubs-only, interpreter mismatch)—then state that briefly for the user.

5. **If project adds tools later**  
   If `pyproject.toml` gains `[tool.ruff]`, `[tool.pytest.ini_options]`, or CI documents a single check command, run that command as part of step 3 and treat its output like lints.

## Constraints (this repo)

- Use **`uv run`** so checks use the project environment.  
- Stay **cross-platform**: `pathlib`, UTF-8, no Unix-only paths in fixes.  
- Do not expand scope beyond fixing diagnostics for the changed work unless the user asked.

## Done criteria

- `read_lints` shows no new problems on edited paths (or only documented externals).  
- `compileall` passes for `src`.
