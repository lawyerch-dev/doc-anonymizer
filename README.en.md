<h1 align="center">doc-anonymizer</h1>

<p align="center"><b>Local document redaction</b> · Chinese-first · fully offline · keeps the original format</p>

<p align="center">
  <a href="https://lawyerch-dev.github.io/doc-anonymizer/"><img alt="Online docs" src="https://img.shields.io/badge/docs-%E5%9C%A8%E7%BA%BF%E6%96%87%E6%A1%A3-2ea44f.svg"></a>
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Platform: macOS arm64" src="https://img.shields.io/badge/platform-macOS%20arm64-lightgrey.svg">
  <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg">
  <img alt="No network by default" src="https://img.shields.io/badge/network-offline%20by%20default-success.svg">
</p>

<p align="center">
  <a href="https://lawyerch-dev.github.io/doc-anonymizer/"><b>Online docs</b></a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="CONTRIBUTING.en.md">Contributing</a> ·
  <a href=".github/SECURITY.md">Security</a> ·
  <a href="README.md">中文</a>
</p>

<p align="center">
  <img src="docs/images/web-ui.png" width="900" alt="Web UI: pick a document on the left, compare the original and the redacted file side by side in the middle, and see detection stats in the right panel">
</p>

Person names, phone numbers (mobile and landline), ID cards, passports, license plates, bank cards,
emails, IPs, unified social credit codes, secrets, custom sensitive terms — detected and erased, emitting
**same-format** files plus a reversible mapping table.
**No network, no uploads, no cloud APIs** — the one exception being when you explicitly click
"download model", which fetches that single file from modelscope.

## Features

