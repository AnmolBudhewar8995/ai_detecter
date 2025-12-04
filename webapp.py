import textwrap
from io import BytesIO

from flask import Flask, render_template_string, request, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ai_detector import analyze_text, read_docx_bytes

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Content Detector</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #f4f6fb; }
    main { max-width: 820px; margin: 4rem auto; padding: 2rem; background: #fff; border-radius: 12px; box-shadow: 0 30px 45px rgba(15, 23, 42, 0.15); }
    h1 { margin-top: 0; }
    label { display: block; margin-bottom: .5rem; font-weight: 600; }
    textarea { width: 100%; min-height: 140px; padding: .75rem; border-radius: 8px; border: 1px solid #d0d7e3; }
    button { border: none; background: #2563eb; color: #fff; padding: .75rem 1.5rem; border-radius: 999px; font-weight: 600; cursor: pointer; }
    .muted { color: #6b7280; font-size: .95rem; }
    .error { background: #fee2e2; color: #991b1b; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; }
    .result { margin-top: 1.5rem; padding: 1rem 1.25rem; border-radius: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; }
    .result.bad { background: #fef2f2; border-color: #fecaca; }
    .badge { float: right; font-weight: 700; font-size: .9rem; padding: .2rem .75rem; border-radius: 999px; background: #e0f2fe; color: #075985; }
    .sentence-list { list-style: none; padding-left: 0; margin-top: 1rem; }
    .sentence { margin-bottom: .5rem; padding: .5rem .75rem; border-radius: 8px; background: #f9fafb; border: 1px solid #e5e7eb; }
    .sentence.fake { background: #fef2f2; border-color: #fecaca; }
    .sentence span { display: block; font-size: .85rem; color: #6b7280; }
    .report-form { margin-top: 1rem; display: inline-block; }
    .report-button { background: #0f172a; }
  </style>
</head>
<body>
  <main>
    <h1>AI Content Detector</h1>
    <p class="muted">Upload a Word document or paste suspicious text. The model will report whether the content feels human-written or AI-generated.</p>

    {% if error %}
      <p class="error">{{ error }}</p>
    {% endif %}

    <form method="post" enctype="multipart/form-data">
      <label for="document">Upload Word document (.docx)</label>
      <input id="document" type="file" name="document" accept=".docx" />
      <p class="muted">This will override the text area if a file is submitted.</p>

      <label for="text">Or paste text to analyze</label>
      <textarea id="text" name="text">{{ submitted_text or '' }}</textarea>

      <button type="submit">Analyze</button>
    </form>

    {% if result %}
      <div class="result {% if result.label == 'Fake' %}bad{% endif %}">
        <div class="badge">{{ result.label }}</div>
        <p><strong>Confidence:</strong> {{ result.score|round(2) }}%</p>
        <p><strong>Interpretation:</strong>
          {% if result.score > 98 %}
            Possible Source: GPT-4 / Claude (very structured)
          {% elif result.score > 90 %}
            Possible Source: ChatGPT / Gemini class models
          {% elif result.label == 'Fake' %}
            Possible Source: Basic AI/paraphrasing tool
          {% else %}
            Looks convincingly human-written.
          {% endif %}
        </p>
        <details>
          <summary>View snippet (first 300 chars)</summary>
          <p>{{ result.text[:300] }}{% if result.text|length > 300 %}…{% endif %}</p>
        </details>
        <form action="/report" method="post" class="report-form">
          <input type="hidden" name="text" value="{{ submitted_text }}" />
          <button type="submit" class="report-button">Download detailed PDF report</button>
        </form>
      </div>
    {% endif %}
  </main>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    result = None
    submitted_text = ""

    if request.method == "POST":
        uploaded = request.files.get("document")
        submitted_text = request.form.get("text", "").strip()

        if uploaded and uploaded.filename:
            if not uploaded.filename.lower().endswith(".docx"):
                error = "Please upload a .docx file."
            else:
                contents = uploaded.read()
                submitted_text = read_docx_bytes(contents)
        elif not submitted_text:
            error = "Provide text or upload a document."

        if not error:
            result = analyze_text(submitted_text)

    return render_template_string(
        TEMPLATE,
        error=error,
        result=result,
        submitted_text=submitted_text,
    )


@app.route("/report", methods=["POST"])
def report():
    text = request.form.get("text", "").strip()
    if not text:
        return "Text is required for report generation", 400

    analysis = analyze_text(text)
    pdf_bytes = _create_pdf_report(analysis)
    return send_file(
        pdf_bytes,
        as_attachment=True,
        download_name="ai_detection_report.pdf",
        mimetype="application/pdf",
    )


def _create_pdf_report(analysis: dict) -> BytesIO:
    buffer = BytesIO()
    page_width, page_height = A4
    margin = 40
    c = canvas.Canvas(buffer, pagesize=A4)
    y = page_height - margin

    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y, "AI Content Detector Report")
    y -= 30

    c.setFont("Helvetica", 12)
    c.drawString(margin, y, f"Result: {analysis['label']}")
    y -= 16
    c.drawString(margin, y, f"Confidence: {analysis['score']:.2f}%")
    y -= 24

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Analyzed Text")
    y -= 18
    c.setFont("Helvetica", 10)
    for line in textwrap.wrap(analysis['text'], 90):
        if y < margin + 20:
            c.showPage()
            y = page_height - margin
            c.setFont("Helvetica", 10)
        c.drawString(margin, y, line)
        y -= 14

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def _is_port_free(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", port))
            return True
        except OSError:
            return False


def _get_port() -> int:
    from os import environ
    import socket

    port_str = environ.get("AI_DETECTOR_PORT")
    if port_str and port_str.isdigit():
        port_candidate = int(port_str)
    else:
        port_candidate = 8090

    if _is_port_free(port_candidate):
        return port_candidate

    print(f"Port {port_candidate} is busy. Falling back to a free port.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=_get_port())
    except OSError as exc:
        if exc.errno == 98:
            print("Port already in use. Set AI_DETECTOR_PORT to a free port and restart.")
        raise
