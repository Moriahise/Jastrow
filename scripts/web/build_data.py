#!/usr/bin/env python3
"""Build the four public lexicon families and source library. Standard library only."""
import pathlib,json,hashlib,gzip,re,html,collections,shutil,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; OUT=ROOT/'web'; UP=ROOT/'.build/data-upstream'
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
# A clean output directory prevents old personal data surviving a rebuild.
for stale in ['data','archive','audio_cache']:
 shutil.rmtree(OUT/stale,ignore_errors=True)
(OUT/'data').mkdir(exist_ok=True)
ALLOWED={'Jastrow Dictionary','Klein Dictionary','BDB Dictionary','BDB Aramaic Dictionary','BDB Augmented Strong',"Strong's Hebrew & Aramaic"}
supplement=[r for p in sorted((ROOT/'snapshots/public-lexicons').glob('*.json.gz')) for r in json.loads(gzip.decompress(p.read_bytes()))]
for raw in supplement:
 assert raw.get('parent_lexicon',raw.get('lexicon')) in ALLOWED
 add(raw,raw.get('headword',''),'Dictionary supplement')
sources=[];postings=collections.defaultdict(lambda:collections.defaultdict(list))
hebrew_titles={'Berakhot':'ברכות','Shabbat':'שבת','Eruvin':'עירובין','Pesachim':'פסחים','Yoma':'יומא','Sukkah':'סוכה','Beitzah':'ביצה','Rosh Hashanah':'ראש השנה','Taanit':'תענית','Megillah':'מגילה','Moed Katan':'מועד קטן','Chagigah':'חגיגה','Yevamot':'יבמות','Ketubot':'כתובות','Nedarim':'נדרים','Nazir':'נזיר','Sotah':'סוטה','Gittin':'גיטין','Kiddushin':'קידושין','Bava Kamma':'בבא קמא','Bava Metzia':'בבא מציעא','Bava Batra':'בבא בתרא','Sanhedrin':'סנהדרין','Makkot':'מכות','Shevuot':'שבועות','Avodah Zarah':'עבודה זרה','Horayot':'הוריות','Zevachim':'זבחים','Menachot':'מנחות','Chullin':'חולין','Bekhorot':'בכורות','Arakhin':'ערכין','Temurah':'תמורה','Keritot':'כריתות','Meilah':'מעילה','Tamid':'תמיד','Niddah':'נדה','Jerusalem Talmud Shekalim':'תלמוד ירושלמי שקלים'}
for src in sorted((ROOT/'sources/Talmud').rglob('*.txt')):
 blob=src.read_bytes();text=blob.decode('utf-8-sig');lines=text.splitlines();sid=len(sources)
 digest=hashlib.sha256(blob).hexdigest();url='data/texts/'+digest[:20]+'.txt.gz';dest=OUT/url;dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(blob,mtime=0))
 title=re.sub(r'^\d+-','',src.stem);work=title.split('HebrewWilliam')[0].split('EnglishWilliam')[0]
 language='en' if 'EnglishWilliam' in title else 'he'
 edition=title.split('Edition - ',1)[-1] if 'Edition - ' in title else ''
 toc=[]
 for ln,line in enumerate(lines):
  if re.match(r'^Daf \d+[ab]',line):toc.append({'label':line.strip(),'line':ln})
  for w in set(re.findall(r'[\u05d0-\u05ea][\u0591-\u05c7\u05d0-\u05ea]*',plain(line))):
   w=norm(w)
   if w:postings[w][sid].append(ln)
 toc=[x for i,x in enumerate(toc) if any(l.strip() for l in lines[x['line']+1:toc[i+1]['line'] if i+1<len(toc) else len(lines)])]
 base=work.replace('Steinsaltz on ','');he_title=hebrew_titles.get(base,base)
 if work.startswith('Steinsaltz on '):he_title='ביאור שטיינזלץ על '+he_title
 sources.append({'id':sid,'path':str(src.relative_to(ROOT)),'title':work,'he_title':he_title,'work':base,'category':'Talmud','edition':edition,'language':language,'url':url,'lines':len(lines),'bytes':len(blob),'sha256':digest,'toc':toc})