- **Chinese-first**: rules + a Chinese dictionary + Chinese NER (ONNX), all three working together.
- **Fully offline**: no cloud calls; the optional LLM route only talks to a local `llama-server`.
- **Keeps the original format**: docx rewritten run by run, xlsx/csv rewritten cell by cell, pdf/images blacked out — compare before and after side by side.
- **Legacy Office accepted too**: `.doc`/`.xls`/`.wps` are converted to a modern format via LibreOffice before redaction (the output format therefore changes; the ledger and UI say so).
- **Recall first**: anything uncertain is always flagged, and every hit's position and origin stay inspectable.
- **Reversible**: editable office documents (docx/xlsx/csv/txt/md) are replaced with `{{TYPE_N}}` anchors, so
  the output carries **no originals and is safe to send out**, while a locally kept `mapping.json` puts the
  redacted values back **in place**, formatting and styling untouched — see [Redact → AI → restore](#redact--ai--restore).
- **No silently missing layer**: if an engine cannot start it fails before the run, rather than producing a result with less detection.
- **Resumable**: the ledger is flushed as soon as each file finishes, so `--resume` never redoes completed work.
- **Three ways in**: CLI / browser / desktop window, all on the same engines and config.

## Quick start

Prerequisites: Apple Silicon macOS + Python 3.10–3.13.

```bash
git clone https://github.com/lawyerch-dev/doc-anonymizer && cd doc-anonymizer
npm run setup          # one-shot setup: Python venv + five packages + preview assets + npm install
npm run dev            # product UI: backend + Vite dev (hot reload) → http://127.0.0.1:5173
npm run dev:website    # website/docs site → http://localhost:4321
npm test               # one-shot full test run (all Python + component library checks + docs site build)
```

**npm scripts are the entry points** (`scripts/dev.sh` is the implementation layer they call):

| Command | What it does |
|---|---|
| `npm run setup` | idempotent environment setup; `npm run doctor` tells you what is missing and why it cannot start |
| `npm run dev` / `dev:website` / `dev:desktop` | product UI / website & docs site / desktop shell |
| `npm run dev:backend` | backend for the product UI only (production shape: `npm run build:web && npm run dev:backend`) |
| `npm test` | one-shot full test run (`test:py` runs Python only, `test:web` runs the frontend only) |
| `npm run test:strict` | anti-false-green: once the environment is declared complete, **any skip counts as a failure** (run it after installing models, see `docs/cookbook/reviewing-a-change.md`) |
| `npm run check:scope` | works out the **smallest** set of checks your change needs (not a blanket full run) |
| `npm run build:web` | build the product UI → `apps/web/dist/` (served statically by `docanon web`) |
| `npm run build` | build the static site → `website/dist/` |
| `npm run cli -- <args>` | call docanon directly (mind npm's `--`) |
| `npm run engines` / `models` / `doctor` | engine self-check / fetch models / environment self-check |

`npm run models` fetches the Chinese NER models that `configs/onnx.yaml` asks for (two models, about 780MB; the official
huggingface.co is unreachable on some networks, so the script defaults to `hf-mirror.com`, and `HF_ENDPOINT`
can point elsewhere).
Step-by-step walkthrough: [docs/quickstart.en.md](docs/quickstart.en.md).

## Run flow and structure

```mermaid
flowchart TD
  A["input: file / directory"] --> B{"docanon run"}
  B -->|"missing input / unreadable config"| E1["exit 1"]
  B --> C["engine pre-check"]
  C -->|"any layer fails to start"| E2["fails before the run<br/>not a single file written"]
  C --> D["per file"]
  D --> F["extract · route by extension"]
  F --> G["detect · all detectors + de-overlap"]
  G --> H["pick strategy · keep = untouched, else replace"]
  H --> I["make a replacement · consistent document-wide"]
  I --> J["write back in place · same format"]
  J --> K["flush ledger<br/>manifest + mapping"]
  K --> L["exit code 0 all processed / 2 some file has no artifact / 1 bad input"]
```

```mermaid
flowchart TB
  U["CLI / browser UI / desktop window<br/>three entry points, one set of engines and config"] --> CORE["docanon-core<br/>extract → detect → redact + write back + ledger + CLI + Web"]
  CORE --> R["rule"]
  CORE --> D2["dictionary"]
  CORE --> ON["onnx_ner"]
  CORE --> LL["llm_ner"]
  R --> CT["docanon-contract<br/>shared ABC"]
  D2 --> CT
  ON --> CT
  LL --> CT
  ROOT["resource root: configs / models<br/>resolved independently of the current directory"] -.-> CORE
```

Why the packages are split this way, the hard boundaries and the decision records: [docs/architecture.en.md](docs/architecture.en.md).

## Usage

### CLI

```bash
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml        # process a file or directory
.venv/bin/docanon run ./案件 -o var/out -c configs/onnx.yaml --resume  # resume after an interruption
.venv/bin/docanon engines -c configs/onnx.yaml                         # how many detection layers this config runs
.venv/bin/docanon restore "var/out/【脱敏版】sample.md" --mapping var/out/mapping.json
```

Exit codes: `0` everything processed · `1` bad input/config/engine (not a single file is written) · `2` some
files produced no result (unsupported format / failed extraction / interrupted) — `2` is a heads-up, not a crash.

### Web UI

```bash
./scripts/fetch_file_viewer.sh                       # first run: preview assets (232MB, gitignored)
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml
```

Pick a sample or upload → preview the original → redact → compare side by side + hit counts; the "Run log"
traces every hit back to its source (which engine, where, what matched, what it was replaced with). It listens
on `127.0.0.1` only, with no auth (for local, single-user use).

**The redaction scheme is layered in three levels** (progressive disclosure — casual users only ever touch L1):

- **L1 scheme**: choose one of the **three built-ins** (`configs/*.yaml`, read-only) or **my configs**
  (`var/configs/<name>.yaml`) — General / Most accurate / Fastest. The dropdown lists only a **short name**;
  "when to use which" is shown on its own line underneath — both come from the **first two comment lines** of
  each yaml (edit the wording in the file and the UI follows), while anything below them is detail for whoever
  edits the config and never reaches users. The default is "General" (recognises numbers, names, organizations
  and addresses, using the local small model, in milliseconds). **Edits are saved automatically**, with a
  "reset to defaults" right there; export / import also available.
  `configs/legal.yaml` ("redact identifiers and contacts only, leave names/orgs/amounts alone") still ships
  (it is **not** the CLI default — with no `-c` the CLI uses `configs/default.yaml`), but it is **not exposed
  in the UI dropdown** (see `HIDDEN_SCHEMES` in `apps/web/src/lib/formats.ts`).
- **L2 custom redaction**: per-type strategy (shown in plain language, e.g. "blank out with `**`"; maps to
  `redact` / `mask` / `placeholder` / `pseudonym` / `remove` / `keep`, each row with a worked example) + custom
  sensitive words; the "use pseudonyms for people/orgs" switch merely flips the matrix between `redact` and
  `pseudonym` (it introduces no second representation).
- **L3 detection engines**: this layer answers exactly one question — **should a model recognise names,
  organizations and addresses**: no model / the local small model / the local LLM ("both" only appears when the
  current config already uses both). Choose a model and only then do the catalogue (`configs/llm_models.yaml`)
  and "which LLM" show up: **click one and it is used**; if it is not installed the download starts on its own
  (progress, cancel, resumes if interrupted). Starting the server is the app's job (it brings `llama-server` up
  before the run and swaps it when you switch models) — no terminal, no address, no alias. Fixed-format numbers,
  emails and your own word list are **always on** (they need no model and there is no reason to turn them off):
  to leave one kind alone, set its strategy to `keep` in L2 — don't switch off an engine (that silently drops
  detections).

