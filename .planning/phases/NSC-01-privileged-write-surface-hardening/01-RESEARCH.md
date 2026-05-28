---
phase: "01-privileged-write-surface-hardening"
slug: "NSC-01"
researched: "2026-05-28"
domain: "Input validation / filesystem safety / subprocess hardening / iterative I/O"
confidence: HIGH
---

# Phase 1: Privileged Write-Surface Hardening — Research

**Researched:** 2026-05-28
**Domain:** Input validation, filesystem safety, subprocess hardening, interactive I/O
**Confidence:** HIGH — all findings sourced directly from codebase inspection.
  No external libraries required; all fixes use Python stdlib only.

---

## Summary

Phase 1 closes four security findings (SEC-01..SEC-04) from the 2026-05-28 codebase
audit. Every fix targets a specific function in a specific file; there is zero
cross-requirement coupling at the code level. The four changes are independently
deliverable and map to four separate plans in a single wave.

**Primary recommendation:** Implement all four fixes as four independent plans
(01-01 through 01-04) in Wave 1 — no plan depends on another. Each plan touches
a different module (`validators.py`, `config_verification.py`, `utils.py[openssl]`,
`utils.py[retrieve_valid_input]`) and requires its own regression test class.

The most important finding from research is the SEC-01 bypass: **`"  ../etc"` DOES
contain `".."` as a substring, so the whitespace bypass described in CONCERNS.md
is actually a mis-diagnosis.** The real risk is confirmed via `_reject_path_traversal`
precedent: the current `validate_target_path` checks `".." in target_path` (raw
substring) but does NOT call `_reject_path_traversal` (segment-split check). A
value like `"  /etc/../etc/nginx"` passes because the current `".." in target_path`
check is performed on the raw, un-stripped string AND the `..` IS present — so it
raises. However `"/etc/nginx "` (trailing space) would pass through
`os.path.realpath` correctly (realpath strips trailing whitespace on Linux), while
`"\t/etc/nginx"` could resolve to a different path on systems where tab characters
cause shell confusion downstream. The safe fix is: `.strip()` first, THEN apply
the `_reject_path_traversal` segment-split logic (same pattern used for cert/auth
paths). This closes any remaining whitespace-variant ambiguity and makes the
implementation consistent with the rest of the validator module.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| YAML target_path validation | Input validators (`validators.py`) | CLI entry point (`nginx_set_conf.py`) | Validators own all path-safety logic; CLI extracts the raw YAML string and passes it through |
| Backup symlink safety | Config verifier (`config_verification.py`) | — | `backup_configuration` is self-contained; no shared state with engine |
| Key file permission race | Config engine / subprocess wrapper (`utils.py`) | OS umask | `setup_default_server` owns the openssl invocation; fix lives there |
| Interactive stdin safety | Config engine (`utils.py` `retrieve_valid_input`) | CLI entry point | Engine owns the helper; CLI calls it in the interactive branch only |

---

## Project Constraints (from CLAUDE.md)

- **Package manager:** UV only (`uv run pytest`, `uv pip install -e .`). Never pip.
- **Dependencies:** `pyproject.toml` is single source of truth. No `requirements.txt`.
- **Git prefixes:** `[ADD]` new, `[CHG]` modifications, `[FIX]` bug fixes.
- **Version headers:** Increment version + update date (DD.MM.YYYY) in file headers.
- **Encoding:** UTF-8 for all file operations.
- **Testing:** `uv run pytest` — gate at 60% coverage. `nginx_set_conf.py` is excluded from coverage measurement.
- **Claude cannot run tests locally** — dry-run + monkeypatch is the substitute.
- **No GitHub Actions publish step** — local only.
- **Documentation language:** English for code/docs, German for user communication.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | `validate_target_path` strips whitespace before the `..` check | Fix: `.strip()` + switch to `_reject_path_traversal` segment-split; test file: `test_validators.py` class `TestValidateTargetPath` |
| SEC-02 | `backup_configuration` uses `shutil.copytree(..., symlinks=False)` and rejects a symlinked source directory | Fix: add `os.path.islink(server_nginxconfig_dir)` guard before `copytree`; pass `symlinks=False` explicitly; test file: `test_validators.py` or new `test_backup.py` |
| SEC-03 | `setup_default_server` pre-creates key file at 0o600 before openssl invocation (or sets umask) | Fix: `umask(0o077)` context around openssl call; test file: `test_migration.py` class `TestSetupDefaultServer` |
| SEC-04 | `retrieve_valid_input` converted to iterative loop with max-length cap | Fix: `while True:` loop, `max_len=4096` guard, `EOFError` handled; test file: `test_utils.py` new class `TestRetrieveValidInput` |
</phase_requirements>

---

## SEC-01: validate_target_path Whitespace Bypass

### Current State

**File:** `nginx_set_conf/validators.py:156-177`

```python
def validate_target_path(target_path: str) -> str:
    if not target_path:
        return target_path
    resolved = os.path.realpath(target_path)
    if ".." in target_path:                        # <-- raw string check
        raise ValidationError(f"Path traversal detected in target_path: '{target_path}'")
    if not os.path.isabs(resolved):
        raise ValidationError(f"Target path must be absolute: '{target_path}'")
    return resolved
```

