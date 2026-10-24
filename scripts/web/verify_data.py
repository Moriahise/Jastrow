#!/usr/bin/env python3
"""Verify all source bytes, dictionary payloads and snapshot RIDs."""
import json,gzip,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'web'
def read(p):return json.loads(gzip.decompress((OUT/p).read_bytes()))
meta=json.loads((OUT/'data/meta.json').read_text());index=read('data/index.json.gz')
entries={}
for p in (OUT/'data/entries').glob('*.json.gz'):entries.update(json.loads(gzip.decompress(p.read_bytes())))
allowed={'Jastrow Dictionary','Klein Dictionary','BDB Dictionary','BDB Aramaic Dictionary','BDB Augmented Strong',"Strong's Hebrew & Aramaic"}
assert set(meta['lexicons'])<=allowed
assert all(e['lexicon'] in allowed and e['kind'] in ['lexicon','catalog'] for e in entries.values())
assert len(entries)==meta['entries']==len(index)
assert {r['id'] for r in index}==set(entries)
assert sum(r['kind']=='catalog' for r in index)==meta['klein_pending']
for forbidden in ['history.json.gz','archive.json.gz']:
 assert not (OUT/'data'/forbidden).exists()
assert not (OUT/'archive').exists() and not (OUT/'audio_cache').exists()
upstream={e['rid']:e for p in (ROOT/'.build/data-upstream').glob('jastrow-*.json') for e in json.loads(p.read_text())}
imported={e['raw']['rid']:e['raw']['upstream_original'] for e in entries.values() if 'upstream_original' in e['raw']}
assert len(upstream)==32512 and imported==upstream
# Verify every imported Strong's record against the same pinned XML projection.
from import_strongs import load_strongs,LEXICON as STRONGS_LEXICON
strongs_path=ROOT/'.build/data-upstream/strongs/StrongHebrewG.xml'
expected_strongs={r['strong_id']:r for r in load_strongs(strongs_path)}
actual_strongs={e['raw']['strong_id']:e['raw'] for e in entries.values() if e['lexicon']==STRONGS_LEXICON}
assert actual_strongs==expected_strongs and len(actual_strongs)==8674
assert gzip.decompress((OUT/'data/strongs-source.xml.gz').read_bytes())==strongs_path.read_bytes()
sources=read('data/sources.json.gz');assert len(sources)==114
for src in sources:
 assert gzip.decompress((OUT/src['url']).read_bytes())==(ROOT/src['path']).read_bytes()
 assert hashlib.sha256((ROOT/src['path']).read_bytes()).hexdigest()==src['sha256']
report={'status':'PASS','public_lexicons_only':True,'personal_data_in_public_build':False,'jastrow_snapshot_records_verified':len(imported),'strongs_records_verified':len(actual_strongs),'strongs_original_xml_byte_identical':True,'search_rows':len(index),'klein_definition_records':meta['lexicons']['Klein Dictionary'],'klein_catalog_headwords':meta['klein_catalog'],'klein_pending_definition_records':meta['klein_pending'],'public_source_files':len(sources),'public_catalogue_works':meta['library_works']}
(OUT/'data/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
# Version code and styles together, including the search worker's imports.
# Normalise a previous generated suffix first so repeat verification is idempotent.
import re
module_files=[*OUT.glob('*.mjs'),OUT/'index.html',OUT/'sw.js']
for p in module_files:
 p.write_text(re.sub(r'(\.(?:mjs|css))\?build=[0-9a-f]{16}',r'\1',p.read_text()))
# A changed data/code snapshot gets a new offline cache, preventing stale data on updates.
fingerprint=hashlib.sha256()
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p.name not in ['sw.js','meta.json','verification.json','offline-files.json']:
  fingerprint.update(str(p.relative_to(OUT)).encode());fingerprint.update(hashlib.sha256(p.read_bytes()).digest())
revision=fingerprint.hexdigest()[:16]
cache_name='beit-hamillon-public-'+revision
for p in module_files:
 p.write_text(re.sub(r"(['\"])((?:\./)?[\w-]+\.(?:mjs|css))\1",lambda m:m[1]+m[2]+'?build='+revision+m[1],p.read_text()))
meta['cache_name']=cache_name;(OUT/'data/meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
import re
p=OUT/'sw.js';p.write_text(re.sub(r"const VERSION='[^']+'","const VERSION='"+cache_name+"'",p.read_text()))
# Refresh after verification.json exists; ensure every app module is cached offline.
(OUT/'offline-files.json').write_text(json.dumps([str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name!='offline-files.json']))
