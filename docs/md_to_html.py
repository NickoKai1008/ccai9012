#!/usr/bin/env python3
"""docs/md_to_html.py

Single-purpose docs builder:
- Convert Markdown sources under docs/md/ into HTML pages under docs/.
- Navigation and page mapping are driven by docs/pages.json.

Non-goals (by design):
- No rewriting of markdown links or asset paths. Markdown should already contain
  correct relative links for the final HTML output structure.
- No starter-kit splitting/generation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import markdown
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension


def _ensure_dirs(*, docs_dir: Path) -> tuple[Path, Path]:
    """Return (md_root, site_root), creating them if missing.

    md_root: docs/md (markdown sources)
    site_root: docs/ (final site root where index.html lives and all HTML is generated)
    """
    md_root = docs_dir / "md"
    site_root = docs_dir
    md_root.mkdir(parents=True, exist_ok=True)
    site_root.mkdir(parents=True, exist_ok=True)
    return md_root, site_root


def _rel_to_root(p: Path, root: Path) -> str:
    """Relative path from root using POSIX separators."""
    return p.resolve().relative_to(root.resolve()).as_posix()


def _base_href_for_output(*, output_path: Path, site_root: Path) -> str:
    """Compute base href prefix to reach site_root from output_path.parent.

    site_root must be the *true* website root (docs/), not docs/html/.
    """
    rel_parent = output_path.parent.resolve().relative_to(site_root.resolve())
    depth = len(rel_parent.parts)
    return "../" * depth


def _css_href_for_output(*, cfg: dict, output_path: Path, site_root: Path, docs_dir: Path) -> str:
    """Compute css href for output page.

    Supports both:
      - site.css.path == "docs-style.css" (preferred; relative to site_root)
      - legacy site.css.top_level_href/subdir_href (relative to docs root)
    """
    site_css = (cfg.get("site") or {}).get("css") or {}

    css_path = site_css.get("path")
    if isinstance(css_path, str) and css_path.strip():
        return _base_href_for_output(output_path=output_path, site_root=site_root) + css_path.strip()

    # Legacy behavior: treat docs_dir as the root (same as site_root).
    legacy = site_css.get("subdir_href") if output_path.parent != site_root else site_css.get("top_level_href")
    if not isinstance(legacy, str) or not legacy:
        legacy = "docs-style.css"

    legacy_abs = (docs_dir / legacy).resolve()
    try:
        rel = os.path.relpath(legacy_abs, output_path.parent.resolve())
    except ValueError:
        rel = str(legacy_abs)
    return rel.replace(os.sep, "/")


def _load_site_config(*, docs_dir: Path) -> dict:
    """Load docs/pages.json (single source of truth)."""
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

    # Validate tree and enforce unique keys.
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
                    if not isinstance(output, str) or output.startswith("/"):
                        raise ValueError(
                            f"docs/pages.json pages[{key}].output must be a relative path: {output!r}"
                        )

            children = node.get("children")
            if children is not None:
                if not isinstance(children, list):
                    raise ValueError(f"docs/pages.json pages[{key}].children must be a list")
                validate_nodes(children)

    validate_nodes(cfg["pages"])
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

        source_key = Path(source).as_posix()
        if source_key in out:
            raise ValueError(f"docs/pages.json: duplicated source in pages tree: {source_key}")

        output = node.get("output")
        if not isinstance(output, str) or not output:
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


def _new_markdown() -> markdown.Markdown:
    # NOTE: Avoid using nl2br here (it breaks list parsing).
    return markdown.Markdown(extensions=[
        TableExtension(),
        FencedCodeExtension(),
        "sane_lists",
        "smarty",
    ])


def _nav_active_classes(cfg: dict, *, active_key: str | None) -> dict[str, str]:
    """Compute which nav keys should have class=active (including ancestors)."""
    active: set[str] = set()
    if active_key:
        active.add(active_key)

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
            if isinstance(node.get("output"), str) and node.get("output"):
                href = node.get("output")
            elif isinstance(node.get("source"), str) and node.get("source"):
                href = Path(node.get("source")).with_suffix(".html").name
            else:
                continue

        if href.startswith("/") or href.startswith(".."):
            continue

        li_class = None
        if entry["level"] > 0:
            li_class = entry.get("children_class")
        li_attr = f' class="{li_class}"' if isinstance(li_class, str) and li_class else ""

        a_active = active_classes.get(key, "") if isinstance(key, str) else ""
        lines.append(f"                <li{li_attr}><a href=\"{base_href}{href}\"{a_active}>{label}</a></li>")

    return "\n".join(lines)


def _render_html(cfg: dict, *, title: str, html_content: str, active_key: str | None, base_href: str, css_href: str) -> str:
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


def _render_home_cards_section(cfg: dict) -> str:
    """Render the Home page 'quick links' card grid from the pages tree."""

    # Find Home node to get title
    home_title = "Documentation"
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        if node.get("key") == "home":
            t = node.get("home_cards_title")
            if isinstance(t, str) and t.strip():
                home_title = t.strip()
            break

    # Build mapping from page key -> href
    key_to_href: dict[str, str] = {}
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

        # Keep only safe relative links
        if href and (href.startswith("/") or href.startswith("..")):
            href = ""

        if href:
            key_to_href[key] = href

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
            continue

        order = hc.get("order")
        try:
            order_val = int(order) if order is not None else 10_000
        except Exception:
            order_val = 10_000

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


def _patch_api_html_css_links(*, site_root: Path, cfg: dict):
    """Ensure pdoc-generated API pages use the site-wide CSS."""
    site_css = (cfg.get("site") or {}).get("css") or {}
    css_rel = site_css.get("path") if isinstance(site_css.get("path"), str) and site_css.get("path").strip() else "docs-style.css"
    css_rel = css_rel.strip().lstrip("/")

    api_dir = site_root / "api"
    if not api_dir.exists():
        return

    link_pat = re.compile(r"\n?\s*<link[^>]+rel=[\"']stylesheet[\"'][^>]*>\s*\n?", re.IGNORECASE)

    for p in api_dir.rglob("*.html"):
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        m = re.search(r"</head>", html, flags=re.IGNORECASE)
        if not m:
            continue

        try:
            rel = os.path.relpath((site_root / css_rel).resolve(), p.parent.resolve())
        except ValueError:
            rel = str((site_root / css_rel).resolve())
        rel = rel.replace(os.sep, "/")

        head_start = re.search(r"<head[^>]*>", html, flags=re.IGNORECASE)
        if head_start:
            hs = head_start.end()
            he = m.start()
            head_block = html[hs:he]
            head_block = link_pat.sub("\n", head_block)
            html = html[:hs] + head_block + html[he:]

        inject = f'\n<link rel="stylesheet" href="{rel}">\n'
        html = re.sub(r"</head>", inject + "</head>", html, flags=re.IGNORECASE, count=1)

        p.write_text(html, encoding="utf-8")


def _finalize_api_output_layout(*, site_root: Path):
    """Normalize API output: delete flat pages + ensure api/index.html redirect exists."""
    api_dir = site_root / "api"
    if not api_dir.exists():
        return

    for p in api_dir.glob("*.html"):
        if p.name == "index.html":
            continue
        try:
            p.unlink()
        except Exception:
            pass

    index_path = api_dir / "index.html"
    target = "ccai9012/index.html"
    redirect_html = "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <meta http-equiv=\"refresh\" content=\"0; url=" + target + "\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "  <title>API Documentation</title>",
        "</head>",
        "<body>",
        "  <p>Redirecting to <a href=\"" + target + "\">API Documentation</a>…</p>",
        "  <script>location.replace('" + target + "');</script>",
        "</body>",
        "</html>",
        "",
    ])
    index_path.write_text(redirect_html, encoding="utf-8")


def _wrap_api_pages_with_site_chrome(*, docs_dir: Path, cfg: dict, site_root: Path):
    """Wrap pdoc-generated API pages with the same left sidebar as the main site."""
    api_dir = site_root / "api"
    if not api_dir.exists():
        return

    def _extract_between(s: str, start_pat: re.Pattern, end_pat: re.Pattern) -> str | None:
        m1 = start_pat.search(s)
        if not m1:
            return None
        m2 = end_pat.search(s, m1.end())
        if not m2:
            return None
        return s[m1.end():m2.start()]

    def _extract_pdoc_article(html: str) -> str:
        inner = _extract_between(
            html,
            re.compile(r"<article\s+id=\"content\"[^>]*>", re.IGNORECASE),
            re.compile(r"</article>", re.IGNORECASE),
        )
        if inner is not None:
            return "<article class=\"api-doc\">\n" + inner.strip() + "\n</article>"

        inner = _extract_between(
            html,
            re.compile(r"<main[^>]*>", re.IGNORECASE),
            re.compile(r"</main>", re.IGNORECASE),
        )
        if inner is not None:
            return "<article class=\"api-doc\">\n" + inner.strip() + "\n</article>"

        return "<article class=\"api-doc\">\n" + html.strip() + "\n</article>"

    def _unwrap_if_wrapped(existing_html: str) -> str:
        if "<!-- START PDOC WRAPPER -->" not in existing_html:
            return existing_html

        inner = _extract_between(
            existing_html,
            re.compile(r"<article\s+class=\"api-doc\"[^>]*>", re.IGNORECASE),
            re.compile(r"</article>", re.IGNORECASE),
        )
        if inner is not None:
            return "<article id=\"content\">\n" + inner.strip() + "\n</article>"

        inner = _extract_between(
            existing_html,
            re.compile(r"<main\s+id=\"content\"[^>]*>", re.IGNORECASE),
            re.compile(r"</main>", re.IGNORECASE),
        )
        if inner is not None:
            return inner.strip()

        return existing_html

    for p in api_dir.rglob("*.html"):
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        html = _unwrap_if_wrapped(html)

        module_name = "API Documentation"
        m_title = re.search(r"<h1[^>]*class=\"title\"[^>]*>\s*(.*?)\s*</h1>", html, flags=re.IGNORECASE | re.DOTALL)
        if m_title:
            module_name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m_title.group(1))).strip() or module_name
        else:
            m_title = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            if m_title:
                module_name = re.sub(r"\s+", " ", m_title.group(1)).strip() or module_name

        content_html = _extract_pdoc_article(html)

        css_href = _css_href_for_output(cfg=cfg, output_path=p, site_root=site_root, docs_dir=docs_dir)
        base_href = _base_href_for_output(output_path=p, site_root=site_root)
        nav_items_html = _render_nav_items(cfg, base_href=base_href, active_key="api")

        wrapped = "\n".join([
            "<!-- START PDOC WRAPPER -->",
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            f"  <title>{module_name}</title>",
            f"  <link rel=\"stylesheet\" href=\"{css_href}\">",
            "</head>",
            "<body>",
            "  <div class=\"container\">",
            "    <nav id=\"sidebar\">",
            "      <div class=\"sidebar-header\">",
            "        <h2>CCAI9012</h2>",
            "      </div>",
            "      <ul class=\"nav-menu\">",
            nav_items_html,
            "      </ul>",
            "    </nav>",
            "",
            "    <main id=\"content\" class=\"api-content\">",
            "      <!-- API content extracted from pdoc -->",
            content_html,
            "    </main>",
            "  </div>",
            "</body>",
            "</html>",
            "<!-- END PDOC WRAPPER -->",
            "",
        ])

        p.write_text(wrapped, encoding="utf-8")


def _starter_modules_from_pages(cfg: dict) -> list[dict]:
    """Extract starter kit module metadata from pages.json.

    Returns list of dicts: {number:int, title:str, href:str}
    where href is like 'starter_kits/m2_llm.html'.
    """
    modules: list[dict] = []
    for entry in _flatten_pages_tree(cfg):
        node = entry["node"]
        module = node.get("module")
        if not isinstance(module, dict):
            continue

        try:
            number = int(module.get("number"))
        except Exception:
            continue

        href = node.get("href")
        if not isinstance(href, str) or not href:
            href = node.get("output") if isinstance(node.get("output"), str) else ""
        if not isinstance(href, str) or not href or href.startswith("/") or href.startswith(".."):
            continue

        title = module.get("page_title")
        if not isinstance(title, str) or not title.strip():
            title = node.get("label") or node.get("title") or f"Module {number}"

        modules.append({
            "number": number,
            "title": title.strip(),
            "href": href,
        })

    modules.sort(key=lambda m: m["number"])
    return modules


def _infer_api_to_modules_from_md(*, md_root: Path) -> dict[str, set[int]]:
    """Parse docs/md/starter_kits/*.md to infer API module -> starter module numbers."""
    out: dict[str, set[int]] = {}
    sk_dir = md_root / "starter_kits"
    if not sk_dir.exists():
        return out

    # allow ../ or ../../ etc
    pat = re.compile(r"\((?:\.{1,2}/)+api/ccai9012/([A-Za-z0-9_]+)\.html\)")

    for md_path in sk_dir.glob("m*_*.md"):
        m = re.match(r"^m(\d+)_", md_path.name)
        if not m:
            continue
        try:
            module_num = int(m.group(1))
        except Exception:
            continue

        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            continue

        for api_name in pat.findall(text):
            out.setdefault(api_name, set()).add(module_num)

    return out


def _inject_starterkit_backlinks_into_api_pages(*, docs_dir: Path, cfg: dict, site_root: Path, md_root: Path):
    """Add 'Related Starter Kit(s)' block into wrapped API HTML pages."""
    api_dir = site_root / "api" / "ccai9012"
    if not api_dir.exists():
        return

    api_to_modules = _infer_api_to_modules_from_md(md_root=md_root)
    if not api_to_modules:
        return

    modules = _starter_modules_from_pages(cfg)
    num_to_mod = {m["number"]: m for m in modules}

    start_mark = "<!-- STARTERKIT_BACKLINKS_START -->"
    end_mark = "<!-- STARTERKIT_BACKLINKS_END -->"

    def _build_block(*, module_nums: list[int], api_page_dir: Path) -> str:
        items: list[str] = []
        for n in sorted(set(module_nums)):
            m = num_to_mod.get(n)
            if not m:
                continue
            try:
                rel_href = os.path.relpath((site_root / m["href"]).resolve(), api_page_dir.resolve())
            except ValueError:
                rel_href = m["href"]
            rel_href = rel_href.replace(os.sep, "/")
            items.append(f'<li><a href="{rel_href}">{m["title"]}</a></li>')

        if not items:
            return ""

        return "\n".join([
            '<section class="api-related-block" style="margin:1rem 0; padding:1rem; border:1px solid #e5e7eb; border-left:6px solid #4f46e5; border-radius:10px; background:#fafafa">',
            '  <div class="api-related-block__title" style="font-weight:700; margin-bottom:0.5rem">Related Starter Kit(s)</div>',
            '  <ul style="margin:0; padding-left:1.2rem">',
            "\n".join(items),
            '  </ul>',
            '</section>',
        ])

    def _upsert(html: str, block_html: str) -> str:
        block = f"{start_mark}\n{block_html}\n{end_mark}"
        if start_mark in html and end_mark in html:
            return re.sub(rf"{re.escape(start_mark)}.*?{re.escape(end_mark)}", block, html, flags=re.DOTALL)

        if "</header>" in html:
            return html.replace("</header>", "</header>\n" + block, 1)

        m = re.search(r"(<main[^>]*id=\"content\"[^>]*>)", html)
        if m:
            i = m.end()
            return html[:i] + "\n" + block + html[i:]

        return html + "\n" + block

    for p in api_dir.rglob("*.html"):
        slug = p.stem
        if p.name == "index.html":
            slug = p.parent.name

        module_nums = api_to_modules.get(slug)
        if not module_nums:
            continue

        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        block_html = _build_block(module_nums=sorted(module_nums), api_page_dir=p.parent)
        if not block_html:
            continue

        new_html = _upsert(html, block_html)
        if new_html != html:
            p.write_text(new_html, encoding="utf-8")


def convert_md_to_html(md_file_path: str | os.PathLike, output_dir: str | os.PathLike | None = None) -> bool:
    """Convert a markdown file to HTML under docs/ (no path rewriting)."""
    docs_dir = Path(__file__).parent
    cfg = _load_site_config(docs_dir=docs_dir)

    md_root, site_root = _ensure_dirs(docs_dir=docs_dir)

    md_file = Path(md_file_path)
    if not md_file.exists():
        print(f"Error: File {md_file} not found", flush=True)
        return False

    # Support passing either a path under docs/md or a legacy path under docs/.
    md_file_res = md_file.resolve()
    if not str(md_file_res).startswith(str(md_root.resolve())):
        candidate = (md_root / md_file_path).resolve()
        if candidate.exists():
            md_file = candidate
        else:
            md_file = md_file_res

    md_content = md_file.read_text(encoding="utf-8")

    pages_by_source = _pages_by_source(cfg)
    try:
        source_key = _rel_to_root(md_file, md_root)
    except Exception:
        source_key = Path(md_file.name).as_posix()

    config = pages_by_source.get(source_key)
    if not config:
        print(f"Warning: No configuration found for {source_key}, using defaults", flush=True)
        title = md_file.stem.replace("_", " ").title()
        html_rel = Path(source_key).with_suffix(".html").as_posix()
        active_key = None
    else:
        title = config["title"]
        html_rel = config["output"]
        active_key = config.get("nav_key")

    # Default output location:
    # - When output_dir is provided, honor it exactly.
    # - Otherwise, write pages under docs/ (site_root).
    if output_dir:
        output_path = Path(output_dir) / html_rel
    else:
        output_path = site_root / html_rel

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = _new_markdown().convert(md_content)

    # Home page: append cards section driven by pages.json
    if source_key == "index.md":
        cards_html = _render_home_cards_section(cfg)
        if cards_html:
            html_content = "\n".join([html_content, cards_html])

    base_href = _base_href_for_output(output_path=output_path, site_root=site_root)
    css_href = _css_href_for_output(cfg=cfg, output_path=output_path, site_root=site_root, docs_dir=docs_dir)

    full_html = _render_html(
        cfg,
        title=title,
        html_content=html_content,
        active_key=active_key,
        base_href=base_href,
        css_href=css_href,
    )

    output_path.write_text(full_html, encoding="utf-8")
    print(f"✓ Converted: {source_key} → {output_path}", flush=True)
    return True


def convert_all_docs() -> None:
    """Convert markdown files referenced by docs/pages.json."""
    docs_dir = Path(__file__).parent
    cfg = _load_site_config(docs_dir=docs_dir)

    md_root, site_root = _ensure_dirs(docs_dir=docs_dir)

    _patch_api_html_css_links(site_root=site_root, cfg=cfg)
    _finalize_api_output_layout(site_root=site_root)
    _wrap_api_pages_with_site_chrome(docs_dir=docs_dir, cfg=cfg, site_root=site_root)
    # Inject backlinks after wrapping so insertion points (<header> / <main id="content">) are stable.
    _inject_starterkit_backlinks_into_api_pages(docs_dir=docs_dir, cfg=cfg, site_root=site_root, md_root=md_root)

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

    print("-" * 50, flush=True)
    print(f"Converted {success_count}/{len(md_files)} files successfully", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        convert_md_to_html(sys.argv[1])
    else:
        convert_all_docs()