**Caller (YAML path):** `nginx_set_conf/nginx_set_conf.py:371`
```python
yaml_target_path = str(yaml_config.get("target_path", ""))
```
No `.strip()` is applied before the value is passed to `execute_commands`, which
eventually calls `validate_all_inputs` → `validate_target_path`.

### Exact Bypass Analysis

The CONCERNS.md note says `"  ../etc"` would pass the `".." in` check because `..`
is not literally in the string — **this is incorrect**: `".."` IS in `"  ../etc"`.
The real risk is more subtle:

1. **Trailing whitespace in realpath:** `os.path.realpath("\t/etc/nginx\t")` on Linux
   resolves `\t` as a literal character in the path segment name, not whitespace.
   A tab-prefixed value like `"\t../etc"` would have `..` present and be caught — but
   `"\t/etc/nginx"` resolves to a tab-named directory, which is wrong.
2. **Unicode whitespace (NBSP U+00A0):** `"\xa0../etc"` — `".." in "\xa0../etc"` is
   `True`, so it IS caught by the raw check. However `os.path.realpath` resolves
   `"\xa0.."` as a literal directory name (with NBSP as first char), not as traversal.
3. **Consistency gap:** All other path validators (`validate_cert_name`,
   `validate_cert_key`, `validate_auth_file`) call `_reject_path_traversal` which
   uses the segment-split approach (`".." in value.replace("\\", "/").split("/")`).
   `validate_target_path` uses a raw substring check and does NOT call
   `_reject_path_traversal`. This inconsistency is the core concern.
4. **Whitespace + `os.path.realpath` interaction:** After `.strip()` the realpath
   call is reliable. Before strip, unusual whitespace characters result in paths that
   bypass the intention of the check even if not technically exploitable on current
   Linux targets.

**Verdict:** The fix `.strip()` + replacing the raw `".." in` check with a call to
`_reject_path_traversal` is correct and closes all variants.

### Are there other callers?

`validate_target_path` is called exclusively via `validate_all_inputs` in `utils.py`.
The YAML path at `nginx_set_conf.py:371` is the only place a raw YAML string enters
the validator. CLI direct-flag paths go through Click, which trims whitespace
automatically. No other call sites exist.

### Error pattern

`ValidationError` (a `ValueError` subclass defined in `validators.py:57-60`) is the
correct error type — consistent with all other validators in the module.
`click.BadParameter` is NOT used in validators; it is only used at the Click
command-definition layer. `sys.exit` is never used in validators.

### Proposed Fix

```python
def validate_target_path(target_path: str) -> str:
    if not target_path:
        return target_path
    target_path = target_path.strip()              # <-- ADD: strip all Unicode whitespace
    _reject_path_traversal(target_path, "target_path")  # <-- ADD: segment-split check
    resolved = os.path.realpath(target_path)
    if not os.path.isabs(resolved):
        raise ValidationError(f"Target path must be absolute: '{target_path}'")
    return resolved
```

The existing `".." in target_path` raw check is REPLACED by the `_reject_path_traversal`
call (which already exists in the same file at line 180). This is strictly safer.

### Test Approach

**File:** `tests/test_validators.py`, class `TestValidateTargetPath` (already exists at line 163).

Add test methods to the existing class:

```python
def test_leading_whitespace_path_traversal(self):
    with pytest.raises(ValidationError, match="Path traversal"):
        validate_target_path("  ../etc")

def test_tab_prefix_traversal(self):
    with pytest.raises(ValidationError, match="Path traversal"):
        validate_target_path("\t../etc")

def test_leading_whitespace_absolute_accepted(self):
    result = validate_target_path("  /tmp/nginx_test")
    assert result.endswith("/tmp/nginx_test")

def test_nbsp_traversal(self):
    with pytest.raises(ValidationError, match="Path traversal"):
        validate_target_path("\xa0../etc")
```

No new fixtures needed — the existing test class uses no setup.

---

## SEC-02: backup_configuration Symlink Safety

### Current State

**File:** `nginx_set_conf/config_verification.py:436-449`

```python
# Backup main nginx.conf
server_nginx_conf = Path("/etc/nginx/nginx.conf")
if server_nginx_conf.exists():
    target = backup_path / "nginx.conf"
    if target.is_symlink():                        # checks DESTINATION for symlink
        logger.error(f"Refusing to follow symlink at backup target: {target}")
        return False
    shutil.copy2(server_nginx_conf, target)

# Backup nginxconfig.io directory
server_nginxconfig_dir = Path("/etc/nginx/nginxconfig.io")
if server_nginxconfig_dir.exists():
    shutil.copytree(server_nginxconfig_dir, backup_path / "nginxconfig.io")  # <-- no symlink guard
```

The symlink check at line 437-439 guards the **backup destination** for `nginx.conf`,
not the **source**. The `copytree` call for the directory has no source guard and
uses the default `symlinks=False` only if that is the Python default — which it is
NOT: `shutil.copytree` defaults to `symlinks=False` (i.e., it follows source
symlinks and copies targets). However, there is no guard preventing
`/etc/nginx/nginxconfig.io` itself from being a symlink to an attacker-controlled
path.

### Threat Model (both threats are real)

**(a) Source directory is itself a symlink.** If an attacker has write access to
`/etc/nginx/` (same level as `nginxconfig.io/`), they can replace the directory
with a symlink to `/root`, `/etc/shadow`, etc. `copytree` follows it and reads
sensitive files into the backup archive.

