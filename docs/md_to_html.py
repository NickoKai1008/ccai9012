#!/usr/bin/env python3
"""
Simple script to convert markdown files to HTML with consistent styling.
Usage: python md_to_html.py [markdown_file]
Or run without arguments to convert all markdown files in docs/

Extra behavior:
- When converting docs/starter_kits.md, also generates per-module subpages under
  docs/starter_kits/ (index.html + m1_gan.html ... m5_bias.html) by splitting
  the markdown on "## Module X:" headings.
- Rewrites relative image paths so they work from subpages.
- Optionally copies referenced local images into docs/starter_kits/.

Configuration:
- Single source of truth: docs/pages.json
"""

import sys
import os
import re
import shutil
from pathlib import Path

import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension

import json

# NOTE: The docs generator uses docs/pages.json only.
# (Legacy config.yaml is no longer used.)

# ----------------------------
# Config loading / validation
# ----------------------------

def _load_site_config(*, docs_dir: Path) -> dict:
    """Load docs/pages.json.

    Single source of truth:
    - `pages` tree defines navigation structure and markdown->html conversion.
    - Starter kits module metadata lives under the Starter Kits node's children
      (node.module).
    """
    cfg_path = docs_dir / "pages.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config file: {cfg_path}")

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {cfg_path}: {e}")

    if not isinstance(cfg, dict):
        raise ValueError("docs/pages.json must be a JSON object")

    if cfg.get("version") != 1:
        raise ValueError("docs/pages.json: unsupported or missing version (expected 1)")

    if "site" not in cfg:
        raise ValueError("docs/pages.json missing required key: site")
    if "pages" not in cfg:
        raise ValueError("docs/pages.json missing required key: pages")
    if not isinstance(cfg["pages"], list):
        raise ValueError("docs/pages.json 'pages' must be a list")

    # Validate the pages tree and enforce unique keys.
    seen_keys: set[str] = set()

    def validate_nodes(nodes: list[dict]):
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("docs/pages.json pages items must be objects")

            key = node.get("key")
            if not key or not isinstance(key, str):
                raise ValueError("docs/pages.json pages node missing string 'key'")
            if key in seen_keys:
                raise ValueError(f"docs/pages.json pages node key is duplicated: {key}")
            seen_keys.add(key)

            href = node.get("href")
            source = node.get("source")
            output = node.get("output")

            if href is not None:
                if not isinstance(href, str) or href.startswith("/") or href.startswith(".."):
                    raise ValueError(f"docs/pages.json pages[{key}].href must be a relative path under docs/: {href!r}")

            if source is not None:
                if not isinstance(source, str):
                    raise ValueError(f"docs/pages.json pages[{key}].source must be a string")
                if output is not None:
                    if not isinstance(output, str) or output.startswith("/") or output.startswith(".."):
                        raise ValueError(f"docs/pages.json pages[{key}].output must be a relative path under docs/: {output!r}")

            module = node.get("module")
            if module is not None:
                if not isinstance(module, dict):
                    raise ValueError(f"docs/pages.json pages[{key}].module must be an object")
                for req in ("number", "filename", "page_title"):
                    if req not in module:
                        raise ValueError(f"docs/pages.json pages[{key}].module missing '{req}'")

            children = node.get("children")
            if children is not None:
                if not isinstance(children, list):
                    raise ValueError(f"docs/pages.json pages[{key}].children must be a list")
                validate_nodes(children)

    validate_nodes(cfg["pages"])

    # Starter kits validation (optional)
    starter = cfg.get("starter_kits")
    if starter is not None and not isinstance(starter, dict):
        raise ValueError("docs/pages.json starter_kits must be an object")

    return cfg


def _flatten_pages_tree(cfg: dict) -> list[dict]:
    """Flatten the pages tree into pre-order list with level + parent information."""
    flat: list[dict] = []

    def walk(nodes: list[dict], *, level: int, parent_key: str | None, inherited_child_class: str | None):
        for node in nodes:
            child_class = node.get("nav_children_class") if isinstance(node.get("nav_children_class"), str) else None
            node_child_class_for_desc = child_class or inherited_child_class
            flat.append({
                "node": node,
                "level": level,
                "parent_key": parent_key,
                "children_class": node_child_class_for_desc,
            })
            children = node.get("children")
            if isinstance(children, list) and children:
                walk(children, level=level + 1, parent_key=node.get("key"), inherited_child_class=node_child_class_for_desc)

    walk(cfg.get("pages", []), level=0, parent_key=None, inherited_child_class=None)
    return flat


