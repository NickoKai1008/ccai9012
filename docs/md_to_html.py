#!/usr/bin/env python3
"""
Simple script to convert markdown files to HTML with consistent styling.
Usage: python md_to_html.py [markdown_file]
Or run without arguments to convert all markdown files in docs/

Docs structure (new):
- Markdown sources live under docs/md/
- Generated HTML lives under docs/html/
- Assets (figs/, docs-style.css, api/) currently remain under docs/ (legacy) unless configured otherwise.

Extra behavior:
- When converting the Starter Kits source, can generate per-module starter kit pages.
  In the new layout, this means generating markdown pages under docs/md/starter_kits/
  (index.md + m1_gan.md ... m5_bias.md) so they correspond 1:1 with HTML outputs.

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

def _ensure_dirs(*, docs_dir: Path) -> tuple[Path, Path]:
    """Return (md_root, html_root), creating them if missing."""
    md_root = docs_dir / "md"
    html_root = docs_dir / "html"
    md_root.mkdir(parents=True, exist_ok=True)
    html_root.mkdir(parents=True, exist_ok=True)
    return md_root, html_root


def _rel_to_root(p: Path, root: Path) -> str:
    """Relative path from root using POSIX separators."""
    return p.resolve().relative_to(root.resolve()).as_posix()


def _base_href_for_output(*, output_path: Path, html_root: Path) -> str:
    """Compute base href prefix to reach html_root from output_path.parent."""
    rel_parent = output_path.parent.resolve().relative_to(html_root.resolve())
    depth = len(rel_parent.parts)
    return "../" * depth


def _css_href_for_output(*, cfg: dict, output_path: Path, html_root: Path, docs_dir: Path) -> str:
    """Compute css href for output page.

    Supports both:
      - site.css.path == "docs-style.css" (preferred; relative to html_root)
      - legacy site.css.top_level_href/subdir_href (relative to docs root)
    """
    site_css = (cfg.get("site") or {}).get("css") or {}

    css_path = site_css.get("path")
    if isinstance(css_path, str) and css_path.strip():
        return _base_href_for_output(output_path=output_path, html_root=html_root) + css_path.strip()

    legacy = site_css.get("subdir_href") if output_path.parent != html_root else site_css.get("top_level_href")
    if not isinstance(legacy, str) or not legacy:
        legacy = "docs-style.css"

    legacy_abs = (docs_dir / legacy).resolve()
    try:
        rel = os.path.relpath(legacy_abs, output_path.parent.resolve())
    except ValueError:
        rel = str(legacy_abs)
    return rel.replace(os.sep, "/")


def _rewrite_relative_links_in_markdown(md_text: str, *, from_dir: Path, to_dir: Path, docs_dir: Path, html_root: Path):
    """Rewrite markdown/HTML links that assume docs-root locations.

    We want authoring convenience in docs/md/*.
    Today, docs/api and docs/figs are still under docs/ (legacy), so links like:
      - api/gan_utils.html
      - figs/img.png
    must be rewritten to correct relative paths from the output html location.

    Notes:
    - Images are also handled by _rewrite_relative_asset_paths; this mainly targets href links.
    """

    def _rewrite_href(path_str: str) -> str:
        path_str = path_str.strip()
        if ("://" in path_str) or path_str.startswith("data:") or path_str.startswith("/"):
            return path_str
        if path_str.startswith("#"):
            return path_str

        if path_str.startswith("api/") or path_str.startswith("figs/"):
            src_abs = (docs_dir / path_str).resolve()
            try:
                rel = os.path.relpath(src_abs, to_dir)
            except ValueError:
                rel = str(src_abs)
            return rel.replace(os.sep, "/")

        return path_str

    md_text = re.sub(
        r"(\[[^]]*]\()(.*?)(\))",
        lambda m: f"{m.group(1)}{_rewrite_href(m.group(2))}{m.group(3)}",
        md_text,
    )
    md_text = re.sub(
        r"(href=[\"'])([^\"']+)([\"'])",
        lambda m: f"{m.group(1)}{_rewrite_href(m.group(2))}{m.group(3)}",
        md_text,
    )
    return md_text

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
    """Build mapping: markdown source relative path -> page config used for conversion."""
    out: dict[str, dict] = {}
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        source = node.get("source")
        if not isinstance(source, str):
            continue

        # Normalize to POSIX-style relative paths (as used in JSON)
        source_key = Path(source).as_posix()

        if source_key in out:
            raise ValueError(f"docs/pages.json: duplicated source in pages tree: {source_key}")

        output = node.get("output")
        if not isinstance(output, str) or not output:
            # default output: replace .md with .html at docs root
            output = Path(source_key).with_suffix(".html").as_posix()

        out[source_key] = {
            "title": node.get("title") or Path(source_key).stem.replace("_", " ").title(),
            "output": Path(output).as_posix(),
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


_DEF_DOCS_ROOT_ASSET_PREFIXES = ("figs/", "api/")


def _rewrite_relative_asset_paths(md_text: str, *, from_dir: Path, to_dir: Path, docs_dir: Path | None = None):
    """Rewrite relative image src/hrefs in markdown so they remain correct after moving.

    Special handling:
    - Paths starting with 'figs/' (and optionally 'api/') are treated as docs-root assets
      (docs/figs, docs/api) rather than relative to the markdown file directory.
    """

    def _rewrite(path_str: str) -> str:
        path_str = path_str.strip()
        if ("://" in path_str) or path_str.startswith("data:") or path_str.startswith("/"):
            return path_str
        if path_str.startswith("#"):
            return path_str
        if path_str.startswith("../"):
            # already relative upwards; leave as-is
            return path_str

        # Docs-root assets
        if docs_dir is not None and any(path_str.startswith(p) for p in _DEF_DOCS_ROOT_ASSET_PREFIXES):
            src_abs = (docs_dir / path_str).resolve()
        else:
            src_abs = (from_dir / path_str).resolve()

        try:
            rel = os.path.relpath(src_abs, to_dir)
        except ValueError:
            rel = str(src_abs)
        return rel.replace(os.sep, "/")

    md_text = _IMG_SRC_RE.sub(lambda m: f"{m.group(1)}{_rewrite(m.group(2))}{m.group(3)}", md_text)
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


# NOTE: Legacy starter_kits HTML subpage generator is no longer used in the new md/html layout.
# We keep starter_kits splitting utilities and generate markdown pages instead.

# (Deleted) def _generate_starter_kits_subpages(...)


def _starter_kits_index_landing_md(md_text: str, *, cfg: dict) -> str:
    """Generate a landing page markdown for starter_kits/index.

    Why previously it looked "HTML style":
    - We used raw <div>/<style> cards to match the site's CSS buttons without extra markdown extensions.

    New behavior:
    - Keep it as pure Markdown (plus existing preface HTML blocks/images from the legacy source),
      so the md files look like md and stay editable.
    - Link targets remain as HTML filenames (m1_gan.html, ...) because the navigation is for the generated site.
    """
    title_match = re.search(r"^#\s+(.+?)\s*$", md_text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Starter Kits"

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

    parts: list[str] = [f"# {title}", ""]

    if preface:
        parts.extend([preface, "", "---", ""])

    parts.extend([
        "Pick one module to view details and starter code.",
        "",
    ])

    for num, module_title, _ in modules:
        mcfg = num_to_cfg.get(num, {})
        summary = mcfg.get("index_summary") or "Module overview."
        href = mcfg.get("filename") or "index.html"
        parts.append(f"## Module {num}: {module_title}")
        parts.append("")
        parts.append(summary)
        parts.append("")
        parts.append(f"[Open Module →]({href})")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


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


def _inject_starterkit_backlinks_into_api_pages(*, docs_dir: Path, cfg: dict, html_root: Path):
    """Inject backlinks into docs/html/api/*.html based on starter kits source.

    Canonical source is docs/md/starter_kits.md (if present), fallback to legacy.
    """
    md_root, _ = _ensure_dirs(docs_dir=docs_dir)

    starter_cfg = cfg.get("starter_kits") or {}

    starter_md_candidates = [
        md_root / (starter_cfg.get("source") or "starter_kits.md"),
        docs_dir / (starter_cfg.get("source") or "starter_kits.md"),
    ]
    starter_md = next((p for p in starter_md_candidates if p.exists()), None)

    api_dir = html_root / "api"
    if starter_md is None or not api_dir.exists():
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

    def build_links(module_nums: list[int], *, api_page_dir: Path) -> str:
        items = []
        for n in module_nums:
            fn = num_to_file.get(n) or "index.html"
            dest_abs = (html_root / "starter_kits" / fn).resolve()
            try:
                href = os.path.relpath(dest_abs, api_page_dir.resolve())
            except ValueError:
                href = str(dest_abs)
            href = href.replace(os.sep, "/")
            items.append(f'<li><a href="{href}">Starter Kit Module {n}</a></li>')
        return "\n".join(items)

    def _strip_legacy_module_nav(html: str) -> str:
        return re.sub(r"\n?\s*<div class=\"module-nav\">.*?</div>\s*\n?", "\n", html, flags=re.DOTALL)

    def upsert_section(html: str, section_html: str) -> str:
        start_mark = "<!-- STARTERKIT_BACKLINKS_START -->"
        end_mark = "<!-- STARTERKIT_BACKLINKS_END -->"
        block = f"{start_mark}\n{section_html}\n{end_mark}"

        html = _strip_legacy_module_nav(html)

        if start_mark in html and end_mark in html:
            return re.sub(rf"{re.escape(start_mark)}.*?{re.escape(end_mark)}", block, html, flags=re.DOTALL)

        if "</header>" in html:
            return html.replace("</header>", "</header>\n" + block, 1)

        m = re.search(r"(<main[^>]*id=\"content\"[^>]*>)", html)
        if m:
            insert_at = m.end()
            return html[:insert_at] + "\n" + block + html[insert_at:]

        return html + "\n" + block

    for api_name, module_nums in api_to_modules.items():
        api_path = api_dir / f"{api_name}.html"
        if not api_path.exists():
            continue

        html = api_path.read_text(encoding="utf-8", errors="replace")

        section_html = "\n".join([
            '<section class="starterkit-backlinks" style="margin-top:1.5rem; padding:1rem; border:1px solid #e5e7eb; border-radius:10px; background:#fff">',
            '  <h2 style="margin-top:0">Related Starter Kit(s)</h2>',
            '  <ul>',
            build_links(module_nums, api_page_dir=api_path.parent),
            '  </ul>',
            '</section>',
        ])

        new_html = upsert_section(html, section_html)
        api_path.write_text(new_html, encoding="utf-8")


def _write_text(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _generate_starter_kits_md_pages(*, docs_dir: Path, md_root: Path, cfg: dict) -> list[Path]:
    """Generate starter_kits markdown pages under docs/md/starter_kits/.

    Canonical behavior:
    - Use docs/md/starter_kits.md as the "single source" if it exists.
    - Otherwise, migrate from legacy docs/starter_kits.md into docs/md/starter_kits.md first.

    Output:
      docs/md/starter_kits/index.md
      docs/md/starter_kits/m1_gan.md ...
    """
    starter_cfg = cfg.get("starter_kits") or {}
    source_rel = starter_cfg.get("source") or "starter_kits.md"

    canonical_source = (md_root / source_rel)
    legacy_source = (docs_dir / source_rel)

    if canonical_source.exists():
        src_path = canonical_source
    elif legacy_source.exists():
        # migrate legacy -> canonical
        canonical_source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_source, canonical_source)
        src_path = canonical_source
    else:
        return []

    md_text = src_path.read_text(encoding="utf-8")

    out_dir = md_root / (starter_cfg.get("output_dir") or "starter_kits")
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []

    index_md = _starter_kits_index_landing_md(md_text, cfg=cfg)
    index_path = out_dir / "index.md"
    _write_text(index_path, index_md)
    created.append(index_path)

    modules = _split_starter_kits_modules(md_text)
    if not modules:
        return created

    module_cfgs = _starter_module_config(cfg)
    num_to_cfg = {int(m["number"]): m for m in module_cfgs if "number" in m}

    for num, _module_title, module_block in modules:
        mcfg = num_to_cfg.get(num)
        if not mcfg:
            continue

        module_md = re.sub(r"^##\s+Module\s+\d+\s*:\s*", "# ", module_block, flags=re.MULTILINE)
        if not module_md.endswith("\n"):
            module_md += "\n"

        html_filename = mcfg.get("filename") or f"module_{num}.html"
        md_filename = Path(html_filename).with_suffix(".md").name

        module_path = out_dir / md_filename
        _write_text(module_path, module_md)
        created.append(module_path)

    return created


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

    md_root, html_root = _ensure_dirs(docs_dir=docs_dir)

    # Ensure style is available under docs/html
    _ensure_site_css_available(docs_dir=docs_dir, html_root=html_root, cfg=cfg)

    md_file = Path(md_file_path)
    if not md_file.exists():
        print(f"Error: File {md_file} not found", flush=True)
        return False

    # Support passing either a path under docs/md or a legacy path under docs/.
    md_file_res = md_file.resolve()
    if not str(md_file_res).startswith(str(md_root.resolve())):
        # Try interpreting it as relative to md_root.
        candidate = (md_root / md_file_path).resolve()
        if candidate.exists():
            md_file = candidate
        else:
            md_file = md_file_res

    # Read markdown content
    md_content = md_file.read_text(encoding='utf-8')

    # Get page configuration from the tree (lookup by relative path under md_root)
    pages_by_source = _pages_by_source(cfg)

    try:
        source_key = _rel_to_root(md_file, md_root)
    except Exception:
        source_key = Path(md_file.name).as_posix()

    config = pages_by_source.get(source_key)
    if not config:
        print(f"Warning: No configuration found for {source_key}, using defaults", flush=True)
        title = md_file.stem.replace('_', ' ').title()
        html_rel = Path(source_key).with_suffix(".html").as_posix()
        active_key = None
    else:
        title = config['title']
        html_rel = config['output']
        active_key = config.get('nav_key')

    # Determine output path
    if output_dir:
        output_path = Path(output_dir) / html_rel
    else:
        output_path = (html_root / html_rel)

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Rewrite links so they work from output HTML directory
    md_for_render = md_content

    # Rewrite things that are relative to docs/ (like api/, figs/) into correct relative paths.
    md_for_render = _rewrite_relative_links_in_markdown(
        md_for_render,
        from_dir=md_file.parent,
        to_dir=output_path.parent,
        docs_dir=docs_dir,
        html_root=html_root,
    )

    # Rewrite images when the html lives in a different folder than md source.
    md_for_render = _rewrite_relative_asset_paths(
        md_for_render,
        from_dir=md_file.parent,
        to_dir=output_path.parent,
        docs_dir=docs_dir,
    )

    # Copy referenced local assets into the target html directory.
    _copy_local_assets(md_for_render, from_dir=md_file.parent, to_dir=output_path.parent)

    # Convert markdown to HTML
    html_content = _new_markdown().convert(md_for_render)

    # Home page: append cards section driven by pages.json
    if source_key == "index.md":
        cards_html = _render_home_cards_section(cfg)
        if cards_html:
            html_content = "\n".join([
                '<header></header>' if not html_content.strip().startswith('<header') else "",
                html_content,
                cards_html,
            ]).replace('<header></header>\n', '')

    base_href = _base_href_for_output(output_path=output_path, html_root=html_root)
    css_href = _css_href_for_output(cfg=cfg, output_path=output_path, html_root=html_root, docs_dir=docs_dir)

    full_html = _render_html(
        cfg,
        title=title,
        html_content=html_content,
        active_key=active_key,
        base_href=base_href,
        css_href=css_href,
    )

    # Write HTML file
    output_path.write_text(full_html, encoding='utf-8')

    print(f"✓ Converted: {source_key} → {output_path}", flush=True)

    return True


def _copy_tree(src: Path, dst: Path):
    """Copy a directory tree to dst (overwriting changed files)."""
    if not src.exists() or not src.is_dir():
        return
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        out = dst / rel
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)


def _migrate_api_to_html(*, docs_dir: Path, html_root: Path):
    """Copy docs/api -> docs/html/api.

    API docs are treated as static HTML produced elsewhere, so we copy them into the site root.
    """
    src = docs_dir / "api"
    dst = html_root / "api"
    dst.mkdir(parents=True, exist_ok=True)
    _copy_tree(src, dst)


def _ensure_site_css_available(*, docs_dir: Path, html_root: Path, cfg: dict):
    """Copy the site CSS into docs/html so all pages can reference it reliably.

    After the folder refactor, our generated pages live under docs/html/.
    So the simplest invariant is:
      - the stylesheet must be present at docs/html/<site.css.path>

    Source of truth remains docs/docs-style.css.
    """
    site_css = (cfg.get("site") or {}).get("css") or {}
    css_rel = site_css.get("path") if isinstance(site_css.get("path"), str) and site_css.get("path").strip() else "docs-style.css"
    css_rel = css_rel.strip().lstrip("/")

    src = docs_dir / "docs-style.css"
    if not src.exists():
        # Nothing to copy.
        return

    dst = html_root / css_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _patch_api_html_css_links(*, html_root: Path, cfg: dict):
    """Rewrite API html pages to reference the same site stylesheet.

    API pages are copied as static HTML into docs/html/api.
    We ensure they link to ../<site.css.path>.
    """
    site_css = (cfg.get("site") or {}).get("css") or {}
    css_rel = site_css.get("path") if isinstance(site_css.get("path"), str) and site_css.get("path").strip() else "docs-style.css"
    css_rel = css_rel.strip().lstrip("/")

    api_dir = html_root / "api"
    if not api_dir.exists():
        return

    target_href = "../" + css_rel
    pat = re.compile(
        r'(<link\s+rel=["\']stylesheet["\']\s+href=["\'])([^"\']*docs-style\.css)(["\'])',
        re.IGNORECASE,
    )

    for p in api_dir.glob("*.html"):
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if "docs-style.css" not in html:
            continue

        new_html, n = pat.subn(r"\1" + target_href + r"\3", html, count=1)
        if n:
            p.write_text(new_html, encoding="utf-8")


def convert_all_docs():
    """Convert markdown files referenced by docs/pages.json."""
    docs_dir = Path(__file__).parent
    cfg = _load_site_config(docs_dir=docs_dir)

    md_root, html_root = _ensure_dirs(docs_dir=docs_dir)

    # Ensure style is available under docs/html
    _ensure_site_css_available(docs_dir=docs_dir, html_root=html_root, cfg=cfg)

    # Ensure starter kits markdown pages exist
    _generate_starter_kits_md_pages(docs_dir=docs_dir, md_root=md_root, cfg=cfg)

    # move/copy API docs under the generated site root
    _migrate_api_to_html(docs_dir=docs_dir, html_root=html_root)

    # Patch API pages to point at the unified stylesheet
    _patch_api_html_css_links(html_root=html_root, cfg=cfg)

    pages_by_source = _pages_by_source(cfg)
    md_files: list[Path] = []

    for source in pages_by_source.keys():
        p = md_root / source
        if p.exists():
            md_files.append(p)
        else:
            print(f"Warning: pages.json references missing markdown under docs/md: {source}", flush=True)

    if not md_files:
        print("No markdown files found from docs/pages.json", flush=True)
        return

    print(f"Found {len(md_files)} markdown file(s) from pages.json", flush=True)
    print("-" * 50, flush=True)

    success_count = 0
    for md_file in md_files:
        if convert_md_to_html(md_file):
            success_count += 1

    # Update backlinks from API pages back to the relevant starter kits.
    _inject_starterkit_backlinks_into_api_pages(docs_dir=docs_dir, cfg=cfg, html_root=html_root)

    print("-" * 50, flush=True)
    print(f"Converted {success_count}/{len(md_files)} files successfully", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        md_file = sys.argv[1]
        convert_md_to_html(md_file)
    else:
        convert_all_docs()
