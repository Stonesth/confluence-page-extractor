import json
import os
from datetime import datetime

from selenium.webdriver.common.by import By


def _first_text(driver, selectors):
    for by, selector in selectors:
        try:
            element = driver.find_element(by, selector)
            text = element.text.strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def _first_html(driver, selectors):
    for by, selector in selectors:
        try:
            element = driver.find_element(by, selector)
            html = element.get_attribute("innerHTML") or ""
            if html.strip():
                return html
        except Exception:
            continue
    return ""


def _first_outer_html(driver, selectors):
    for by, selector in selectors:
        try:
            element = driver.find_element(by, selector)
            html = element.get_attribute("outerHTML") or ""
            if html.strip():
                return html
        except Exception:
            continue
    return ""


def _extract_head_styles(driver):
    script = """
const nodes = Array.from(document.querySelectorAll('head link[rel="stylesheet"], head style'));
return nodes.map(node => node.outerHTML).join('\n');
"""
    try:
        return driver.execute_script(script) or ""
    except Exception:
        return ""


def _build_styled_html(page_data):
    title = page_data.get("title", "Confluence Page")
    page_url = page_data.get("url", "")
    space = page_data.get("space", "")
    author = page_data.get("author", "")
    last_updated = page_data.get("last_updated", "")
    head_styles = page_data.get("head_styles", "")
    content_html = page_data.get("content_html", "")

    fallback_css = """
<style>
body { margin: 0; background: #f5f7fa; font-family: Segoe UI, Arial, sans-serif; color: #172b4d; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.header { background: #fff; border: 1px solid #dfe1e6; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
.meta { font-size: 13px; color: #5e6c84; }
.content { background: #fff; border: 1px solid #dfe1e6; border-radius: 8px; padding: 20px; overflow-x: auto; }
a { color: #0052cc; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #dfe1e6; padding: 8px; }
code, pre { background: #f4f5f7; }
</style>
"""

    return f"""<!doctype html>
<html lang=\"fr\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <base href=\"{page_url}\" />
  <title>{title}</title>
  {head_styles}
  {fallback_css}
</head>
<body>
  <div class=\"container\">
    <div class=\"header\">
      <h1>{title}</h1>
      <div class=\"meta\">Space: {space} | Auteur: {author} | Updated: {last_updated}</div>
      <div class=\"meta\"><a href=\"{page_url}\" target=\"_blank\">Ouvrir la page Confluence</a></div>
    </div>
    <div class=\"content\">{content_html}</div>
  </div>
</body>
</html>
"""


def extract_current_page(driver):
    title = _first_text(
        driver,
        [
            (By.ID, "title-text"),
            (By.CSS_SELECTOR, "h1#title-text"),
            (By.CSS_SELECTOR, "h1[data-test-id='page-title']"),
            (By.TAG_NAME, "h1"),
        ],
    )

    space = _first_text(
        driver,
        [
            (By.CSS_SELECTOR, "a.space-name"),
            (By.CSS_SELECTOR, "[data-testid='space-title-link']"),
            (By.CSS_SELECTOR, ".aui-page-header-main .breadcrumbs a"),
        ],
    )

    last_updated = _first_text(
        driver,
        [
            (By.CSS_SELECTOR, "#content-metadata-page-version .date"),
            (By.CSS_SELECTOR, "time"),
            (By.CSS_SELECTOR, "[data-testid='content-last-updated']"),
        ],
    )

    author = _first_text(
        driver,
        [
            (By.CSS_SELECTOR, "#content-metadata-page-version .user-link"),
            (By.CSS_SELECTOR, "[data-testid='content-byline-author-link']"),
            (By.CSS_SELECTOR, "a.confluence-userlink"),
        ],
    )

    content_html = _first_outer_html(
        driver,
        [
            (By.ID, "main-content"),
            (By.CSS_SELECTOR, "#content"),
            (By.CSS_SELECTOR, "main"),
        ],
    )

    content_text = _first_text(
        driver,
        [
            (By.ID, "main-content"),
            (By.CSS_SELECTOR, "#content"),
            (By.CSS_SELECTOR, "main"),
        ],
    )

    return {
        "title": title,
        "url": driver.current_url,
        "space": space,
        "last_updated": last_updated,
        "author": author,
        "head_styles": _extract_head_styles(driver),
        "content_html": content_html,
        "content_text": content_text,
    }


def save_page_data(page_data, output_dir="output"):
    # Support Windows long paths (>260 chars)
    if os.name == "nt" and not output_dir.startswith("\\\\?\\"):
        safe_dir = f"\\\\?\\{os.path.abspath(output_dir)}"
    else:
        safe_dir = output_dir
    os.makedirs(safe_dir, exist_ok=True)
    output_dir = safe_dir

    metadata = {
        "title": page_data.get("title", ""),
        "url": page_data.get("url", ""),
        "space": page_data.get("space", ""),
        "last_updated": page_data.get("last_updated", ""),
        "author": page_data.get("author", ""),
        "extracted_at": datetime.now().isoformat(),
    }

    folder_name = os.path.basename(os.path.normpath(output_dir))
    if not folder_name:
        folder_name = "content"

    metadata_path = os.path.join(output_dir, "metadata.json")
    content_path = os.path.join(output_dir, f"{folder_name}.html")
    content_raw_path = os.path.join(output_dir, f"{folder_name}_raw.html")

    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)

    with open(content_path, "w", encoding="utf-8") as file:
        file.write(_build_styled_html(page_data))

    with open(content_raw_path, "w", encoding="utf-8") as file:
        file.write(page_data.get("content_html", ""))
