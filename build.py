"""Build a portable static page. No third-party Python packages required."""
from pathlib import Path
import json, tempfile, os

ROOT=Path(__file__).resolve().parent
def build():
    data=json.loads((ROOT/'data.json').read_text())
    ids=set(); companies={c['id'] for c in data['companies']}
    for event in data['events']:
        assert event['id'] not in ids, 'Duplicate event ID'
        ids.add(event['id'])
        assert event['company'] in companies
        assert event['category'] in ('brand','pr','product')
        assert event.get('month') is None or 1<=event['month']<=12
        assert event['status'] in ('pending','collected','verified')
        if event['status'] in ('collected','verified'):
            assert event.get('sources'), 'A sourced event must have a source'
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=(ROOT/'template.html').read_text()
    html=template.replace('/*__STYLES__*/',(ROOT/'styles.css').read_text()).replace('/*__APP__*/',(ROOT/'app.js').read_text()).replace('/*__DATA__*/',payload)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=ROOT,delete=False) as f:
        f.write(html); temp=f.name
    os.replace(temp,ROOT/'index.html')
    return len(data['events'])
if __name__=='__main__':print(f'Built index.html with {build()} records')
