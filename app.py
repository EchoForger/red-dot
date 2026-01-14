from flask import Flask, render_template_string, send_from_directory, request
import json
import os
import argparse
import math

# -----------------------------
# argparse
# -----------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Red Dot Projects Viewer")

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
    parser.add_argument(
        "--per-page",
        type=int,
        default=12,
        help="每页展示数量"
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
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }}</title>

  <!-- Tailwind CDN -->
  <script src="https://cdn.tailwindcss.com"></script>

  <style>
    img { transition: opacity .2s ease; }
  </style>
</head>

<body class="min-h-screen bg-slate-50 text-slate-900">
  <!-- Header -->
  <header class="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
    <div class="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">{{ title }}</h1>
        <p class="text-sm text-slate-500">Red Dot Projects Viewer</p>
      </div>
      <div class="hidden sm:flex items-center gap-2 text-sm text-slate-500">
        <span class="inline-flex items-center rounded-full bg-slate-100 px-3 py-1">
          共 {{ total }} 项 · 每页 {{ per_page }} 项
        </span>
      </div>
    </div>
  </header>

  <!-- Main -->
  <main class="mx-auto max-w-6xl px-4 py-8 space-y-6">
    {% for p in projects %}
    {% set row_id = loop.index %}
    <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div class="flex flex-col md:flex-row">

        <!-- Left: Image (half page on md+) -->
        <div class="md:w-1/2 bg-slate-100">
          {% if p["Local Images"] %}
            <div class="relative w-full">
              <div class="aspect-[4/3] w-full overflow-hidden">
                <img
                  id="img-{{ row_id }}"
                  class="h-full w-full object-cover"
                  src="{{ url_for('data_files', filename=p['Local Images'][0]) }}"
                  alt="{{ p.Title }}"
                  loading="lazy"
                />
              </div>

              {% if p["Local Images"]|length > 1 %}
              <div class="absolute bottom-3 left-3 right-3 flex flex-wrap gap-2">
                {% for img in p["Local Images"] %}
                <button
                  type="button"
                  class="rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-slate-700 shadow hover:bg-white focus:outline-none focus:ring-2 focus:ring-slate-400"
                  onclick="switchImage('{{ row_id }}', '{{ img }}')"
                >
                  {{ loop.index }}
                </button>
                {% endfor %}
              </div>
              {% endif %}
            </div>
          {% else %}
            <div class="flex aspect-[4/3] w-full items-center justify-center text-slate-500">
              <div class="text-center">
                <div class="text-base font-medium">No Image</div>
                <div class="text-xs text-slate-400 mt-1">未提供本地图片</div>
              </div>
            </div>
          {% endif %}
        </div>

        <!-- Right: Info (half page on md+) -->
        <div class="md:w-1/2 p-6 md:p-8">
          <div class="flex items-start justify-between gap-4">
            <h2 class="text-lg md:text-xl font-semibold leading-snug">
              {{ p.Title }}
            </h2>

            {% if p.Year %}
            <span class="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
              {{ p.Year }}
            </span>
            {% endif %}
          </div>

          {% if p.Description %}
          <p class="mt-4 text-sm md:text-base leading-relaxed text-slate-600">
            {{ p.Description }}
          </p>
          {% endif %}

          <div class="mt-6 flex flex-wrap items-center gap-3">
            {% if p["Project URL"] %}
            <a
              href="{{ p['Project URL'] }}"
              target="_blank"
              rel="noreferrer"
              class="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400"
            >
              查看 Red Dot 项目 →
            </a>
            {% endif %}

            {% if p["Local Images"] and (p["Local Images"]|length > 1) %}
            <span class="text-xs text-slate-400">
              共 {{ p["Local Images"]|length }} 张图片
            </span>
            {% endif %}
          </div>
        </div>

      </div>
    </section>
    {% endfor %}
  </main>

  <!-- Pagination -->
  <nav class="mx-auto max-w-6xl px-4 pb-6">
    <div class="flex flex-col sm:flex-row items-center justify-between gap-3">
      <div class="text-sm text-slate-500">
        第 {{ page }} / {{ total_pages }} 页 · 共 {{ total }} 项
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <!-- Prev -->
        {% if page > 1 %}
          <a href="/?page={{ page - 1 }}"
             class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm hover:bg-slate-50">
            ← 上一页
          </a>
        {% else %}
          <span class="rounded-xl border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-400">
            ← 上一页
          </span>
        {% endif %}

        <!-- Page numbers (全量显示；数量很大时建议改省略号分页) -->
        <div class="flex flex-wrap items-center gap-1">
          {% for n in page_numbers %}
            {% if n == page %}
              <span class="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white">
                {{ n }}
              </span>
            {% else %}
              <a href="/?page={{ n }}"
                 class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                {{ n }}
              </a>
            {% endif %}
          {% endfor %}
        </div>

        <!-- Next -->
        {% if page < total_pages %}
          <a href="/?page={{ page + 1 }}"
             class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm hover:bg-slate-50">
            下一页 →
          </a>
        {% else %}
          <span class="rounded-xl border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-400">
            下一页 →
          </span>
        {% endif %}
      </div>
    </div>
  </nav>

  <footer class="mx-auto max-w-6xl px-4 pb-10 pt-4 text-xs text-slate-400">
    <div class="border-t border-slate-200 pt-6">
      本页面使用 Tailwind CSS 渲染。小屏自动上下布局；大屏左右各半。
    </div>
  </footer>

  <script>
    function switchImage(rowId, src) {
      const el = document.getElementById("img-" + rowId);
      if (!el) return;
      el.style.opacity = "0.4";
      el.onload = () => { el.style.opacity = "1"; };
      el.src = "/data/" + src;
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

    # 关键：规范化 Local Images，避免 /data/data/... 这种双层路径
    for p in projects:
        imgs = p.get("Local Images") or []
        fixed = []
        for x in imgs:
            x = str(x).replace("\\", "/")  # 兼容 Windows 反斜杠
            if x.startswith("data/"):
                x = x[len("data/"):]      # 去掉多余的 data/
            fixed.append(x)
        p["Local Images"] = fixed

    # -----------------------------
    # Pagination
    # -----------------------------
    per_page = max(1, args.per_page)

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    if page < 1:
        page = 1

    total = len(projects)
    total_pages = max(1, math.ceil(total / per_page))
    if page > total_pages:
        page = total_pages

    start = (page - 1) * per_page
    end = start + per_page
    projects_page = projects[start:end]

    page_numbers = list(range(1, total_pages + 1))

    return render_template_string(
        HTML,
        projects=projects_page,
        title=args.title,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        page_numbers=page_numbers,
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
