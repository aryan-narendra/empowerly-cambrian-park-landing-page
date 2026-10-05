"""Serve the downloaded page. Public event queries and images are cached locally."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen
import argparse
import hashlib
import json
import re
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

def query_key(payload):
    canonical = dict(payload)
    canonical['variables'] = {key: value for key, value in payload.get('variables', {}).items() if key not in {'startAfter', 'publishedBefore'}}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

def qualify_local_images(value, origin):
    if isinstance(value, dict):
        return {key: qualify_local_images(item, origin) for key, item in value.items()}
    if isinstance(value, list):
        return [qualify_local_images(item, origin) for item in value]
    if isinstance(value, str) and value.startswith('/assets/cdn/'):
        # The shipped media component prepends its CMS host to relative media URLs.
        from urllib.parse import quote
        return origin + quote(value, safe='/')
    return value

def cache_images(value):
    if isinstance(value, dict):
        return {k: cache_images(v) for k, v in value.items()}
    if isinstance(value, list):
        return [cache_images(v) for v in value]
    if isinstance(value, str) and value.startswith('https://cdn.empowerly.com/'):
        parts = urlsplit(value)
        if Path(unquote(parts.path)).suffix.lower() in {'.webp', '.png', '.jpg', '.jpeg', '.svg', '.gif', '.avif'}:
            path = ROOT / 'assets' / 'cdn' / unquote(parts.path).lstrip('/')
            if not path.resolve().is_relative_to(ROOT):
                return value
            try:
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with urlopen(Request(value, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
                        path.write_bytes(response.read())
                return '/' + path.relative_to(ROOT).as_posix()
            except Exception:
                return value
    return value

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep the launcher readable; the app also issues frequent telemetry requests.
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route in {'/', '/index.html'}:
            self.send_response(302)
            self.send_header('Location', '/locations/palo-alto')
            self.end_headers()
            return
        if route.rstrip('/') == '/locations/palo-alto':
            self.path = '/index.html'
        elif route.rstrip('/') == '/locations/cambrian-park':
            self.path = '/cambrian-park.html'
        # Next.js occasionally loads an extra public chunk when a menu is opened.
        if route.startswith('/_next/static/'):
            path = ROOT / unquote(route).lstrip('/')
            if path.resolve().is_relative_to(ROOT) and not path.exists():
                try:
                    with urlopen(Request('https://empowerly.com' + self.path, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
                        content = response.read()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                except Exception:
                    pass
        super().do_GET()

    def do_POST(self):
        if self.path != '/preview-api/graphql':
            self.send_error(405, 'This local preview only supports reading public event data.')
            return
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        try:
            payload = json.loads(body)
            if re.search(r'\bmutation\b', payload.get('query', '')):
                # The downloaded frontend logs activity with mutations. A local preview
                # acknowledges those without sending them to the production service.
                match = re.search(r'\{\s*(\w+)', payload['query'])
                field = match.group(1) if match else 'localPreview'
                if re.search(r'track|log|record|visit|impression|interaction|session|event', field, re.I):
                    value = {'data': {field: {'success': True, 'message': None, 'id': 'local-preview', 'data': None}}}
                else:
                    value = {'data': {field: None}, 'errors': [{'message': 'This is a local page preview. Use the original Empowerly website to submit forms.'}]}
                result = json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(result)))
                self.end_headers()
                self.wfile.write(result)
                return
            # Canonical JSON makes an identical query use its captured response offline.
            digest = query_key(payload)
            file = DATA / (digest + '.json')
            if file.exists():
                result = file.read_bytes()
            else:
                request = Request('https://connect-api.empowerly.com/graphql', data=body, headers={'Content-Type': 'application/json', 'Origin': 'https://empowerly.com', 'Referer': 'https://empowerly.com/locations/palo-alto'})
                with urlopen(request, timeout=30) as response:
                    value = cache_images(json.load(response))
                result = json.dumps(value, ensure_ascii=False).encode('utf-8')
                file.write_bytes(result)
                file.with_suffix('.request.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
            origin = 'http://' + self.headers.get('Host', '127.0.0.1:4173')
            result = json.dumps(qualify_local_images(json.loads(result), origin), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        except Exception as error:
            self.send_error(502, str(error))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}/locations/palo-alto'
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        if args.open:
            print('A preview may already be running. Opening ' + url, flush=True)
            webbrowser.open(url)
            raise SystemExit(0)
        raise
    print('Empowerly local copy: ' + url, flush=True)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()
