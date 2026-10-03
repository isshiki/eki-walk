# Agent instructions

## Purpose and boundary

This is an independent, public personal project linked to a personal blog: map apps about walking distance to railway stations in Japan. Use only publicly obtainable data and public sources.

The current app is the station territory map (`web/`). Its road network, shortest paths, grid and place search come from `ekiwalk` in isshiki/rail-gap-map, pinned as a git dependency (`pyproject.toml`). Do not edit rail-gap-map from here; raising the pinned commit needs the user's approval.

- Do not access, reference, copy, or import any company repositories, private code, internal documents, prompts, configuration, proprietary logic or know-how, or nonpublic/commercial data. Do not explore sibling company projects for context.
- Public outputs of this repository may be referenced by others under their licenses; that never authorizes importing nonpublic assets here.

## Public safety

- Never commit raw/downloaded data, generated app data, credentials, API keys, tokens, `.env`, databases, or caches. Do not force-add ignored files.
- Raw files go to `data/raw/` (copied from rail-gap-map with `eki-walk import-raw`, SHA-256 checked), ekiwalk build files to `data/build/<region>/` (all git-ignored). Generated web data under `web/data/` is also ignored and is published only on the `gh-pages` branch.
- **Ask the user before every download**, stating file name, source URL, and size. Ask before creating the GitHub repository, before every push, and before enabling GitHub Pages.
- Before using a new source, document its license, attribution, redistribution conditions, official source, version, and review date in `docs/data-sources.md`.
- Pin versions (dated OSM extract, 国土数値情報 year, ekiwalk commit). Record retrieval time (UTC), size, and SHA-256 in `data/raw/manifest.json` (written by `eki-walk import-raw`).
- Before every `git add` and `git commit`, inspect `git status --short --untracked-files=all`, candidate paths, sizes, and contents. Review `git diff --cached --stat` before committing. Investigate any file over 1 MiB.
- Code and original documentation: Apache-2.0. Generated databases derived from OpenStreetMap: ODbL 1.0, with attribution and a license link. Source contents retain their own terms: 国土数値情報 N02/N03: CC BY 4.0; ABR town/place search: PDL1.0 (compatible with CC BY 4.0). Keep source-page links, credits, and processing notices in sync across README, docs/data-sources.md, docs/publish/data-README.md, web/index.html, and web/app.js. See docs/data-sources.md for the separate, unresolved N03 survey-law review.

## Development

- Python via uv: `uv sync --locked`, `uv run pytest`. Add dependencies with `uv add` only when needed; commit `uv.lock`.
- Territory code lives in `src/eki_walk/territory/`; it may import `ekiwalk`, never the other way round. Things worth sharing with rail-gap-map are proposed upstream separately (see the design spec, section 3.4).
- Design and plan: `docs/superpowers/specs/` and `docs/superpowers/plans/`.
- Use these instructions with any development tool or AI agent; no vendor-specific skills are required. Historical plans are background, not the current implementation or a requirement to install plugins.
- Read README.md, docs/method.md, docs/data-sources.md, and docs/validation.md before changes. Update current documentation to match the implementation.
- Local preview: `uv run scripts/serve.py` (127.0.0.1:8815, current web/, Ctrl+C to stop). Reload the browser after edits.
- Rebuild all four regions and combine with `uv run scripts/build_territories.py --from territory`. A first build uses the same script without `--from`; it prepares all admin boundaries first. Never regenerate only one region's drawing when shared boundaries change.
- Validate with `uv run pytest -q` and `node --test web/test/*.test.js`. Keep temporary test output under a Git-ignored project-local directory and use LF for edited text.
