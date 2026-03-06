# BullX Automation -- Audit TODO

## Critical Issues (Fixed)

- [x] **Hardcoded Windows Chrome paths** -- `config.py`, `database.py`
  Platform-specific Chrome profile paths now use `sys.platform` detection.

- [x] **Headless mode disabled** -- `chrome_driver.py`
  Headless now configurable via `CHROME_HEADLESS` env var; defaults to headless on Linux.
  Added `--no-sandbox` and `--disable-dev-shm-usage` for VPS compatibility.

- [x] **Two-phase Telegram login for headless VPS** -- `chrome_driver.py`
  When running headless and not logged in, prompts user to paste login link from @BullXNeoBot.
  Session persists in Chrome profile for subsequent restarts.

- [x] **`reload=True` hardcoded** -- `main.py`, `start.py`
  Now uses `config.API_RELOAD` from config.py (False in production).

- [x] **Bare except clauses** -- `chrome_driver.py` lines 106, 189
  Changed to `except Exception:`.

- [x] **Debug `print(1)` statement** -- `chrome_driver.py` line 97
  Removed.

- [x] **Relative database path** -- `config.py`, `database.py`
  Database path now absolute, anchored to project directory via `Path(__file__).parent`.

- [x] **CORS allows all origins** -- `main.py`
  CORS origins now configurable via `config.CORS_ORIGINS` / `CORS_ORIGINS` env var.

- [x] **API keys printed to console** -- `database.py`
  Replaced `print()` with `logger.warning()`.

- [x] **Unpinned dependency versions** -- `requirements.txt`
  Pinned `sqlalchemy` and `pydantic` to exact versions.

- [x] **Dark theme dashboard** -- `frontend/css/styles.css`
  Full dark theme overhaul with new CSS variable system.

- [x] **Footer `--card-bg` CSS variable undefined** -- `frontend/css/styles.css`
  Variable now defined in `:root`.

## Medium Priority

- [x] **No `.env` file loading** -- `config.py`
  Added `load_dotenv()` call in `config.py` startup.

- [x] **Chrome user agent string outdated** -- `chrome_driver.py`
  Updated from Chrome 60 to Chrome 131.

- [x] **`bracket_config.py` uses `print()` for validation errors**
  Replaced with `logger.warning()`.

- [x] **Frontend API base URL hardcoded** -- `frontend/js/api.js`
  Changed from `'http://localhost:8000'` to `window.location.origin`.

- [x] **`background_tasks.py` uses `print()` with emojis for console output**
  Replaced all `print()` calls with `logger.info()` / `logger.error()`.

- [ ] **No request rate limiting** -- `main.py`
  Add rate limiting middleware to prevent abuse of the API.

- [ ] **No HTTPS / TLS configuration** -- `main.py`
  For production, uvicorn should be run behind a reverse proxy (nginx) or configured with SSL.

- [ ] **No database migrations strategy** -- Multiple `migrate_*.py` files exist as one-off scripts.
  Consider using Alembic for structured migrations.

- [ ] **No authentication on health endpoint** -- Public health endpoint exposes system information.
  Consider limiting information returned.

- [ ] **No graceful shutdown handling for Chrome drivers in error paths**
  If the app crashes during a Selenium operation, Chrome processes may be left orphaned.

- [ ] **Selenium timeout of 300s for manual login** -- `chrome_driver.py`
  Only applies to non-headless GUI mode now. Consider making configurable.

## Features Added

- [x] **Execution queue system** -- Queue bracket strategy executions via API and dashboard UI.
  New `QueuedExecution` model, background `QueueProcessor` (10s poll interval),
  5 API endpoints (`/queue/*`), dashboard queue panel with auto-refresh.

## Low Priority / Nice-to-Have

- [ ] Add comprehensive test suite
- [ ] Add typing annotations to all function signatures
- [ ] Consider async database operations with `aiosqlite`
- [ ] Add health check for Chrome driver availability
- [ ] Add monitoring/metrics endpoint (Prometheus)
- [ ] Add systemd service file for VPS deployment
