"""Zonkel self-edit engine: site/ + content/*.json  ->  _site/

Runs on every save (GitHub Action or Netlify build). The editor (Pages CMS) only
ever writes content/*.json and uploads photos into site/img/uploads/. Layout and
code stay out of its reach; this script applies the edits to a copy of site/.

What it can change:
  * banner     : one-line announcement above the header on every page
  * hours      : per-day hours -> every hours sentence, the live open/closed line,
                 and Google's structured data (JSON-LD)
  * photos     : swap any photo slot; the upload is cropped to each size the
                 design uses, so the layout never moves
  * more photos: add a photo section (heading + 1..12 photos with captions) to
                 any page, e.g. a group photo on About

Config: tools/edit_config.json (written by make_edit_repo.py, not by the editor).
Needs: Python 3.9+, Pillow.
"""
import copy
import html
import json
import pathlib
import re
import shutil
import sys

from PIL import Image, ImageOps

try:  # iPhone photos arrive as HEIC
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
OUT = ROOT / '_site'
CFG = json.loads((ROOT / 'tools' / 'edit_config.json').read_text(encoding='utf8'))
BASE = CFG.get('base', '')

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
LONG = {d: d.capitalize() for d in DAYS}
SHORT = {d: d[:3].capitalize() for d in DAYS}
JS_IDX = {'sunday': 0, 'monday': 1, 'tuesday': 2, 'wednesday': 3, 'thursday': 4, 'friday': 5, 'saturday': 6}
WS = r'(?: |&nbsp;|&amp;nbsp;)'

esc = lambda v: html.escape(str(v or '').strip(), quote=True)
log = []
USED = set()  # editor uploads consumed by this build


def load(rel, default):
    p = ROOT / 'content' / rel
    if not p.is_file():
        return copy.deepcopy(default)
    return json.loads(p.read_text(encoding='utf8') or 'null') or copy.deepcopy(default)


# ---------------------------------------------------------------- images
def open_upload(rel):
    """Value from the editor, e.g. '/img/uploads/x.jpg' -> PIL image (EXIF-rotated)."""
    rel = str(rel or '').strip()
    if not rel:
        return None
    path = SITE / rel.lstrip('/')
    USED.add(rel.lstrip('/'))
    if not path.is_file():
        log.append(f'WARNING missing photo {rel}')
        return None
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return im.convert('RGB') if im.mode not in ('RGB', 'RGBA') else im


FOCUS = {'middle': (0.5, 0.5), 'top': (0.5, 0.15), 'bottom': (0.5, 0.85), 'left': (0.15, 0.5), 'right': (0.85, 0.5)}


def fit(im, w, h, focus='middle'):
    return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=FOCUS.get(focus, (0.5, 0.5)))


def save(im, dest, quality=84):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.suffix.lower() in ('.jpg', '.jpeg'):
        im.convert('RGB').save(dest, quality=quality, optimize=True, progressive=True)
    elif dest.suffix.lower() == '.webp':
        im.save(dest, quality=quality)
    else:
        im.save(dest, optimize=True)


# ---------------------------------------------------------------- pages
def pages():
    return {p: p.read_text(encoding='utf8') for p in OUT.rglob('*.html')}


def apply_photos(docs):
    for slug, page in CFG['pages'].items():
        data = load(f'pages/{slug}.json', {})
        for key, slot in page.get('slots', {}).items():
            cur = (data.get('photos') or {}).get(key) or {}
            photo = (cur.get('photo') or '').strip()
            focus = cur.get('crop') or 'middle'
            desc = (cur.get('description') or '').strip()
            if photo and (photo != slot['default'] or focus != 'middle'):
                im = open_upload(photo)
                if im is not None:
                    for f in slot['files']:
                        save(fit(im, f['w'], f['h'], focus), OUT / f['file'])
                    log.append(f'photo {slug}/{key} <- {photo} ({focus})')
            if desc and desc != slot.get('alt', ''):
                names = [re.escape('/' + f['file']) for f in slot['files']]
                pat = re.compile(r'<img\b[^>]*(?:' + '|'.join(names) + r')[^>]*>')
                for p, t in docs.items():
                    docs[p] = pat.sub(lambda m: re.sub(r'alt="[^"]*"', f'alt="{esc(desc)}"', m.group(0), count=1), t)
                log.append(f'alt {slug}/{key}')


def more_section(slug, page, data):
    m = data.get('more_photos') or {}
    items = [i for i in (m.get('items') or []) if (i or {}).get('photo')]
    if not items:
        return ''
    figs = []
    for n, it in enumerate(items[:12], 1):
        im = open_upload(it['photo'])
        if im is None:
            continue
        im.thumbnail((1400, 1400))
        rel = f'img/more/{slug}-{n}.jpg'
        save(im, OUT / rel)
        cap = esc(it.get('caption'))
        alt = cap or esc(m.get('heading')) or 'Photo'
        figs.append(f'<figure><img src="/{rel}" alt="{alt}" width="{im.width}" height="{im.height}" loading="lazy">'
                    + (f'<figcaption>{cap}</figcaption>' if cap else '') + '</figure>')
    if not figs:
        return ''
    head = esc(m.get('heading'))
    kick = CFG.get('kick_html', '')
    heading = f'<div class="sec-head c">{kick}<h2>{head}</h2></div>' if head else ''
    cls = 'one' if len(figs) == 1 else ('two' if len(figs) == 2 else 'many')
    log.append(f'more photos {slug}: {len(figs)}')
    return (f'\n  <section class="sec zk-more" aria-label="{head or "Photos"}">\n    <div class="wrap">{heading}'
            f'<div class="zk-grid {cls}">{"".join(figs)}</div></div>\n  </section>\n  ')


