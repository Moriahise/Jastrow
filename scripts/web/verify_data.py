#!/usr/bin/env python3
"""Verify all source bytes, dictionary payloads and snapshot RIDs."""
import json,gzip,zipfile,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'web'
def read(p):return json.loads(gzip.decompress((OUT/p).read_bytes()))
manifest=read('data/archive.json.gz');meta=json.loads((OUT/'data/meta.json').read_text());index=read('data/index.json.gz')
with zipfile.ZipFile(ROOT/'.build/uploaded-original.zip') as z:
 original={p.filename:z.read(p) for p in z.infolist() if not p.is_dir()}
 assert len(manifest)==len(original)==meta['original_files']
 for f in manifest:
  b=gzip.decompress((OUT/f['url']).read_bytes());assert b==original[f['path']],f['path']
  assert hashlib.sha256(b).hexdigest()==f['sha256'] and len(b)==f['bytes']
entries={}
for p in (OUT/'data/entries').glob('*.json.gz'):entries.update(json.loads(gzip.decompress(p.read_bytes())))
assert len(entries)==meta['entries']==len(index)
assert {r['id'] for r in index}==set(entries)
assert sum(r['kind']=='catalog' for r in index)==meta['klein_pending']
upstream={e['rid']:e for p in (ROOT/'.build/data-upstream').glob('jastrow-*.json') for e in json.loads(p.read_text())}
imported={e['raw']['rid']:e['raw']['upstream_original'] for e in entries.values() if 'upstream_original' in e['raw']}
assert len(upstream)==32512 and imported==upstream
raws={json.dumps(e['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')) for e in entries.values()}
for name in ['sefaria_cache/sefaria_lexicon_cache.json','sefaria_cache/_back_sefaria_lexicon_cache.json']:
 for data in [json.loads(original[name]),json.loads((ROOT/name).read_text('utf-8-sig'))]:
  for word,v in data.items():
   for raw in v.get('data',[]):assert json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')) in raws,(name,word)
assert len(read('data/sources.json.gz'))==115
history=read('data/history.json.gz');assert len(history['queries'])==meta['history']
# Every imported file URL must resolve inside the published root.
for f in manifest:assert (OUT/f['url']).is_file()
report={'status':'PASS','original_files_byte_identical':len(original),'original_bytes':sum(map(len,original.values())),'jastrow_snapshot_records_verified':len(imported),'search_rows':len(index),'klein_definition_records':meta['lexicons']['Klein Dictionary'],'klein_catalog_headwords':meta['klein_catalog'],'klein_pending_definition_records':meta['klein_pending'],'source_files':meta['source_files'],'history_records':meta['history'],'all_cache_payloads_preserved_from_upload_and_repository':True}
(OUT/'data/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
# Version every module reference together, including the search worker's imports.
# Normalise a previous generated suffix first so repeat verification is idempotent.
import re
module_files=[*OUT.glob('*.mjs'),OUT/'index.html',OUT/'sw.js']
for p in module_files:
 p.write_text(re.sub(r'(\.mjs)\?build=[0-9a-f]{16}',r'\1',p.read_text()))
# A changed data/code snapshot gets a new offline cache, preventing stale data on updates.
fingerprint=hashlib.sha256()
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p.name not in ['sw.js','meta.json','verification.json','offline-files.json']:
  fingerprint.update(str(p.relative_to(OUT)).encode());fingerprint.update(hashlib.sha256(p.read_bytes()).digest())
revision=fingerprint.hexdigest()[:16]
cache_name='beit-hamillon-jastrow-'+revision
for p in module_files:
 p.write_text(re.sub(r"(['\"])((?:\./)?[\w-]+\.mjs)\1",lambda m:m[1]+m[2]+'?build='+revision+m[1],p.read_text()))
meta['cache_name']=cache_name;(OUT/'data/meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
import re
p=OUT/'sw.js';p.write_text(re.sub(r"const VERSION='[^']+'","const VERSION='"+cache_name+"'",p.read_text()))
# Refresh after verification.json exists; ensure every app module is cached offline.
(OUT/'offline-files.json').write_text(json.dumps([str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name!='offline-files.json']))
