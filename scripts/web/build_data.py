#!/usr/bin/env python3
"""Lossless archive + non-destructive search projection. Standard library only."""
import pathlib,json,hashlib,gzip,re,html,collections,zipfile,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; OUT=ROOT/'web'; ORIG=ROOT/'.build/uploaded-original.zip'; UP=ROOT/'.build/data-upstream'
def pack(path,data):
 p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
def norm(s):return re.sub(r'[^\u05d0-\u05ea\w\s]','',re.sub(r'[\u0591-\u05c7]','',s)).strip().lower()
def plain(s):return html.unescape(re.sub('<[^>]*>','',str(s)))
entries={};aliases=collections.defaultdict(set);provenance=collections.defaultdict(list)
def add(raw,word,path,kind='lexicon'):
 payload=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'));key=hashlib.sha256(payload.encode()).hexdigest()[:20]
 if key not in entries:
  entries[key]={'id':key,'kind':kind,'raw':raw,'origins':[],'aliases':[]}
 e=entries[key]
 if path not in e['origins']:e['origins'].append(path)
 if word and word not in e['aliases']:e['aliases'].append(word)
 aliases[norm(word)].add(key)
 return key
manifest=[];sources=[];postings=collections.defaultdict(lambda:collections.defaultdict(list));local=collections.defaultdict(lambda:collections.defaultdict(list))
with zipfile.ZipFile(ORIG) as z:
 files={p.filename:z.read(p) for p in z.infolist() if not p.is_dir()}
 def load(n):return json.loads(files[n].decode('utf-8-sig'))
 for i,(name,blob) in enumerate(files.items()):
  dest=f'archive/{i:03d}.gz';p=OUT/dest;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(blob,mtime=0));manifest.append({'path':name,'url':dest,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
  if name.startswith('audio_cache/'):
   p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob)
  if name.startswith('sources/'):
   text=blob.decode('utf-8-sig');lines=text.splitlines();sid=len(sources); ref=''
   for ln,line in enumerate(lines):
    if re.match(r'^Daf \d+[ab]',line):ref=line
    for w in set(re.findall(r'[\u05d0-\u05ea][\u0591-\u05c7\u05d0-\u05ea]*',line)):
     w=norm(w)
     if w:postings[w][sid].append(ln)
   sources.append({'id':sid,'path':name,'title':pathlib.Path(name).stem,'url':dest,'lines':len(lines),'bytes':len(blob)})
 for n in ['sefaria_cache/sefaria_lexicon_cache.json','sefaria_cache/_back_sefaria_lexicon_cache.json']:
  for w,v in load(n).items():
   for e in v.get('data',[]):add(e,w,n)
 for n in ['jastrow_words/jastrow_words_1.json','sefaria_cache/local_sefaria_entries.json']:
  for w,v in load(n).items():
   for e in (v.get('entries',[]) if isinstance(v,dict) else v):add(e,w,n)
 # Keep meanings isolated by tractate and RID: never overwrite a reused ID.
 for tract in ['Bava_Batra','Berakhot','Beitzah']:
  meanings=load(f'dictionaries/merged_dict_{tract}.json')
  def walk(x):
   if isinstance(x,list):
    for y in x:walk(y)
   elif isinstance(x,dict):
    for w,ids in x.items():
     if norm(w):
      for rid in ids if isinstance(ids,list) else [ids]:
       if rid in meanings:
        record={'tractate':tract,'rid':rid,'meanings':meanings[rid]}
        h=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
        local[norm(w)][h]=record
  walk(load(f'dictionaries/{tract}.json'))
 for w,records in local.items():
  add({'headword':w,'lexicon':'Lokale Wortbedeutungen','mappings':list(records.values())},w,'dictionaries/','local')
 for w,v in load('user_dictionary.json').items():add({'headword':w,'lexicon':'Eigene Einträge','items':v},w,'user_dictionary.json','user')
 for w,v in load('sefaria_translations.json').items():add({'headword':w,'lexicon':'Gespeicherte Übersetzungen','items':v},w,'sefaria_translations.json','translation')
 for i,(original,items) in enumerate(load('api_translations/translations_1.json').items()):
  words=list(dict.fromkeys(v.get('word','') for v in items if v.get('word')))
  add({'headword':' · '.join(words) or 'Übersetzung '+str(i+1),'lexicon':'Archivierte KI-Übersetzung','items':items,'source_text':original},words[0] if words else '', 'api_translations/translations_1.json','api')
 history=load('query_history.json');pack('data/history.json.gz',history)
 # Every archived translation remains searchable, including those only in history.
 for q in history.get('queries',[]):
  if q.get('api_translations'):add({'headword':q['word'],'lexicon':'Übersetzung aus Suchverlauf','translations':q['api_translations']},q['word'],'query_history.json','history')
# Include additional records from the pre-existing repository as a second provenance.
for n in ['sefaria_cache/sefaria_lexicon_cache.json','sefaria_cache/_back_sefaria_lexicon_cache.json']:
 p=ROOT/n
 if p.exists():
  for w,v in json.loads(p.read_text('utf-8-sig')).items():
   for raw in v.get('data',[]):add(raw,w,'Repository: '+n)
for n in ['jastrow_words/jastrow_words_1.json','sefaria_cache/local_sefaria_entries.json']:
 p=ROOT/n
 if p.exists():
  for w,v in json.loads(p.read_text('utf-8-sig')).items():
   for raw in v.get('entries',[]) if isinstance(v,dict) else v:add(raw,w,'Repository: '+n)
for n,kind,lex in [('sefaria_translations.json','translation','Gespeicherte Übersetzungen'),('user_dictionary.json','user','Eigene Einträge')]:
 p=ROOT/n
 if p.exists():
  for w,v in json.loads(p.read_text('utf-8-sig')).items():add({'headword':w,'lexicon':lex,'items':v},w,'Repository: '+n,kind)
p=ROOT/'api_translations/translations_1.json'
if p.exists():
 for i,(original,items) in enumerate(json.loads(p.read_text('utf-8-sig')).items()):
  words=list(dict.fromkeys(v.get('word','') for v in items if v.get('word')))
  add({'headword':' · '.join(words) or 'Übersetzung '+str(i+1),'lexicon':'Archivierte KI-Übersetzung','items':items,'source_text':original},words[0] if words else '', 'Repository: api_translations/translations_1.json','api')
p=ROOT/'query_history.json'
if p.exists():
 history_repo=json.loads(p.read_text('utf-8-sig'));seen={json.dumps(v,sort_keys=True,ensure_ascii=False) for v in history.get('queries',[])}
 for q in history_repo.get('queries',[]):
  h=json.dumps(q,sort_keys=True,ensure_ascii=False)
  if h not in seen:history['queries'].append(q);seen.add(h)
  if q.get('api_translations'):add({'headword':q['word'],'lexicon':'Übersetzung aus Suchverlauf','translations':q['api_translations']},q['word'],'Repository: query_history.json','history')
 history['repository_original_stats']=history_repo.get('stats');pack('data/history.json.gz',history)

# Optional complete upstream snapshots imported without modifying local originals.
for p in sorted(UP.glob('*.json')):
 data=json.loads(p.read_text());rows=data.get('entries',[]) if isinstance(data,dict) else data
 if isinstance(rows,list):
  for e in rows:
   if isinstance(e,dict) and (e.get('headword') or e.get('hw')):
    if e.get('hw'):
     def convert(senses):
      return [dict(**({'definition':s['def']} if 'def' in s else {}),**({'grammar':s['gram']} if 'gram' in s else {}),**({'senses':convert(s['senses'])} if s.get('senses') else {})) for s in senses]
     e={'headword':e['hw'],'rid':e['rid'],'parent_lexicon':'Jastrow Dictionary','content':{'senses':convert(e.get('senses',[]))},'refs':e.get('refs',[]),'prev_hw':e.get('prev'),'next_hw':e.get('next'),'upstream_original':e,'parent_lexicon_details':{'attribution':'Marcus Jastrow (1903); digitized by Sefaria','source_url':'https://jastrow.us/data/','license':'Public Domain'}}
    add(e,e.get('headword',e.get('hw')),p.name)
# Full Klein headword catalog, with explicit pending definitions.
klein_catalog={}
for p in sorted((UP/'klein-catalog').glob('*.json')):
 for display,head in json.loads(p.read_text()):klein_catalog[head]=display
known={e['raw'].get('headword') for e in entries.values() if e['raw'].get('parent_lexicon',e['raw'].get('lexicon'))=='Klein Dictionary'}
for head,display in klein_catalog.items():
 if head not in known:add({'headword':head,'parent_lexicon':'Klein Dictionary','pending':True},display,'Sefaria Klein headword completion','catalog')
pack('data/klein-catalog.json.gz',sorted(klein_catalog))
pack('data/klein-known.json.gz',sorted(known))
index=[];buckets=collections.defaultdict(dict);counts=collections.Counter()
def alltext(x):
 if isinstance(x,str):return plain(x)
 if isinstance(x,list):return ' '.join(alltext(v) for v in x)
 if isinstance(x,dict):return ' '.join(alltext(v) for k,v in x.items() if k not in ['parent_lexicon_details','origins','upstream_original'])
 return ''
for key,e in entries.items():
 r=e['raw'];hw=r.get('headword','');lex=r.get('parent_lexicon',r.get('lexicon','Weitere'));e['lexicon']=lex;e['headword']=hw;counts[lex]+=int(e['kind']!='catalog')
 text=alltext(r);a=list(dict.fromkeys([norm(hw)]+[norm(x) for x in e['aliases'] if norm(x)])); preview=plain((r.get('content',{}).get('senses') or [{}])[0].get('definition','')) if isinstance(r.get('content'),dict) else ''; preview=preview or plain(' · '.join(x.get('de') or x.get('en') or '' for m in r.get('mappings',[]) for x in m.get('meanings',[])))[:180] or plain(' · '.join(x.get('de') or x.get('translation') or x.get('en') or x.get('text','') for x in r.get('items',[])))[:180]
 index.append({'id':key,'hw':hw,'lex':lex,'kind':e['kind'],'aliases':a,'text':' '.join(dict.fromkeys(norm(text).split())),'preview':preview[:180],'pending':e['kind']=='catalog'});buckets[key[:1]][key]=e
for bucket,rows in buckets.items():pack(f'data/entries/{bucket}.json.gz',rows)
pack('data/index.json.gz',index);pack('data/sources.json.gz',sources);pack('data/archive.json.gz',manifest)
# Inverted full-corpus index: all token occurrences, no arbitrary truncation.
byletter=collections.defaultdict(dict)
for w,byfile in postings.items():byletter[str(ord(w[0]))][w]=[[sid,lns] for sid,lns in byfile.items()]
for letter,words in byletter.items():pack(f'data/corpus/{letter}.json.gz',words)
meta={'schema':1,'version':'2026-10-23.1','entries':len(entries),'lexicons':dict(counts),'source_files':len(sources),'source_words':len(postings),'original_files':len(manifest),'original_bytes':sum(v['bytes'] for v in manifest),'history':len(history.get('queries',[])),'klein_catalog':len(klein_catalog),'klein_pending':sum(e['kind']=='catalog' for e in entries.values()),'archive_sha256':'7b2f6c2abcd9ea16917de5b62c27dddaf90898d17ce95eea352a8c3d51414f86','complete_lexicons':['Jastrow mirror snapshot (32,512 records)'] if (UP/'jastrow-manifest.txt').exists() and not json.loads((UP/'jastrow-manifest.txt').read_text()).get('missing_rids') else []}
(OUT/'data/meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
# File listing for optional offline installation and integrity checks.
assets=[str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name!='offline-files.json']
(OUT/'offline-files.json').write_text(json.dumps(assets))
print(json.dumps(meta,ensure_ascii=False,indent=2))
