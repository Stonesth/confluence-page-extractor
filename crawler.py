import json
import os
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import scraper


def _normalize_url(url):
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="", query="")
    normalized = urlunparse(cleaned)
    if normalized.endswith("/"):
        return normalized[:-1]
    return normalized


def _extract_page_id(url):
    parsed = urlparse(url)
    path_match = re.search(r"/pages/(\d+)", parsed.path)
    if path_match:
        return path_match.group(1)

    query = parse_qs(parsed.query)
    page_id = query.get("pageId")
    if page_id and page_id[0]:
        return page_id[0]

    return ""


def _extract_space_key(url):
    parsed = urlparse(url)
    path_match = re.search(r"/spaces/([^/]+)/", parsed.path)
    if path_match:
        return path_match.group(1)

    query = parse_qs(parsed.query)
    query_space = query.get("spaceKey")
    if query_space and query_space[0]:
        return query_space[0]

    return ""


def _slugify(value, max_len=40):
    if not value:
        return "untitled"
    slug = re.sub(r"[^a-zA-Z0-9\- _]", "", value).strip().replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len] if slug else "untitled"


def _safe_path(path):
    """Add Windows long-path prefix if needed."""
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        abs_path = os.path.abspath(path)
        return f"\\\\?\\{abs_path}"
    return path


def _diagnose_sidebar(driver, current_page_id):
    """
    Dumps diagnostic info about the sidebar DOM including full ancestor chain
    from the current page anchor up to the tree root.
    """
    script = r"""
const currentPageId = String(arguments[0]);
const diag = {};

function extractPageId(href) {
    if (!href) return '';
    const m1 = href.match(/\/pages\/(\d+)/);
    if (m1) return m1[1];
    const m2 = href.match(/[?&]pageId=(\d+)/);
    if (m2) return m2[1];
    return '';
}

// 1. Check main containers
diag['containers'] = {
    '.plugin_pagetree': !!document.querySelector('.plugin_pagetree'),
    '.plugin_pagetree_children': !!document.querySelector('.plugin_pagetree_children'),
    '.ia-secondary-container': !!document.querySelector('.ia-secondary-container'),
};

// 2. Ancestor chain from current page span to tree root
const treeRoot = document.querySelector('.plugin_pagetree');
const currentSpan = treeRoot ? treeRoot.querySelector('span.plugin_pagetree_current') : null;
const currentAnchor = currentSpan ? currentSpan.querySelector('a[href]') : null;

if (currentAnchor) {
    const chain = [];
    let el = currentAnchor;
    while (el && el !== treeRoot) {
        chain.push({
            tag: el.tagName,
            id: el.id || '',
            className: (el.className || '').toString().substring(0, 150),
            childElementCount: el.childElementCount || 0,
        });
        el = el.parentElement;
    }
    diag['ancestor_chain'] = chain;

    // 3. NodeWrapper (grandparent of span) children details
    const nodeContent = currentSpan.closest('div.plugin_pagetree_children_content');
    if (nodeContent && nodeContent.parentElement) {
        const wrapper = nodeContent.parentElement;
        diag['node_wrapper'] = {
            tag: wrapper.tagName,
            id: wrapper.id,
            className: (wrapper.className || '').toString(),
            childElementCount: wrapper.childElementCount,
            children: Array.from(wrapper.children).map(c => ({
                tag: c.tagName,
                id: c.id || '',
                className: (c.className || '').toString().substring(0, 120),
                childElementCount: c.childElementCount,
                hasPageLinks: c.querySelectorAll('a[href*="/pages/"]').length,
            })),
        };
    }
}

// 4. AJAX endpoint test
try {
    const xhr = new XMLHttpRequest();
    const url = '/plugins/pagetree/naturalchildren.action?decorator=none&excerpt=false&sort=position&reverse=false&disableLinks=false&expandCurrent=false&hasRoot=true&pageId=' + currentPageId + '&treeId=0&startDepth=0';
    xhr.open('GET', url, false);
    xhr.send();
    diag['ajax_test'] = {
        status: xhr.status,
        responseLength: (xhr.responseText || '').length,
        responsePreview: (xhr.responseText || '').substring(0, 500),
    };
} catch(e) {
    diag['ajax_test'] = {error: e.message};
}

return diag;
"""
    try:
        return driver.execute_script(script, current_page_id) or {}
    except Exception as e:
        return {"error": str(e)}


