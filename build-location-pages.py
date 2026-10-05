"""Rebuild the two drafts from the original download and editable location data.

Both the HTML and Next.js server-component payload are updated together so the
original navigation, footer, and webinar components can still hydrate normally.
"""
from pathlib import Path
from html import escape
from bs4 import BeautifulSoup, Tag, NavigableString
import json
import re

ROOT = Path(__file__).resolve().parent
pages = json.loads((ROOT / 'location-pages.json').read_text(encoding='utf-8'))
credits = json.loads((ROOT / 'school-photo-sources.json').read_text(encoding='utf-8'))
credit_map = {item['file']: item for item in credits}
assets = json.loads((ROOT / 'asset-manifest.json').read_text(encoding='utf-8'))['assets']
base = (ROOT / 'original.html').read_text(encoding='utf-8')
for url, entry in sorted(assets.items(), key=lambda item: -len(item[0])):
    local = '/' + entry['path']
    base = base.replace(url, local).replace(url.replace('/', '\\/'), local.replace('/', '\\/'))
base = base.replace('</head>', '<link rel="stylesheet" href="/location-pages.css"><script src="/local-preview.js"></script></head>')
calendar = 'https://luma.com/embed/calendar/cal-HPMbRCcE9xVSR7g/events?tag=Bay%20Area'

def react_node(node):
    if isinstance(node, NavigableString):
        return str(node)
    props = {}
    for key, value in node.attrs.items():
        key = {'class': 'className', 'tabindex': 'tabIndex', 'frameborder': 'frameBorder'}.get(key, key)
        if key == 'disabled':
            value = True
        props[key] = ' '.join(value) if isinstance(value, list) else value
    children = [react_node(child) for child in node.contents]
    if children:
        props['children'] = children[0] if len(children) == 1 else children
    return ['$', node.name, None, props]

def parse_fragment(html):
    soup = BeautifulSoup(html, 'html.parser')
    for text in list(soup.find_all(string=True)):
        if not text.strip():
            text.extract()
    return soup.find()

def school_card(school):
    sample = '<span class="local-sample-badge">Sample data</span>' if school['sample'] else ''
    results = ''.join(f'<li><strong>{count}</strong><span>admitted to {escape(college)}</span></li>' for count, college in school['results'])
    return f'''<article class="local-school-card"><img class="local-school-photo local-school-photo-{school['photo'].split('.')[0]}" src="/assets/schools/{school['photo']}" alt="{escape(school['alt'])}" width="1000" height="400" loading="eager"><div class="local-school-body"><div class="local-school-topline"><h3>{escape(school['name'])}</h3>{sample}</div><ul class="local-school-results">{results}</ul></div></article>'''

def photo_credits(schools):
    items = []
    for school in schools:
        credit = credit_map[school['photo']]
        author = credit.get('author', credit.get('credit', school['name']))
        license = f' · <a href="{credit["license_url"]}" target="_blank" rel="noopener noreferrer">{credit["license"]}</a>' if credit.get('license_url') else ''
        items.append(f'<li>{escape(school["name"])}: <a href="{credit["source"]}" target="_blank" rel="noopener noreferrer">{escape(author)}</a>{license}. Cropped for display.</li>')
    return '<details class="local-photo-credits"><summary>Photo credits</summary><ul>' + ''.join(items) + '</ul></details>'

def hero(page):
    stats = ''.join(f'<div class="local-stat"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>' for value, label in page['stats'])
    return parse_fragment(f'''<section class="local-hero"><div class="local-shell local-hero-layout"><div><p class="local-eyebrow">{escape(page['eyebrow'])}</p><h1>College admissions events for {escape(page['name'])} families</h1><p class="local-hero-description">{escape(page['description'])}</p></div><aside class="local-stat-card" aria-label="Admissions metrics">{stats}<p class="local-metrics-note">{escape(page['metrics_note'])}</p></aside></div></section>''')