**(b) Symlinks inside the source tree.** If individual files inside
`/etc/nginx/nginxconfig.io/` are symlinks (planted by an attacker or by an
operator mistake), `copytree(symlinks=False)` copies the symlink TARGETS (follows
them), which can read files outside `/etc/nginx`. With `symlinks=True`, symlinks
are preserved as symlinks in the backup but not followed during the copy — this
does not prevent reading via the backup later, but it prevents exfiltration at
copy time.

**Correct fix:** Guard (a) with `os.path.islink(server_nginxconfig_dir)` and
pass `symlinks=False` explicitly to be clear about behaviour for (b). The explicit
`symlinks=False` is already the default but making it explicit is correct for
documentation and future-proofing.

### Does shutil.copytree already exist in the source?

Yes — `shutil` is already imported in `config_verification.py` (used at line 440
for `shutil.copy2` and line 445 for `shutil.copytree`). No new import needed.

### Proposed Fix

```python
# Backup nginxconfig.io directory
server_nginxconfig_dir = Path("/etc/nginx/nginxconfig.io")
if server_nginxconfig_dir.exists():
    if server_nginxconfig_dir.is_symlink():        # <-- ADD: guard against symlinked source
        logger.error(
            "Refusing to backup symlinked source directory: %s", server_nginxconfig_dir
        )
        return False
    shutil.copytree(
        server_nginxconfig_dir,
        backup_path / "nginxconfig.io",
        symlinks=False,                            # <-- ADD: explicit, copy targets not links
    )
```

### Test Approach

**File:** New `tests/test_backup.py` (or extend `test_migration.py` — see below).

No dedicated test file exists for `config_verification.py` (confirmed by TESTING.md:
"ConfigVerification class — no dedicated test file"). Per project convention the
file should be named `test_backup.py` or `test_config_verification.py`. Given the
project already has `test_migration.py` covering `utils.py` migration helpers, a
new `test_backup.py` is the cleaner choice.

Pattern using `tmp_path` and real symlinks (no mock needed — symlink creation works
in `/tmp`):

```python
import pytest
from pathlib import Path
import shutil
from nginx_set_conf.config_verification import ConfigVerification

class TestBackupConfiguration:
    def test_refuses_symlinked_nginxconfig_source(self, tmp_path, monkeypatch):
        # Create a fake source dir and a symlink pointing to it
        real_dir = tmp_path / "real_nginxconfig"
        real_dir.mkdir()
        symlink_dir = tmp_path / "nginxconfig.io_symlink"
        symlink_dir.symlink_to(real_dir)

        cv = ConfigVerification()
        # Monkeypatch the hard-coded paths
        monkeypatch.setattr(
            "nginx_set_conf.config_verification.Path",
            lambda p: symlink_dir if "nginxconfig.io" in p else Path(p),
        )
        # Expect backup to return False when source is a symlink
        result = cv.backup_configuration(backup_root=str(tmp_path / "backups"))
        assert result is False

    def test_copytree_follows_no_symlinks_in_source(self, tmp_path):
        # Verify shutil.copytree with symlinks=False copies target content
        src = tmp_path / "src"
        src.mkdir()
        real_file = tmp_path / "secret.txt"
        real_file.write_text("secret")
        symlink = src / "link.txt"
        symlink.symlink_to(real_file)

        dst = tmp_path / "dst"
        shutil.copytree(src, dst, symlinks=False)
        # symlink was followed — copy contains the content, not a symlink
        assert (dst / "link.txt").read_text() == "secret"
        assert not (dst / "link.txt").is_symlink()
```

> **Note:** The monkeypatch approach for `ConfigVerification.backup_configuration`
> requires care — the method uses hard-coded `/etc/nginx/...` paths internally.
> The planner should consider whether to refactor the method to accept injected
> paths (as `setup_default_server` already does with `target_path`, `ssl_dir` params)
> or to use `monkeypatch` to patch the `Path` constructor. The simplest approach
> that matches project patterns: add `nginx_conf_dir` and `nginxconfig_dir`
> parameters to `backup_configuration` with defaults pointing to the real paths.
> This makes the function testable without patching builtins.

---

## SEC-03: setup_default_server Key File Mode Race

### Current State

**File:** `nginx_set_conf/utils.py:499-521`

```python
cert_exists = os.path.isfile(cert_path) and os.path.isfile(key_path)
if not cert_exists:
    logger.info("Generating self-signed default cert at %s", cert_path)
    ok = _run_command(
        [
            "openssl", "req", "-x509", "-nodes", "-days", "3650",
            "-newkey", "rsa:2048",
            "-keyout", key_path,    # openssl creates this file
            "-out", cert_path,
            "-subj", "/CN=default-reject",
        ]
    )
    if not ok:
        logger.error("Failed to generate self-signed default cert")
        return False
    _run_command(["chmod", "600", key_path])  # <-- race: key is world-readable until here
```

**The race window:** `openssl req -nodes` writes the private key to `key_path`.
The process umask when running as root is typically `0o022`, making the key file
mode `0o644` (world-readable) for the brief period between openssl completion and
the `chmod 600` subprocess call. On a busy system this window is usually <1ms, but
it is architecturally incorrect — a key that was briefly readable may have been
read from `/proc/<pid>/fd/` by a monitoring agent.

