#!/usr/bin/env python3
"""
把汇报正文 Markdown 转成可直接浏览器打开的 HTML（含 Mermaid 架构图 / 流程图）。

依赖：pip install markdown
用法：
    python scripts/md2html.py                                   # 默认：正文第一章 → 数据平台.html
    python scripts/md2html.py -i AI＋数据平台建设汇报_正文.md -o 输出.html --chapter 1
    python scripts/md2html.py --chapter all                     # 全部章节

图表输出方式：
    默认（静态）：生成时把 Mermaid 图预先渲染成 SVG 写进 HTML，打开时无需联网、无需脚本。
        需要：pip install playwright && playwright install chromium
              npm install mermaid@10.9.1   （在仓库根目录执行，生成 node_modules/mermaid）
    --cdn：不预渲染，打开 HTML 时从 cdn.jsdelivr.net 加载 Mermaid（需联网）。
"""
import argparse
import html
import re
from pathlib import Path

import markdown

MERMAID_CDN = 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js'
CN_NUM = '一二三四五六七八九十'


def split_chapter(md, chapter):
    """保留文档标题 + 指定章（# 一、… 到下一个一级标题之前）。"""
    if chapter == 'all':
        return md
    idx = int(chapter) - 1
    title = re.match(r'#\s+[^\n]+\n', md)
    head = title.group(0) if title else ''
    pat = re.compile(rf'^#\s+{CN_NUM[idx]}、[^\n]*\n.*?(?=^#\s+\S|\Z)', re.S | re.M)
    m = pat.search(md)
    if not m:
        raise SystemExit(f'未找到第 {chapter} 章')
    return head + '\n' + m.group(0)


def render_layers(src):
    """```layers 块：每行“层名 | 组件1, 组件2*”，* 表示已有；以 @ 开头的行作为右侧贯穿栏，
    以 ~ 开头的行（如数据来源）用浅色块。"""
    rows, side = [], None
    for line in src.strip().splitlines():
        if '|' not in line:
            continue
        name, items = [x.strip() for x in line.split('|', 1)]
        items = [x.strip() for x in items.split(',') if x.strip()]
        if name.startswith('@'):
            side = (name[1:], items)
        else:
            rows.append((name, items))
    h = ['<div class="arch">', '<div class="arch-main">']
    for name, items in rows:
        src_row = name.startswith('~')
        name = name.lstrip('~')
        chips = ''.join(
            f'<span class="chip{" have" if it.endswith("*") else " src" if src_row else ""}">{html.escape(it.rstrip("*"))}</span>'
            for it in items)
        h.append(f'<div class="arch-row"><div class="arch-name">{html.escape(name)}</div><div class="arch-items">{chips}</div></div>')
    h.append('</div>')
    if side:
        title = '<br/>'.join(html.escape(t) for t in side[0].split('/'))
        h.append('<div class="arch-side"><div class="arch-side-title">' + title + '</div>'
                 + ''.join(f'<div class="arch-side-item">{html.escape(x)}</div>' for x in side[1]) + '</div>')
    h.append('</div>')
    return ''.join(h)


def render_components(src):
    """```components 块：每行“能力组 | 组件*, 组件+, 组件”；* 已有，+ 升级，无标记为新建。"""
    cols = []
    for line in src.strip().splitlines():
        if '|' not in line:
            continue
        name, items = [x.strip() for x in line.split('|', 1)]
        cols.append((name, [x.strip() for x in items.split(',') if x.strip()]))
    legend = ('<div class="cmp-legend"><span class="cmp have">已有</span><span class="cmp up">升级</span>'
              '<span class="cmp new">新建</span></div>')
    h = [legend, f'<div class="cmp-grid" style="grid-template-columns: repeat({len(cols)}, minmax(0, 1fr));">']
    for name, items in cols:
        cells = []
        for it in items:
            cls = 'have' if it.endswith('*') else 'up' if it.endswith('+') else 'new'
            cells.append(f'<div class="cmp {cls}">{html.escape(it.rstrip("*+"))}</div>')
        h.append(f'<div class="cmp-col"><div class="cmp-head">{html.escape(name)}</div>{"".join(cells)}</div>')
    h.append('</div>')
    return ''.join(h)


def render_kpi(src):
    """```kpi 块：每行“指标名 | 目标值”，渲染为 PPT 底部的“关键指标”条。"""
    tiles = []
    for line in src.strip().splitlines():
        if '|' not in line:
            continue
        name, val = [x.strip() for x in line.split('|', 1)]
        tiles.append(f'<div class="kpi-tile"><div class="kpi-val">{html.escape(val)}</div>'
                     f'<div class="kpi-name">{html.escape(name)}</div></div>')
    return ('<div class="kpi"><div class="kpi-head">关键指标</div>'
            f'<div class="kpi-grid" style="grid-template-columns: repeat({len(tiles)}, minmax(0, 1fr));">'
            + ''.join(tiles) + '</div></div>')