Edits are **saved automatically and take effect at once** — the three built-ins are read-only, so a change lands
in a **same-named user config** (editing "General" writes `var/configs/onnx.yaml`). The scheme dropdown therefore
**still lists only those three**, marking the edited one as changed, with a "reset to defaults" that clears every
edit and goes back to the factory scheme (configs you imported from elsewhere are left alone). Use export / import
to back the current settings up or move them to another machine. Engine pre-check runs at run time — a missing model / unreachable LLM returns 400 + a reason
(never silently dropping a layer); the list endpoint does **not** pre-check (so it never loads ONNX each call).
User configs share the built-in schema and live in the gitignored `var/configs/`; **built-ins are read-only**
(no edit, no delete). UI preferences (the "Settings → Upload files" intake rule) live in `var/settings.json`
(`/api/settings`) — like models and configs they count as **writable state**, so in a packaged build they land
under `DOCANON_DATA` (macOS `~/Library/Application Support/docanon`) and survive a machine move.

Endpoints: `/` `/assets/*` `/health` `/api/presets` `/api/configs` `/api/configs/{ref}` `/api/models`
`/api/models/download` `/api/formats` `/api/upload` `/api/anonymize` `/api/prepare` `/api/restore`
`/api/progress/{job}` (plus `PUT`/`DELETE /api/configs/{name}`,
`POST /api/configs/import`, `GET /api/configs/{name}/export`, `POST /api/models/download/cancel`,
`POST /api/prepare/cancel`, `POST /api/anonymize/cancel`, `GET`/`PUT /api/settings`).
`/api/configs` lists built-ins and user configs and marks the current one; `/api/models` reports the ONNX
dirs, the LLM defaults and the **downloadable model catalogue**; `/api/models/download` starts / polls /
cancels the in-app model download (it takes a catalogue `id` only, **never a URL**); `/api/upload` takes `{filename, content_b64}`;
`/api/anonymize` takes `{preset|token, config?, job?}`, where `config` is a **config name** or an **inline object**,
and returns `counts` and `trace`; uploads are capped at 50MB.
`/api/anonymize`'s response also carries `restorable` / `anchors` / `restore_token` (present only when there
are addressable anchors; the UI uses it to decide whether to show the "Restore" entry); batch results carry
`restorable` and `anchors` per file.
`/api/restore` takes `{token, filename, content_b64, expected?}`, where `expected` is that file's anchor list
(it is what lets us report "what is missing"); output lands in its **own `/restored/` directory** with a
`restore-report.json`, and the response carries `total_restored` / `missing` / `unknown` / `complete`.
`POST /api/restore/batch` is the batch version: `{token, items: [{filename, content_b64}], anchors?}` — **one
failure does not sink the batch** (per-file `status` and reason), and as long as at least one succeeded a
`zip_url` is also given (the whole restored set, at `GET /api/restore/{rtoken}/zip`).
`job` is a short id the UI generates: poll `/api/progress/{job}` while it runs (reading the file / recognising
segment N / writing back), or stop it with `POST /api/anonymize/cancel` — cancelling **leaves no file at all**
(a half-written product is more dangerous than none).

