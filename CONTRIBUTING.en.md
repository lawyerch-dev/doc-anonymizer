English | [中文](CONTRIBUTING.md)

# Contributing

## Environment

```bash
npm run setup              # one-shot setup: Python venv + five packages (editable) + preview assets + npm install
```

Prerequisites: Apple Silicon macOS + Python 3.11/3.12. The LLM route needs `llama.cpp`, building the desktop shell needs a Rust toolchain,
and browser-side e2e needs `npm`. Run `npm run doctor` to see what is missing.

## Common commands

Every development action goes through the npm scripts at the repo root: `npm test` (one-shot full test), `npm run test:py` / `test:web`,
`npm run dev` / `dev:website` / `dev:desktop`, `npm run cli -- …`. The underlying commands (use them directly when troubleshooting):

```bash
.venv/bin/python -m pytest -q                                        # full suite (about 5 seconds)
.venv/bin/python -m pytest packages/docanon-core/tests/test_job.py -q # a single file
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml       # CLI end-to-end
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml                    # product web end-to-end
npm test                                                             # Python + component library + docs site build
```

> You must use `.venv/bin/python -m pytest`: the `pytest` on PATH may be running on a different Python (one without
> `rapidocr`), and then the scanned-document tests are silently skipped — which means the OCR regression is not tested at all.

The repo has **no** lint / typecheck / CI / pre-commit (rationale in [docs/architecture.en.md](docs/architecture.en.md) §7).
So "tests pass + output pasted" is the gate here.

## Where the code lives

Five packages under `packages/` (`docanon-contract` + three engine packages + `docanon-core`), with dependencies flowing in
one direction only: **core → engine → contract**, and each engine can be lifted out whole. Cross-package tests live in `tests/`.

The frontend has two paths: **zero node at product runtime** (`apps/web/` is built by Vite and the `dist/` output is served by `docanon web`);
**node is fine at build time** (npm workspaces: `packages/ui` shared components + the `apps/web` product UI + the `website/` site and docs,
which is Astro + Starlight, all static output to `dist/`).

**Components live only in `packages/ui`** (`@doc-anonymizer/ui`): both the website and the product frontend (`apps/web`) import it — copying
another set of velora components into an app means reuse has failed (`tests/test_docs.py` will stop you). One `npm install` at the repo root is enough.

## Read before changing code

[AGENTS.md](AGENTS.md) is the entry point: six inviolable boundaries + topic-by-topic pointers into [.agent/rules/](.agent/rules/).
An engine that fails to start must error out, the contract may use the standard library only, layout changes go through `resources.LAYOUT` only, output naming and ledger discipline, rasterizing matched PDF pages… every one of them is locked by tests. Read the one rule for the area you are touching; don't read the whole set.

Remember to sync the docs when you are done: `tests/test_docs.py` checks the paths, links, and test filenames in the docs,
**and the test count stated in `AGENTS.md`** (update it when you add or remove tests, or the test goes red).

## Docs site (only needed if you changed it)

```bash
npm run dev:website        # dev server :4321 (Astro default)
npm run build              # must pass: static output to website/dist/
```

The content comes from the markdown in the repo: adding a page = adding one line to `website/content-manifest.json`
(at build time `website/scripts/sync-content.py` generates the frontmatter Starlight needs, and a test checks that the file exists).
Installing a new component: `cd packages/ui && npx shadcn@latest add @velora/<名字>` (the component goes into the shared package, not into the built app).
The mechanics and the pitfalls we actually hit are written up in [website/README.md](website/README.md).

## Browser-side check (only needed if you changed previews or the UI)

```bash
.venv/bin/docanon web -p 8803 -c configs/onnx.yaml &
cd tests/e2e/webkit && npm install && npx playwright install webkit
DOCANON_URL=http://127.0.0.1:8803 PRESET=sample_text.pdf node webkit-check.mjs   # errors must be []
```

## Commits and PRs

- Branches: `feat/` `fix/` `refactor/` `docs/` …, cut from `main`.
- Commit messages: in Chinese; the first line starts with a verb and says what was done, the body says why; one commit does one thing.
- PRs: fill in the template, and the key part is **pasting the result line from `pytest -q`** (there is no CI, so this is all a human has to go on).

## What we don't do

No cloud APIs, no dependency on Ollama, no lint/typecheck/CI, no multi-user or permissions; turning matched PDF pages into bitmaps is a
security choice, not a todo. Do not commit `mapping.json`, model weights, or `var/`.

## Reporting problems

Missed redaction / sensitive content that might be recoverable → the private channel in [SECURITY.md](.github/SECURITY.md).
For everything else use the [issue template](.github/ISSUE_TEMPLATE/bug_report.yml), including the `docanon engines` output and the version number,
and **do not** attach real sensitive source documents.
