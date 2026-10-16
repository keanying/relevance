"""把正文（含 layers / components / figure 等自定义块）转换为标准 Markdown 终稿。

用法：python3 scripts/md2final.py [-i 正文.md] [-o 终稿.md]
- layers / components 块转为表格；figure 块转为要点列表；mermaid 保留。
"""
import argparse
import re
from pathlib import Path

NOTE_MAP = {
    '> 渐变色块为已有能力，白色块为新建或升级。': '> 加粗为已有能力，其余为新建或升级。',
    '> 图例：带 * 为已购 DataWorks 模块（深色）；发布检查脚本、质量校验节点为自建，替代未购的数据标准、数据质量模块。':
        '> 加粗为已购 DataWorks 模块；发布检查脚本、质量校验节点为自建，替代未购的数据标准、数据质量模块。',
    '> 渐变为已有智能体，白框为产品全景中的智能体，浅紫为基于积累可扩展。':
        '> 加粗为已有智能体；标“全景”为产品全景中的智能体，标“扩展”为基于积累可扩展。',
}
DROP_PREFIX = ('> 写法：', '> 本稿按', '> 当前进度', '> 关键指标的目标值为建议值')


def items_of(s):
    return [x.strip() for x in s.split(',') if x.strip()]


def layers_table(src):
    rows, side = [], None
    for line in src.strip().splitlines():
        if '|' not in line:
            continue
        name, items = [x.strip() for x in line.split('|', 1)]
        if name.startswith('@'):
            side = (name[1:].replace('/', ' · '), items_of(items))
            continue
        cells = ['**' + i.rstrip('*') + '**' if i.endswith('*') else i for i in items_of(items)]
        rows.append((name.lstrip('~'), '、'.join(cells)))
    out = ['| 层 | 内容 |', '|---|---|']
    out += [f'| {n} | {c} |' for n, c in rows]
    if side:
        out.append(f'| {side[0]} | ' + '、'.join(side[1]) + ' |')
    return '\n'.join(out)


def components_table(src):
    out = ['| 能力组 | 已有 | 升级 | 新建 |', '|---|---|---|---|']
    for line in src.strip().splitlines():
        if '|' not in line:
            continue
        name, items = [x.strip() for x in line.split('|', 1)]
        have, up, new = [], [], []
        for i in items_of(items):
            (have if i.endswith('*') else up if i.endswith('+') else new).append(i.rstrip('*+'))
        out.append(f'| {name} | ' + ' | '.join('、'.join(x) or '—' for x in (have, up, new)) + ' |')
    return '\n'.join(out)


def status_map(html):
    tag = {'self': 'have', 'oss': '全景', 'buy': '扩展'}
    return {m.group(2).strip(): tag[m.group(1)]
            for m in re.finditer(r'<span class="own (self|oss|buy)">([^<]+)</span>', html)}


def mark(text, smap):
    def one(name):
        k = name.strip()
        st = smap.get(k)
        if st == 'have':
            return f'**{k}**'
        if st:
            return f'{k}（{st}）'
        return k
    return re.sub(r'([^：、；]+)', lambda m: one(m.group(1)), text)


def figure_list(path, src, base):
    lines = [l.strip() for l in src.strip().splitlines() if l.strip()]
    smap = {}
    if '2.2_场景架构' in path:
        smap = status_map((base / path).read_text(encoding='utf-8'))
    out = []
    for l in lines:
        if smap and '：' in l:
            head, rest = l.split('：', 1)
            l = f'{head}：{mark(rest, smap)}'
        if '：' in l and not l.startswith(('①', '②', '③', '④', '⑤')):
            head, rest = l.split('：', 1)
            out.append(f'- **{head}**：{rest}')
        else:
            out.append(f'- {l}')
    return '\n'.join(out)


def convert(md, base):
    md = re.sub(r'```layers\s*\n(.*?)```', lambda m: layers_table(m.group(1)), md, flags=re.S)
    md = re.sub(r'```components\s*\n(.*?)```', lambda m: components_table(m.group(1)), md, flags=re.S)
    md = re.sub(r'```figure[ \t]+(\S+)[^\n]*\n(.*?)```', lambda m: figure_list(m.group(1), m.group(2), base), md, flags=re.S)
    out = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith(DROP_PREFIX):
            continue
        out.append(NOTE_MAP.get(s, line))
    md = '\n'.join(out)
    md = re.sub(r'\n{3,}', '\n\n', md)
    # 目录
    toc = []
    for m in re.finditer(r'(?m)^(#{1,2})\s+(.+)$', md):
        lvl, t = len(m.group(1)), m.group(2).strip()
        if lvl == 1 and t == 'AI＋数据平台':
            continue
        toc.append(('' if lvl == 1 else '  ') + f'- {t}')
    md = re.sub(r'^(# [^\n]+\n)', lambda m: m.group(1) + '\n**目录**\n\n' + '\n'.join(toc) + '\n', md, count=1)
    return md.strip() + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', default='AI＋数据平台建设汇报_正文.md')
    ap.add_argument('-o', '--output', default='AI＋数据平台建设汇报_终稿.md')
    a = ap.parse_args()
    src = Path(a.input)
    Path(a.output).write_text(convert(src.read_text(encoding='utf-8'), src.parent), encoding='utf-8')
    print('已生成', a.output)


if __name__ == '__main__':
    main()
