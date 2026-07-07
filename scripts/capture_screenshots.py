"""Capture FieldSight Edge routes in constrained CI environments.

Normal developer workflow: use Playwright (a real browser) to capture the running app.
Fallback used here: print-render the server-rendered demo snapshot when browser policies
block local navigation. It preserves content and styling but simplifies CSS grid/flex layout.
"""
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import urlopen
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'screenshots'
OUT.mkdir(exist_ok=True)
ROUTES = [
    ('00-landing.png', '/landing'), ('01-mission-control.png', '/'),
    ('02-map-workspace.png', '/map'), ('03-image-review.png', '/review'),
    ('04-defects-work-orders.png', '/defects'), ('05-asset-digital-twin.png', '/assets'),
    ('06-edge-fleet.png', '/devices'), ('07-model-registry.png', '/models'),
    ('08-reporting.png', '/reports'),
]

def render(route: str, destination: Path) -> None:
    url = f'http://127.0.0.1:3000{route}'
    html = urlopen(url, timeout=20).read().decode('utf-8')
    css_link = re.search(r'href="([^\"]*layout\.css[^\"]*)"', html)
    if not css_link:
        raise RuntimeError('Next layout stylesheet not found')
    css_url = 'http://127.0.0.1:3000' + css_link.group(1).replace('&amp;', '&')
    css = urlopen(css_url, timeout=20).read().decode('utf-8')
    # WeasyPrint currently hits a layout assertion on this app's nested CSS grids.
    # This keeps the static server-rendered content and core styling visible in CI.
    css = css.replace('display:grid', 'display:block').replace('display:flex', 'display:block').replace('position:fixed', 'position:absolute')
    html = re.sub(r'<link[^>]*layout\.css[^>]*>', '', html)
    html = html.replace('</head>', f'<style>@page{{size:1440px 1000px;margin:0}}html,body{{width:1440px!important;overflow:hidden!important}}{css}</style></head>')
    with tempfile.TemporaryDirectory() as temp:
        pdf = Path(temp) / 'screen.pdf'
        prefix = Path(temp) / 'screen'
        HTML(string=html, base_url=url).write_pdf(str(pdf))
        subprocess.run(['pdftoppm', '-png', '-r', '115', '-singlefile', str(pdf), str(prefix)], check=True)
        destination.write_bytes(prefix.with_suffix('.png').read_bytes())

for filename, route in ROUTES:
    render(route, OUT / filename)
    print(f'captured {filename}')