def _try_expand_tree_node(driver, current_page_id):
    """
    Tries to click the expand arrow on the current page's tree node
    to load children that might not be visible yet.
    Returns True if an expand action was triggered.
    """
    script = r"""
const treeRoot = document.querySelector('.plugin_pagetree');
if (!treeRoot) return {expanded: false, reason: 'no tree'};

const currentSpan = treeRoot.querySelector('span.plugin_pagetree_current');
if (!currentSpan) return {expanded: false, reason: 'no current span'};

const nodeContent = currentSpan.closest('div.plugin_pagetree_children_content');
if (!nodeContent) return {expanded: false, reason: 'no content div'};

// Look for expand/collapse toggle in this node
// Confluence uses various classes for the toggle icon
const toggleSelectors = [
    '.plugin_pagetree_childtoggle_container .aui-iconfont-chevron-right',
    '.plugin_pagetree_childtoggle_container .icon-section-closed',
    '.plugin_pagetree_childtoggle_container .aui-icon',
    '.plugin_pagetree_childtoggle_container a',
    '.plugin_pagetree_childtoggle_container',
];

for (const sel of toggleSelectors) {
    const toggle = nodeContent.querySelector(sel);
    if (toggle) {
        toggle.click();
        return {expanded: true, selector: sel};
    }
}

// Also check the parent (nodeWrapper) for the toggle
const nodeWrapper = nodeContent.parentElement;
if (nodeWrapper) {
    for (const sel of toggleSelectors) {
        const toggle = nodeWrapper.querySelector(sel);
        if (toggle && !nodeContent.contains(toggle)) {
            toggle.click();
            return {expanded: true, selector: sel + ' (from wrapper)'};
        }
    }
}

return {expanded: false, reason: 'no toggle found'};
"""
    try:
        result = driver.execute_script(script) or {}
        return result.get("expanded", False)
    except Exception:
        return False