def _pages_by_source(cfg: dict) -> dict[str, dict]:
    """Build mapping: markdown source filename -> page config used for conversion."""
    out: dict[str, dict] = {}
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        source = node.get("source")
        if not isinstance(source, str):
            continue
        if source in out:
            raise ValueError(f"docs/pages.json: duplicated source in pages tree: {source}")

        output = node.get("output")
        if not isinstance(output, str) or not output:
            # default output: replace .md with .html at docs root
            output = Path(source).with_suffix(".html").name

        out[source] = {
            "title": node.get("title") or Path(source).stem.replace("_", " ").title(),
            "output": output,
            "nav_key": node.get("key"),
        }

    return out


def _parent_active_map(cfg: dict) -> dict[str, set[str]]:
    """Map a page key -> set of its ancestor keys (for parent highlighting)."""
    ancestors: dict[str, set[str]] = {}

    def walk(nodes: list[dict], stack: list[str]):
        for node in nodes:
            key = node.get("key")
            if isinstance(key, str):
                ancestors[key] = set(stack)
                children = node.get("children")
                if isinstance(children, list) and children:
                    walk(children, stack + [key])

    walk(cfg.get("pages", []), [])
    return ancestors


def _starter_module_config(cfg: dict) -> list[dict]:
    """Return module configs from the Starter Kits subtree.

    Expected structure:
      pages[].key == 'starter' -> children[].module
    """
    starter_node = None
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        if node.get("key") == "starter":
            starter_node = node
            break

    if not starter_node:
        return []

    out: list[dict] = []
    for child in starter_node.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        module = child.get("module")
        if not isinstance(module, dict):
            continue

        try:
            num = int(module.get("number"))
        except Exception:
            continue
        filename = module.get("filename")
        page_title = module.get("page_title")
        if not isinstance(filename, str) or not filename:
            continue
        if not isinstance(page_title, str) or not page_title:
            continue

        out.append({
            "number": num,
            "nav_key": child.get("key"),
            "filename": filename,
            "page_title": page_title,
            "index_summary": module.get("index_summary"),
        })

    # Stable order by module number
    out.sort(key=lambda m: m.get("number", 0))
    return out


# ----------------------------
# HTML template + rendering
# ----------------------------

# NOTE:
# We keep the overall page structure consistent but render the sidebar items
# from docs/pages.json.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{title_full}</title>
    <link rel=\"stylesheet\" href=\"{css_href}\">
</head>
<body>
    <div class=\"container\">
        <nav id=\"sidebar\">
            <div class=\"sidebar-header\">
                <h2>{site_name}</h2>
            </div>
            <ul class=\"nav-menu\">
{nav_items}
            </ul>
        </nav>

        <main id=\"content\">
{content}
        </main>
    </div>