def conversion_area(page):
    cards = ''.join(school_card(school) for school in page['schools'])
    return parse_fragment(f'''<div class="local-shell local-conversion-layout"><section class="local-schools" aria-labelledby="local-school-title"><p class="local-section-eyebrow">Local schools · College admissions</p><h2 id="local-school-title">From local schools to top colleges</h2><p class="local-section-description">{escape(page['school_description'])}</p><div class="local-school-carousel" role="region" aria-roledescription="carousel" aria-label="High school admissions results"><div class="local-carousel-stage"><div class="local-school-track" tabindex="0" aria-label="School photos and admissions data. Use arrow keys or swipe to browse.">{cards}</div><button type="button" class="local-carousel-arrow local-carousel-previous" data-carousel-step="-1" aria-label="Previous schools" disabled="disabled"><span aria-hidden="true">←</span></button><button type="button" class="local-carousel-arrow local-carousel-next" data-carousel-step="1" aria-label="Next schools"><span aria-hidden="true">→</span></button></div><div class="local-carousel-controls"><p class="local-carousel-hint" aria-live="polite">4 schools · Use arrows or swipe</p></div></div><p class="local-results-note">{escape(page['sample_note'])}</p>{photo_credits(page['schools'])}</section><section class="local-events" id="events" aria-labelledby="local-events-title"><div class="local-events-intro"><p class="local-section-eyebrow">In your area</p><h2 id="local-events-title">Upcoming local events</h2><p class="local-section-description">Explore Bay Area college admissions events near {escape(page['name'])}. Select an event to see the details and register.</p><a class="local-button local-event-button" href="{escape(calendar)}" target="_blank" rel="noopener noreferrer">View event calendar <span aria-hidden="true">↗</span></a></div><div class="local-calendar"><iframe src="{escape(calendar)}" title="Empowerly Bay Area events for {escape(page['name'])} families" loading="eager"></iframe></div></section></div>''')

def bottom_consultation(page):
    return parse_fragment(f'''<section class="local-bottom-consultation"><div class="local-shell"><p class="local-section-eyebrow">Your next step</p><h2>Build your college admissions plan</h2><p>Get personalized guidance for your {escape(page['name'])} student from an Empowerly counselor.</p><a class="local-button local-button-white" href="https://empowerly.com/consult/" target="_blank" rel="noopener noreferrer">Book a free consultation <span aria-hidden="true">↗</span></a></div></section>''')

for slug, page in pages.items():
    source = base if slug == 'palo-alto' else base.replace('Palo Alto', page['name']).replace('palo-alto', slug)
    soup = BeautifulSoup(source, 'html.parser')
    hero_node, conversion_node = hero(page), conversion_area(page)
    bottom_node = bottom_consultation(page)
    content = soup.select_one('#main-content')
    original_children = content.find_all(recursive=False)
    for child in original_children[:8]:
        child.extract()
    content.insert(0, conversion_node)
    content.insert(0, hero_node)
    content.append(bottom_node)
    scripts = []
    flight = ''
    for script in soup.find_all('script'):
        match = re.fullmatch(r'self.__next_f.push\(\[1,(.*)\]\)', script.string or '', re.S)
        if match:
            scripts.append(script)
            flight += json.loads(match.group(1))
    lines = flight.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith('20:'):
            record = json.loads(line[3:])
            container_props = record[1][3]['children'][1][3]
            original_react_children = container_props['children']
            container_props['children'] = [react_node(hero_node), react_node(conversion_node)] + original_react_children[8:] + [react_node(bottom_node)]
            lines[index] = '20:' + json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n'
        elif line.startswith(('2f:', '30:')):
            lines[index] = line.split(':', 1)[0] + ':null\n'
    # Keep the complete stream intact, including records split across original chunks.
    scripts[0].string = 'self.__next_f.push([1,' + json.dumps(''.join(lines), ensure_ascii=False).replace('</', '<\\/') + '])'
    for script in scripts[1:]:
        script.decompose()
    path = ROOT / 'locations' / slug / 'index.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    output = str(soup)
    path.write_text(output, encoding='utf-8')
    (ROOT / ('index.html' if slug == 'palo-alto' else 'cambrian-park.html')).write_text(output, encoding='utf-8')
    print('Built /locations/' + slug + ' with a photo carousel, events beneath, and a bottom consultation section.')
