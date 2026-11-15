"""Recipe extraction shared by cucina and e-ink, using only the standard library."""
import html
import json
import re
import urllib.request
from urllib.parse import urljoin

BROWSER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'


def duration(iso):
    match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not match:
        return ''
    return ' '.join(f'{int(n)} {unit}' for n, unit in zip(match.groups(), ('h', 'min', 's')) if n and int(n))


def quantity(line):
    match = re.fullmatch(r'(.*?)\s+(\d[\d,./]*(?:\s*[^\s\d()]+)?|q\.b\.)', line.strip())
    return (match[1], match[2]) if match else (line.strip(), '')


def plain(text):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', text))).strip()


def recipe_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from recipe_nodes(item)
    elif isinstance(value, dict):
        kind = value.get('@type', '')
        if kind == 'Recipe' or isinstance(kind, list) and 'Recipe' in kind:
            yield value
        if '@graph' in value:
            yield from recipe_nodes(value['@graph'])


def extract(url, page):
    data = None
    for block in re.findall(r'<script\b[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = next(recipe_nodes(json.loads(block)), data)
        except (ValueError, TypeError):
            continue
    if data is None:
        raise ValueError('La pagina non contiene una ricetta leggibile.')
    steps = []
    for chunk in page.split('class="gz-content-recipe-step"')[1:]:
        p = re.search(r'<p[\s>]', chunk)
        start, end = (p.start() if p else -1), chunk.find('</p>')
        if start < 0 or end < start:
            continue
        image = re.search(r'<img src="([^"]+)"', chunk[:start])
        pieces = re.split(r'<span class="num-step">(\d+)</span>', chunk[chunk.find('>', start) + 1:end])
        text = ''.join(html.escape(html.unescape(re.sub(r'<[^>]+>', '', part))) if i % 2 == 0 else f'<span class="ref">{part}</span>' for i, part in enumerate(pieces))
        steps.append({'html': re.sub(r'\s+', ' ', text).strip(), 'img': urljoin(url, image[1]) if image else None})
    if not steps:
        def instructions(items):
            for item in items if isinstance(items, list) else [items]:
                if isinstance(item, dict) and 'itemListElement' in item:
                    yield from instructions(item['itemListElement'])
                else:
                    text = item.get('text', '') if isinstance(item, dict) else str(item)
                    if text:
                        yield {'html': html.escape(plain(text)), 'img': None}
        steps = list(instructions(data.get('recipeInstructions', [])))
    servings = data.get('recipeYield', '')
    servings = servings[0] if isinstance(servings, list) and servings else servings
    match = re.search(r'Dosi per:\s*<strong>([^<]+)</strong>', page)
    servings = plain(match[1]) if match else str(servings)
    difficulty = re.search(r'Difficoltà:\s*<strong>(.*?)</strong>', page, re.S)
    basis = re.search(r'class="gz-text-calories-title">(.*?)</div>', page, re.S)
    remarks = re.search(r'<li class="remarks">(.*?)</li>', page, re.S)
    image = data.get('image') or ''
    if isinstance(image, list):
        image = image[0] if image else ''
    if isinstance(image, dict):
        image = image.get('url') or image.get('contentUrl') or ''
    image = urljoin(url, image) if isinstance(image, str) and image else ''
    nutrition = data.get('nutrition') or {}
    times = [(label, duration(data.get(key))) for label, key in (('Preparazione', 'prepTime'), ('Cottura', 'cookTime'))]
    return {
        'name': html.unescape(data.get('name', '')),
        'servings': servings,
        'times': [(label, value) for label, value in times if value],
        'ingredients': [quantity(html.unescape(i)) for i in data.get('recipeIngredient', [])],
        'steps': steps,
        'url': url,
        'image': image,
        'difficulty': plain(difficulty[1]) if difficulty else '',
        'calories': str(nutrition.get('calories', '')),
        'calorie_basis': plain(basis[1]) if basis else 'Calorie (base non indicata)',
        'remarks': plain(remarks[1]) if remarks else '',
    }


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': BROWSER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return extract(url, response.read().decode('utf-8', errors='replace'))
