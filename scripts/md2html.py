#!/usr/bin/env python3
"""
把汇报正文 Markdown 转成可直接浏览器打开的 HTML（含 Mermaid 架构图 / 流程图）。

依赖：pip install markdown
用法：
    python scripts/md2html.py                                   # 默认：正文第一章 → 数据平台.html
    python scripts/md2html.py -i AI＋数据平台建设汇报_正文.md -o 输出.html --chapter 1
    python scripts/md2html.py --chapter all                     # 全部章节

说明：Mermaid 图通过 CDN 加载（cdn.jsdelivr.net），打开 HTML 时需要联网。
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


def convert(md):
    blocks = []

    def keep(m):
        blocks.append(m.group(1).strip())
        return f'\n\nMERMAIDBLOCK{len(blocks) - 1}\n\n'

    md = re.sub(r'```mermaid\s*\n(.*?)```', keep, md, flags=re.S)
    # 列表前补空行（Markdown 要求列表与上一段之间有空行）
    md = re.sub(r'(?m)^((?![ \t]*(?:[-*+] |\d+\. |\|)).+)\n(?=[ \t]*(?:[-*+] |\d+\. ))', r'\1\n\n', md)
    body = markdown.markdown(md, extensions=['tables', 'fenced_code', 'sane_lists', 'toc'],
                             extension_configs={'toc': {'permalink': False}})
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
    ap.add_argument('--mermaid-src', default=MERMAID_CDN, help='Mermaid 脚本地址（可改为本地文件）')
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
    out.write_text(TEMPLATE.format(title=html.escape(title), subtitle=html.escape(subtitle), toc=build_toc(body),
                                   body=body, mermaid_src=a.mermaid_src), encoding='utf-8')
    print('已生成', out)


if __name__ == '__main__':
    main()
