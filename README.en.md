<h1 align="center">doc-anonymizer</h1>

<p align="center"><b>Local document redaction</b> · Chinese-first · fully offline · keeps the original format</p>

<p align="center">
  <a href="https://lawyerch-dev.github.io/doc-anonymizer/"><img alt="Online docs" src="https://img.shields.io/badge/docs-%E5%9C%A8%E7%BA%BF%E6%96%87%E6%A1%A3-2ea44f.svg"></a>
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Platform: macOS arm64" src="https://img.shields.io/badge/platform-macOS%20arm64-lightgrey.svg">
  <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg">
  <img alt="No network" src="https://img.shields.io/badge/network-offline%20by%20design-success.svg">
</p>

<p align="center">
  <a href="https://lawyerch-dev.github.io/doc-anonymizer/"><b>Online docs</b></a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="CONTRIBUTING.en.md">Contributing</a> ·
  <a href=".github/SECURITY.md">Security</a> ·
  <a href="README.md">中文</a>
</p>

<p align="center">
  <img src="docs/images/web-ui.png" width="900" alt="Web UI: pick a document on the left, preview the original in the middle, and after clicking “Start redacting” the right pane previews the redacted file with its formatting preserved">
</p>

Person names, phone numbers (mobile and landline), ID cards, passports, license plates, bank cards,
emails, IPs, unified social credit codes, secrets, custom sensitive terms — detected and erased, emitting
**same-format** files plus a reversible mapping table.
**No network, no uploads, no cloud APIs.**

## Features

- **Chinese-first**: rules + a Chinese dictionary + Chinese NER (ONNX), all three working together.
- **Fully offline**: no cloud calls; the optional LLM route only talks to a local `llama-server`.
- **Keeps the original format**: docx rewritten run by run, xlsx/csv rewritten cell by cell, pdf/images blacked out — compare before and after side by side.
- **Recall first**: anything uncertain is always flagged, and every hit's position and origin stay inspectable.
- **Reversible**: `mapping.json` records original ↔ replacement, and `restore` rebuilds text outputs.
- **No silently missing layer**: if an engine cannot start it fails before the run, rather than producing a result with less detection.
- **Resumable**: the ledger is flushed as soon as each file finishes, so `--resume` never redoes completed work.
- **Three ways in**: CLI / browser / desktop window, all on the same engines and config.

## Quick start

Prerequisites: Apple Silicon macOS + Python 3.11/3.12.

```bash
git clone https://github.com/lawyerch-dev/doc-anonymizer && cd doc-anonymizer
npm run setup          # one-shot setup: Python venv + five packages + preview assets + npm install
npm run dev            # product UI → http://127.0.0.1:8000
npm run dev:website    # website/docs site → http://127.0.0.1:4321
npm test               # one-shot full test run (all Python + component library checks + docs site build)
```

**npm scripts are the entry points** (`scripts/dev.sh` is the implementation layer they call):

