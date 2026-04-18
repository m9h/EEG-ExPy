"""Minimal Pweave-compatible .Pnw -> .tex processor.

Supports the subset of Pweave we need for this project's reports:

* ``<<name, opt=val, opt2=val2>>=`` starts a chunk; ``@`` on its own
  line ends it.
* Chunk options understood:
    - ``echo``     (default True)   — include the source code
    - ``results``  (default 'verbatim')  — 'verbatim', 'tex', or 'hide'
    - ``fig``      (default False)  — save a matplotlib figure and
                                      emit ``\\includegraphics``
    - ``width``    (default '\\linewidth') — LaTeX width for figures
    - ``caption``  (default None)   — caption text for figure env
* Jinja-style conditionals: ``<% if cond %> ... <% endif %>`` with
  plain Python expressions, evaluated in the chunk namespace. Used to
  conditionally include paradigm sections.
* All chunks share one ``globals`` namespace so variables flow
  between them.

This is a deliberate 1:1 subset of Pweave's feature set; it is not a
drop-in replacement for general Pweave usage.
"""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

CHUNK_START = re.compile(r"<<(?P<header>[^>]*)>>=\s*$")
_QUOTED = re.compile(r"""'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*\"""")


def _split_options(header: str) -> list[str]:
    """Split a chunk-header into tokens on commas, respecting quotes."""
    out: list[str] = []
    buf: list[str] = []
    i = 0
    in_quote = None
    while i < len(header):
        ch = header[i]
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == ",":
            out.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        out.append("".join(buf).strip())
    return out

CHUNK_END = re.compile(r"^@\s*$")
JINJA_IF = re.compile(r"<%\s*if\s+(?P<expr>.+?)\s*%>")
JINJA_ENDIF = re.compile(r"<%\s*endif\s*%>")
JINJA_VAR = re.compile(r"<%=\s*(?P<expr>.+?)\s*%>")


def weave(pnw_path: Path, tex_path: Path) -> Path:
    """Process a .Pnw into a .tex file. Returns tex_path."""
    text = Path(pnw_path).read_text()
    out = _Weaver(cwd=pnw_path.parent).weave(text)
    tex_path.write_text(out)
    return tex_path


class _Weaver:
    def __init__(self, cwd: Path):
        self.cwd = Path(cwd)
        self.ns: dict = {"__name__": "__pweave__"}
        self._fig_counter = 0

    def weave(self, text: str) -> str:
        """Main entry: runs chunks in order, then conditionals."""
        # Pass 1: substitute chunks with their rendered output.
        out_lines: list[str] = []
        in_chunk = False
        chunk_header = ""
        chunk_lines: list[str] = []

        for line in text.splitlines(keepends=False):
            if not in_chunk:
                m = CHUNK_START.match(line)
                if m:
                    in_chunk = True
                    chunk_header = m.group("header").strip()
                    chunk_lines = []
                    continue
                out_lines.append(line)
            else:
                if CHUNK_END.match(line):
                    out_lines.append(
                        self._render_chunk(chunk_header, "\n".join(chunk_lines))
                    )
                    in_chunk = False
                    continue
                chunk_lines.append(line)

        rendered = "\n".join(out_lines)

        # Pass 2: handle <% if cond %> ... <% endif %> blocks.
        rendered = self._expand_conditionals(rendered)

        # Pass 3: inline <%= expr %> variable substitutions.
        rendered = JINJA_VAR.sub(
            lambda m: str(eval(m.group("expr"), self.ns)), rendered
        )

        return rendered

    def _parse_options(self, header: str) -> dict:
        """Parse `name, opt=val, opt2='string with, commas'` into a dict.

        Respects single- and double-quoted string values so that
        captions containing commas are preserved. Backslash sequences
        inside quoted values are kept literally (no Python-style
        unescape), so authors should write LaTeX commands with a single
        backslash: ``caption='A \\linewidth caption'``.
        """
        opts = {
            "name": None,
            "echo": True,
            "results": "verbatim",
            "fig": False,
            "width": r"\linewidth",
            "caption": None,
        }
        tokens = _split_options(header)
        if tokens and "=" not in tokens[0]:
            opts["name"] = tokens[0].strip()
            tokens = tokens[1:]
        for tok in tokens:
            if "=" not in tok:
                continue
            key, val = tok.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith("'") and val.endswith("'")) or (
                val.startswith('"') and val.endswith('"')
            ):
                val = val[1:-1]
            if val in ("True", "False"):
                val = val == "True"
            opts[key] = val
        return opts

    def _render_chunk(self, header: str, code: str) -> str:
        opts = self._parse_options(header)
        captured = io.StringIO()

        fig_active = bool(opts.get("fig"))
        if fig_active:
            import matplotlib.pyplot as plt

            plt.close("all")

        with contextlib.redirect_stdout(captured):
            try:
                exec(compile(code, f"<chunk {opts.get('name')}>", "exec"), self.ns)
            except Exception as exc:
                return (
                    r"\textcolor{red}{\textbf{Chunk "
                    + str(opts.get("name")) + " failed: "
                    + str(exc).replace("_", r"\_") + r"}}"
                )

        captured_text = captured.getvalue()
        parts: list[str] = []

        if opts.get("echo"):
            parts.append(r"\begin{verbatim}")
            parts.append(code.rstrip())
            parts.append(r"\end{verbatim}")

        results = opts.get("results", "verbatim")
        if results == "tex":
            parts.append(captured_text.rstrip())
        elif results == "verbatim" and captured_text.strip():
            parts.append(r"\begin{verbatim}")
            parts.append(captured_text.rstrip())
            parts.append(r"\end{verbatim}")
        # results == "hide": do nothing with captured_text.

        if fig_active:
            import matplotlib.pyplot as plt

            self._fig_counter += 1
            fig_name = f"fig_{self._fig_counter:03d}.png"
            fig_path = self.cwd / fig_name
            plt.savefig(fig_path, dpi=140, bbox_inches="tight")
            plt.close("all")

            caption = opts.get("caption")
            parts.append(r"\begin{figure}[h!]")
            parts.append(r"\centering")
            parts.append(
                rf"\includegraphics[width={opts['width']}]{{{fig_name}}}"
            )
            if caption:
                # Escape percent signs at minimum; trust the rest.
                safe_caption = str(caption).replace("%", r"\%")
                parts.append(rf"\caption{{{safe_caption}}}")
            parts.append(r"\end{figure}")

        return "\n".join(parts)

    def _expand_conditionals(self, text: str) -> str:
        """Evaluate <% if cond %> ... <% endif %> against self.ns."""
        lines = text.splitlines(keepends=False)
        out: list[str] = []
        stack: list[bool] = [True]  # True = emit

        for line in lines:
            mif = JINJA_IF.search(line)
            mend = JINJA_ENDIF.search(line)
            if mif:
                cond = bool(eval(mif.group("expr"), self.ns)) and stack[-1]
                stack.append(cond)
                continue
            if mend:
                if len(stack) > 1:
                    stack.pop()
                continue
            if stack[-1]:
                out.append(line)
        return "\n".join(out)
