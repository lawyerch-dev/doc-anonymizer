English | [中文](quickstart.md)

# Quickstart

Prerequisites: Apple Silicon macOS + Python 3.11/3.12; all commands run from the repository root.
For the one-shot entry point and full usage, see [README](../README.md#快速上手).

## 1. Install

```bash
npm run setup      # one-shot install: Python venv + five packages + preview assets + npm install
npm run doctor     # verify: toolchain/preview assets/ONNX models + which engines this config loads
```

Resolve anything `doctor` reports as "unavailable" before moving on — this project would rather
fail loudly than produce a file with one detection layer missing.
If it reports that `onnx_ner` has no model, fetch it once: `npm run models` (about 830MB, via the
hf-mirror mirror).

## 2. Run a document

```bash
npm run cli -- run ./samples -o var/out -c configs/onnx.yaml
ls var/out          # sample.docx.redacted.docx  manifest.json  mapping.json  …
```

- Output keeps the same format and preserves subdirectories; in `manifest.json`, **only `ok` entries were redacted**;
- `mapping.json` contains all of the original text, **do not send it outside**.

To use your own files: replace `./samples` with a file or directory (do **not** put the output
directory inside the input directory).

## 3. UI

```bash
npm run dev                 # → http://127.0.0.1:8000 (website/docs site: npm run dev:website)
```

Pick a sample or upload → view the original → redact → compare; "Run log" traces every hit
back to its source.

## 4. Resume after an interruption / restore

```bash
npm run cli -- run ./案件 -o var/out -c configs/onnx.yaml --resume
npm run cli -- restore var/out/sample.md.redacted.md --mapping var/out/mapping.json -o restored.md
```

`--resume` decides by "the manifest marks it `ok` **and the output file is still there**".
`restore` only accepts txt/md/csv; text deleted by `remove` has no anchor left, so it cannot be
restored.

## 5. Choose a detection route

| What you want | Config | Extra setup |
|---|---|---|
| Rules + dictionary only (fastest) | `configs/default.yaml` (this is the default when `-c` is omitted) | none |
| Person names/organizations/addresses (recommended for everyday use) | `-c configs/onnx.yaml` | `npm run models` |
| More flexible entity recognition | `-c configs/llm.yaml` | `./scripts/download_model.sh` + `./scripts/serve_llm.sh` |

## FAQ

- **Blank preview pane** → preview assets were not fetched: `./scripts/fetch_file_viewer.sh`.
- **Resource root error / missing frontend pages** → non-editable install: set `DOCANON_ROOT=/path/to/doc-anonymizer`.
- **Some engine is unavailable** → read the reason it gives (ONNX missing a model / no LLM server running); you can also set it to `false` in the config for now.
- **Exit code 2** → some files produced no result: check `error` / `unsupported` in `manifest.json`; the run did not break.
- **Missed detections** → confirm you passed `-c configs/onnx.yaml` (without it you only get rules + dictionary, which in practice misses person and place names);
  add the terms you care about to the config's `dictionary`. **Zero missed detections is not guaranteed**; see [README "Known limitations"](../README.md#已知限制).
