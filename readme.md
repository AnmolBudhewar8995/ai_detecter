# AI Detector

This project uses Hugging Face `transformers` and PyTorch to determine whether a piece
of writing looks AI-generated or human-written. It exposes both a CLI (`ai_detector.py`)
and a Flask-based web application (`webapp.py`) that accepts text or `.docx` uploads and
generates Turnitin-style PDF reports with highlighted sentences.

## Requirements

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

> If you prefer, you can install the dependencies directly:
>
> ```bash
> python3 -m pip install transformers torch==2.9.1 python-docx flask reportlab
> ```

## CLI Usage

```bash
python3 ai_detector.py --text "Paste your suspicious paragraph here"
# or analyze a Word document
python3 ai_detector.py --doc essay.docx
```

- `--text`: analyzes inline text
- `--doc`: accepts `.docx` (reads full content via `python-docx`)
- Interactive mode: omit both flags and paste text or pipe from stdin

The CLI now truncates text at 512 tokens, caches the pipeline, and prints a simple verdict with originality percentage plus sentence-level breakdown.

## Web Application

```bash
AI_DETECTOR_PORT=8090 python3 webapp.py
```

- Visit `http://localhost:<port>` (defaults to 8090 unless already busy). The server automatically falls back to a free port if the default is taken and prints the new port number in the console.
- Upload a `.docx` or paste text, then click **Analyze**.
- Results show a highlighted sentence list; a button generates a Turnitin-style PDF report containing the original text plus the calculated originality percentage and highlighted sentences.

## PDF Reports

- The `/report` endpoint reuses the same analysis pipeline and generates a multi-page PDF via ReportLab.
- The report includes the overall originality score and every sentence, with suspected AI-generated sentences highlighted in red.

## Troubleshooting

- Install PyTorch for your platform; the project currently targets CPU/MPS-backed macOS (torch 2.9.1 built for Py 3.14). Use the virtualenv above for isolation.
- If the Flask server cannot bind to the default port, either set `AI_DETECTOR_PORT` or allow the fallback to pick one.
- The first `webapp.py` run may take several minutes as the HF checkpoint downloads (the console logs when the model loads).

## Testing

Manually verify:
1. `python3 ai_detector.py --text "Sample text..."`
2. `python3 webapp.py`, upload/paste, then download the PDF report.

## Notes

- The analyzer uses an `lru_cache` around `transformers.pipeline` so repeated calls remain fast within a session.
- Formatting in the PDF is intentionally minimal to preserve paper-like flow while highlighting sentences; the original `.docx` fonts/layout may not match exactly.