def apply_more(docs):
    for slug, page in CFG['pages'].items():
        sec = more_section(slug, page, load(f'pages/{slug}.json', {}))
        if not sec:
            continue
        p = OUT / page['html']
        t = docs[p]
        starts = [m.start() for m in re.finditer(r'<section\b', t)]
        n = page.get('insert_before_section', 2)
        at = starts[n] if len(starts) > n else t.index('</main>')
        docs[p] = t[:at] + sec.strip() + '\n  ' + t[at:]


def apply_banner(docs):
    b = load('settings.json', {}).get('banner') or {}
    text = str(b.get('text') or '').strip()
    if not b.get('show') or not text:
        return
    tag = f'<div class="zk-banner" role="status">{esc(text)}</div>\n'
    for p, t in docs.items():
        docs[p] = t.replace('<header class="hdr">', tag + '<header class="hdr">', 1)
    log.append('banner on')


# ---------------------------------------------------------------- hours
def to_num(s):
    m = re.match(r'\s*(\d{1,2})(?::(\d\d))?\s*([AaPp])', str(s or ''))
    if not m:
        return None
    h, mi, ap = int(m.group(1)) % 12, int(m.group(2) or 0), m.group(3).upper()
    return h + (12 if ap == 'P' else 0) + mi / 60


def t_long(x):
    h, mi = int(x), round((x - int(x)) * 60)
    ap = 'AM' if h < 12 else 'PM'
    h12 = h % 12 or 12
    return f'{h12}:{mi:02d} {ap}' if mi else f'{h12} {ap}'


def t_short(x):
    return t_long(x).rsplit(' ', 1)[0]


def read_hours():
    raw = load('settings.json', {}).get('hours') or {}
    out = {}
    for d in DAYS:
        r = raw.get(d) or {}
        o, c = to_num(r.get('opens')), to_num(r.get('closes'))
        out[d] = (o, c) if r.get('open') and o is not None and c is not None and c > o else None
    return out


def default_hours():
    return {d: (tuple(v) if v else None) for d, v in CFG['hours_default'].items()}


def groups(hours):
    gs, cur = [], None
    for d in DAYS:
        v = hours[d]
        if v is None:
            cur = None
            continue
        if cur and cur['v'] == v:
            cur['days'].append(d)
        else:
            cur = {'v': v, 'days': [d]}
            gs.append(cur)
    return gs


def day_span(days, names):
    return names[days[0]] if len(days) == 1 else f'{names[days[0]]} to {names[days[-1]]}'


def summary(hours, short_days, short_time):
    names = SHORT if short_days else LONG
    tf = (lambda v: f'{t_short(v[0])} to {t_short(v[1])}') if short_time else (lambda v: f'{t_long(v[0])} to {t_long(v[1])}')
    gs = groups(hours)
    if not gs:
        return 'by appointment'
    return '; '.join(f'{day_span(g["days"], names)}, {tf(g["v"])}' for g in gs)


def closed_list(hours):
    c = [LONG[d] for d in DAYS[6:] + DAYS[:6] if hours[d] is None]  # Sunday first, like the site copy
    if not c:
        return None
    return c[0] if len(c) == 1 else ', '.join(c[:-1]) + ' and ' + c[-1]


def ws_pat(text):
    return WS.join(re.escape(w) for w in text.split(' '))


