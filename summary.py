# summary.py
import json
import os
from datetime import datetime
from collections import Counter


DATA_DIR = "data"
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
SUMMARY_FILE = os.path.join(DATA_DIR, "summary.json")


def normalize_path(p: str) -> str:
    p = str(p).strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    if p.startswith("data/"):
        p = p[len("data/"):]
    return p


def word_count(text: str) -> int:
    return len(text.strip().split())


def bucket_word_count(n: int) -> str:
    if n < 10:
        return "<10"
    if n < 30:
        return "10-29"
    if n < 60:
        return "30-59"
    if n < 100:
        return "60-99"
    return "100+"


def main():
    if not os.path.exists(PROJECTS_FILE):
        raise FileNotFoundError(f"{PROJECTS_FILE} not found")

    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        projects = json.load(f)

    project_count = len(projects)

    # ---- image stats ----
    image_total = 0
    image_count_dist = Counter()
    missing_images = []

    # ---- description stats ----
    desc_word_counts = []
    desc_bucket_dist = Counter()

    for idx, p in enumerate(projects):
        title = p.get("Title", f"index-{idx}")

        # ---- Local Images ----
        imgs = p.get("Local Images") or []
        image_count_dist[len(imgs)] += 1

        for img in imgs:
            image_total += 1
            rel = normalize_path(img)
            abs_path = os.path.join(DATA_DIR, rel)

            if not os.path.exists(abs_path):
                missing_images.append({
                    "title": title,
                    "path_in_json": img,
                    "resolved_path": abs_path
                })

        # ---- Description ----
        desc = p.get("Description")
        if desc and str(desc).strip():
            wc = word_count(desc)
            desc_word_counts.append(wc)
            desc_bucket_dist[bucket_word_count(wc)] += 1

    # ---- aggregate description stats ----
    if desc_word_counts:
        desc_stats = {
            "count": len(desc_word_counts),
            "min": min(desc_word_counts),
            "max": max(desc_word_counts),
            "avg": round(sum(desc_word_counts) / len(desc_word_counts), 2),
            "bucket_distribution": dict(desc_bucket_dist)
        }
    else:
        desc_stats = {
            "count": 0,
            "min": 0,
            "max": 0,
            "avg": 0,
            "bucket_distribution": {}
        }

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "projects": {
            "count": project_count
        },
        "local_images": {
            "total": image_total,
            "per_project_distribution": dict(image_count_dist),
            "missing_count": len(missing_images),
            "missing_images": missing_images
        },
        "description_words": desc_stats
    }

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"[OK] summary written to {SUMMARY_FILE}")
    print(f"Projects: {project_count}")
    print(f"Local images: {image_total}")
    print(f"Missing images: {len(missing_images)}")


if __name__ == "__main__":
    main()
