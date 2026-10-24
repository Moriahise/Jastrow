#!/usr/bin/env python3
"""Fetch and verify pinned public dictionaries and the source catalogue."""
import json,pathlib,hashlib,urllib.request,concurrent.futures,time
ROOT=pathlib.Path(__file__).resolve().parents[2];BUILD=ROOT/'.build';BUILD.mkdir(exist_ok=True)
UP=BUILD/'data-upstream';UP.mkdir(exist_ok=True);pins=json.loads((ROOT/'scripts/web/upstream-pins.json').read_text())
def digest(b):return hashlib.sha256(b).hexdigest()
def fetch(item):
 rel,meta=item;dest=UP/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists() and digest(dest.read_bytes())==meta['sha256']:return
 for attempt in range(4):
  try:
   with urllib.request.urlopen(meta['url'],timeout=60) as r:data=r.read()
   assert digest(data)==meta['sha256'],rel+': upstream data changed; review and update pins before rebuilding'
   assert len(data)==meta['bytes'];dest.write_bytes(data);print('Verified',rel,flush=True);return
  except Exception:
   if attempt==3:raise
   time.sleep(min(2**attempt,8))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,pins.items()))
rows=[r for p in UP.glob('jastrow-*.json') for r in json.loads(p.read_text())];assert len(rows)==32512 and len({r['rid'] for r in rows})==32512
(UP/'jastrow-manifest.txt').write_text(json.dumps({'source':'https://jastrow.us/data/','original_source':'https://www.sefaria.org/Jastrow','license':'Public Domain','received_entries':len(rows),'missing_rids':[]}))
print('Verified Jastrow snapshot:',len(rows),'unique records',flush=True)
