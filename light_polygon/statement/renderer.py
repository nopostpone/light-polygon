from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_inline import StateInline


# ─── Markdown → HTML with MathJax ──────────────────────────────────

def _math_inline(state: StateInline, silent: bool) -> bool:
    """Parse inline $...$ math."""
    if state.src[state.pos] != "$":
        return False
    # Check not $$ (display math)
    if state.src[state.pos:state.pos + 2] == "$$":
        return False
    end = state.src.find("$", state.pos + 1)
    if end == -1:
        return False
    if not silent:
        token = state.push("math_inline", "", 0)
        token.content = state.src[state.pos + 1:end]
    state.pos = end + 1
    return True


def _math_display(state: StateBlock, start_line: int, end_line: int, silent: bool) -> bool:
    """Parse display $$...$$ math."""
    line = state.src[state.bMarks[start_line]:state.eMarks[start_line]]
    if not line.startswith("$$"):
        return False

    # Find closing $$
    end_line_idx = -1
    for i in range(start_line + 1, end_line):
        blk = state.src[state.bMarks[i]:state.eMarks[i]]
        if blk.rstrip().endswith("$$"):
            end_line_idx = i
            break
    else:
        # Single-line: $$ ... $$
        if not line.rstrip().endswith("$$") or len(line.strip()) <= 4:
            return False
        end_line_idx = start_line

    if not silent:
        # Collect content between $$ and $$
        if end_line_idx == start_line:
            # Single line
            content = line.strip()[2:-2].strip()
        else:
            content_lines = []
            for j in range(start_line, end_line_idx + 1):
                line_text = state.src[state.bMarks[j]:state.eMarks[j]].rstrip()
                if j == start_line:
                    line_text = line_text[2:] if line_text.startswith("$$") else line_text
                if j == end_line_idx:
                    line_text = line_text[:-2] if line_text.rstrip().endswith("$$") else line_text
                content_lines.append(line_text)
            content = "\n".join(content_lines)

        token = state.push("math_display", "", 0)
        token.content = content

    state.line = end_line_idx + 1
    return True


def _init_markdown_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.inline.ruler.before("escape", "math_inline", _math_inline)
    md.block.ruler.before("fence", "math_display", _math_display)

    # Custom renderers for math tokens
    def render_math_inline(self, tokens, idx, options, env):
        return f'<span class="math inline">\\({tokens[idx].content}\\)</span>'

    def render_math_display(self, tokens, idx, options, env):
        return f'<div class="math display">\\[{tokens[idx].content}\\]</div>'

    md.add_render_rule("math_inline", render_math_inline)
    md.add_render_rule("math_display", render_math_display)
    return md


_md: MarkdownIt | None = None


def _get_md() -> MarkdownIt:
    global _md
    if _md is None:
        _md = _init_markdown_parser()
    return _md


def render_html(markdown_text: str) -> str:
    """Convert Markdown to HTML, preserving LaTeX math for MathJax."""
    md = _get_md()
    return md.render(markdown_text)


# ─── Markdown → LaTeX ──────────────────────────────────────────────

