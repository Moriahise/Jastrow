#!/usr/bin/env python3
"""Reconstruct the uploaded snapshot byte-for-byte and fetch pinned public data."""
import json,pathlib,subprocess,hashlib,zipfile,urllib.request,concurrent.futures,time,shutil,base64,zlib
ROOT=pathlib.Path(__file__).resolve().parents[2];BUILD=ROOT/'.build';BUILD.mkdir(exist_ok=True)
SNAP=ROOT/'snapshots/upload-2026-10-23';manifest=json.loads((SNAP/'manifest.json').read_text());recipes=json.loads(zlib.decompress(base64.b64decode((SNAP/'recipe.json.zlib.b64').read_text())))
def digest(b):return hashlib.sha256(b).hexdigest()
def restore(r,base):
 if 'ref' in r:
  for k in r['ref']:base=base[k]
  return base
 if 'value' in r:return r['value']
 if 'object' in r:return {k:restore(v,base) for k,v in r['object']}
 return [restore(v,base) for v in r['array']]
with zipfile.ZipFile(BUILD/'uploaded-original.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in manifest['files']:
  data=subprocess.check_output(['git','show',manifest['base_commit']+':'+f['path']],cwd=ROOT)
  assert digest(data)==f['base_sha256'],f['path']+': base differs'
  if f.get('recipe'):data=json.dumps(restore(recipes[f['path']],json.loads(data)),ensure_ascii=False,indent=2).replace('\n','\r\n').encode()
  assert digest(data)==f['sha256'] and len(data)==f['bytes'],f['path']+': snapshot differs'
  z.writestr(f['path'],data)
print('Verified uploaded snapshot:',len(manifest['files']),'byte-identical files',flush=True)
UP=BUILD/'data-upstream';UP.mkdir(exist_ok=True);pins=json.loads((ROOT/'scripts/web/upstream-pins.json').read_text())
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