def apply_hours(docs, js_files):
    new, old = read_hours(), default_hours()
    changed = new != old
    # live open/closed line: always table-driven, so it is exercised on every build
    table = [None] * 7
    for d in DAYS:
        table[JS_IDX[d]] = list(new[d]) if new[d] else None
    js_block = ("var D=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],N=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],"
                f"H={json.dumps(table)},d=D.indexOf(p.weekday),t=(+p.hour%24)+(+p.minute)/60,txt,on=false;\n"
                "    var f=function(x){var h=Math.floor(x),m=Math.round((x-h)*60),a=h<12?'AM':'PM';h=h%12||12;return h+(m?':'+(m<10?'0':'')+m:'')+' '+a};\n"
                "    var nx=function(){for(var i=1;i<=7;i++){var n=(d+i)%7;if(H[n])return (i===1?'tomorrow':N[n])+' '+f(H[n][0])}return ''};\n"
                "    if(H[d]&&t>=H[d][0]&&t<H[d][1]){on=true;txt='Open now until '+f(H[d][1])}\n"
                "    else if(H[d]&&t<H[d][0]){txt='Opens today at '+f(H[d][0])}\n"
                "    else{txt='Closed, opens '+nx()}\n"
                "    oh.querySelector('b').textContent=txt;")
    js_pat = re.compile(r"var D=\['Sun'.*?oh\.querySelector\('b'\)\.textContent=txt;", re.S)
    for jf in js_files:
        t = jf.read_text(encoding='utf8')
        t2, n = js_pat.subn(lambda m: js_block, t, count=1)
        if n != 1:
            raise SystemExit(f'hours script not found in {jf}')
        jf.write_text(t2, encoding='utf8')
    if not changed:
        return
    # every hours sentence
    d = CFG['hours_phrases']
    pairs = [
        (d['days_long'], d['time_short'], False, True),
        (d['days_long'], d['time_long'], False, False),
        (d['days_short'], d['time_short'], True, True),
        (d['days_short'], d['time_long'], True, False),
    ]
    total = 0
    for days, tm, sd, st in pairs:
        pat = re.compile(ws_pat(days) + ',' + WS + ws_pat(tm))
        rep = summary(new, sd, st)
        for p, t in docs.items():
            docs[p], n = pat.subn(rep, t)
            total += n
    cl = closed_list(new)
    cpat = re.compile(r"(We're closed|[Cc]losed)" + WS + ws_pat(d['closed']))
    for p, t in docs.items():
        docs[p], n = cpat.subn(lambda m: (f'{m.group(1)} {cl}' if cl else 'Open seven days a week'), t)
        total += n
    # Google's structured data
    spec = [{'@type': 'OpeningHoursSpecification', 'dayOfWeek': [LONG[x] for x in g['days']],
             'opens': '%02d:%02d' % (int(g['v'][0]), round((g['v'][0] % 1) * 60)),
             'closes': '%02d:%02d' % (int(g['v'][1]), round((g['v'][1] % 1) * 60))} for g in groups(new)]

    def fix(node):
        if isinstance(node, dict):
            if 'openingHoursSpecification' in node:
                node['openingHoursSpecification'] = spec
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    ld = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)
    for p, t in docs.items():
        def sub(m):
            try:
                data = json.loads(m.group(2))
            except ValueError:
                return m.group(0)
            fix(data)
            return m.group(1) + json.dumps(data, ensure_ascii=False) + m.group(3)
        docs[p] = ld.sub(sub, t)
    log.append(f'hours changed: {total} sentences rewritten')


# ---------------------------------------------------------------- base path
def rebase(text):
    if not BASE:
        return text
    text = re.sub(r'((?:href|src|action|content)=")/(?!/)', rf'\1{BASE}/', text)
    text = re.sub(r'url\((["\']?)/(?!/)', rf'url(\1{BASE}/', text)
    return re.sub(r'srcset="([^"]*)"', lambda m: 'srcset="' + re.sub(r'(^|,\s*)/(?!/)', rf'\1{BASE}/', m.group(1)) + '"', text)


CSS = """
/* zonkel self-edit */
.zk-banner{background:%(ink)s;color:%(paper)s;text-align:center;padding:10px 16px;font-size:15px;line-height:1.4;font-weight:600}
.zk-more .sec-head{margin-bottom:26px}
.zk-grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.zk-grid.one{grid-template-columns:minmax(0,820px);justify-content:center}
.zk-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
.zk-grid figure{margin:0}
.zk-grid img{display:block;width:100%%;height:auto;border-radius:12px}
.zk-grid.two img,.zk-grid.many img{aspect-ratio:4/3;object-fit:cover;object-position:50%% 30%%}
.zk-grid.one img{max-height:80vh;width:auto;max-width:100%%;margin:0 auto}
.zk-grid figcaption{margin-top:8px;font-size:.92rem;line-height:1.4;opacity:.8;text-align:center}
@media (max-width:640px){.zk-grid.two{grid-template-columns:minmax(0,1fr)}}
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE, OUT)
    (OUT / '.nojekyll').write_text('')
    docs = pages()
    js_files = [OUT / f for f in CFG['hours_js']]
    apply_photos(docs)
    apply_more(docs)
    apply_banner(docs)
    apply_hours(docs, js_files)
    for p, t in docs.items():
        p.write_text(rebase(t), encoding='utf8')
    css = OUT / CFG['css']
    css.write_text(rebase(css.read_text(encoding='utf8') + CSS % CFG['colors']), encoding='utf8')
    for sheet in OUT.rglob('*.css'):
        if sheet != css:
            sheet.write_text(rebase(sheet.read_text(encoding='utf8')), encoding='utf8')
    # raw phone uploads were copied into the slot files above; don't publish the originals
    alltext = ''.join(p.read_text(encoding='utf8') for p in OUT.rglob('*') if p.suffix in ('.html', '.css', '.js', '.xml'))
    for rel in USED:
        f = OUT / rel
        if f.is_file() and pathlib.PurePosixPath(rel).name not in alltext:
            f.unlink()
    print('built', len(docs), 'pages')
    for line in log:
        print(' ', line)
    if any(l.startswith('WARNING') for l in log):
        sys.exit(0)


if __name__ == '__main__':
    main()