# Regex patterns
RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
RE_ITALIC = re.compile(r"\*(.+?)\*")
RE_INLINE_CODE = re.compile(r"`([^`]+)`")
RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RE_DISPLAY_MATH = re.compile(r"\$\$([^$]+)\$\$")
RE_INLINE_MATH = re.compile(r"\$([^$]+)\$")


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters outside math mode."""
    # Common escapes for problem statements
    for char in ["&", "%", "#", "_", "{", "}"]:
        # Simple: escape everything unless in math mode
        pass  # Most markdown→latex content doesn't have raw special chars
    return text


def _convert_inline_formatting(text: str) -> str:
    """Convert markdown inline formatting to LaTeX."""
    # Order matters: code before bold/italic
    text = RE_INLINE_CODE.sub(r"\\texttt{\1}", text)
    text = RE_BOLD.sub(r"\\textbf{\1}", text)
    text = RE_ITALIC.sub(r"\\textit{\1}", text)
    text = RE_LINK.sub(r"\\href{\2}{\1}", text)
    # Math: display first (longer pattern), then inline
    text = RE_DISPLAY_MATH.sub(r"\\[\1\\]", text)
    text = RE_INLINE_MATH.sub(r"$\1$", text)  # passthrough
    text = text.replace("#", r"\#")
    return text


def render_latex(markdown_text: str) -> str:
    """Convert Markdown to LaTeX (hand-coded, no pandoc)."""
    lines = markdown_text.split("\n")
    out: list[str] = []
    i = 0
    in_code_block = False
    in_list = False
    list_type: str | None = None  # "itemize" or "enumerate"

    # Track paragraphs: avoid double empty lines
    prev_empty = True

    while i < len(lines):
        line = lines[i]

        # Code block fence
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                out.append("\\begin{verbatim}")
            else:
                in_code_block = False
                out.append("\\end{verbatim}")
                prev_empty = False
            i += 1
            continue

        if in_code_block:
            out.append(line)
            i += 1
            continue

        # Close list if needed (blank lines between items don't break the list)
        if in_list and line.strip():
            is_list_item = line.strip().startswith("- ") or re.match(r"^\d+\.\s", line.strip())
            if not is_list_item:
                out.append(f"\\end{{{list_type}}}")
                in_list = False
                list_type = None
                prev_empty = False

        # Single-line display math: $$...$$
        dm = re.match(r"^\$\$(.+)\$\$\s*$", line.strip())
        if dm:
            out.append(f"\\[{dm.group(1).strip()}\\]")
            prev_empty = False
            i += 1
            continue

        # Multi-line display math: $$ on its own line
        if line.strip() == "$$":
            # Collect content lines until closing $$
            content_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                content_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # skip closing $$
            body = "\n".join(content_lines).strip()
            out.append(f"\\[{body}\\]")
            prev_empty = False
            continue

        # Headings
        if line.startswith("# "):
            out.append(f"\\section*{{{_convert_inline_formatting(line[2:].strip())}}}")
            prev_empty = False
            i += 1
            continue
        if line.startswith("## "):
            out.append(f"\\subsection*{{{_convert_inline_formatting(line[3:].strip())}}}")
            prev_empty = False
            i += 1
            continue
        if line.startswith("### "):
            out.append(f"\\subsubsection*{{{_convert_inline_formatting(line[4:].strip())}}}")
            prev_empty = False
            i += 1
            continue

        # Unordered list
        if line.strip().startswith("- "):
            if not in_list:
                in_list = True
                list_type = "itemize"
                out.append(f"\\begin{{{list_type}}}")
            item = line.strip()[2:]
            out.append(f"\\item {_convert_inline_formatting(item)}")
            prev_empty = False
            i += 1
            continue

        # Ordered list
        ol = re.match(r"^(\d+)\.\s+(.*)", line.strip())
        if ol:
            if not in_list:
                in_list = True
                list_type = "enumerate"
                out.append(f"\\begin{{{list_type}}}")
            out.append(f"\\item {_convert_inline_formatting(ol.group(2))}")
            prev_empty = False
            i += 1
            continue

        # Horizontal rule
        if line.strip() == "---":
            out.append("\\hrulefill")
            out.append("")
            prev_empty = True
            i += 1
            continue

        # Empty line
        if not line.strip():
            if not prev_empty:
                out.append("")
                prev_empty = True
            i += 1
            continue

        # Regular paragraph line
        converted = _convert_inline_formatting(line.strip())
        out.append(converted)
        prev_empty = False
        i += 1

    # Close any open list
    if in_list and list_type:
        out.append(f"\\end{{{list_type}}}")

    return "\n".join(out) + "\n"


# ─── Terminal preview ──────────────────────────────────────────────

def _strip_math(markdown_text: str) -> str:
    """Strip $ and $$ delimiters, leaving LaTeX as plain text for terminal display."""
    # Display math: $$...$$ → just the content
    text = re.sub(r"\$\$\s*(.+?)\s*\$\$", r"\1", markdown_text, flags=re.DOTALL)
    # Inline math: $...$ → just the content
    text = re.sub(r"\$(.+?)\$", r"\1", text)
    return text


def render_terminal(markdown_text: str) -> str:
    """Render markdown for terminal preview: strip math, keep structure."""
    stripped = _strip_math(markdown_text)
    return stripped


# ─── Jinja2 template rendering ─────────────────────────────────────

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_html_page(markdown_text: str, title: str = "Problem Statement") -> str:
    """Full HTML page with MathJax and styling."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))
    template = env.get_template("page.html")
    content_html = render_html(markdown_text)
    return template.render(title=title, content=content_html)


def render_latex_page(markdown_text: str, title: str = "Problem Statement") -> str:
    """Full LaTeX document with preamble."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))
    template = env.get_template("page.tex")
    content_tex = render_latex(markdown_text)
    return template.render(title=title, content=content_tex)