</body>
</html>
"""


def _new_markdown():
    # NOTE: Avoid using nl2br here.
    # nl2br turns every newline into <br>, which breaks Markdown list parsing
    # (e.g., "- item" becomes literal text with <br/> instead of <ul><li>...).
    return markdown.Markdown(extensions=[
        TableExtension(),
        FencedCodeExtension(),
        'sane_lists',
        'smarty',
    ])


def _nav_active_classes(cfg: dict, *, active_key: str | None) -> dict[str, str]:
    """Compute which nav keys should have class=active.

    Uses tree structure to also highlight ancestor items (e.g. Starter Kits parent
    is highlighted when a module subpage is active).
    """
    active: set[str] = set()
    if active_key:
        active.add(active_key)

    # Highlight ancestor nodes too.
    ancestors = _parent_active_map(cfg)
    if active_key and active_key in ancestors:
        active |= ancestors[active_key]

    return {k: ' class="active"' for k in active}


def _render_nav_items(cfg: dict, *, base_href: str, active_key: str | None) -> str:
    active_classes = _nav_active_classes(cfg, active_key=active_key)

    lines: list[str] = []
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        key = node.get("key")
        label = node.get("label") or node.get("title") or key

        href = node.get("href")
        if not isinstance(href, str) or not href:
            # If this node is a markdown-converted page, default its href to output.
            if isinstance(node.get("output"), str) and node.get("output"):
                href = node.get("output")
            elif isinstance(node.get("source"), str) and node.get("source"):
                href = Path(node.get("source")).with_suffix(".html").name
            else:
                # Non-link placeholder: skip it from nav.
                continue

        # Ensure we remain relative.
        if href.startswith("/") or href.startswith(".."):
            continue

        li_class = None
        if entry["level"] > 0:
            li_class = entry.get("children_class")
        li_attr = f' class="{li_class}"' if isinstance(li_class, str) and li_class else ""

        a_active = active_classes.get(key, "") if isinstance(key, str) else ""
        lines.append(f"                <li{li_attr}><a href=\"{base_href}{href}\"{a_active}>{label}</a></li>")

    return "\n".join(lines)


def _render_html(cfg: dict, *, title: str, html_content: str, active_key: str | None, base_href: str, css_href: str):
    site = cfg.get("site") or {}
    site_name = site.get("name") or "CCAI9012"
    title_prefix = site.get("title_prefix") or ""

    return HTML_TEMPLATE.format(
        site_name=site_name,
        title_full=f"{title_prefix}{title}" if title_prefix else title,
        content=html_content,
        nav_items=_render_nav_items(cfg, base_href=base_href, active_key=active_key),
        css_href=css_href,
    )


_IMG_SRC_RE = re.compile(r"(<img\s+[^>]*src=[\"'])([^\"']+)([\"'][^>]*>)", re.IGNORECASE)
_MD_IMG_RE = re.compile(r"(!\[[^]]*]\()([^)]*)(\))")


def _rewrite_relative_asset_paths(md_text: str, *, from_dir: Path, to_dir: Path):
    """Rewrite relative image src/hrefs in markdown so they remain correct after moving."""

    def _rewrite(path_str: str) -> str:
        path_str = path_str.strip()
        if ("://" in path_str) or path_str.startswith("data:") or path_str.startswith("/"):
            return path_str
        if path_str.startswith("#"):
            return path_str
        if path_str.startswith("../"):
            # already relative upwards; leave as-is
            return path_str

        src_abs = (from_dir / path_str).resolve()
        try:
            rel = os.path.relpath(src_abs, to_dir)
        except ValueError:
            # different drives etc.
            rel = str(src_abs)
        return rel.replace(os.sep, "/")

    # HTML <img src>
    md_text = _IMG_SRC_RE.sub(lambda m: f"{m.group(1)}{_rewrite(m.group(2))}{m.group(3)}", md_text)
    # Markdown images ![]()
    md_text = _MD_IMG_RE.sub(lambda m: f"{m.group(1)}{_rewrite(m.group(2))}{m.group(3)}", md_text)
    return md_text


def _collect_local_image_paths(md_text: str):
    paths: set[str] = set()

    for m in _IMG_SRC_RE.finditer(md_text):
        paths.add(m.group(2).strip())
    for m in _MD_IMG_RE.finditer(md_text):
        paths.add(m.group(2).strip())

    local_paths = []
    for p in paths:
        if ("://" in p) or p.startswith("data:") or p.startswith("/") or p.startswith("#"):
            continue
        local_paths.append(p)
    return local_paths


def _copy_local_assets(md_text: str, *, from_dir: Path, to_dir: Path):
    """Copy locally referenced images into to_dir, preserving relative subfolders."""
    for rel_path in _collect_local_image_paths(md_text):
        src = (from_dir / rel_path).resolve()
        if not src.exists() or not src.is_file():
            continue
        dest = (to_dir / rel_path).resolve()
        # ensure we stay inside to_dir
        try:
            dest.relative_to(to_dir.resolve())
        except Exception:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def _split_starter_kits_modules(md_text: str):
    """Return list of (module_number:int, module_title:str, module_md:str)."""
    # Capture full module block until next module or end.
    pat = re.compile(r"^##\s+Module\s+(\d+)\s*:\s*(.+?)\s*$", re.MULTILINE)
    matches = list(pat.finditer(md_text))
    if not matches:
        return []

    modules = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        num = int(m.group(1))
        title = m.group(2).strip()
        block = md_text[start:end].strip() + "\n"
        modules.append((num, title, block))
    return modules


def _generate_starter_kits_subpages(starter_md_path: Path, *, cfg: dict):
    docs_dir = starter_md_path.parent
    starter_cfg = cfg.get("starter_kits") or {}
    out_dir = docs_dir / (starter_cfg.get("output_dir") or "starter_kits")
    out_dir.mkdir(parents=True, exist_ok=True)

    md_text = starter_md_path.read_text(encoding="utf-8")
    modules = _split_starter_kits_modules(md_text)
    if not modules:
        print("Warning: No '## Module X:' sections found; skipping starter_kits subpages", flush=True)
        return

    module_cfgs = _starter_module_config(cfg)
    num_to_cfg = {int(m["number"]): m for m in module_cfgs if isinstance(m.get("number"), int) or isinstance(m.get("number"), bool) is False}

    # From docs/ to docs/starter_kits/
    from_dir = docs_dir
    to_dir = out_dir

    def _rewrite_api_links_for_subpages(s: str) -> str:
        """On subpages (docs/starter_kits/*.html), links like api/xxx.html must become ../api/xxx.html."""
        # Markdown links: [text](api/xxx.html)
        s = re.sub(r"(\()api/", r"\1../api/", s)
        # Raw HTML links: href="api/xxx.html"
        s = re.sub(r"(href=[\"'])api/", r"\1../api/", s)
        return s

    for num, module_title, module_block in modules:
        mcfg = num_to_cfg.get(num)
        if not mcfg:
            continue

        # Make module page content self-contained: keep heading as H1
        module_md = re.sub(r"^##\s+Module\s+\d+\s*:\s*", "# ", module_block, flags=re.MULTILINE)

        # Fix links that must point to sibling ../api/ from docs/starter_kits/*.
        module_md = _rewrite_api_links_for_subpages(module_md)

        # Ensure images work from docs/starter_kits/
        module_md = _rewrite_relative_asset_paths(module_md, from_dir=from_dir, to_dir=to_dir)

        # Copy local images into docs/starter_kits/ as requested (keeps referenced relative paths)
        _copy_local_assets(module_md, from_dir=from_dir, to_dir=to_dir)

        html_body = _new_markdown().convert(module_md)

        full_html = _render_html(
            cfg,
            title=mcfg.get("page_title") or f"Module {num}",
            html_content=html_body,
            active_key=mcfg.get("nav_key"),
            base_href="../",
            css_href=((cfg.get("site") or {}).get("css") or {}).get("subdir_href") or "../docs-style.css",
        )

        filename = mcfg.get("filename") or f"module_{num}.html"
        (out_dir / filename).write_text(full_html, encoding="utf-8")
        print(f"✓ Generated subpage: starter_kits/{filename}", flush=True)


def _starter_kits_index_landing_md(md_text: str, *, cfg: dict) -> str:
    """Generate a landing page markdown for docs/starter_kits/index.html.

    Requirement:
    - Include the content before "## Module 1" from the source markdown at the top
      (this includes images / HTML blocks).
    - Then show only one-line intro per module + a button/link to the module subpage.
    - No detailed per-module content on the index page.

    We keep the title from the source markdown (if present), then render a simple list.
    """
    title_match = re.search(r"^#\s+(.+?)\s*$", md_text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Starter Kits"

    # Grab everything before Module 1 heading (if present)
    m1 = re.search(r"^##\s+Module\s+1\b", md_text, flags=re.MULTILINE)
    preface = md_text[: m1.start()].strip() if m1 else md_text.strip()

    # Remove the first H1 from the preface to avoid duplicating the title (we add our own).
    preface = re.sub(r"^#\s+.+?\s*$", "", preface, count=1, flags=re.MULTILINE).strip()

    modules = _split_starter_kits_modules(md_text)
    if not modules:
        modules = [
            (1, "Traditional Generative ML", ""),
            (2, "LLM for Structuring Information", ""),
            (3, "Multimodal Reasoning", ""),
            (4, "CV Models", ""),
            (5, "Bias Detection & Interpretability", ""),
        ]

    module_cfgs = _starter_module_config(cfg)
    num_to_cfg = {int(m["number"]): m for m in module_cfgs if "number" in m}

    parts: list[str] = [
        f"# {title}",
        "",
    ]

    # Include preface (images/HTML included) at the very top.
    if preface:
        parts.extend([preface, "", "---", ""])  # small separator before cards

    parts.extend([
        "Pick one module to view details and starter code.",
        "",
        "<style>",
        ".module-card{border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;margin:12px 0;background:#fff}",
        ".module-card h3{margin:0 0 6px 0}",
        ".module-card p{margin:0 0 10px 0;color:#374151}",
        "</style>",
        "",
    ])

    for num, module_title, _ in modules:
        mcfg = num_to_cfg.get(num, {})
        summary = mcfg.get("index_summary") or "Module overview."
        href = mcfg.get("filename") or "index.html"
        parts.append(
            "\n".join([
                '<div class="module-card">',
                f"  <h3>Module {num}: {module_title}</h3>",
                f"  <p>{summary}</p>",
                f"  <a class=\"btn\" href=\"{href}\">Open Module</a>",
                "</div>",
            ])
        )

    parts.append("")
    return "\n".join(parts)


def _infer_module_api_mapping_from_markdown(starter_md_text: str):
    """Infer mapping from starter_kits.md.

    Returns:
        module_to_api: dict[int, list[str]]  (api module basenames like 'gan_utils')
        api_to_modules: dict[str, list[int]]
    """
    module_to_api: dict[int, set[str]] = {}
    cur_module: int | None = None

    for line in starter_md_text.splitlines():
        m = re.match(r"^##\s+Module\s+(\d+)\b", line)
        if m:
            cur_module = int(m.group(1))
            module_to_api.setdefault(cur_module, set())

        if cur_module is None:
            continue

        for api in re.findall(r"\(api/([A-Za-z0-9_]+)\.html\)", line):
            module_to_api.setdefault(cur_module, set()).add(api)

    module_to_api_list: dict[int, list[str]] = {k: sorted(v) for k, v in module_to_api.items()}

    api_to_modules: dict[str, set[int]] = {}
    for mod, apis in module_to_api_list.items():
        for api in apis:
            api_to_modules.setdefault(api, set()).add(mod)

    api_to_modules_list: dict[str, list[int]] = {k: sorted(v) for k, v in api_to_modules.items()}
    return module_to_api_list, api_to_modules_list


def _inject_starterkit_backlinks_into_api_pages(*, docs_dir: Path, cfg: dict):
    """Inject backlinks into docs/api/*.html based on starter_kits.md.

    This avoids hardcoding the mapping: the links are derived from the markdown itself.
    """
    starter_cfg = cfg.get("starter_kits") or {}
    starter_md = docs_dir / (starter_cfg.get("source") or "starter_kits.md")
    api_dir = docs_dir / "api"
    if not starter_md.exists() or not api_dir.exists():
        return

    md_text = starter_md.read_text(encoding="utf-8")
    _, api_to_modules = _infer_module_api_mapping_from_markdown(md_text)

    # Map module number -> starter_kits subpage filename (from config)
    num_to_file = {}
    for m in _starter_module_config(cfg):
        try:
            num_to_file[int(m.get("number"))] = m.get("filename")
        except Exception:
            continue

    def build_links(module_nums: list[int]) -> str:
        items = []
        for n in module_nums:
            fn = num_to_file.get(n) or "index.html"
            href = f"../starter_kits/{fn}"
            items.append(f'<li><a href="{href}">Starter Kit Module {n}</a></li>')
        return "\n".join(items)

    def _strip_legacy_module_nav(html: str) -> str:
        # Some API pages previously had a hardcoded top-left back button container:
        # <div class="module-nav"> ... </div>
        # Remove it for consistent navigation.
        return re.sub(r"\n?\s*<div class=\"module-nav\">.*?</div>\s*\n?", "\n", html, flags=re.DOTALL)

    def upsert_section(html: str, section_html: str) -> str:
        """Insert or replace a small marked block inside <main id=\"content\" ...>."""
        start_mark = "<!-- STARTERKIT_BACKLINKS_START -->"
        end_mark = "<!-- STARTERKIT_BACKLINKS_END -->"
        block = f"{start_mark}\n{section_html}\n{end_mark}"

        # Always remove any legacy nav blocks first.
        html = _strip_legacy_module_nav(html)

        if start_mark in html and end_mark in html:
            return re.sub(rf"{re.escape(start_mark)}.*?{re.escape(end_mark)}", block, html, flags=re.DOTALL)

        # default insertion point: right after the intro section or header
        # try to insert after </header> if present, else after <main ...>
        if "</header>" in html:
            return html.replace("</header>", "</header>\n" + block, 1)

        m = re.search(r"(<main[^>]*id=\"content\"[^>]*>)", html)
        if m:
            insert_at = m.end()
            return html[:insert_at] + "\n" + block + html[insert_at:]

        return html + "\n" + block

    # Update each api module page that is referenced from starter_kits
    for api_name, module_nums in api_to_modules.items():
        api_path = api_dir / f"{api_name}.html"
        if not api_path.exists():
            continue

        html = api_path.read_text(encoding="utf-8", errors="replace")

        section_html = "\n".join([
            '<section class="starterkit-backlinks" style="margin-top:1.5rem; padding:1rem; border:1px solid #e5e7eb; border-radius:10px; background:#fff">',
            '  <h2 style="margin-top:0">Related Starter Kit(s)</h2>',
            '  <ul>',
            build_links(module_nums),
            '  </ul>',
            '</section>',
        ])

        new_html = upsert_section(html, section_html)
        api_path.write_text(new_html, encoding="utf-8")


def _render_home_cards_section(cfg: dict) -> str:
    """Render the Home page 'quick links' card grid from the pages tree.

    pages.json is the single source of truth:
    - Any page node can opt in by setting:
        "home_card": {"show": true, "order": 1, ...}
    - The section heading is controlled by the Home node:
        pages[key=="home"].home_cards_title
    """

    # Find Home node to get title
    home_title = "Documentation"
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        if node.get("key") == "home":
            t = node.get("home_cards_title")
            if isinstance(t, str) and t.strip():
                home_title = t.strip()
            break

    # Build mapping from page key -> href (output/href)
    key_to_href: dict[str, str] = {}
    key_to_node: dict[str, dict] = {}
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        key = node.get("key")
        if not isinstance(key, str):
            continue

        href = node.get("href")
        if not isinstance(href, str) or not href:
            if isinstance(node.get("output"), str) and node.get("output"):
                href = node.get("output")
            elif isinstance(node.get("source"), str) and node.get("source"):
                href = Path(node.get("source")).with_suffix(".html").name
            else:
                href = ""

        # keep only safe relative links
        if href and (href.startswith("/") or href.startswith("..")):
            href = ""

        if href:
            key_to_href[key] = href
            key_to_node[key] = node

    # Collect card nodes
    cards: list[dict] = []
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        key = node.get("key")
        if not isinstance(key, str):
            continue

        hc = node.get("home_card")
        if not isinstance(hc, dict) or not hc.get("show"):
            continue

        href = key_to_href.get(key)
        if not href:
            # no link target; silently skip
            continue

        order = hc.get("order")
        try:
            order_val = int(order) if order is not None else 10_000
        except Exception:
            order_val = 10_000

        # home_card.title is optional and can inherit from page metadata.
        # Treat empty/whitespace as missing.
        hc_title = hc.get("title")
        if isinstance(hc_title, str):
            hc_title = hc_title.strip()
        if not hc_title:
            hc_title = node.get("title") or node.get("label") or key

        cards.append({
            "key": key,
            "order": order_val,
            "icon": hc.get("icon") if isinstance(hc.get("icon"), str) else "",
            "title": hc_title,
            "description": hc.get("description") if isinstance(hc.get("description"), str) else "",
            "button": hc.get("button") if isinstance(hc.get("button"), str) else "Open →",
            "href": href,
        })

    if not cards:
        return ""

    cards.sort(key=lambda c: (c["order"], c["key"]))

    # Render
    lines: list[str] = []
    lines.append('<section class="quick-links">')
    lines.append(f"  <h2>{home_title}</h2>")
    lines.append('  <div class="card-grid">')

    for c in cards:
        lines.append('    <div class="card">')
        lines.append(f"      <h3>{c['icon']} {c['title']}</h3>".replace("  ", " "))
        if c["description"]:
            lines.append(f"      <p>{c['description']}</p>")
        lines.append(f"      <a href=\"{c['href']}\" class=\"btn\">{c['button']}</a>")
        lines.append("    </div>")

    lines.append("  </div>")
    lines.append("</section>")

    return "\n".join(lines)


def convert_md_to_html(md_file_path, output_dir=None):
    """Convert a markdown file to HTML with styling"""

    docs_dir = Path(__file__).parent
    cfg = _load_site_config(docs_dir=docs_dir)

    md_file = Path(md_file_path)
    if not md_file.exists():
        print(f"Error: File {md_file} not found", flush=True)
        return False

    # Read markdown content
    md_content = md_file.read_text(encoding='utf-8')

    # Get page configuration from the tree
    pages_by_source = _pages_by_source(cfg)
    config = pages_by_source.get(md_file.name)
    if not config:
        print(f"Warning: No configuration found for {md_file.name}, using defaults", flush=True)
        title = md_file.stem.replace('_', ' ').title()
        html_filename = md_file.stem + '.html'
        active_key = None
    else:
        title = config['title']
        html_filename = config['output']
        active_key = config.get('nav_key')

    # Convert markdown to HTML
    starter_source = (cfg.get("starter_kits") or {}).get("source") or "starter_kits.md"
    if md_file.name == starter_source:
        md_for_index = _starter_kits_index_landing_md(md_content, cfg=cfg)

        # IMPORTANT: index.html lives in docs/starter_kits/, so rewrite image paths accordingly
        # (e.g., figs/... -> ../figs/...) and copy any referenced assets.
        out_dir = docs_dir / ((cfg.get("starter_kits") or {}).get("output_dir") or "starter_kits")
        out_dir.mkdir(parents=True, exist_ok=True)

        md_for_index = _rewrite_relative_asset_paths(md_for_index, from_dir=docs_dir, to_dir=out_dir)
        _copy_local_assets(md_for_index, from_dir=docs_dir, to_dir=out_dir)

        html_content = _new_markdown().convert(md_for_index)
    else:
        html_content = _new_markdown().convert(md_content)

    # Home page: append cards section driven by pages.json
    if md_file.name == "index.md":
        cards_html = _render_home_cards_section(cfg)
        if cards_html:
            html_content = "\n".join([
                '<header></header>' if not html_content.strip().startswith('<header') else "",
                html_content,
                cards_html,
            ]).replace('<header></header>\n', '')

    # Determine output path
    if output_dir:
        output_path = Path(output_dir) / html_filename
    else:
        # Default: output under docs/ respecting any subdirectories in html_filename.
        output_path = md_file.parent / html_filename

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Pick correct relative links for top-level vs subdir pages.
    is_in_subdir = output_path.parent != md_file.parent

    site_css = (cfg.get("site") or {}).get("css") or {}

    full_html = _render_html(
        cfg,
        title=title,
        html_content=html_content,
        active_key=active_key,
        base_href="../" if is_in_subdir else "",
        css_href=site_css.get("subdir_href") if is_in_subdir else site_css.get("top_level_href"),
    )

    # Write HTML file
    output_path.write_text(full_html, encoding='utf-8')

    print(f"✓ Converted: {md_file.name} → {output_path}", flush=True)

    # Special: starter_kits.md -> also generate module subpages
    if md_file.name == starter_source:
        _generate_starter_kits_subpages(md_file, cfg=cfg)
        # And add backlinks from API pages back to the relevant starter kits.
        _inject_starterkit_backlinks_into_api_pages(docs_dir=md_file.parent, cfg=cfg)

    return True


def convert_all_docs():
    """Convert markdown files referenced by docs/pages.json.

    This keeps the website output deterministic and avoids publishing unlisted
    markdown files (e.g., docs/README.md) unless they are explicitly added to
    pages.json.
    """
    docs_dir = Path(__file__).parent
    cfg = _load_site_config(docs_dir=docs_dir)

    pages_by_source = _pages_by_source(cfg)
    md_files: list[Path] = []

    for source in pages_by_source.keys():
        p = docs_dir / source
        if p.exists():
            md_files.append(p)
        else:
            print(f"Warning: pages.json references missing markdown: {source}", flush=True)

    # Also include starter_kits source if configured but not present in pages tree
    starter_cfg = cfg.get("starter_kits") or {}
    starter_source = starter_cfg.get("source")
    if isinstance(starter_source, str) and starter_source:
        p = docs_dir / starter_source
        if p.exists() and p not in md_files:
            md_files.append(p)

    if not md_files:
        print("No markdown files found from docs/pages.json", flush=True)
        return

    print(f"Found {len(md_files)} markdown file(s) from pages.json", flush=True)
    print("-" * 50, flush=True)

    success_count = 0
    for md_file in md_files:
        if convert_md_to_html(md_file):
            success_count += 1

    print("-" * 50, flush=True)
    print(f"Converted {success_count}/{len(md_files)} files successfully", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Convert specific file
        md_file = sys.argv[1]
        convert_md_to_html(md_file)
    else:
        # Convert all markdown files
        convert_all_docs()
