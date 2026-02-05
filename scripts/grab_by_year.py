import subprocess

base_url = (
    "https://www.red-dot.org/search?"
    "solr%5Bfilter%5D%5B%5D=meta_categories%3A%2F11%2F"
    "&solr%5Bfilter%5D%5B%5D=year%3A"
)

subsets = [
    {
        'year': 2023,
        'max-pages': 58,
    },
    {
        'year': 2024,
        'max-pages': 188,
    },
    {
        'year': 2025,
        'max-pages': 191,
    },
]

for subset in subsets:
    year = subset['year']
    max_pages = subset['max-pages']
    print(f"Grabbing projects from year {year}...")

    subprocess.run([
        "python", "main.py",
        "--search-url", f"{base_url}{year}",
        "--output-dir", f"data_grab_by_year/{year}",
        "--max-pages", str(max_pages)
    ], check=True)
