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
"""

import sys
import os
import re
import shutil
from pathlib import Path

import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension

# HTML template with navigation
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CCAI9012 - {title}</title>
    <link rel="stylesheet" href="{css_href}">
</head>
<body>
    <div class="container">
        <nav id="sidebar">
            <div class="sidebar-header">
                <h2>CCAI9012</h2>
            </div>
            <ul class="nav-menu">
                <li><a href="{base_href}index.html"{home_active}>Home</a></li>
                <li><a href="{base_href}timetable.html"{timetable_active}>Timetable</a></li>
                <li><a href="{base_href}installation.html"{installation_active}>Installation Guide</a></li>
                <li><a href="{base_href}starter_kits/index.html"{starter_active}>Starter Kits</a></li>
                <li class="sub-item"><a href="{base_href}starter_kits/m1_gan.html"{m1_active}>Module 1: Traditional Generative ML</a></li>
                <li class="sub-item"><a href="{base_href}starter_kits/m2_llm.html"{m2_active}>Module 2: LLM for Structuring Information</a></li>
                <li class="sub-item"><a href="{base_href}starter_kits/m3_mm.html"{m3_active}>Module 3: Multimodal Reasoning</a></li>
                <li class="sub-item"><a href="{base_href}starter_kits/m4_cv.html"{m4_active}>Module 4: CV Models</a></li>
                <li class="sub-item"><a href="{base_href}starter_kits/m5_bias.html"{m5_active}>Module 5: Bias & Interpretability</a></li>
                <li><a href="{base_href}reading_material.html"{reading_active}>Reading Materials</a></li>
                <li><a href="{base_href}datasets.html"{datasets_active}>Datasets Reference</a></li>
                <li><a href="{base_href}api/index.html">API Documentation</a></li>
            </ul>
        </nav>

        <main id="content">
{content}
        </main>
    </div>
</body>
</html>
"""

# Page titles and active states
PAGE_CONFIG = {
    'installation.md': {
        'title': 'Installation Guide',
        'html_file': 'installation.html',
        'active': 'installation_active'
    },
    'starter_kits.md': {
        'title': 'Starter Kits',
        'html_file': 'starter_kits/index.html',
        'active': 'starter_active'
    },
    'reading_material.md': {
        'title': 'Reading Materials',
        'html_file': 'reading_material.html',
        'active': 'reading_active'
    },
    'datasets.md': {
        'title': 'Datasets Reference',
        'html_file': 'datasets.html',
        'active': 'datasets_active'
    },
    'timetable.md': {
        'title': 'Course Timetable',
        'html_file': 'timetable.html',
        'active': 'timetable_active'
    }
}

MODULE_SUBPAGES = [
    {"key": "m1_active", "title": "Module 1 - Traditional Generative ML", "filename": "m1_gan.html", "heading": "Module 1"},
    {"key": "m2_active", "title": "Module 2 - LLM for Structuring Information", "filename": "m2_llm.html", "heading": "Module 2"},
    {"key": "m3_active", "title": "Module 3 - Multimodal Reasoning", "filename": "m3_mm.html", "heading": "Module 3"},
    {"key": "m4_active", "title": "Module 4 - CV Models", "filename": "m4_cv.html", "heading": "Module 4"},
    {"key": "m5_active", "title": "Module 5 - Bias Detection & Interpretability", "filename": "m5_bias.html", "heading": "Module 5"},
]

# Short one-line descriptions used ONLY for docs/starter_kits/index.html
MODULE_INDEX_SUMMARY = {
    1: "Traditional generative ML for synthetic data generation and prediction.",
    2: "LLMs to structure unstructured text into analyzable formats.",
    3: "Multimodal (vision-language) reasoning over images and text.",
    4: "Computer vision: detection, segmentation, tracking, and visual analytics.",
    5: "Bias detection, fairness evaluation, and interpretability tooling.",
}


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


def _build_nav_states(active_key: str | None):
    nav_states = {
        'home_active': '',
        'installation_active': '',
        'starter_active': '',
        'reading_active': '',
        'datasets_active': '',
        'timetable_active': '',
        'm1_active': '',
        'm2_active': '',
        'm3_active': '',
        'm4_active': '',
        'm5_active': '',
    }
    if active_key:
        nav_states[active_key] = ' class="active"'

    # If any module subpage is active, keep the parent "Starter Kits" highlighted too.
    if active_key and active_key.startswith('m'):
        nav_states['starter_active'] = ' class="active"'

    return nav_states


def _render_html(title: str, html_content: str, active_key: str | None, *, base_href: str, css_href: str):
    return HTML_TEMPLATE.format(
        title=title,
        content=html_content,
        base_href=base_href,
        css_href=css_href,
        **_build_nav_states(active_key)
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


def _generate_starter_kits_subpages(starter_md_path: Path):
    docs_dir = starter_md_path.parent
    out_dir = docs_dir / "starter_kits"
    out_dir.mkdir(parents=True, exist_ok=True)

    md_text = starter_md_path.read_text(encoding="utf-8")
    modules = _split_starter_kits_modules(md_text)
    if not modules:
        print("Warning: No '## Module X:' sections found; skipping starter_kits subpages")
        return

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
        sub = next((x for x in MODULE_SUBPAGES if x["heading"] == f"Module {num}"), None)
        if not sub:
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
            title=sub["title"],
            html_content=html_body,
            active_key=sub["key"],
            base_href="../",
            css_href="../docs-style.css",
        )

        (out_dir / sub["filename"]).write_text(full_html, encoding="utf-8")
        print(f"✓ Generated subpage: starter_kits/{sub['filename']}")