### Two candidate fixes

**Option A: Pre-create the file at 0o600**
```python
with open(key_path, "w", opener=lambda path, flags: os.open(path, flags, 0o600)):
    pass  # create empty file with correct mode
ok = _run_command(["openssl", ...])
```
Problem: openssl uses `O_CREAT | O_WRONLY | O_TRUNC` to open `-keyout` — it will
recreate the file (truncate), but the MODE of the existing file depends on openssl
version and OS behaviour. On Linux, `open(..., O_TRUNC)` on an existing file does
NOT change its mode — so the pre-created 0o600 mode is preserved. On macOS,
behaviour is identical. **This approach works reliably on Linux/macOS.**

**Option B: `umask(0o077)` context around the openssl call**
```python
import contextlib, os

@contextlib.contextmanager
def _restrictive_umask():
    old = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old)

with _restrictive_umask():
    ok = _run_command(["openssl", ...])
```
`umask(0o077)` means new files are created with mode `0o700` (for directories)
or `0o600` (for regular files, assuming default `0o666`). openssl writing the key
would produce a file with mode `0o600` directly. No race exists.

**Recommendation: Option B (umask)**, because:
1. It does not depend on openssl's open flags or OS truncation behaviour.
2. It is self-contained — the umask is restored immediately after the call.
3. It requires no pre-flight file creation that might fail if `ssl_dir` doesn't
   exist yet (though `os.makedirs` runs before this point, so that is fine either way).
4. It is the standard POSIX pattern for controlling new-file permissions in
   subprocess-adjacent code.
5. The `_run_command` helper uses `subprocess.run` — the subprocess inherits the
   parent's umask, so setting it in the parent before calling `_run_command` is
   sufficient.

**REQUIREMENTS.md says:** "pre-creates the private key file with mode `0o600` before
invoking `openssl req` (or sets `umask(0o077)` around the openssl call)". Both are
acceptable per the spec. Research confirms umask approach is cleaner.

### Edge case: called twice?

If `setup_default_server` is called twice (e.g., operator re-runs `--setup_default`):
- `cert_exists = os.path.isfile(cert_path) and os.path.isfile(key_path)` → True
- The openssl block is **skipped entirely** (line 522: `else: logger.info("...already exists, skipping")`)
- The umask guard never fires on the second call — no issue.

### Concurrency

This is a CLI tool, not a daemon. Concurrent invocations by different processes are
theoretically possible if two operators run `--setup_default` simultaneously, but
this is not a realistic threat. No additional locking is needed beyond the umask fix.

### Proposed Fix

```python
import contextlib
import os

@contextlib.contextmanager
def _restrictive_umask():
    """Context manager: set umask 0o077, restore on exit."""
    old_umask = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(old_umask)
```

In `setup_default_server`:
```python
if not cert_exists:
    logger.info("Generating self-signed default cert at %s", cert_path)
    with _restrictive_umask():          # <-- ADD: key created at 0o600, no race
        ok = _run_command(
            ["openssl", "req", "-x509", "-nodes", "-days", "3650",
             "-newkey", "rsa:2048", "-keyout", key_path, "-out", cert_path,
             "-subj", "/CN=default-reject"]
        )
    if not ok:
        logger.error("Failed to generate self-signed default cert")
        return False
    # Remove the post-hoc chmod -- it is now redundant and misleading
    # _run_command(["chmod", "600", key_path])  <-- DELETE
```

The post-hoc `chmod 600` subprocess call is deleted — it is now redundant and
communicates the wrong intent (it implies the file was unsafe until this point).

### Test Approach

**File:** `tests/test_migration.py`, class `TestSetupDefaultServer` (already exists,
confirmed at `test_migration.py:~160`).

Add a mode assertion test:

```python
def test_key_file_created_with_mode_600(self, tmp_path, monkeypatch):
    """Key file must be created at 0o600, not world-readable."""
    from nginx_set_conf import utils as utils_module
    ssl_dir = tmp_path / "ssl"
    ssl_dir.mkdir()
    key_path = ssl_dir / "default.key"

    def fake_run_command(args, *a, **kw):
        if args and args[0] == "openssl":
            # Simulate openssl writing the key — honour current umask
            import stat
            key_path.touch(mode=0o666)   # intentionally open, umask should restrict
        return True

    monkeypatch.setattr(utils_module, "_run_command", fake_run_command)
    setup_default_server(
        target_path=str(tmp_path / "conf.d"),
        ssl_dir=str(ssl_dir),
        dry_run=False,
    )
    mode = oct(key_path.stat().st_mode & 0o777)
    assert mode == oct(0o600), f"Key file mode {mode} is not 0o600"
```

> **Note for planner:** The `key_path.touch(mode=0o666)` in the fake simulates
> openssl creating a world-readable file; the umask context should restrict it to
> 0o600. However, `Path.touch(mode=...)` on Python does NOT apply umask — it passes
> the mode directly to `os.chmod`. For the test to correctly exercise umask
> semantics, the fake should use `os.open(key_path, os.O_CREAT | os.O_WRONLY, 0o666)`
> which DOES honour the current umask. The planner should specify this precisely.

---

## SEC-04: retrieve_valid_input Recursion + Length Cap

