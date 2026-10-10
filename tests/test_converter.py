"""Storage format -> Markdown conversion: structure, macros, tables, images."""

from src.backup.converter import Converter
from src.backup.refs import ImageRef, find_image_refs

IMAGES = {"a.png": "../assets/h1.png", "arq.png": "../assets/h2.png"}


def convert(html: str, **kw) -> tuple[str, Converter]:
    conv = Converter(
        resolve_image=lambda r: IMAGES.get(r.value),
        resolve_link=lambda t: "outra/index.md" if t == "Outra" else None,
        **kw,
    )
    return conv.convert(html), conv


def test_text_structure_and_inline():
    md, _ = convert(
        "<h2>Título</h2><p>Olá <strong>mundo</strong> <em>x</em>&nbsp;<code>c</code> "
        '<del>d</del> <a href="http://x.io">l</a><br/>fim</p><hr/>'
        "<blockquote><p>cita</p></blockquote><pre>a\n  b</pre>"
    )
    assert "## Título" in md
    assert "Olá **mundo** *x* `c` ~~d~~ [l](http://x.io)" in md
    assert "---" in md and "> cita" in md and "```\na\n  b\n```" in md


def test_lists_nested_ordered_and_tasks():
    md, _ = convert(
        "<ul><li>um<ul><li>aninhado</li></ul></li><li>dois</li></ul>"
        "<ol><li>a</li><li>b</li></ol>"
        "<ac:task-list><ac:task><ac:task-status>complete</ac:task-status>"
        "<ac:task-body>feito</ac:task-body></ac:task><ac:task>"
        "<ac:task-status>incomplete</ac:task-status><ac:task-body>falta</ac:task-body>"
        "</ac:task></ac:task-list>"
    )
    assert "- um\n  - aninhado\n- dois" in md
    assert "1. a\n2. b" in md
    assert "- [x] feito\n- [ ] falta" in md


def test_tables_gfm_and_html_fallback():
    md, _ = convert(
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>x|y</td></tr></table>"
    )
    assert "| A | B |\n| --- | --- |\n| 1 | x\\|y |" in md
    headless, _ = convert("<table><tr><td>1</td><td>2</td></tr></table>")
    assert headless.startswith("| | |\n| --- | --- |\n| 1 | 2 |")
    merged, _ = convert(
        '<table><tr><td colspan="2">big</td></tr><tr><td>1</td><td>2</td></tr></table>'
    )
    assert '<td colspan="2">big</td>' in merged
    nested, _ = convert(
        "<table><tr><td><table><tr><td>in</td></tr></table></td></tr></table>"
    )
    assert nested.count("<table>") == 2
    empty, _ = convert("<table></table>")
    assert empty == ""


def test_images_resolved_and_missing_reported():
    md, conv = convert(
        '<ac:image ac:alt="foto"><ri:attachment ri:filename="a.png"/></ac:image>'
        '<ac:image><ri:attachment ri:filename="lost.png"/></ac:image>'
        '<ac:image><ri:url ri:value="http://x/y.png"/></ac:image><ac:image/>'
    )
    assert "![foto](../assets/h1.png)" in md
    assert "<!-- missing image: lost.png -->" in md
    assert conv.missing_images == ["lost.png", "http://x/y.png", "image"]


