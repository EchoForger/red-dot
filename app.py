from flask import Flask, render_template_string, send_from_directory
import json
import os
import argparse

# -----------------------------
# argparse
# -----------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Red Dot Projects Viewer"
    )

    parser.add_argument(
        "--data-dir",
        default="data",
        help="项目数据目录（包含 projects.json 和图片）"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Flask 监听地址"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Flask 端口"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启 Flask debug 模式"
    )

    parser.add_argument(
        "--title",
        default="Red Dot Projects",
        help="网页标题"
    )

    return parser.parse_args()


args = parse_args()

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__)

BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, args.data_dir)

HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
    margin: 40px;
    background: #f6f6f6;
}
.project-row {
    display: flex;
    background: #ffffff;
    margin-bottom: 20px;
    padding: 20px;
    border-radius: 8px;
    gap: 24px;
}
.image-viewer {
    width: 280px;
    flex-shrink: 0;
}
.project-image {
    width: 100%;
    border-radius: 6px;
    object-fit: cover;
}
.image-controls {
    margin-top: 8px;
    text-align: center;
}
.image-controls button {
    margin: 0 4px;
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid #ccc;
    background: #fff;
    cursor: pointer;
}
.image-controls button:hover {
    background: #eee;
}
.no-image {
    width: 100%;
    height: 180px;
    background: #ddd;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    border-radius: 6px;
}
.project-info {
    flex: 1;
}
.project-info h2 {
    margin-top: 0;
}
.description {
    color: #444;
    line-height: 1.6;
}
</style>
</head>

<body>

<h1>{{ title }}</h1>

{% for p in projects %}
{% set row_id = loop.index %}
<div class="project-row">

    <div class="image-viewer">
        {% if p["Local Images"] %}
            <img
                id="img-{{ row_id }}"
                class="project-image"
                src="/{{ p['Local Images'][0] }}"
            >
            {% if p["Local Images"]|length > 1 %}
            <div class="image-controls">
                {% for img in p["Local Images"] %}
                <button onclick="switchImage('{{ row_id }}', '{{ img }}')">
                    {{ loop.index }}
                </button>
                {% endfor %}
            </div>
            {% endif %}
        {% else %}
            <div class="no-image">No Image</div>
        {% endif %}
    </div>

    <div class="project-info">
        <h2>{{ p.Title }}</h2>

        {% if p.Year %}
        <p><strong>Year:</strong> {{ p.Year }}</p>
        {% endif %}

        {% if p.Description %}
        <p class="description">{{ p.Description }}</p>
        {% endif %}

        {% if p["Project URL"] %}
        <p>
            <a href="{{ p['Project URL'] }}" target="_blank">
                查看 Red Dot 项目 →
            </a>
        </p>
        {% endif %}
    </div>

</div>
{% endfor %}

<script>
function switchImage(rowId, src) {
    document.getElementById("img-" + rowId).src = "/" + src;
}
</script>

</body>
</html>
"""

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    with open(os.path.join(DATA_DIR, "projects.json"), "r", encoding="utf-8") as f:
        projects = json.load(f)
    return render_template_string(
        HTML,
        projects=projects,
        title=args.title
    )

@app.route("/data/<path:filename>")
def data_files(filename):
    return send_from_directory(DATA_DIR, filename)

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )
