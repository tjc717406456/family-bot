# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Family Bot — a Google Family Group automation tool built with Python/Flask/Playwright. See `README.md` for full usage docs.

### Running the application

- **Web UI (recommended):** `python3 run_web.py` → http://127.0.0.1:5000
- **CLI:** `python3 main.py --help`
- Set `BROWSER_HEADLESS=true` env var when running in headless/CI environments (default is `false`).

### Key caveats

- The system `python` command may not exist; always use `python3`.
- Playwright Chromium must be installed (`playwright install chromium`) and its system deps (`playwright install-deps chromium`) before browser automation works.
- `~/.local/bin` must be on `PATH` for user-installed Python scripts (playwright, flask CLI, etc.).
- The `config.py` default `BROWSER_CHANNEL=chrome` expects a local Chrome install. In cloud/CI, either install Chrome or set `BROWSER_CHANNEL=""` to use Playwright's bundled Chromium.
- SQLite DB at `data/family_bot.db` is auto-created on first run; no external database needed.
- No auth by default (`WEB_AUTH_PASSWORD` is empty). Set it to enable Basic Auth.

### Lint

```bash
flake8 --max-line-length=120 .
```

(flake8 is not in `requirements.txt`; install separately with `pip install flake8` if needed.)

### Tests

No automated test suite exists in this repository. Manual testing is done via the Web UI or CLI.