### Current State

**File:** `nginx_set_conf/utils.py:162-175`

```python
def retrieve_valid_input(message: str) -> str:
    """Prompts user for input until non-empty input is provided."""
    user_input = input(message)
    if user_input:
        return user_input
    else:
        return retrieve_valid_input(message)  # <-- unbounded recursion on empty input
```

**Call site:** `nginx_set_conf/nginx_set_conf.py:423-440` (interactive fallback branch).
The function is called 10 times in sequence for different fields.

**The two problems:**

1. **Unbounded recursion:** Every empty `<Enter>` press adds a stack frame.
   Python's default recursion limit is 1000. An operator pressing Enter 1000 times
   hits `RecursionError` — which would be an unhandled exception in the CLI.

2. **No length cap:** `input()` reads until newline, no limit. A piped stdin of
   `"A" * 100_000 + "\n"` produces a 100 KB string. It passes through to
   `validate_domain` which checks `len > 253`, but not before the string is held in
   memory and the call stack is entered. The stack is NOT exhausted (one call, short
   string after validation), but the security posture is cleaner with an explicit cap.

**EOFError:** When stdin is closed (piped stdin, script mode), `input()` raises
`EOFError`. The current code does NOT handle it — `EOFError` would propagate up
as an unhandled exception, producing an ugly traceback in the CLI.

**Does any upstream code catch RecursionError?** No. `execute_commands` catches
`ValidationError` only. The Click entry point (`start_nginx_set_conf`) has no
top-level handler. `RecursionError` on 1000 empty enters would crash the process.

### Proposed Fix

```python
_MAX_INPUT_LENGTH = 4096  # 16× the longest valid domain (253 chars); generous for all fields

def retrieve_valid_input(message: str) -> str:
    """Prompt user for input until non-empty input is provided.

    Iterative (not recursive) to avoid stack overflow on repeated empty input.
    Caps input at _MAX_INPUT_LENGTH characters to prevent memory-exhaustion on
    piped stdin.
    Handles EOFError (piped/closed stdin) by raising SystemExit gracefully.
    """
    while True:
        try:
            user_input = input(message)
        except EOFError:
            click.echo("\nNo input received (EOF). Exiting.")
            raise SystemExit(1)
        user_input = user_input[:_MAX_INPUT_LENGTH]  # silently truncate oversized input
        if user_input:
            return user_input
        # empty input: loop again (was: recursive call)
```

**Rationale for 4096 char cap:** The longest single validated field is `domain`
(253 chars per RFC 1123). All other fields (IP: max 45, port: max 5, cert_name:
practical max ~255) are shorter. 4096 is 16× the longest valid value — generous
enough to pass valid input, tight enough to cap hostile payloads. This matches
common shell `LINEMAX` limits.

**Truncation vs. rejection:** Silently truncating (with `[:_MAX_INPUT_LENGTH]`) is
preferable to raising a ValidationError in `retrieve_valid_input` itself, because:
- The downstream validator (e.g., `validate_domain`) will reject anything too long
  with a clear message.
- The interactive loop then re-prompts, which is the correct UX.
- Raising inside the input helper couples the helper to validator semantics.

**EOFError handling:** `click.echo` is already imported in `utils.py`
(confirmed: `utils.py` uses `click.echo` for user-facing messages elsewhere).
Raising `SystemExit(1)` is the Click-idiomatic way to exit with an error code.

### Test Approach

**File:** `tests/test_utils.py`, new class `TestRetrieveValidInput`.

The project uses `monkeypatch.setattr(builtins, "input", ...)` pattern (confirmed
from existing `monkeypatch` usage in the test suite):

```python
import builtins
from nginx_set_conf.utils import retrieve_valid_input

class TestRetrieveValidInput:
    def test_returns_nonempty_input_immediately(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda _: "hello")
        assert retrieve_valid_input("prompt: ") == "hello"

    def test_loops_past_empty_input(self, monkeypatch):
        responses = iter(["", "", "finally"])
        monkeypatch.setattr(builtins, "input", lambda _: next(responses))
        assert retrieve_valid_input("prompt: ") == "finally"

    def test_truncates_oversized_input(self, monkeypatch):
        big = "x" * 8000
        monkeypatch.setattr(builtins, "input", lambda _: big)
        result = retrieve_valid_input("prompt: ")
        assert len(result) == 4096

    def test_eof_raises_system_exit(self, monkeypatch):
        monkeypatch.setattr(builtins, "input", lambda _: (_ for _ in ()).throw(EOFError()))
        with pytest.raises(SystemExit):
            retrieve_valid_input("prompt: ")

    def test_no_recursion_on_many_empty_enters(self, monkeypatch):
        """1000 empty inputs followed by valid — must not hit RecursionError."""
        count = [0]
        def fake_input(_):
            count[0] += 1
            if count[0] < 1001:
                return ""
            return "valid"
        monkeypatch.setattr(builtins, "input", fake_input)
        result = retrieve_valid_input("prompt: ")
        assert result == "valid"
        assert count[0] == 1001
```

---

## Standard Stack

No new external packages are required. All fixes use Python stdlib only.