### Website & docs site (optional)

```bash
npm run dev:website        # → http://localhost:4321 (runs npm install automatically on first use)
npm run build              # static output into website/dist/, servable by any static host
```

Deploying to GitHub Pages: Settings → Pages → Source, pick **GitHub Actions**; from then on a push to `main`
runs [`.github/workflows/deploy-website.yml`](.github/workflows/deploy-website.yml), which passes the gates
before publishing (the deployment-related gates: doc drift + package boundaries + component library checks
+ site build; the full engine test suite stays local via `npm test`).
Sub-path deployments need `SITE_BASE=/<repo-name> SITE_URL=https://<username>.github.io`; the full steps and
how to verify them are in [`docs/cookbook/shipping-the-website.md`](docs/cookbook/shipping-the-website.md).

Astro 5 + Starlight (search/TOC/prev-next built in), with content coming straight from this repo's markdown
(manifest `website/content-manifest.json`); components live in the shared library [`packages/ui`](packages/ui/README.md)
(`@doc-anonymizer/ui`: velora **100 components + 31 blocks** + shadcn primitives, MIT), and
**whenever the product frontend changes stacks it imports that same package**, so the look and the components
never fork. The catalog is on the site under "Developers → Engineering → Component library overview".
For details, the measured framework comparison, and pitfalls, see [website/README.md](website/README.md).

### Desktop build (the thing you hand to someone else)

```bash
npm run dev:desktop       # dev: system WebView, :8770
npm run dist:desktop      # build the distributable locally: macOS .dmg, Windows -setup.exe (Python backend and resources included)
```

Development never needs the shell (`.venv/bin/docanon web` serves the same UI); **it is the only artefact
meant to be handed to someone else**. First launch walks the user through picking a scheme and prepares
whatever it needs in the background (models are not shipped inside the app).

**Official builds come from Actions**: `.github/workflows/build-desktop.yml` (push a `v*` tag, or dispatch
it by hand) builds on macOS and Windows runners and uploads to a GitHub Release. Each platform must be built
on **its own OS** — PyInstaller cannot cross-compile, and Tauri only emits the host platform's bundles.
Only **Apple Silicon** is published, and the packages are **unsigned and un-notarized** (first launch needs
one manual allow).
See [apps/desktop/README.md](apps/desktop/README.md).

## Supported formats & outputs

| Input | Output | How it is redacted |
|---|---|---|
| `.docx` | `【脱敏版】x.docx` | text rewritten run by run (hyperlinks, content controls, nested tables included), formatting kept |
| `.xlsx` / `.csv` | `【脱敏版】x.xlsx` | cells rewritten, keeping sheet structure |
| `.doc` / `.xls` / `.wps` (legacy Office) | `【脱敏版】x.doc.docx` | converted to `.docx`/`.xlsx` by LibreOffice first, then redacted; **the output format changes and the layout may be reflowed** |
| `.pdf` (text layer) | `【脱敏版】x.pdf` | hit pages blacked out (**the page becomes a bitmap**) |
| `.pdf` (scan) / `.png` `.jpg` `.tiff` … | same as above / `【脱敏版】x.png` | OCR locates the text, then black boxes are drawn proportionally to character width |
| `.txt` / `.md` | `【脱敏版】x.txt` / `x.md` | line-by-line plain-text replacement |