# The public catalogue is pinned to the same published library as Shiurim.
catalog=json.loads((UP/'source-library/catalog.json').read_text());pack('data/library.json.gz',catalog)
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
# Complete Hebrew/Aramaic Strong's corpus; keep the pinned XML byte-for-byte too.
from import_strongs import load_strongs,LEXICON as STRONGS_LEXICON,COMMIT as STRONGS_COMMIT
strongs_path=UP/'strongs/StrongHebrewG.xml'
for raw in load_strongs(strongs_path):
 key=add(raw,raw['headword'],'Open Scriptures: '+STRONGS_COMMIT+' / hebrew/StrongHebrewG.xml')
 for alias in [raw['strong_id'],raw['strong_number'],'H'+raw['strong_number'].zfill(4)]:
  if alias not in entries[key]['aliases']:entries[key]['aliases'].append(alias)
strongs_blob=strongs_path.read_bytes()
(OUT/'data/strongs-source.xml.gz').write_bytes(gzip.compress(strongs_blob,mtime=0))
# Durable centrally collected Klein records supplement the same independent website.
p=ROOT/'data/klein-collected.json.gz'
klein_collection={}
if p.exists():
 klein_collection=json.loads(gzip.decompress(p.read_bytes()))
 for raw in klein_collection.get('entries',[]):add(raw,raw.get('headword',''),'GitHub Klein collection: '+klein_collection.get('updated',''))
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
 if isinstance(x,dict):return ' '.join(alltext(v) for k,v in x.items() if k not in ['parent_lexicon_details','origins','upstream_original','source_entry_xml'])
 return ''
for key,e in entries.items():
 r=e['raw'];hw=r.get('headword','');lex=r.get('parent_lexicon',r.get('lexicon','Weitere'));assert lex in ALLOWED,lex;e['lexicon']=lex;e['headword']=hw;counts[lex]+=int(e['kind']!='catalog')
 text=alltext(r);a=list(dict.fromkeys([norm(hw)]+[norm(x) for x in e['aliases'] if norm(x)])); preview=plain((r.get('content',{}).get('senses') or [{}])[0].get('definition','')) if isinstance(r.get('content'),dict) else ''; preview=preview or plain(' · '.join(x.get('de') or x.get('en') or '' for m in r.get('mappings',[]) for x in m.get('meanings',[])))[:180] or plain(' · '.join(x.get('de') or x.get('translation') or x.get('en') or x.get('text','') for x in r.get('items',[])))[:180]
 index.append({'id':key,'hw':hw,'lex':lex,'kind':e['kind'],'aliases':a,'text':' '.join(dict.fromkeys(norm(text).split())),'preview':preview[:180],'pending':e['kind']=='catalog',**({'strongId':'H'+str(int(r['strong_number']))} if str(r.get('strong_number','')).isdigit() else {})});buckets[key[:1]][key]=e
for bucket,rows in buckets.items():pack(f'data/entries/{bucket}.json.gz',rows)
pack('data/index.json.gz',index);pack('data/sources.json.gz',sources);pack('data/source-manifest.json.gz',[{'path':v['path'],'url':v['url'],'bytes':v['bytes'],'sha256':v['sha256']} for v in sources])
# Inverted full-corpus index: all token occurrences, no arbitrary truncation.
byletter=collections.defaultdict(dict)
for w,byfile in postings.items():byletter[str(ord(w[0]))][w]=[[sid,lns] for sid,lns in byfile.items()]
for letter,words in byletter.items():pack(f'data/corpus/{letter}.json.gz',words)
meta={'schema':1,'version':'2026-10-24-public.1','entries':len(entries),'lexicons':dict(counts),'source_files':len(sources),'source_words':len(postings),'source_bytes':sum(v['bytes'] for v in sources),'library_works':len(catalog['works']),'strongs':{'entries':8674,'source_commit':STRONGS_COMMIT,'source_sha256':hashlib.sha256(strongs_blob).hexdigest(),'source_url':'https://github.com/openscriptures/strongs','download':'data/strongs-source.xml.gz'},'klein_catalog':len(klein_catalog),'klein_collection':{k:v for k,v in klein_collection.items() if k not in ['entries','completed','failures']},'klein_pending':sum(e['kind']=='catalog' for e in entries.values()),'complete_lexicons':["Strong's Hebrew & Aramaic (8,674 records)"]+(['Jastrow mirror snapshot (32,512 records)'] if (UP/'jastrow-manifest.txt').exists() and not json.loads((UP/'jastrow-manifest.txt').read_text()).get('missing_rids') else [])}
(OUT/'data/meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
# File listing for optional offline installation and integrity checks.
assets=[str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name!='offline-files.json']
(OUT/'offline-files.json').write_text(json.dumps(assets))
print(json.dumps(meta,ensure_ascii=False,indent=2))