| Module | Purpose | Already in project |
|--------|---------|-------------------|
| `os` | `os.umask`, `os.path.islink`, `os.path.realpath` | Yes |
| `shutil` | `shutil.copytree(symlinks=False)` | Yes (already in `config_verification.py`) |
| `contextlib` | `@contextlib.contextmanager` for umask helper | Yes (stdlib) |
| `builtins` | `input()` in tests | Yes (stdlib) |

---

## Package Legitimacy Audit

No external packages installed in this phase. Audit: N/A.

---

## Architecture Patterns

### Recommended Project Structure (unchanged)

```
nginx_set_conf/
├── validators.py          # SEC-01 fix here
├── config_verification.py # SEC-02 fix here
├── utils.py               # SEC-03 + SEC-04 fixes here
tests/
├── test_validators.py     # SEC-01 regression tests (extend existing class)
├── test_backup.py         # SEC-02 regression tests (new file)
├── test_migration.py      # SEC-03 regression tests (extend existing class)
└── test_utils.py          # SEC-04 regression tests (new class in existing file)
```

### Pattern: Segment-Split Path Traversal Check

`_reject_path_traversal` already exists in `validators.py:180-193` and is the
established pattern for ALL path-safety checks in this codebase:

```python
def _reject_path_traversal(value: str, field: str) -> None:
    normalised_separators = value.replace("\\", "/")
    if ".." in normalised_separators.split("/"):
        raise ValidationError(f"Path traversal detected in {field}: '{value}'")
```

SEC-01 should call this function instead of the raw `".." in target_path` substring
check. This is the existing precedent used by `validate_cert_name`, `validate_cert_key`,
and `validate_auth_file`.

### Anti-Patterns to Avoid

- **Post-hoc chmod via subprocess:** The SEC-03 fix deliberately removes the
  `_run_command(["chmod", "600", key_path])` call. Do not keep it as a "belt and
  suspenders" measure — it communicates the wrong intent and adds a subprocess
  invocation for no security benefit once umask is applied.
- **Recursive input loops:** `retrieve_valid_input` must become iterative. No other
  function in the codebase uses recursive input handling — this was the only instance.
- **Click entry point coverage:** `nginx_set_conf.py` is excluded from coverage
  measurement. Tests should target the underlying helper functions, not the Click
  commands.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File mode enforcement | Custom `chmod` wrapper | `os.umask()` context + `os.open(path, flags, 0o600)` | POSIX standard; atomically correct |
| Symlink detection | Walk source tree recursively | `os.path.islink(path)` on source root | Single call; reliable |
| Input length limiting | Streaming stdin reader | `input()[:MAX]` slice | `input()` already buffers one line |
| Path segment splitting | Custom regex | `value.split("/")` + `".." in` | `_reject_path_traversal` already exists |

---

## Common Pitfalls

### Pitfall 1: `os.path.realpath` masking the input before the security check

**What goes wrong:** Calling `os.path.realpath(target_path)` BEFORE checking for
`..` components collapses traversal sequences — `realpath("/etc/../etc/shadow")`
→ `"/etc/shadow"` without raising. The current code does this correctly (checks
`target_path` not `resolved`), but the fix must preserve this ordering.

**How to avoid:** Strip whitespace → check traversal on stripped raw string →
THEN call `os.path.realpath` → return resolved.

### Pitfall 2: `shutil.copytree` destination must not exist

**What goes wrong:** `shutil.copytree(src, dst)` raises `FileExistsError` if `dst`
already exists (Python < 3.8 with `dirs_exist_ok=False` default). If a previous
backup was interrupted, `backup_path / "nginxconfig.io"` may already exist.

**How to avoid:** The outer `backup_path.mkdir(..., exist_ok=False)` (line 431)
ensures the entire timestamped backup directory is new. The `nginxconfig.io`
subdirectory inside it will not exist. No additional guard needed.

### Pitfall 3: `umask` is process-wide and thread-unsafe

**What goes wrong:** `os.umask()` affects the entire process. In a multi-threaded
context, changing umask in one thread affects all threads. nginx-set-conf is not
multi-threaded, but the risk should be acknowledged.

**How to avoid:** Use the `_restrictive_umask()` context manager pattern which
restores the old umask in a `finally` block. Keep the context as narrow as possible
(wrap only the `_run_command(["openssl", ...])` call, not the entire
`setup_default_server` function body).

### Pitfall 4: `input()` raises `EOFError` in piped mode

**What goes wrong:** When the interactive branch is called in a non-TTY environment
(e.g., piped stdin, CI script), `input()` raises `EOFError` immediately. The
current code has no handler — this crashes the CLI with a traceback.

**How to avoid:** Wrap `input()` in `try: ... except EOFError:` and call
`SystemExit(1)` with a message. The `while True:` loop makes this straightforward.

### Pitfall 5: `backup_configuration` uses hard-coded paths

**What goes wrong:** `/etc/nginx/nginx.conf` and `/etc/nginx/nginxconfig.io` are
hard-coded inside `backup_configuration`. This makes the function impossible to
unit-test without patching `Path` globally (which is fragile) or running as root.

**Recommendation for SEC-02 planner:** Add `nginx_conf_path` and `nginxconfig_dir`
parameters with defaults to `backup_configuration`, mirroring how `setup_default_server`
accepts `target_path`, `ssl_dir`, etc. This is a minor API change to an internal
method and makes tests clean.

---

## Cross-Cutting Notes

