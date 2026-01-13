# main.py
import os
import re
import time
import json
import glob
import argparse
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


# ===================== argparse =====================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Red Dot Award crawler with search page cache"
    )

    parser.add_argument(
        "--search-url",
        default="https://www.red-dot.org/search?solr%5Bfilter%5D%5B%5D=meta_categories%3A%2F11%2F",
        help="Search URL WITHOUT page param"
    )

    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory"
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Number of search pages"
    )

    parser.add_argument(
        "--page-wait",
        type=float,
        default=2.5,
        help="Wait after each search page load"
    )

    parser.add_argument(
        "--detail-delay",
        type=float,
        default=0.8,
        help="Delay after each project detail crawl (per worker)"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of worker threads for detail crawling"
    )

    return parser.parse_args()


# ===================== 工具 =====================

def sanitize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:160]


# ===================== JSON 工具 =====================

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


# ===================== Selenium 搜索页抓取（带缓存） =====================

def collect_project_links_with_cache(
    search_url,
    max_pages,
    page_wait,
    headless,
    user_agent,
    cache_path
):
    cache = load_json(cache_path, [])
    cache_map = {
        item["Search Page URL"]: item["Project URLs"]
        for item in cache
    }

    all_project_urls = set()

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={user_agent}")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    for page in range(1, max_pages + 1):
        page_url = f"{search_url}&solr%5Bpage%5D={page}"

        # ✅ 命中缓存
        if page_url in cache_map:
            print(f"📦 使用缓存搜索页 {page}")
            urls = cache_map[page_url]
            all_project_urls.update(urls)
            continue

        print(f"📄 抓取搜索页 {page}: {page_url}")
        driver.get(page_url)
        time.sleep(page_wait)

        elems = driver.find_elements(By.XPATH, "//a[contains(@href, '/project/')]")
        urls = sorted({
            e.get_attribute("href").split("#")[0]
            for e in elems
            if e.get_attribute("href") and "/project/" in e.get_attribute("href")
        })

        print(f"  ➜ 页面中发现 {len(urls)} 个项目")

        if urls:
            cache.append({
                "Search Page URL": page_url,
                "Project URLs": urls
            })
            cache_map[page_url] = urls
            save_json(cache_path, cache)

        all_project_urls.update(urls)

    driver.quit()
    return sorted(all_project_urls)


# ===================== 详情解析 =====================

def get_soup(url, headers):
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml"), r.text


def extract_project_data(url, headers, base_url):
    soup, raw_text = get_soup(url, headers)

    title = soup.select_one("h1")
    title = title.get_text(strip=True) if title else "Unknown"

    category = ""
    cat = soup.select_one(".breadcrumb")
    if cat:
        category = cat.get_text(" / ", strip=True)

    year_match = re.search(r"\b(19\d{2}|20[0-3]\d)\b", raw_text)
    year = year_match.group(0) if year_match else ""

    desc = ""
    block = soup.select_one(".project-description")
    if block:
        desc = block.get_text("\n", strip=True)

    # ----------------- Images (include slider, exclude "Others interested too") -----------------
    images = []

    def add_img(u: str):
        if not u:
            return
        u = u.split("#")[0]

        # 只收“项目相关图”：projects_pim 或 tx_solr_image(轮播 slider)
        if ("projects_pim" in u) or ("eID=tx_solr_image" in u and "usage=slider" in u):
            images.append(urljoin(base_url, u))

    # 找到 “Others interested too” 标题，作为停止边界
    boundary_tag = None
    boundary_text = soup.find(string=re.compile(r"Others interested too", re.I))
    if boundary_text:
        boundary_tag = boundary_text.find_parent()

    container = soup.select_one("main") or soup.body or soup

    # 按页面顺序遍历，遇到 boundary 就停
    for el in container.descendants:
        if boundary_tag is not None and isinstance(el, Tag) and el is boundary_tag:
            break

        if not isinstance(el, Tag):
            continue

        if el.name == "img":
            src = el.get("src") or el.get("data-src") or ""
            add_img(src)

        elif el.name == "a":
            href = el.get("href") or ""
            add_img(href)

    # 去重（保序）
    images = list(dict.fromkeys(images))
    # ------------------------------------------------------------------------------------------

    return {
        "Title": title,
        "Year": year,
        "Category": category,
        "Description": desc,
        "Project URL": url,
        "Images": images
    }


# ===================== 图片保存（修复 .php 扩展名问题） =====================

def _ext_from_content_type(content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
        "image/svg+xml": ".svg",
    }
    return mapping.get(ct, ".jpg")


def download_image(url, headers):
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "")


def save_images(data, output_dir, headers):
    folder = os.path.join(output_dir, sanitize_name(data["Title"]))
    os.makedirs(folder, exist_ok=True)

    local_images = []

    for i, img in enumerate(data["Images"], 1):
        # 如果 image_i.* 已存在，就复用（避免重复下载）
        existed = glob.glob(os.path.join(folder, f"image_{i}.*"))
        if existed:
            local_images.append(existed[0])
            continue

        content, content_type = download_image(img, headers)
        ext = _ext_from_content_type(content_type)

        path = os.path.join(folder, f"image_{i}{ext}")
        with open(path, "wb") as f:
            f.write(content)

        local_images.append(path)

    return local_images


# ===================== 主入口（多线程加速详情抓取） =====================

def main():
    args = parse_args()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    base_url = "https://www.red-dot.org"
    os.makedirs(args.output_dir, exist_ok=True)

    projects_path = os.path.join(args.output_dir, "projects.json")
    search_cache_path = os.path.join(args.output_dir, "search_pages.json")

    # ✅ 读取已有数据，并建立 url -> index 的映射，方便覆盖更新
    projects = load_json(projects_path, [])
    url_to_idx = {p.get("Project URL"): i for i, p in enumerate(projects) if p.get("Project URL")}

    def is_empty_desc(p: dict) -> bool:
        desc = p.get("Description", "")
        return (desc is None) or (str(desc).strip() == "")

    print("🔎 分页收集项目链接（带缓存）...")
    links = collect_project_links_with_cache(
        args.search_url,
        args.max_pages,
        args.page_wait,
        args.headless,
        headers["User-Agent"],
        search_cache_path
    )

    print(f"✅ 共得到 {len(links)} 个唯一项目链接")

    # ✅ 只处理：不存在 或 Description 为空 的 URL
    todo_urls = [
        url for url in links
        if (url not in url_to_idx) or is_empty_desc(projects[url_to_idx[url]])
    ]

    def worker(url: str):
        data = extract_project_data(url, headers, base_url)
        data["Local Images"] = save_images(data, args.output_dir, headers)
        if args.detail_delay and args.detail_delay > 0:
            time.sleep(args.detail_delay)
        return url, data

    saved_since_last = 0
    save_every = 5  # 每完成 N 个写一次 projects.json（可调）

    if not todo_urls:
        print("✅ 无需更新：所有项目 Description 都已存在")
        return

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(worker, url): url for url in todo_urls}

        for fut in tqdm(as_completed(futures), total=len(futures)):
            url = futures[fut]
            try:
                url, data = fut.result()

                # 主线程合并/覆盖
                if url in url_to_idx:
                    projects[url_to_idx[url]] = data
                else:
                    url_to_idx[url] = len(projects)
                    projects.append(data)

                saved_since_last += 1
                if saved_since_last >= save_every:
                    save_json(projects_path, projects)
                    saved_since_last = 0

            except Exception as e:
                print("❌ 失败:", url, e)

    # 收尾保存
    save_json(projects_path, projects)


if __name__ == "__main__":
    main()