Files are named `【脱敏版】<full name>` (the target extension is appended only when the format changed, e.g.
`【脱敏版】x.doc.docx`, so that `x.doc` and `x.docx` in one directory do not collide), keeping relative
subdirectories. Names beyond the filesystem's 255-byte limit are **truncated deterministically**: the
extension is kept and a `~` + short hash is appended to the shortened stem so different sources never
collide — the same input always yields the same artifact name. The `-o` directory holds two ledgers
(accumulated per source file, so you can run in batches):

- `manifest.json` — `ok` / `error` / `unsupported` per file. **Only `ok` files were redacted.**
- `mapping.json` — original ↔ replacement. **Never send it out or commit it alongside the redacted files.**

## Configuration

`configs/`: `legal.yaml` (**delivery preset for legal documents**: redacts only identifiers and contact
details such as ID numbers, bank cards, phones and addresses; courts, case numbers, judges and clerks, party
names, law firms and agents, dates and amounts are all left alone) · `default.yaml` (rules + dictionary) ·
`onnx.yaml` (+ Chinese NER, swaps names and organizations too — for talks and case write-ups) ·
`llm.yaml` (+ a local LLM; pick one in the UI and the server is started for you before the run).
All three built-in schemes **default to `anchor` for every entity type** — the output is `{{TYPE_N}}` anchors,
carries no originals, is safe to send out and can be restored (see below).
There is also `llm_models.yaml` — the **downloadable model catalogue**, not a redaction preset: each entry
carries a name, one line of when-to-use, the repo and the filename, and the UI's "local LLM" section turns it
into a picker (selecting installs and uses it). Add your own models by editing that file (see the
[design](docs/specs/2026-10-09-llm-model-download-design.md)).
There is also `onnx_models.yaml` — the **recognition-model catalogue** (likewise not a preset): the first-run
"Prepare" step uses it to fill in whatever the chosen scheme needs (mirrors are speed-tested first; a model
counts as installed only when every file is there). **Models never ship inside the installer** (5.9G) — open
the app once, click once, and the backend prepares everything quietly; the UI only ever says "preparing".

