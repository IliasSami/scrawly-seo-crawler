# Contributing to Scrawly

Scrawly is a free, open-source technical SEO and GEO audit tool built for the SEO
community. It improves fastest when the people who use it say what's missing, so every
kind of contribution helps, not just code.

## Send an improvement note (the fastest way)

No GitHub account needed. In the app, click the **speech-bubble icon** (Send feedback) at
the bottom of the left bar and write what to improve, what broke, or what you'd like next.
Notes go straight to the maintainer.

## Report a bug or request a feature

[Open an issue](https://github.com/IliasSami/scrawly-seo-crawler/issues/new/choose). Helpful details:

- what you did, what you expected, and what happened;
- the kind of site (WordPress, Shopify, Next.js and so on) if it matters;
- your operating system, and `scrawly.log` from the data folder if something crashed
  (see [docs/DESKTOP.md](docs/DESKTOP.md#4-where-your-data-lives)).

Security issues: please don't open a public issue; see [SECURITY.md](SECURITY.md).

## Contribute code

1. Fork the repository and create a branch.
2. Set up a development environment (Python 3.11+, Node.js 18+, git):

   ```bash
   python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
   pip install -e ".[dev,desktop]"
   playwright install chromium
   npm --prefix ui install
   ```

3. Run it:

   ```bash
   PYTHONPATH=src uvicorn sentinelseo.web.api:app --port 8000   # the engine
   npm --prefix ui run dev                                       # the UI, http://localhost:3000
   ```

   or the full desktop app: `python -m sentinelseo.desktop`.

4. Make your change, then run the same checks CI runs (all must pass):

   ```bash
   ruff check src tests scripts
   mypy src tests --exclude '\.venv' --follow-imports=skip
   PYTHONPATH=src python -m pytest tests/ -q
   npm --prefix ui run build
   ```

5. Open a pull request describing the change and why.

Read [AGENTS.md](AGENTS.md) before larger changes: it lists the project's invariants (for
example, every write to a WordPress site captures a rollback first, and checks are pure
functions with no network access).

## Ground rules

- Only crawl and audit websites you own or are allowed to test. For development, use the
  local WordPress test site (`make wp-up`, http://localhost:8080).
- Keep user-facing text plain and friendly; write for people who aren't developers.
- Unit tests make no network calls (use recorded fixtures, `respx`, or `httpx.MockTransport`).
- Never commit secrets: `.env`, databases and credential files are git-ignored.
- Don't invent SEO checks: the catalogue in [docs/CHECK_MANIFEST.yaml](docs/CHECK_MANIFEST.yaml)
  is the source of truth. Propose new checks in an issue first.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).

Thank you for helping make good technical SEO free for everyone.