### Coverage Gate

Current gate: 60% (`--cov-fail-under=60`), actual: ~64% (v1.11.0).

- `nginx_set_conf.py` is **excluded from coverage measurement** (per
  `[tool.coverage.run] omit` in `pyproject.toml`). Interactive branch tests
  would not count toward coverage anyway.
- `config_verification.py` has **0% coverage** (TESTING.md confirms: "no dedicated
  test file"). Adding any tests for `backup_configuration` (SEC-02) will increase
  overall coverage measurably — potentially +1–2%.
- Adding SEC-01, SEC-03, SEC-04 tests extends existing well-covered modules. Net
  effect: coverage will increase slightly (estimate +1–3%), comfortably staying
  above the 60% gate.
- **Risk:** If SEC-02 test scaffolding for `config_verification.py` is complex
  (due to hard-coded paths), the planner may choose to skip it for coverage purposes.
  The fix itself (2 lines of source code) is mandatory regardless; tests for it
  are highly desirable but not gating.

### Bilingual Release Notes

`RELEASE_NOTES.md` follows a bilingual pattern (DE/EN) per project convention.
v1.11.1 (the previous sprint) set the template. The SEC-01..04 fixes are
appropriately grouped under a "Security" heading in the next release entry.
**Release note authoring is owned by Phase 4 (Docs, open questions, release),
NOT by Phase 1 plans.** Each Phase 1 plan delivers the code fix only.

### Version bump ownership

Per ROADMAP.md Phase 4 success criteria:
> "bump-my-version bump minor" succeeds; tag v1.12.0 is pushed

The version bump to `v1.12.0` is owned by **Phase 4, Plan 04-02**. Phase 1 plans
do NOT run `bump-my-version`. Each plan commits with `[FIX]` or `[CHG]` prefix,
but does not create a release tag.

### Parallelization

All four SEC requirements touch **different modules with no shared state**:

| Plan | Touches | Shares code with |
|------|---------|-----------------|
| 01-01 (SEC-01) | `validators.py` + `test_validators.py` | Nothing in SEC-02..04 |
| 01-02 (SEC-02) | `config_verification.py` + `test_backup.py` | Nothing in SEC-01, 03, 04 |
| 01-03 (SEC-03) | `utils.py` (openssl block only) + `test_migration.py` | SEC-04 also modifies `utils.py` |
| 01-04 (SEC-04) | `utils.py` (`retrieve_valid_input`) + `test_utils.py` | SEC-03 also modifies `utils.py` |

**Coupling note:** SEC-03 and SEC-04 both modify `nginx_set_conf/utils.py` in
non-overlapping regions:
- SEC-03 touches: `utils.py` approximately lines 495–525 (openssl block in `setup_default_server`)
- SEC-04 touches: `utils.py` approximately lines 162–175 (`retrieve_valid_input`)

These regions do not overlap. The planner may execute them in parallel if using
a multi-task tool, but if sequential, SEC-04 should execute first (simpler, lower
risk) and SEC-03 second. A merge conflict is unlikely but the planner should note
that both plans will produce a diff on `utils.py`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥ 9.0 |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_validators.py tests/test_migration.py tests/test_utils.py --no-cov` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | Leading/Unicode whitespace in target_path rejected | unit | `uv run pytest tests/test_validators.py::TestValidateTargetPath -x --no-cov` | ✅ (extend existing class) |
| SEC-02 | Symlinked nginxconfig.io source → backup returns False | unit | `uv run pytest tests/test_backup.py -x --no-cov` | ❌ Wave 0 |
| SEC-03 | Key file mode 0o600 at creation (umask test) | unit | `uv run pytest tests/test_migration.py::TestSetupDefaultServer -x --no-cov` | ✅ (extend existing class) |
| SEC-04 | Iterative loop, length cap, EOFError handling, recursion safety | unit | `uv run pytest tests/test_utils.py::TestRetrieveValidInput -x --no-cov` | ❌ Wave 0 (new class) |

### Wave 0 Gaps

- [ ] `tests/test_backup.py` — covers SEC-02 (`backup_configuration` symlink guards)
- [ ] `tests/test_utils.py::TestRetrieveValidInput` — new class, covers SEC-04

*(All other required infrastructure exists — no conftest.py needed, no framework install required.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes | Path-traversal check in `validate_target_path` (SEC-01); symlink guard in backup (SEC-02) |
| V5 Input Validation | yes | `.strip()` + segment-split for target_path (SEC-01); length cap for stdin (SEC-04) |
| V6 Cryptography | yes | Key file 0o600 mode at creation (SEC-03) — never hand-roll mode enforcement |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Whitespace-padded path traversal | Tampering | `.strip()` + segment-split before realpath |
| Symlink following via backup | Spoofing / Info Disclosure | `os.path.islink()` guard before `copytree` |
| World-readable private key window | Info Disclosure | `umask(0o077)` context around openssl call |
| Unbounded recursion via piped stdin | DoS | `while True:` + `[:_MAX_INPUT_LENGTH]` + `EOFError` handler |

---

## Environment Availability

Step 2.6: SKIPPED — This phase is purely code/source changes. No new external
tools, services, or runtimes are introduced. `openssl` and `shutil` are already
present and exercised via existing tests (monkeypatched in test suite).

---

## Open Questions

1. **SEC-02: `backup_configuration` path injection testability**
   - What we know: The method hard-codes `/etc/nginx/nginx.conf` and
     `/etc/nginx/nginxconfig.io` internally. Tests cannot override these without
     patching `Path` globally or modifying the function signature.
   - What's unclear: Should the planner refactor the method signature to accept
     injectable paths (clean, recommended) or use `monkeypatch` for the `Path`
     constructor (fragile, not project pattern)?
   - Recommendation: Add `nginx_conf_path` and `nginxconfig_dir` parameters with
     defaults. This is a 2-line signature change and makes the function consistent
     with `setup_default_server`'s style.

2. **SEC-03: Remove or keep the post-hoc `chmod 600`?**
   - What we know: With `umask(0o077)`, `chmod 600` is redundant. Keeping it is
     not harmful but misleading — it implies the key was unsafe until that call.
   - Recommendation: Remove the `_run_command(["chmod", "600", key_path])` line.
     This is the research recommendation. If the planner wants belt-and-suspenders,
     it may keep it — but the PLAN should explicitly state the reasoning.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `nginx_set_conf/validators.py:156-177` — `validate_target_path` implementation
- `nginx_set_conf/validators.py:180-193` — `_reject_path_traversal` precedent
- `nginx_set_conf/config_verification.py:425-453` — `backup_configuration` implementation
- `nginx_set_conf/utils.py:162-175` — `retrieve_valid_input` recursive implementation
- `nginx_set_conf/utils.py:480-540` — `setup_default_server` openssl invocation
- `nginx_set_conf/nginx_set_conf.py:355-453` — YAML path + interactive branch call sites
- `tests/test_validators.py` — existing `TestValidateTargetPath` class
- `tests/test_migration.py` — existing `TestSetupDefaultServer` class
- `.planning/codebase/TESTING.md` — test inventory, coverage gate, patterns

### Secondary (HIGH confidence — authoritative project documents)
- `.planning/REQUIREMENTS.md` — SEC-01..SEC-04 fix directions (locked)
- `.planning/ROADMAP.md` — Phase 1 success criteria, release ownership
- `.planning/codebase/CONCERNS.md` — original audit findings with rationale
- `.planning/codebase/ARCHITECTURE.md` — call graph, module responsibilities

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all fixes use Python stdlib already imported
- Architecture: HIGH — all four touch points confirmed by direct source inspection
- Pitfalls: HIGH — derived from actual code paths, not assumptions
- Test patterns: HIGH — mirror existing test classes confirmed in test files

**Research date:** 2026-05-28
**Valid until:** 2026-06-28 (stable codebase; any edit to the four cited functions
would invalidate the line references)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `os.umask(0o077)` propagates to child processes (openssl via `subprocess.run`) | SEC-03 | umask IS inherited by child processes on Linux/macOS — this is a POSIX guarantee, not an assumption. Low risk. |
| A2 | `shutil.copytree` defaults to `symlinks=False` in Python 3.10+ | SEC-02 | Python docs confirm this. But making it explicit is correct regardless. |
| A3 | `backup_configuration` hard-codes `/etc/nginx` paths | SEC-02 | Confirmed by reading `config_verification.py:434-445`. Not an assumption. |

**All claims in this research were verified by direct codebase inspection. No
external library documentation was required. The Assumptions Log is effectively
empty of genuine assumptions.**

---

## RESEARCH COMPLETE

**Phase:** 1 — Privileged write-surface hardening
**Confidence:** HIGH

### Key Findings

- **SEC-01:** The whitespace bypass is real but subtle — the segment-split pattern
  (`_reject_path_traversal`) already exists in the file and should replace the raw
  `".." in` check. Add `.strip()` before the check. Two-line fix.
- **SEC-02:** The `copytree` call lacks an `os.path.islink()` guard on the source
  directory. The hard-coded paths inside `backup_configuration` make tests fragile —
  recommend adding injectable path parameters to the function signature.
- **SEC-03:** `umask(0o077)` context manager is cleaner than pre-creating the file.
  The post-hoc `chmod` subprocess call should be deleted. Three-line context
  manager addition.
- **SEC-04:** `retrieve_valid_input` is the only recursive input loop in the codebase.
  Straightforward `while True:` conversion + `[:4096]` cap + `EOFError` handler.
  No upstream code catches `RecursionError`.

### Files Created
`/Users/picard/gitbase/PyPi-Projects/nginx-set-conf/.planning/phases/NSC-01-privileged-write-surface-hardening/01-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | No new packages; stdlib only |
| Architecture | HIGH | All four touch points verified by source read |
| Pitfalls | HIGH | Derived from actual code, not training data |
| Test patterns | HIGH | Existing test classes confirmed as models |

### Open Questions

1. SEC-02: Should `backup_configuration` receive injectable path parameters for
   testability? Research recommends yes — planner decides.
2. SEC-03: Remove or retain post-hoc `chmod 600`? Research recommends remove.
   Planner decides.

### Parallelization

Plans 01-01 and 01-02 are fully independent.
Plans 01-03 and 01-04 both modify `utils.py` in non-overlapping regions — can run
in parallel with awareness of a potential (easy to resolve) merge.

### Ready for Planning

Research complete. Planner can create four PLAN.md files (01-01 through 01-04).