**Use `legal.yaml` for delivery**: `onnx.yaml` treats the court as an organization, "审判员" and
"委托诉讼代理人" as roles, and the judgment date as a date of birth — redacts them all, and the document can
no longer be filed (measured). List what you want redacted; every type you do not list stays `keep` ("only
what I name gets touched"). Hits that were identified but kept by config are listed separately in the web run log.

- Strategies are configured per entity type: `anchor` (`{{PERSON_1}}`, **addressable and restorable**,
  **the default of all three built-in schemes**) / `redact` (**replaces the whole span with `**`**) /
  `mask` (`138****0000`) / `placeholder` (`<PHONE_1>`, also addressable and restorable) /
  `pseudonym` (a stable fake name per entity of the same kind — **only when you ask for it**) / `remove`
  (delete outright) / `keep` (**leave it alone** — it exists so a config can say "don't touch this class").
  `mask` / `redact` / `remove` discard the original at replacement time and are **irreversible by design**
  (`run` lists them); `pseudonym` is not an addressable anchor, so it cannot be restored either.
  Custom terms go under `dictionary` and are tagged `CUSTOM`.
- Relative paths in config (e.g. `onnx.model_dirs`) resolve against the **resource root** (found by walking up
  from `configs/default.yaml`; override it with `DOCANON_ROOT`) and are independent of the cwd; input/output
  paths given on the command line resolve against the cwd.

## Redact → AI → restore (reversible round trip)

When you need to hand a redacted document to an AI for rewriting (reformatting, rephrasing, restructuring)
and want the original values filled back in afterwards — the three built-in schemes are already this route:
every sensitive value becomes a `{{TYPE_N}}` **anchor** (no originals, safe to send out), so `restore` can put
the originals back **without touching the formatting or styling**.

```bash
.venv/bin/docanon run ./cases -o var/rt -c configs/onnx.yaml
# hand var/rt/【脱敏版】x.docx to your AI, then take its edited file back:
.venv/bin/docanon restore AI-edited.docx \
    --mapping var/rt/mapping.json \
    --expected var/rt/manifest.json \        # which anchors this file should contain
    --report var/rt/restore-report.json
```

**When it cannot be restored**: only if you switch some type back to `mask` (`138****5678`) /
`redact` (`**`) / `remove` in L2 — they discard the original at replacement time, which is mathematically
irreversible, and no later `restore` can recover it. `run` lists the irreversible strategies your config
actually uses.

| Capability | Detail |
|---|---|
| Zero style change | docx only touches `run.text`: fonts, sizes, colours, underline, paragraph styles and table structure stay exactly as they were; xlsx only touches cell values |
| Reorder-proof | Anchors are located by **text**, never by position — correct even after the AI reorders paragraphs or merges cells |
| Run-split proof | Restores anchors that Word/the AI split across several runs (spell check and format brushes do this) |
| Forgiving matching | Tolerates whitespace and case changes around anchors; HTML-unescapes first (`&lt;` and friends) |
| Never silent | Anchors the AI deleted or mangled are reported and the exit code is 2; anchors the AI invented are left untouched — **never guessed** |

Exit codes: `0` fully restored · `1` bad input or unsupported format · `2` missing or unknown anchors
(the output is still written, but a human needs to look at it)

**In the web UI**: after the run a "Redact → restore" entry appears in the top bar (it opens a drawer,
`RestorePanel`), **marked "under development" and disabled for now** (`POST /api/restore/batch` and the CLI `restore` are already
usable). Once it opens, choose the AI-edited file (multiple files, or a whole folder) and the per-file
results, zip download and reconciliation report show up there. The entry appears **only when the output is
actually restorable**: products made with `mask`/`redact` have no addressable anchors, and a button that can
only fail is worse than none.
The mapping table stays on the server and never passes through the browser (it *is* the original
data); restored files land in their own `/restored/` directory, separate from the shareable output.

**Not restorable**: pdf and images. Matching pages are rasterised during redaction and the text layer is
physically gone — use docx for this workflow. `restore` refuses these formats with a reason rather than
handing back a file that only looks restored.

⚠ `mapping.json` **is** the original data: keep it local, never send it to the AI.
⚠ If the AI returns markdown, the text restores but the styling does not.

## Detection engines

| Engine | What it does | Depends on |
|---|---|---|
| `rule` | ID cards / phones (mobile and landline) / passports / license plates / bank cards / emails / IPs / unified social credit codes / secrets / amounts | nothing |
| `dictionary` | custom business-sensitive terms → `CUSTOM` | nothing |
| `onnx_ner` | Chinese NER (person names / organizations / addresses, …), 34ms per item, no server needed | `var/models/onnx/*` |
| `llm_ner` | local LLM NER that takes instructions and generates natural-looking fake names | `llama-server` + GGUF (started for you in the web UI; start it yourself for the CLI) |

`docanon engines` reports whether each layer is available (with the reason) and what it can actually do;
for choosing between them, and for benchmark numbers, see [docs/benchmarks.md](docs/benchmarks.md).

The model layers (`onnx_ner` / `llm_ner`) have two **deterministic guards** (no prompt wording — adding a
"do not tag …" list to the 4B model actually *lost* entities on a real contract): law, document and work titles
inside `《》` are never entities (the Civil Code was once blanked to `《**》`, removing the document's legal
basis); and `AMOUNT` must carry a money trace (a digit / `¥` / 元/万/亿), so a duration like "十日" is not
treated as an amount. `rule` / `dictionary` match exactly and are exempt from both.

## Known limitations

- **A hit PDF page becomes a full-page bitmap** (the text layer is gone — nothing to select, search, or edit again).
  This is a security guarantee: blacking out the text layer would still leave the original copyable. Pages without
  hits are kept as they are.
- docx **headers, footers, footnotes, and text boxes are not extracted** (body paragraphs, hyperlinks, content
  controls, and tables — nested ones included — are covered).
- docx **document properties are left untouched**: metadata such as the author name in `docProps` survives
  (measured — the body is redacted while the property still carries the name).
- A sensitive value that exists **only in a link target and is never shown in the body** is not detected; values
  that do appear in the body are scrubbed from the `mailto:`/URL as well, but an email or token travelling purely
  inside a URL is out of scope.
- When restoring docx/xlsx, `restore` **only recognises anchors** (`anchor` / `placeholder`), not masked
  values or pseudonyms — they are not addressable, and in docx a value can span several runs, so a literal
  global replace would hit unrelated text. Purely symbolic replacements (`redact`'s `**`) are excluded too,
  because markdown bold is also `**`.
- Text deleted by `remove` has no anchor and cannot be restored (which is why all three built-in schemes use
  `anchor` for `SECRET`, not `remove`).
- Masked values that look the same (two numbers masked identically) restore to the wrong original text.
- Text getting longer shifts line breaks (unavoidable when restoring, but it is the true length of the original).
- If the AI returns only markdown, the text restores but the styling does not.
- `.doc` / `.xls` / `.wps` are converted to `.docx`/`.xlsx` and then redacted (LibreOffice required): check the
  `soffice` line in `npm run doctor`, and fetch it with `./scripts/fetch_libreoffice.sh` if missing. The output
  format therefore becomes `.docx`/`.xlsx`, and **the layout may be reflowed — review by hand before delivery**;
  without LibreOffice the file is recorded as `unsupported` (exit code 2). To turn the conversion off, set
  `legacy_convert: false`. GBK CSVs must be converted to UTF-8 first.
- The output directory must not live inside the input directory, or the next run will treat the previous run's
  `【脱敏版】*` files as new documents and redact them again.
- **It assists human review and does not guarantee zero misses**: OCR misreads and unusual spellings can slip through.
  Review by hand before delivery, especially scans and tables.

## Documentation

| I want to… | Read |
|---|---|
| a step-by-step walkthrough, common problems | [docs/quickstart.en.md](docs/quickstart.en.md) |
| to contribute (environment, tests, commits, PRs) | [CONTRIBUTING.en.md](CONTRIBUTING.en.md) |
| the contracts to read before changing code (entry point + topic rules) | [AGENTS.md](AGENTS.md) · [.agent/rules/](.agent/rules/) |
| five-package structure, hard boundaries, decision records, relocation history | [docs/architecture.en.md](docs/architecture.en.md) |
| model choice and benchmark numbers | [docs/benchmarks.md](docs/benchmarks.md) |
| the script inventory | [scripts/README.md](scripts/README.md) |
| how to change the website/docs site or the component library | [website/README.md](website/README.md) · [packages/ui/README.md](packages/ui/README.md) |
| version changes | [CHANGELOG.md](CHANGELOG.md) |
| how to report a missed redaction or another security issue | [SECURITY.md](.github/SECURITY.md) |
| the original design document (historical) | [docs/specs/2026-10-05-doc-anonymizer-design.md](docs/specs/2026-10-05-doc-anonymizer-design.md) |
| the legacy-format auto-conversion design and decision | [design](docs/specs/2026-10-08-legacy-office-conversion-design.md) · [decision note](.agent/notes/implemented/feature/2026-10-08-legacy-office-conversion.md) |
| the layered web redaction-config design and decision | [design](docs/specs/2026-10-08-redaction-config-design.md) · [decision note](.agent/notes/implemented/feature/2026-10-08-web-redaction-config.md) |

[MIT](LICENSE) © 2026 [LawyerCH](https://github.com/LawyerCH) ·
thanks to [RapidOCR](https://github.com/RapidAI/RapidOCR), [pypdfium2](https://github.com/pypdfium2-team/pypdfium2),
[python-docx](https://github.com/python-openxml/python-docx), [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl),
[llama.cpp](https://github.com/ggml-org/llama.cpp), [file-viewer](https://github.com/flyfish-dev/file-viewer),
[Electrobun](https://github.com/blackboardsh/electrobun) (the shell's predecessor), [Tauri](https://tauri.app), [velora-ui](https://github.com/ColorlibHQ/velora-ui)