def _collect_child_page_links(driver, current_page_id):
    """
    Finds direct child pages of the current page.
    Strategy 1: AJAX - Confluence's pagetree naturalchildren.action endpoint
    Strategy 2: DOM  - Navigate from span.plugin_pagetree_current through the tree
    Strategy 3: Expand + retry - Click the tree expand arrow, then re-scan
    """

    # ------------------------------------------------------------------
    # Strategy 1: AJAX pagetree endpoint (most reliable)
    # ------------------------------------------------------------------
    ajax_script = r"""
const currentPageId = String(arguments[0]);

function extractPageId(href) {
    if (!href) return '';
    const m1 = href.match(/\/pages\/(\d+)/);
    if (m1) return m1[1];
    const m2 = href.match(/[?&]pageId=(\d+)/);
    if (m2) return m2[1];
    return '';
}

try {
    const xhr = new XMLHttpRequest();
    const url = '/plugins/pagetree/naturalchildren.action?decorator=none&excerpt=false&sort=position&reverse=false&disableLinks=false&expandCurrent=false&hasRoot=true&pageId=' + currentPageId + '&treeId=0&startDepth=0';
    xhr.open('GET', url, false);
    xhr.send();

    if (xhr.status === 200 && xhr.responseText && xhr.responseText.trim().length > 0) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(xhr.responseText, 'text/html');
        const anchors = Array.from(doc.querySelectorAll('a[href]'));
        const children = [];
        const seen = new Set();

        for (const a of anchors) {
            const href = a.getAttribute('href') || '';
            const pid = extractPageId(href);
            if (pid && pid !== currentPageId && !seen.has(pid)) {
                seen.add(pid);
                children.push(href);
            }
        }

        if (children.length > 0) {
            return {strategy: 'ajax-naturalchildren', found: children.length, links: children};
        }
        return {strategy: 'ajax-empty', found: 0, links: []};
    }
    return {strategy: 'ajax-bad-status', status: xhr.status, found: 0, links: []};
} catch(e) {
    return {strategy: 'ajax-error', error: e.message, found: 0, links: []};
}
"""

    # ------------------------------------------------------------------
    # Strategy 2: DOM - walk from span.plugin_pagetree_current
    # ------------------------------------------------------------------
    dom_script = r"""
const currentPageId = String(arguments[0]);

function extractPageId(href) {
    if (!href) return '';
    const m1 = href.match(/\/pages\/(\d+)/);
    if (m1) return m1[1];
    const m2 = href.match(/[?&]pageId=(\d+)/);
    if (m2) return m2[1];
    return '';
}

const treeRoot = document.querySelector('.plugin_pagetree');
if (!treeRoot) return {strategy: 'dom-no-tree', found: 0, links: []};

const currentSpan = treeRoot.querySelector('span.plugin_pagetree_current');
if (!currentSpan) return {strategy: 'dom-no-current', found: 0, links: []};

// Navigate: span → div.plugin_pagetree_children_content → nodeWrapper
const nodeContent = currentSpan.closest('div.plugin_pagetree_children_content');
if (!nodeContent) return {strategy: 'dom-no-content', found: 0, links: []};

const nodeWrapper = nodeContent.parentElement;
if (!nodeWrapper) return {strategy: 'dom-no-wrapper', found: 0, links: []};

const results = [];
const seen = new Set();

// Look through all children of nodeWrapper EXCEPT nodeContent
// to find the children container with child page spans
for (const wrapperChild of nodeWrapper.children) {
    if (wrapperChild === nodeContent) continue;

    // Find page spans inside this container
    const spans = wrapperChild.querySelectorAll('span.plugin_pagetree_children_span');
    for (const span of spans) {
        const a = span.querySelector('a[href]');
        if (!a) continue;

        const href = a.getAttribute('href') || '';
        const pid = extractPageId(href);
        if (!pid || pid === currentPageId || seen.has(pid)) continue;

        // Only take DIRECT children: ensure there's no intermediate
        // plugin_pagetree_children_content between this span's content-div
        // and the wrapperChild root
        const contentDiv = span.closest('div.plugin_pagetree_children_content');
        if (!contentDiv) continue;

        let isDirectChild = true;
        let el = contentDiv.parentElement;
        while (el && el !== wrapperChild) {
            if (el.classList && el.classList.contains('plugin_pagetree_children_content')) {
                isDirectChild = false;
                break;
            }
            el = el.parentElement;
        }

        if (isDirectChild) {
            seen.add(pid);
            results.push(href);
        }
    }
}

if (results.length > 0) {
    return {strategy: 'dom-wrapper', found: results.length, links: results};
}

// Fallback: DOM order scan with element depth
// Walk through all tree spans in DOM order, find current, then collect
// the spans that are deeper until we hit the same or shallower depth
const allSpans = Array.from(treeRoot.querySelectorAll('span.plugin_pagetree_children_span'));
let currentIdx = -1;
let currentDepth = 0;

function getDepthFromTree(el) {
    let d = 0;
    let cur = el;
    while (cur && cur !== treeRoot) {
        d++;
        cur = cur.parentElement;
    }
    return d;
}

for (let i = 0; i < allSpans.length; i++) {
    if (allSpans[i] === currentSpan) {
        currentIdx = i;
        currentDepth = getDepthFromTree(allSpans[i]);
        break;
    }
}

if (currentIdx >= 0) {
    let childDepth = -1;
    for (let i = currentIdx + 1; i < allSpans.length; i++) {
        const span = allSpans[i];
        const depth = getDepthFromTree(span);

        if (depth <= currentDepth) break;  // left the subtree

        // The first span after current that is deeper = child level
        if (childDepth === -1) {
            childDepth = depth;
        }

        // Only take spans at the child level (skip grandchildren)
        if (depth === childDepth) {
            const a = span.querySelector('a[href]');
            if (a) {
                const href = a.getAttribute('href') || '';
                const pid = extractPageId(href);
                if (pid && pid !== currentPageId && !seen.has(pid)) {
                    seen.add(pid);
                    results.push(href);
                }
            }
        }
    }

    if (results.length > 0) {
        return {strategy: 'dom-depth-scan', found: results.length, links: results};
    }
}

return {strategy: 'dom-none', found: 0, links: [],
    debug: {
        wrapperTag: nodeWrapper ? nodeWrapper.tagName : null,
        wrapperId: nodeWrapper ? nodeWrapper.id : null,
        wrapperChildCount: nodeWrapper ? nodeWrapper.childElementCount : 0,
        wrapperChildren: nodeWrapper ? Array.from(nodeWrapper.children).map(c =>
            c.tagName + (c.className ? '.' + c.className.toString().split(' ')[0] : '')
        ) : [],
    }
};
"""

    def _normalize_links(raw_links):
        normalized = []
        seen_ids = set()
        for raw_link in raw_links:
            absolute = urljoin(driver.current_url, raw_link)
            clean = _normalize_url(absolute)
            page_id = _extract_page_id(clean)
            if page_id and page_id not in seen_ids:
                seen_ids.add(page_id)
                normalized.append(clean)
        return normalized

    # --- Try Strategy 1: AJAX ---
    try:
        result = driver.execute_script(ajax_script, current_page_id) or {}
        strategy = result.get("strategy", "")
        raw_links = result.get("links", [])
        found = result.get("found", 0)
        print(f"  -> Child detection [AJAX]: {strategy}, found: {found}")
        if found > 0:
            return _normalize_links(raw_links)
    except Exception as e:
        print(f"  [WARN] AJAX strategy error: {e}")

    # --- Try Strategy 2: DOM ---
    try:
        result = driver.execute_script(dom_script, current_page_id) or {}
        strategy = result.get("strategy", "")
        raw_links = result.get("links", [])
        found = result.get("found", 0)
        debug = result.get("debug", {})
        print(f"  -> Child detection [DOM]: {strategy}, found: {found}")
        if debug:
            print(f"     Debug: {debug}")
        if found > 0:
            return _normalize_links(raw_links)
    except Exception as e:
        print(f"  [WARN] DOM strategy error: {e}")

    # --- Strategy 3: Try expanding the tree node, wait, and retry DOM ---
    print(f"  -> No children found, trying to expand tree node...")
    expanded = _try_expand_tree_node(driver, current_page_id)
    if expanded:
        print(f"  -> Expand triggered, waiting 3s for children to load...")
        time.sleep(3)
        try:
            result = driver.execute_script(dom_script, current_page_id) or {}
            strategy = result.get("strategy", "")
            raw_links = result.get("links", [])
            found = result.get("found", 0)
            print(f"  -> Child detection [DOM after expand]: {strategy}, found: {found}")
            if found > 0:
                return _normalize_links(raw_links)
        except Exception as e:
            print(f"  [WARN] DOM after expand error: {e}")

    return []


