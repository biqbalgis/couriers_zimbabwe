"""Render self-contained document editions to stdout; caller applies file updates.

Requires the documentation-only Python markdown package already in this environment.
Usage: python docs/render_documents.py
"""
import json
import re
import sys
from pathlib import Path
import markdown

ROOT=Path(__file__).resolve().parent
CSS='''*{box-sizing:border-box}body{margin:0;background:#f3f6f4;color:#24392f;font:16px/1.65 Arial,Helvetica,sans-serif}.toolbar{background:#102f28;color:white;padding:16px 24px;display:flex;flex-wrap:wrap;gap:18px}.toolbar a{color:white;font-size:14px}.document{max-width:1120px;margin:32px auto;padding:48px 56px;background:white;border:1px solid #e0e8e3;border-radius:12px}h1,h2,h3{color:#000;line-height:1.25;scroll-margin-top:24px}h1{font-size:36px}h2{font-size:25px;margin-top:40px;border-bottom:1px solid #e0e8e3;padding-bottom:10px}h3{font-size:19px;margin-top:28px}a{color:#146c56}code{font:13px Consolas,monospace;overflow-wrap:anywhere}pre{background:#f5f7f5;padding:18px;border:1px solid #e0e8e3;border-radius:6px;overflow:auto}.table-wrap{overflow-x:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.5}th,td{border:1px solid #d9d9d9;padding:10px 12px;text-align:left;vertical-align:middle;overflow-wrap:anywhere}th{background:#eaf0ec;color:black}tr:nth-child(even) td{background:#fafcfb}figure{margin:24px 0}figure svg{width:100%;height:auto;display:block}figcaption,footer{font-size:13px;color:#62766d}li{margin:6px 0}details{margin:16px 0}summary{cursor:pointer}footer{border-top:1px solid #e0e8e3;margin-top:40px;padding-top:16px}@media(max-width:700px){.document{margin:12px;padding:24px 18px}h1{font-size:28px}table{font-size:12px}}@media print{@page{size:A4;margin:18mm}.toolbar{display:none}body{background:white;font-size:10.5pt}.document{border:0;margin:0;padding:0;max-width:none}h1{font-size:25pt}h2{font-size:17pt;break-after:avoid}h3{font-size:13pt;break-after:avoid}table{font-size:8.5pt}thead{display:table-header-group}tr,figure{break-inside:avoid}.table-wrap{overflow:visible}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{display:none}}'''

def render(path):
    source=path.read_text(encoding='utf-8')
    content=markdown.markdown(source,extensions=['tables','fenced_code','toc'])
    content=re.sub(r'<table>(.*?)</table>',r'<div class="table-wrap"><table>\1</table></div>',content,flags=re.S)
    def embed(name,caption):
        return '<figure>'+ (ROOT/name).read_text(encoding='utf-8')+'<figcaption>'+caption+'</figcaption></figure>'
    content=re.sub(r'<p><img alt="([^"]*)" src="([^"]*\.svg)" /></p>',lambda m:embed(m.group(2),m.group(1)),content)
    content=re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',r'<details><summary>Editable Mermaid diagram source</summary><pre><code>\1</code></pre></details>',content,flags=re.S)
    if path.stem=='workflows' and 'workflow.svg' not in source:
        svg=(ROOT/'workflow.svg').read_text(encoding='utf-8')
        content=content.replace('<details>','<figure>'+svg+'<figcaption>Booking through assisted settlement</figcaption></figure><details>',1)
    content=re.sub(r'href="([^"#]+)\.md(#[^"]*)?"',lambda m:'href="'+m.group(1)+'.html'+(m.group(2) or '')+'"',content)
    title=source.splitlines()[0].lstrip('# ')
    nav='<nav class="toolbar" aria-label="Document navigation">'+''.join(f'<a href="{name}.html">{label}</a>' for name,label in [('use-cases','Use cases'),('workflows','Workflows'),('database','Database and ER'),('proposal-audit','Proposal audit'),('launch-runbook','Launch runbook'),('training','Training')])+'</nav>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+CSS+'</style></head><body>'+nav+'<main class="document">'+content+'<footer>Source-verified implementation. See the document header and update notes for version details. Print from the browser for a PDF copy.</footer></main></body></html>'

selected=[ROOT/name for name in sys.argv[1:]] if sys.argv[1:] else ROOT.glob('*.md')
print(json.dumps({p.with_suffix('.html').name:render(p) for p in selected}))
