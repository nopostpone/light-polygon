from __future__ import annotations

from pathlib import Path

from light_polygon.statement.renderer import (
    render_html,
    render_html_page,
    render_latex,
    render_latex_page,
    render_terminal,
    _strip_math,
)


class TestStripMath:
    def test_strips_inline_math(self):
        assert _strip_math("hello $x^2$ world") == "hello x^2 world"

    def test_strips_display_math(self):
        result = _strip_math("hello $$\nx^2\n$$ world")
        assert "x^2" in result
        assert "$$" not in result

    def test_strips_single_line_display(self):
        result = _strip_math("$$ x^2 $$")
        assert result == "x^2"

    def test_preserves_normal_text(self):
        text = "just some **bold** text"
        assert _strip_math(text) == text


class TestRenderHTML:
    def test_basic_paragraph(self):
        html = render_html("Hello world")
        assert "<p>Hello world</p>" in html

    def test_heading(self):
        html = render_html("# Title")
        assert "<h1>Title</h1>" in html

    def test_inline_math(self):
        html = render_html("value $x^2$ here")
        assert '<span class="math inline">' in html
        assert r"\(x^2\)" in html

    def test_display_math(self):
        html = render_html("$$ x^2 $$")
        assert '<div class="math display">' in html
        assert r"\[x^2\]" in html

    def test_code_block(self):
        html = render_html("```\nhello\n```")
        assert "<code>" in html
        assert "hello" in html

    def test_bold(self):
        html = render_html("**bold text**")
        assert "<strong>bold text</strong>" in html


class TestRenderLaTeX:
    def test_heading_section(self):
        tex = render_latex("# My Title")
        assert r"\section*{My Title}" in tex

    def test_heading_subsection(self):
        tex = render_latex("## Sub Title")
        assert r"\subsection*{Sub Title}" in tex

    def test_heading_subsubsection(self):
        tex = render_latex("### Small")
        assert r"\subsubsection*{Small}" in tex

    def test_bold(self):
        tex = render_latex("**bold text**")
        assert r"\textbf{bold text}" in tex

    def test_italic(self):
        tex = render_latex("*italic text*")
        assert r"\textit{italic text}" in tex

    def test_inline_code(self):
        tex = render_latex("`code here`")
        assert r"\texttt{code here}" in tex

    def test_inline_math_passthrough(self):
        tex = render_latex("value $x^2$ here")
        assert "$x^2$" in tex

    def test_display_math_single_line(self):
        tex = render_latex("$$x^2$$")
        assert r"\[x^2\]" in tex

    def test_unordered_list(self):
        tex = render_latex("- item one\n- item two")
        assert r"\begin{itemize}" in tex
        assert r"\item item one" in tex
        assert r"\item item two" in tex
        assert r"\end{itemize}" in tex

    def test_ordered_list(self):
        tex = render_latex("1. first\n2. second")
        assert r"\begin{enumerate}" in tex
        assert r"\item first" in tex
        assert r"\item second" in tex
        assert r"\end{enumerate}" in tex

    def test_verbatim_block(self):
        tex = render_latex("```\nint main() {\n  return 0;\n}\n```")
        assert r"\begin{verbatim}" in tex
        assert "int main() {" in tex
        assert r"\end{verbatim}" in tex

    def test_horizontal_rule(self):
        tex = render_latex("---")
        assert r"\hrulefill" in tex

    def test_link(self):
        tex = render_latex("[click here](https://example.com)")
        assert r"\href{https://example.com}{click here}" in tex

    def test_escapes_hash_in_heading(self):
        tex = render_latex("## 输入输出样例 #1")
        assert r"\subsection*{输入输出样例 \#1}" in tex

    def test_escapes_complex_content(self):
        """Test a realistic problem statement fragment."""
        md = "Given $n$ numbers, find the **maximum** sum.\n\n- $O(n \\log n)$ is trivial\n- $O(n)$ is optimal"
        tex = render_latex(md)
        assert r"\textbf{maximum}" in tex
        assert r"$n$" in tex
        assert r"$O(n \log n)$" in tex
        assert r"$O(n)$" in tex
        assert r"\begin{itemize}" in tex


class TestRenderTerminal:
    def test_strips_math_delimiters(self):
        result = render_terminal("Compute $\\sum_{i=1}^n i$ efficiently")
        assert "$" not in result
        assert "\\sum_{i=1}^n i" in result

    def test_preserves_markdown_structure(self):
        md = "# Title\n\nSome **bold** text\n\n- item"
        result = render_terminal(md)
        assert "Title" in result
        assert "**bold**" in result
        assert "item" in result


class TestRenderHTMLPage:
    def test_full_html_document(self):
        html = render_html_page("# Hello\n\nWorld", "Test Problem")
        assert "<!DOCTYPE html>" in html
        assert "<title>Test Problem</title>" in html
        assert "mathjax" in html.lower()
        assert "<h1>Hello</h1>" in html


class TestRenderLaTeXPage:
    def test_full_latex_document(self):
        tex = render_latex_page("# Hello\n\nWorld", "Test Problem")
        assert r"\documentclass" in tex
        assert r"\begin{document}" in tex
        assert r"\end{document}" in tex
        assert "Test Problem" in tex
        assert r"\section*{Hello}" in tex
