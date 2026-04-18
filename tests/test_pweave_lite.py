"""Unit tests for eegnb.reports.pweave_lite."""

from eegnb.reports.pweave_lite import _split_options, _Weaver


def test_split_options_respects_quoted_commas():
    tokens = _split_options(
        "name, fig=True, caption='A, B, and C', width='0.9\\linewidth'"
    )
    # Expected: 4 tokens; caption has its commas preserved.
    assert tokens[0] == "name"
    assert "fig=True" in tokens
    caption_token = [t for t in tokens if t.startswith("caption=")][0]
    assert "A, B, and C" in caption_token


def test_parse_options_strips_quotes(tmp_path):
    w = _Weaver(cwd=tmp_path)
    opts = w._parse_options(
        "chunk1, fig=True, width='\\linewidth', caption='hi there'"
    )
    assert opts["name"] == "chunk1"
    assert opts["fig"] is True
    assert opts["width"] == r"\linewidth"
    assert opts["caption"] == "hi there"


def test_conditional_if_emits_when_true(tmp_path):
    w = _Weaver(cwd=tmp_path)
    w.ns["flag"] = True
    out = w._expand_conditionals(
        "prelude\n<% if flag %>\nYES\n<% endif %>\ntail"
    )
    assert "YES" in out
    assert "tail" in out


def test_conditional_if_omits_when_false(tmp_path):
    w = _Weaver(cwd=tmp_path)
    w.ns["flag"] = False
    out = w._expand_conditionals(
        "prelude\n<% if flag %>\nNO\n<% endif %>\ntail"
    )
    assert "NO" not in out
    assert "tail" in out


def test_chunk_execution_affects_namespace(tmp_path):
    w = _Weaver(cwd=tmp_path)
    src = "<<setup, echo=False, results='hide'>>=\nfoo = 42\n@\n<%= foo %>"
    out = w.weave(src)
    assert "42" in out
