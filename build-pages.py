"""Package the captured frontend for static hosting under a project subpath."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--base-path', default='/empowerly-cambrian-park-landing-page/')
parser.add_argument('--output', default='_site')
args = parser.parse_args()
prefix = '/' + args.base_path.strip('/') if args.base_path.strip('/') else ''
output = (ROOT / args.output).resolve()
assert output.is_relative_to(ROOT) and output != ROOT, 'Build output must be inside the project.'
output.mkdir(parents=True, exist_ok=True)

for folder in ('_next', 'assets', 'fonts', 'locations'):
    shutil.copytree(ROOT / folder, output / folder, dirs_exist_ok=True)
for name in ('location-pages.css', 'local-preview.js', 'empowerly-icon.png', 'empowerly-footer-logo.svg', 'cambrian-park.html'):
    shutil.copy2(ROOT / name, output / name)
# The published homepage is the Cambrian Park draft; both location routes remain.
shutil.copy2(ROOT / 'cambrian-park.html', output / 'index.html')

records = []
for request in sorted((ROOT / 'data').glob('*.request.json')):
    payload = json.loads(request.read_text(encoding='utf-8'))
    response = request.with_name(request.name.replace('.request.json', '.json'))
    records.append({'operationName': payload.get('operationName'), 'variables': payload.get('variables', {}), 'response': json.loads(response.read_text(encoding='utf-8'))})
static_data = {'basePath': prefix, 'records': records}
(output / 'static-page-data.js').write_text('window.__EMPOWERLY_STATIC__=' + json.dumps(static_data, ensure_ascii=False).replace('</', '<\\/') + ';', encoding='utf-8')
asset_versions = {
    name: hashlib.sha256((output / name).read_bytes()).hexdigest()[:12]
    for name in ('location-pages.css', 'local-preview.js', 'static-page-data.js')
}

local_roots = ('_next/', 'assets/', 'fonts/', 'location-pages.css', 'local-preview.js', 'empowerly-icon.png', 'empowerly-footer-logo.svg')
for path in output.rglob('*'):
    if not path.is_file() or path.suffix not in {'.html', '.js', '.css'}:
        continue
    text = path.read_text(encoding='utf-8')
    if path.name not in {'static-page-data.js', 'local-preview.js'}:
        for stem in local_roots:
            # Handles HTML, JavaScript strings, and the escaped Flight JSON stream.
            text = text.replace('/' + stem, prefix + '/' + stem)
    if path.suffix == '.html':
        text = text.replace('<script src="' + prefix + '/local-preview.js">', '<script src="' + prefix + '/static-page-data.js"></script><script src="' + prefix + '/local-preview.js">')
        for name, version in asset_versions.items():
            text = text.replace(prefix + '/' + name, prefix + '/' + name + '?v=' + version)
        # Next's original font stylesheet still contains the public CDN URLs;
        # the captured HTML and bundles point to the local copies above.
    path.write_text(text, encoding='utf-8')
(output / '.nojekyll').touch()
print(f'Built static homepage and both location routes at {prefix or "/"}.')