| Command | What it does |
|---|---|
| `npm run setup` | idempotent environment setup; `npm run doctor` tells you what is missing and why it cannot start |
| `npm run dev` / `dev:website` / `dev:desktop` | product UI / website & docs site / desktop shell |
| `npm test` | one-shot full test run (`test:py` runs Python only, `test:web` runs the frontend only) |
| `npm run test:strict` | anti-false-green: once the environment is declared complete, **any skip counts as a failure** (run it after installing models, see `docs/cookbook/reviewing-a-change.md`) |
| `npm run check:scope` | works out the **smallest** set of checks your change needs (not a blanket full run) |
| `npm run build` | build the static site → `website/dist/` |
| `npm run cli -- <args>` | call docanon directly (mind npm's `--`) |
| `npm run engines` / `models` / `doctor` | engine self-check / fetch models / environment self-check |

`npm run models` fetches the Chinese NER model that `configs/onnx.yaml` asks for (about 830MB; the official
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
.venv/bin/docanon restore var/out/sample.md.redacted.md --mapping var/out/mapping.json
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

Endpoints: `/` `/app.css` `/app.js` `/health` `/api/presets` `/api/upload` `/api/anonymize`
(the last two take `{filename, content_b64}` / `{preset|token}` and return `counts` and `trace`; uploads are capped at 50MB).

### Website & docs site (optional)

```bash
npm run dev:website        # → http://127.0.0.1:4321 (runs npm install automatically on first use)
npm run build              # static output into website/dist/, servable by any static host
```

Deploying to GitHub Pages: Settings → Pages → Source, pick **GitHub Actions**; from then on a push to `main`
runs [`.github/workflows/deploy-website.yml`](.github/workflows/deploy-website.yml), which passes the gates
before publishing (this is the repo's only CI, running the deployment-related gates: doc drift + package
boundaries + component library checks + site build; the full engine test suite stays local via `npm test`).
Sub-path deployments need `SITE_BASE=/<repo-name> SITE_URL=https://<username>.github.io`; the full steps and
how to verify them are in [`docs/cookbook/shipping-the-website.md`](docs/cookbook/shipping-the-website.md).

Astro 5 + Starlight (search/TOC/prev-next built in), with content coming straight from this repo's markdown
(manifest `website/content-manifest.json`); components live in the shared library [`packages/ui`](packages/ui/README.md)
(`@doc-anonymizer/ui`: velora **100 components + 31 blocks** + shadcn primitives, MIT), and
**whenever the product frontend changes stacks it imports that same package**, so the look and the components
never fork. The catalog is on the site under "Development → Component library overview".
For details, the measured framework comparison, and pitfalls, see [website/README.md](website/README.md).

### Desktop shell (optional)

```bash
cd apps/desktop && hutch install && npm start   # system WebView, :8770
```

See [apps/desktop/README.md](apps/desktop/README.md).

## Supported formats & outputs

| Input | Output | How it is redacted |
|---|---|---|
| `.docx` | `x.docx.redacted.docx` | text rewritten run by run (hyperlinks, content controls, nested tables included), formatting kept |
| `.xlsx` / `.csv` | `x.xlsx.redacted.xlsx` | cells rewritten, keeping sheet structure |
| `.pdf` (text layer) | `x.pdf.redacted.pdf` | hit pages blacked out (**the page becomes a bitmap**) |
| `.pdf` (scan) / `.png` `.jpg` `.tiff` … | same as above / `x.png.redacted.png` | OCR locates the text, then black boxes are drawn proportionally to character width |
| `.txt` / `.md` | `x.txt.redacted.txt` | line-by-line plain-text replacement |

Files are named `<full name>.redacted.<original extension>`, keeping relative subdirectories. The `-o`
directory holds two ledgers (accumulated per source file, so you can run in batches):

- `manifest.json` — `ok` / `error` / `unsupported` per file. **Only `ok` files were redacted.**
- `mapping.json` — original ↔ replacement. **Never send it out or commit it alongside the redacted files.**

## Configuration

`configs/`: `legal.yaml` (**delivery preset for legal documents**: redacts only identifiers and contact
details such as ID numbers, bank cards, phones and addresses; courts, case numbers, judges and clerks, party
names, law firms and agents, dates and amounts are all left alone) · `default.yaml` (rules + dictionary) ·
`onnx.yaml` (+ Chinese NER, swaps names and organizations too — for talks and case write-ups) ·
`llm.yaml` (+ a local LLM; run `./scripts/serve_llm.sh` first).

**Use `legal.yaml` for delivery**: `onnx.yaml` treats the court as an organization, "审判员" and
"委托诉讼代理人" as roles, and the judgment date as a date of birth — redacts them all, and the document can
no longer be filed (measured). List what you want redacted; every type you do not list stays `keep` ("only
what I name gets touched"). Hits that were identified but kept by config are listed separately in the web run log.

- Strategies are configured per entity type: `pseudonym` (a stable fake name per entity of the same kind) /
  `placeholder` (`<PHONE_1>`) / `mask` (`138****0000`) / `remove` (delete outright) / `keep` (**leave it
  alone** — it exists so a config can say "don't touch this class"); custom terms go under
  `dictionary` and are tagged `CUSTOM`.
- Relative paths in config (e.g. `onnx.model_dirs`) resolve against the **resource root** (found by walking up
  from `configs/default.yaml`; override it with `DOCANON_ROOT`) and are independent of the cwd; input/output
  paths given on the command line resolve against the cwd.

## Detection engines

| Engine | What it does | Depends on |
|---|---|---|
| `rule` | ID cards / phones (mobile and landline) / passports / license plates / bank cards / emails / IPs / unified social credit codes / secrets / amounts | nothing |
| `dictionary` | custom business-sensitive terms → `CUSTOM` | nothing |
| `onnx_ner` | Chinese NER (person names / organizations / addresses, …), 34ms per item, no server needed | `var/models/onnx/*` |
| `llm_ner` | local LLM NER that takes instructions and generates natural-looking fake names | `llama-server` + GGUF |

`docanon engines` reports whether each layer is available (with the reason) and what it can actually do;
for choosing between them, and for benchmark numbers, see [docs/benchmarks.md](docs/benchmarks.md).

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
- `restore` only supports text outputs (txt/md/csv); text deleted by `remove` has no anchor left, so it cannot be restored.
- After masking, values that look the same (two numbers masked identically) restore to the wrong original text.
- `.doc` / `.xls` / `.wps` are unsupported (recorded as `unsupported`, exit code 2); convert them to `.docx`/`.xlsx`
  with LibreOffice first (command and caveats in [`docs/cookbook/diagnosing-problems.md`](docs/cookbook/diagnosing-problems.md)). GBK CSVs must be converted to UTF-8 first.
- The output directory must not live inside the input directory, or the next run will treat the previous run's
  `.redacted.*` files as new documents and redact them again.
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

[MIT](LICENSE) © 2026 [LawyerCH](https://github.com/LawyerCH) ·
thanks to [RapidOCR](https://github.com/RapidAI/RapidOCR), [pypdfium2](https://github.com/pypdfium2-team/pypdfium2),
[python-docx](https://github.com/python-openxml/python-docx), [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl),
[llama.cpp](https://github.com/ggml-org/llama.cpp), [file-viewer](https://github.com/flyfish-dev/file-viewer),
[Electrobun](https://github.com/blackboardsh/electrobun), [velora-ui](https://github.com/ColorlibHQ/velora-ui)
