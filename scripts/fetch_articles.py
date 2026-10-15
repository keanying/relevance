#!/usr/bin/env python3
"""
抓取网页文章正文并转换为 Markdown。

依赖：
    pip install requests beautifulsoup4 markdownify
    # 可选：遇到需要 JS 渲染或反爬的页面（如知乎）时使用浏览器模式
    pip install playwright && playwright install chromium

用法：
    python scripts/fetch_articles.py                         # 读取 scripts/urls_数据治理.txt
    python scripts/fetch_articles.py -f my_urls.txt -o 参考资料/数据治理
    python scripts/fetch_articles.py URL1 URL2               # 直接传链接
    python scripts/fetch_articles.py --browser               # 全部用浏览器抓取
    python scripts/fetch_articles.py --cookie "z_c0=..."     # 知乎等需要登录的页面，传入浏览器里复制的 Cookie

输出：每篇文章一个 md 文件，另生成 _index.md 汇总抓取结果。
"""
import argparse
import datetime as dt
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as to_md

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# 各站点正文与标题选择器（按顺序尝试）
SITES = {
    'developer.aliyun.com': {
        'content': ['.article-inner', '.article-content', '.markdown-body', 'article'],
        'title': ['h1.article-title', 'h1', 'title'],
    },
    'blog.csdn.net': {
        'content': ['#content_views', '#article_content', 'article'],
        'title': ['#articleContentId', 'h1.title-article', 'h1', 'title'],
    },
    'zhuanlan.zhihu.com': {
        'content': ['.Post-RichText', '.RichText', 'article'],
        'title': ['h1.Post-Title', 'h1', 'title'],
    },
    'baike.baidu.com': {
        'content': ['.J-lemma-content', '.main-content', '[class*="mainContent"]', '[class*="lemmaContent"]'],
        'title': ['h1', 'title'],
    },
}
GENERIC = {'content': ['article', 'main', '.content', '#content', '.post', '.entry-content'], 'title': ['h1', 'title']}

# 正文中需要去掉的元素
NOISE = ['script', 'style', 'noscript', 'iframe', 'svg', 'button', 'form', 'nav', 'footer', 'aside',
         '.hide-article-box', '.recommend-box', '.comment-box', '.toolbar', '.Reward', '.ContentItem-actions',
         '.lemma-reference', '.top-tool', '.edit-icon']


def fetch_requests(url, cookie=None, timeout=20):
    headers = {'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9', 'Referer': f'https://{urlparse(url).netloc}/'}
    if cookie:
        headers['Cookie'] = cookie
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == 'iso-8859-1':
        r.encoding = r.apparent_encoding
    return r.text


def fetch_browser(url, cookie=None, timeout=30):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA, locale='zh-CN')
        if cookie:
            host = urlparse(url).hostname
            domain = '.' + '.'.join(host.split('.')[-2:])
            ctx.add_cookies([{'name': k.strip(), 'value': v.strip(), 'domain': domain, 'path': '/'}
                             for k, v in (c.split('=', 1) for c in cookie.split(';') if '=' in c)])
        page = ctx.new_page()
        page.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        # 滚动以触发懒加载
        for _ in range(6):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(400)
        html = page.content()
        b.close()
        return html


def pick(soup, selectors):
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el
    return None


def largest_block(soup):
    """兜底：取文本最多的 div / section。"""
    best, n = None, 0
    for el in soup.find_all(['article', 'section', 'div']):
        t = len(el.get_text(strip=True))
        if t > n and len(el.find_all('p')) >= 3:
            best, n = el, t
    return best


def clean(el, base_url):
    for sel in NOISE:
        for x in el.select(sel):
            x.decompose()
    # 懒加载图片与相对链接
    for img in el.find_all('img'):
        src = img.get('data-original') or img.get('data-src') or img.get('data-actualsrc') or img.get('src') or ''
        if src.startswith('//'):
            src = 'https:' + src
        img['src'] = src
    for a in el.find_all('a', href=True):
        if a['href'].startswith('//'):
            a['href'] = 'https:' + a['href']
    # 代码块保留语言标记
    for pre in el.find_all('pre'):
        code = pre.find('code')
        if code:
            lang = next((c.replace('language-', '').replace('lang-', '') for c in code.get('class', [])
                         if c.startswith(('language-', 'lang-'))), '')
            pre.string = code.get_text()
            if lang:
                pre['data-lang'] = lang
    return el