def convert(md):
    blocks = []
    layer_blocks = []
    kpi_blocks = []

    def keep_kpi(m):
        kpi_blocks.append(render_kpi(m.group(1)))
        return f'\n\nKPIBLOCK{len(kpi_blocks) - 1}\n\n'

    md = re.sub(r'```kpi\s*\n(.*?)```', keep_kpi, md, flags=re.S)

    def keep_comp(m):
        layer_blocks.append(render_components(m.group(1)))
        return f'\n\nLAYERBLOCK{len(layer_blocks) - 1}\n\n'

    md = re.sub(r'```components\s*\n(.*?)```', keep_comp, md, flags=re.S)

    def keep_layers(m):
        layer_blocks.append(render_layers(m.group(1)))
        return f'\n\nLAYERBLOCK{len(layer_blocks) - 1}\n\n'

    md = re.sub(r'```layers\s*\n(.*?)```', keep_layers, md, flags=re.S)

    def keep(m):
        blocks.append(m.group(1).strip())
        return f'\n\nMERMAIDBLOCK{len(blocks) - 1}\n\n'

    md = re.sub(r'```mermaid\s*\n(.*?)```', keep, md, flags=re.S)
    # 列表前补空行（Markdown 要求列表与上一段之间有空行）
    md = re.sub(r'(?m)^((?![ \t]*(?:[-*+] |\d+\. |\|)).+)\n(?=[ \t]*(?:[-*+] |\d+\. ))', r'\1\n\n', md)
    body = markdown.markdown(md, extensions=['tables', 'fenced_code', 'sane_lists', 'toc'],
                             extension_configs={'toc': {'permalink': False}})
    for i, frag in enumerate(kpi_blocks):
        body = body.replace(f'<p>KPIBLOCK{i}</p>', frag)
    for i, frag in enumerate(layer_blocks):
        body = body.replace(f'<p>LAYERBLOCK{i}</p>', f'<figure class="diagram">{frag}</figure>')
    for i, code in enumerate(blocks):
        fig = f'<figure class="diagram"><pre class="mermaid">{html.escape(code)}</pre></figure>'
        body = body.replace(f'<p>MERMAIDBLOCK{i}</p>', fig)
    return body


def build_toc(body):
    items = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body)
    out = []
    for lvl, hid, txt in items:
        txt = re.sub('<[^>]+>', '', txt)
        out.append(f'<a class="l{lvl}" href="#{hid}">{txt}</a>')
    return '\n'.join(out)


TEMPLATE = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --p: #776CFD; --b: #5D95F1; --dp: #655BE6; --org: #F08A3C;
  --ink: #2B2F42; --mut: #5E6478; --line: #E3E1F7; --t1: #F6F5FF; --t2: #ECEAFF; --bg: #FFFFFF;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.75 -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif; }}