def test_macros():
    md, conv = convert(
        '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter>'
        '<ac:plain-text-body><![CDATA[print("x")\nif a < b: pass]]></ac:plain-text-body></ac:structured-macro>'
        '<ac:structured-macro ac:name="info"><ac:parameter ac:name="title">Cuidado</ac:parameter>'
        "<ac:rich-text-body><p>texto</p></ac:rich-text-body></ac:structured-macro>"
        '<ac:structured-macro ac:name="warning"><ac:rich-text-body><p>w</p></ac:rich-text-body></ac:structured-macro>'
        '<ac:structured-macro ac:name="toc"/>'
        '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">Mais</ac:parameter>'
        "<ac:rich-text-body><p>oculto</p></ac:rich-text-body></ac:structured-macro>"
        '<ac:structured-macro ac:name="status"><ac:parameter ac:name="title">OK</ac:parameter></ac:structured-macro>'
        '<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">ABC-1</ac:parameter></ac:structured-macro>'
        '<ac:structured-macro ac:name="include"><ri:page ri:content-title="Outra"/></ac:structured-macro>'
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">arq</ac:parameter></ac:structured-macro>'
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">sumiu</ac:parameter></ac:structured-macro>'
        '<ac:structured-macro ac:name="panel"><ac:rich-text-body><p>p</p></ac:rich-text-body></ac:structured-macro>'
        '<ac:structured-macro ac:name="excerpt">'
        "<ac:rich-text-body><p>corpo</p></ac:rich-text-body></ac:structured-macro>"
        '<ac:structured-macro ac:name="weird"><ac:parameter ac:name="x">1</ac:parameter></ac:structured-macro>'
    )
    assert '```python\nprint("x")\nif a < b: pass\n```' in md
    assert "> [!NOTE]\n> **Cuidado**\n> texto" in md
    assert "> [!WARNING]" in md
    assert "<details>\n<summary>Mais</summary>\n\noculto\n\n</details>" in md
    assert "**[OK]**" in md and "JIRA: ABC-1" in md and "[Included page: Outra]" in md
    assert "![arq](../assets/h2.png)" in md
    assert "<!-- missing diagram preview: sumiu -->" in md
    assert "<!-- macro: excerpt -->\ncorpo" in md
    assert "<!-- unsupported macro: weird {'x': '1'} -->" in md
    assert conv.missing_images == ["sumiu.png"]


def test_code_macro_with_fence_inside():
    md, _ = convert(
        '<ac:structured-macro ac:name="code"><ac:plain-text-body><![CDATA[```x```]]>'
        "</ac:plain-text-body></ac:structured-macro>"
    )
    assert md.startswith("````\n```x```\n````")


def test_adf_panel_and_links_and_misc():
    md, _ = convert(
        '<ac:adf-extension><ac:adf-node type="panel"><ac:adf-attribute key="panel-type">warning'
        "</ac:adf-attribute><ac:adf-content><p>adf</p></ac:adf-content></ac:adf-node>"
        "<ac:adf-fallback>ignored</ac:adf-fallback></ac:adf-extension>"
        '<ac:adf-extension><ac:adf-node type="other"><ac:adf-content><p>x</p></ac:adf-content>'
        "</ac:adf-node></ac:adf-extension><ac:adf-extension/>"
        '<ac:link><ri:page ri:content-title="Outra"/><ac:link-body>veja</ac:link-body></ac:link>'
        '<ac:link><ri:page ri:content-title="Nada"/></ac:link>'
        '<ac:link><ri:user ri:account-id="1"/></ac:link>'
        '<ac:link><ri:attachment ri:filename="f.pdf"/></ac:link>'
        '<ac:emoticon ac:emoji-fallback="🙂"/><time datetime="2024-01-02"/><!-- c -->'
        "<ac:inline-comment-marker>marcado</ac:inline-comment-marker>"
        '<a>sem href</a><a href="http://z.io"></a><strong> </strong>'
    )
    assert "> [!WARNING]\n> adf" in md and "ignored" not in md
    assert "\nx\n" in md
    assert "[veja](outra/index.md)" in md
    assert "Nada" in md and "@user" in md and "f.pdf" in md
    assert "🙂" in md and "2024-01-02" in md and "marcado" in md
    assert "sem href" in md and "[http://z.io](http://z.io)" in md


def test_empty_and_whitespace_cleanup():
    assert Converter().convert("") == ""
    md = Converter().convert("<p>a</p>   <p>  b</p>\n\n\n<p>c</p>")
    assert md == "a\n\nb\n\nc\n"


def test_find_image_refs_dedupes():
    html = (
        '<ac:image><ri:attachment ri:filename="a.png"/></ac:image>'
        '<ac:image><ri:attachment ri:filename="a.png"/></ac:image>'
        '<ac:image><ri:attachment ri:filename="b.png"><ri:page ri:content-title="P"/></ri:attachment></ac:image>'
        '<ac:image><ri:url ri:value="http://x/i.png"/></ac:image><ac:image/>'
    )
    assert find_image_refs(html) == [
        ImageRef("attachment", "a.png"),
        ImageRef("attachment", "b.png", "P"),
        ImageRef("url", "http://x/i.png"),
    ]