def crawl_and_save(driver, start_url, output_root="output", max_depth=2, delay_seconds=2):
    root_url = _normalize_url(start_url)
    root_parsed = urlparse(root_url)
    root_netloc = root_parsed.netloc
    root_space_key = _extract_space_key(root_url)
    root_page_id = _extract_page_id(root_url)

    os.makedirs(output_root, exist_ok=True)
    pages_root = os.path.join(output_root, "pages")
    os.makedirs(pages_root, exist_ok=True)

    visited_page_ids = set()
    sequence = 0
    all_pages = []

    def _crawl(url, depth, parent_folder_path):
        """
        Crawls a page and its children.
        parent_folder_path: the filesystem folder where this page's folder
                            will be created (mirrors the Confluence tree).
        """
        nonlocal sequence

        page_id = _extract_page_id(url)
        if not page_id:
            return None

        if page_id in visited_page_ids:
            return None

        visited_page_ids.add(page_id)

        print(f"[depth={depth}] Visiting: {url}")
        driver.get(url)
        time.sleep(delay_seconds)

        page_data = scraper.extract_current_page(driver)
        title = page_data.get("title") or "untitled"

        sequence += 1
        folder_name = f"{sequence:04d}-{_slugify(title)}"
        folder_path = os.path.join(parent_folder_path, folder_name)
        scraper.save_page_data(page_data, output_dir=_safe_path(folder_path))

        node = {
            "title": title,
            "url": page_data.get("url", url),
            "page_id": page_id,
            "depth": depth,
            "folder": os.path.relpath(folder_path, output_root).replace("\\", "/"),
            "children": [],
        }

        all_pages.append({
            "title": title,
            "url": node["url"],
            "page_id": page_id,
            "depth": depth,
            "folder": node["folder"],
        })

        print(f"  -> Extracted: {title} (pageId={page_id})")

        if max_depth >= 0 and depth >= max_depth:
            print(f"  -> Max depth reached, not going deeper.")
            return node

        # Detect direct child pages from sidebar tree
        child_links = _collect_child_page_links(driver, page_id)

        # If no children found, run diagnostic and save it
        if not child_links:
            print(f"  -> No children found, running sidebar diagnostic...")
            diag = _diagnose_sidebar(driver, page_id)
            diag_path = os.path.join(output_root, f"sidebar_diag_{page_id}.json")
            with open(diag_path, "w", encoding="utf-8") as f:
                json.dump(diag, f, ensure_ascii=False, indent=2)
            print(f"  -> Diagnostic saved to {diag_path}")

        print(f"  -> Found {len(child_links)} child page(s)")

        for child_url in child_links:
            child_page_id = _extract_page_id(child_url)
            if child_page_id in visited_page_ids:
                continue
            # Children are stored inside the current page's folder
            child_node = _crawl(child_url, depth + 1, folder_path)
            if child_node is not None:
                node["children"].append(child_node)

        return node

    tree = _crawl(root_url, 0, pages_root)

    summary = {
        "root_url": root_url,
        "space_key": root_space_key,
        "root_page_id": root_page_id,
        "total_pages": len(visited_page_ids),
        "max_depth": max_depth,
        "pages": all_pages,
        "tree": tree,
    }

    index_path = os.path.join(output_root, "crawl_index.json")
    with open(index_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(visited_page_ids)} page(s) extracted -> {index_path}")
    return summary