.layout {{ display: grid; grid-template-columns: 250px minmax(0, 1fr); max-width: 1320px; margin: 0 auto; }}
nav {{ position: sticky; top: 0; height: 100vh; overflow: auto; padding: 32px 18px 32px 24px; border-right: 1px solid var(--line); }}
nav .brand {{ font-weight: 700; color: var(--dp); margin-bottom: 14px; font-size: 15px; }}
nav a {{ display: block; color: var(--mut); text-decoration: none; padding: 4px 8px; border-radius: 6px; font-size: 13.5px; }}
nav a.l2 {{ color: var(--ink); font-weight: 600; margin-top: 8px; }}
nav a.l3 {{ padding-left: 20px; }}
nav a:hover {{ background: var(--t2); color: var(--dp); }}
main {{ padding: 40px 56px 96px; min-width: 0; }}
.cover {{ background: linear-gradient(120deg, var(--p), var(--b)); color: #fff; border-radius: 16px; padding: 36px 40px; margin-bottom: 36px; }}
.cover h1 {{ margin: 0 0 6px; font-size: 32px; letter-spacing: 1px; }}
.cover .sub {{ opacity: .9; font-size: 15px; }}
.cover h1 {{ color: #fff; border: 0; padding: 0; }}
h1 {{ font-size: 26px; color: var(--dp); margin: 28px 0 12px; padding-bottom: 10px; border-bottom: 2px solid var(--t2); }}
h2 {{ font-size: 21px; margin: 40px 0 12px; padding-left: 12px; border-left: 4px solid var(--p); }}
h3 {{ font-size: 17px; margin: 30px 0 10px; color: var(--dp); }}
p, li {{ color: var(--ink); }}
strong {{ color: var(--dp); }}
blockquote {{ margin: 16px 0; padding: 10px 16px; background: var(--t1); border-left: 4px solid var(--b); border-radius: 0 8px 8px 0; color: var(--mut); }}
blockquote p {{ margin: 4px 0; color: var(--mut); }}
code {{ background: var(--t2); color: var(--dp); padding: 1px 6px; border-radius: 4px; font-size: 13px; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin: 14px 0 20px; font-size: 14px;
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
th {{ background: var(--dp); color: #fff; text-align: left; font-weight: 600; padding: 9px 12px; }}
td {{ padding: 9px 12px; border-top: 1px solid var(--line); vertical-align: top; }}
tr:nth-child(even) td {{ background: var(--t1); }}
td:first-child {{ font-weight: 600; white-space: nowrap; }}
.diagram {{ margin: 16px 0 22px; padding: 18px; background: #FBFBFF; border: 1px solid var(--line); border-radius: 12px; overflow-x: auto; text-align: center; }}
.diagram pre.mermaid {{ margin: 0; background: none; font-size: 14px; }}
.mermaid-svg svg {{ max-width: 100%; height: auto; }}
.arch {{ display: grid; grid-template-columns: minmax(0, 1fr) 170px; gap: 12px; text-align: left; }}
.arch-row {{ display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 10px; align-items: stretch; margin-bottom: 10px; }}
.arch-name {{ background: var(--dp); color: #fff; font-weight: 700; font-size: 14px; border-radius: 8px; display: flex; align-items: center; justify-content: center; text-align: center; padding: 14px 8px; }}
.arch-items {{ display: flex; flex-wrap: nowrap; gap: 10px; align-items: stretch; }}
.chip {{ flex: 1 1 0; min-width: 0; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 13.5px; padding: 12px 4px; border-radius: 8px; background: #fff; border: 1.5px solid #C9C4FB; color: var(--ink); }}
.chip.have {{ background: linear-gradient(120deg, var(--p), var(--b)); color: #fff; border-color: transparent; font-weight: 700; }}
.chip.src {{ background: #E6E2FD; border-color: transparent; }}
.arch-side {{ background: linear-gradient(180deg, var(--dp), var(--p)); border-radius: 10px; padding: 18px 16px; color: #fff; display: flex; flex-direction: column; gap: 10px; margin-bottom: 10px; }}
.arch-side-title {{ font-weight: 700; font-size: 16px; line-height: 1.35; margin-bottom: 14px; }}
.arch-side-item {{ font-size: 14px; opacity: .92; }}
.kpi {{ display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 0; margin: 14px 0 28px; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); }}
.kpi-head {{ background: var(--dp); color: #fff; font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center; }}
.kpi-grid {{ display: grid; background: var(--t1); }}
.kpi-tile {{ padding: 12px 10px; text-align: center; border-left: 1px solid var(--line); }}
.kpi-tile:first-child {{ border-left: 0; }}
.kpi-val {{ font-size: 18px; font-weight: 800; color: var(--dp); line-height: 1.3; }}
.kpi-name {{ font-size: 12.5px; color: var(--mut); margin-top: 4px; }}
.cmp-legend {{ display: flex; gap: 10px; justify-content: flex-start; margin-bottom: 12px; }}
.cmp-legend .cmp {{ padding: 3px 14px; }}
.cmp-grid {{ display: grid; gap: 8px; text-align: left; }}
.cmp-col {{ display: flex; flex-direction: column; gap: 6px; }}
.cmp-head {{ background: var(--dp); color: #fff; font-weight: 600; font-size: 13.5px; text-align: center; padding: 8px 4px; border-radius: 8px; }}
.cmp {{ font-size: 12.5px; text-align: center; padding: 7px 4px; border-radius: 6px; line-height: 1.4; }}
.cmp.have {{ background: linear-gradient(120deg, var(--p), var(--b)); color: #fff; font-weight: 600; }}
.cmp.up {{ background: var(--t2); color: var(--dp); font-weight: 600; }}
.cmp.new {{ background: #fff; color: var(--ink); border: 1.5px dashed var(--org); }}
@media (max-width: 900px) {{ .cmp-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }} }}
@media (max-width: 700px) {{ .arch {{ grid-template-columns: 1fr; }} .arch-row {{ grid-template-columns: 1fr; }} .arch-items {{ flex-wrap: wrap; }} .chip {{ flex: 1 1 70px; }} .kpi {{ grid-template-columns: 1fr; }} .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }} }}
hr {{ border: 0; border-top: 1px dashed var(--line); margin: 36px 0; }}
@media (max-width: 900px) {{
  .layout {{ grid-template-columns: 1fr; }}
  nav {{ display: none; }}
  main {{ padding: 24px 16px 64px; }}
}}
@media print {{
  nav {{ display: none; }} .layout {{ grid-template-columns: 1fr; }} main {{ padding: 0; }}
  h2, h3 {{ break-after: avoid; }} .diagram, table {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="layout">
<nav><div class="brand">{title}</div>
{toc}
</nav>
<main>
<div class="cover"><h1>{title}</h1><div class="sub">{subtitle}</div></div>
{body}
</main>
</div>
<script src="{mermaid_src}"></script>
<script>
mermaid.initialize({{
  startOnLoad: true, securityLevel: 'loose', theme: 'base',
  flowchart: {{ htmlLabels: true, curve: 'basis', padding: 12 }},
  themeVariables: {{
    fontFamily: '"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif', fontSize: '14px',
    primaryColor: '#ECEAFF', primaryBorderColor: '#776CFD', primaryTextColor: '#2B2F42',
    lineColor: '#8C84F0', secondaryColor: '#E6EEFD', tertiaryColor: '#F6F5FF',
    clusterBkg: '#F6F5FF', clusterBorder: '#C9C4FB', edgeLabelBackground: '#FFFFFF'
  }}
}});
</script>
</body>
</html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', default='AI＋数据平台建设汇报_正文.md')
    ap.add_argument('-o', '--output', default=None)
    ap.add_argument('--chapter', default='1', help='1 / 2 / 3 / all')
    ap.add_argument('--mermaid-src', default=MERMAID_CDN, help='Mermaid 脚本地址（--cdn 模式使用）')
    ap.add_argument('--cdn', action='store_true', help='不预渲染，打开时从 CDN 加载图表')
    ap.add_argument('--mermaid-js', default='node_modules/mermaid/dist/mermaid.min.js', help='本地 mermaid.min.js（静态模式）')
    ap.add_argument('--browser', default=None, help='Chromium 可执行文件路径（可选）')
    a = ap.parse_args()

    md = Path(a.input).read_text(encoding='utf-8')
    title_m = re.match(r'#\s+([^\n]+)', md)
    title = title_m.group(1).strip() if title_m else '汇报'
    part = split_chapter(md, a.chapter)
    # 去掉文档级标题和进度说明，由封面区展示
    part = re.sub(r'^#\s+[^\n]+\n', '', part, count=1)
    part = re.sub(r'^(>[^\n]*\n)+', '', part.lstrip('\n'))
    body = convert(part)
    chap_title = re.search(r'<h1 id="[^"]*">(.*?)</h1>', body)
    subtitle = re.sub('<[^>]+>', '', chap_title.group(1)) if chap_title and a.chapter != 'all' else '建设汇报'
    out = Path(a.output or ('数据平台.html' if a.chapter == '1' else f'{title}.html'))
    page = TEMPLATE.format(title=html.escape(title), subtitle=html.escape(subtitle), toc=build_toc(body),
                           body=body, mermaid_src=a.mermaid_src)
    if not a.cdn:
        page = prerender(page, Path(a.mermaid_js), a.browser)
    out.write_text(page, encoding='utf-8')
    print('已生成', out, '（图表已预渲染为 SVG）' if not a.cdn else '（图表通过 CDN 加载）')


def prerender(page, mermaid_js, browser=None):
    """用无头浏览器把 Mermaid 渲染成 SVG，写回 HTML，并去掉脚本。"""
    if not mermaid_js.exists():
        raise SystemExit(f'未找到 {mermaid_js}，请先 npm install mermaid@10.9.1，或加 --cdn')
    from playwright.sync_api import sync_playwright
    js = mermaid_js.read_text(encoding='utf-8')
    page = re.sub(r'<script src="[^"]*"></script>', lambda _: '<script>' + js + '</script>', page, count=1)
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(page)
        tmp = f.name
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=browser) if browser else p.chromium.launch()
        pg = b.new_page(viewport={'width': 1400, 'height': 900})
        pg.goto('file://' + tmp)
        pg.wait_for_function("document.querySelectorAll('pre.mermaid').length === "
                             "document.querySelectorAll('pre.mermaid svg').length", timeout=60000)
        bad = pg.locator('text=Syntax error').count()
        if bad:
            print(f'警告：{bad} 张图有语法错误')
        html_out = pg.evaluate("""() => {
            document.querySelectorAll('pre.mermaid').forEach(pre => {
                const d = document.createElement('div'); d.className = 'mermaid-svg'; d.innerHTML = pre.innerHTML;
                pre.replaceWith(d);
            });
            document.querySelectorAll('script').forEach(s => s.remove());
            return '<!doctype html>\\n' + document.documentElement.outerHTML;
        }""")
        b.close()
    Path(tmp).unlink(missing_ok=True)
    return html_out


if __name__ == '__main__':
    main()