def html_to_md(el):
    md = to_md(str(el), heading_style='ATX', bullets='-', strip=['span'],
               code_language_callback=lambda e: e.get('data-lang') or '')
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'[ \t]+\n', '\n', md)
    return md.strip()


def safe_name(s, limit=60):
    s = re.sub(r'[\\/:*?"<>|\s]+', '_', s).strip('_')
    return s[:limit] or 'article'


def extract(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    rule = SITES.get(urlparse(url).netloc, GENERIC)
    tnode = pick(soup, rule['title'])
    title = tnode.get_text(strip=True) if tnode else url
    title = re.sub(r'[-_|]\s*(阿里云开发者社区|CSDN博客|知乎|百度百科).*$', '', title).strip()
    body = pick(soup, rule['content']) or largest_block(soup)
    if body is None:
        raise ValueError('未找到正文（可能需要 --browser 或 --cookie）')
    md = html_to_md(clean(body, url))
    if len(md) < 200:
        raise ValueError(f'正文过短（{len(md)} 字），可能被反爬拦截，建议用 --browser 或 --cookie')
    return title, md


def main():
    ap = argparse.ArgumentParser(description='抓取文章并转为 Markdown')
    ap.add_argument('urls', nargs='*', help='文章链接（不传则读取 -f 文件）')
    ap.add_argument('-f', '--file', default=str(Path(__file__).with_name('urls_数据治理.txt')))
    ap.add_argument('-o', '--out', default='参考资料/数据治理')
    ap.add_argument('--browser', action='store_true', help='全部使用浏览器（Playwright）抓取')
    ap.add_argument('--cookie', default=None, help='请求 Cookie，用于需要登录的页面')
    ap.add_argument('--sleep', type=float, default=1.5, help='每篇之间的间隔秒数')
    a = ap.parse_args()

    urls = a.urls or [l.strip() for l in Path(a.file).read_text(encoding='utf-8').splitlines()
                      if l.strip() and not l.strip().startswith('#')]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, url in enumerate(urls, 1):
        print(f'[{i}/{len(urls)}] {url}')
        title, md, err = None, None, None
        modes = ['browser'] if a.browser else ['requests', 'browser']
        for mode in modes:
            try:
                html = fetch_browser(url, a.cookie) if mode == 'browser' else fetch_requests(url, a.cookie)
                title, md = extract(html, url)
                err = None
                break
            except ImportError:
                err = '需要浏览器模式但未安装 playwright（pip install playwright && playwright install chromium）'
            except Exception as e:  # noqa: BLE001
                err = f'{mode}: {e}'
        if md:
            fname = f'{i:02d}_{safe_name(title)}.md'
            meta = f'> 来源：{unquote(url)}\n> 抓取时间：{dt.datetime.now():%Y-%m-%d %H:%M}\n'
            (out / fname).write_text(f'# {title}\n\n{meta}\n---\n\n{md}\n', encoding='utf-8')
            print(f'    ✓ {fname}（{len(md)} 字）')
            rows.append(f'| {i} | [{title}]({fname}) | {unquote(url)} | 成功 |')
        else:
            print(f'    ✗ {err}')
            rows.append(f'| {i} | — | {unquote(url)} | 失败：{err} |')
        time.sleep(a.sleep)
    idx = ['# 抓取结果', '', '| # | 标题 | 来源 | 状态 |', '|---|---|---|---|'] + rows
    (out / '_index.md').write_text('\n'.join(idx) + '\n', encoding='utf-8')
    print(f'\n完成：{sum("成功" in r for r in rows)}/{len(rows)}，输出目录：{out.resolve()}')
    return 0 if all('成功' in r for r in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