def _starter_kits_index_landing_md(md_text: str) -> str:
    """Generate a compact landing page markdown for docs/starter_kits/index.html.

    Requirement:
    - Only one-line intro per module + a button/link to the module subpage.
    - No detailed content on the index page.

    We keep the title from the source markdown (if present), then render a simple list.
    """
    title_match = re.search(r"^#\s+(.+?)\s*$", md_text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Starter Kits"

    modules = _split_starter_kits_modules(md_text)
    if not modules:
        modules = [(1, "Traditional Generative ML", ""), (2, "LLM for Structuring Information", ""), (3, "Multimodal Reasoning", ""), (4, "CV Models", ""), (5, "Bias Detection & Interpretability", "")]

    # Map module number -> subpage filename
    num_to_file = {i + 1: MODULE_SUBPAGES[i]["filename"] for i in range(min(len(MODULE_SUBPAGES), 5))}

    parts: list[str] = [
        f"# {title}",
        "Pick one module to view details and starter code.",
        "",
        "<style>",
        ".module-card{border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;margin:12px 0;background:#fff}",
        ".module-card h3{margin:0 0 6px 0}",
        ".module-card p{margin:0 0 10px 0;color:#374151}",
        "</style>",
        "",
    ]

    for num, module_title, _ in modules:
        summary = MODULE_INDEX_SUMMARY.get(num, "Module overview.")
        href = num_to_file.get(num, "index.html")
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


def _inject_starterkit_backlinks_into_api_pages(*, docs_dir: Path):
    """Inject backlinks into docs/api/*.html based on starter_kits.md.

    This avoids hardcoding the mapping: the links are derived from the markdown itself.
    """
    starter_md = docs_dir / "starter_kits.md"
    api_dir = docs_dir / "api"
    if not starter_md.exists() or not api_dir.exists():
        return

    md_text = starter_md.read_text(encoding="utf-8")
    _, api_to_modules = _infer_module_api_mapping_from_markdown(md_text)

    # Map module number -> starter_kits subpage filename (from existing config)
    num_to_file = {i + 1: MODULE_SUBPAGES[i]["filename"] for i in range(min(len(MODULE_SUBPAGES), 5))}

    def build_links(module_nums: list[int]) -> str:
        items = []
        for n in module_nums:
            href = f"../starter_kits/{num_to_file.get(n, 'index.html')}"
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


def convert_md_to_html(md_file_path, output_dir=None):
    """Convert a markdown file to HTML with styling"""

    md_file = Path(md_file_path)
    if not md_file.exists():
        print(f"Error: File {md_file} not found")
        return False

    # Read markdown content
    md_content = md_file.read_text(encoding='utf-8')

    # Get page configuration
    config = PAGE_CONFIG.get(md_file.name)
    if not config:
        print(f"Warning: No configuration found for {md_file.name}, using defaults")
        title = md_file.stem.replace('_', ' ').title()
        html_filename = md_file.stem + '.html'
        active_key = None
    else:
        title = config['title']
        html_filename = config['html_file']
        active_key = config['active']

    # Convert markdown to HTML
    if md_file.name == "starter_kits.md":
        md_for_index = _starter_kits_index_landing_md(md_content)
        html_content = _new_markdown().convert(md_for_index)
    else:
        html_content = _new_markdown().convert(md_content)

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

    full_html = _render_html(
        title=title,
        html_content=html_content,
        active_key=active_key,
        base_href="../" if is_in_subdir else "",
        css_href="../docs-style.css" if is_in_subdir else "docs-style.css",
    )

    # Write HTML file
    output_path.write_text(full_html, encoding='utf-8')

    print(f"✓ Converted: {md_file.name} → {output_path}")

    # Special: starter_kits.md -> also generate module subpages
    if md_file.name == "starter_kits.md":
        _generate_starter_kits_subpages(md_file)
        # And add backlinks from API pages back to the relevant starter kits.
        _inject_starterkit_backlinks_into_api_pages(docs_dir=md_file.parent)

    return True


def convert_all_docs():
    """Convert all markdown files in docs/ directory"""
    docs_dir = Path(__file__).parent
    md_files = list(docs_dir.glob('*.md'))

    if not md_files:
        print("No markdown files found in docs/ directory")
        return

    print(f"Found {len(md_files)} markdown file(s)")
    print("-" * 50)

    success_count = 0
    for md_file in md_files:
        if convert_md_to_html(md_file):
            success_count += 1

    print("-" * 50)
    print(f"Converted {success_count}/{len(md_files)} files successfully")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Convert specific file
        md_file = sys.argv[1]
        convert_md_to_html(md_file)
    else:
        # Convert all markdown files
        convert_all_docs()
