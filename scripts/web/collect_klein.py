#!/usr/bin/env python3
"""Resumable, rate-limited collection of the pinned Klein catalog.
Raw entries are kept in a compressed checkpoint; no existing record is replaced.
"""
import pathlib,json,gzip,urllib.request,urllib.parse,concurrent.futures,threading,time,hashlib,os,subprocess,unicodedata,argparse
ROOT=pathlib.Path(__file__).resolve().parents[2];DEST=ROOT/os.environ.get('KLEIN_CHECKPOINT_DIR','data')/'klein-collected.json.gz';DEST.parent.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
PINS=json.loads((ROOT/'scripts/web/upstream-pins.json').read_text())
state=json.loads(gzip.decompress(DEST.read_bytes())) if DEST.exists() else {'schema':1,'lexicon':'Klein Dictionary','entries':[],'completed':[],'failures':{}}
lock=threading.Lock();next_request=0;interval=.5

def request(url):
 global next_request
 with lock:
  delay=max(0,next_request-time.monotonic());next_request=max(time.monotonic(),next_request)+interval
 if delay:time.sleep(delay)
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BeitHaMillonDictionaryCollector/1.0 (Moriahise/Jastrow; noncommercial Torah study)'}),timeout=35) as r:return r.read()
heads=set()
for rel,pin in PINS.items():
 if not rel.startswith('klein-catalog/'):continue
 cached=ROOT/'.build/data-upstream'/rel;b=cached.read_bytes() if cached.exists() else request(pin['url']);assert hashlib.sha256(b).hexdigest()==pin['sha256'],rel+': catalog changed'
 heads.update(h for _,h in json.loads(b))
completed=set(state['completed']);entries={hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest():r for r in state['entries']}
state['catalog_count']=len(heads);start=time.monotonic();deadline=start+4.6*3600

def fetch(word):
 try:
  url='https://www.sefaria.org/api/words/'+urllib.parse.quote(word)+'?never_split=1&always_consonants=1'
  rows=json.loads(request(url));rows=[r for r in rows if isinstance(r,dict) and r.get('parent_lexicon')=='Klein Dictionary'] if isinstance(rows,list) else []
  matched=any(unicodedata.normalize('NFC',r.get('headword',''))==unicodedata.normalize('NFC',word) for r in rows)
  if matched:return word,rows,None
  # Some headwords are not mapped by /words. The text API can still resolve them.
  data=json.loads(request('https://www.sefaria.org/api/v3/texts/'+urllib.parse.quote('Klein Dictionary, '+word)+'?version=english|all'))
  ref=data.get('ref','');reported=ref.split(', ',1)[1].rsplit(' ',1)[0] if ', ' in ref and ref.rsplit(' ',1)[-1].isdigit() else ref.split(', ',1)[-1]
  versions=[v for v in data.get('versions',[]) if v.get('language')=='en'];text=versions[0].get('text',[]) if versions else []
  def flatten(x):
   if isinstance(x,str):return [x] if x.strip() else []
   return [t for y in x for t in flatten(y)] if isinstance(x,list) else []
  parts=flatten(text)
  if parts and unicodedata.normalize('NFC',reported)==unicodedata.normalize('NFC',word):
   rows.append({'headword':word,'parent_lexicon':'Klein Dictionary','content':{'senses':[{'definition':t} for t in parts]},'text_api_original':data,'parent_lexicon_details':{'attribution':'Ernest Klein, Carta Jerusalem, 1987; digitized by Sefaria','source_url':'https://www.sefaria.org/Klein_Dictionary','license':'CC-BY-NC'}});return word,rows,None
  return word,rows,'No verified exact headword returned'
 except Exception as e:return word,[],str(e)[:300]

def checkpoint(push=False):
 state.update(entries=list(entries.values()),completed=sorted(completed),completed_count=len(heads&completed),remaining_count=len(heads-completed),updated=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),complete=heads<=completed)
 blob=gzip.compress(json.dumps(state,ensure_ascii=False,separators=(',',':')).encode(),mtime=0);tmp=DEST.with_suffix('.tmp');tmp.write_bytes(blob);tmp.replace(DEST)
 report={k:state[k] for k in ['schema','lexicon','catalog_count','completed_count','remaining_count','complete','updated']};report['failed_count']=len(state['failures']);(DEST.parent/'klein-collection-status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report),flush=True)
 if push and os.environ.get('GITHUB_ACTIONS')=='true':
  subprocess.run(['git','add','data/klein-collected.json.gz','data/klein-collection-status.json'],cwd=ROOT,check=True)
  if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
   subprocess.run(['git','commit','-m',f"Collect Klein dictionary: {len(heads&completed)}/{len(heads)} verified headwords"],cwd=ROOT,check=True)
   subprocess.run(['git','pull','--rebase','origin','main'],cwd=ROOT,check=True)
   subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,check=True)
checkpoint(True)
queue=sorted(heads-completed);queue=queue[:args.limit] if args.limit else queue;count=0;consecutive=0
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 # Bound in-flight requests so pauses or service errors stop promptly.
 pending={};iterator=iter(queue)
 def fill():
  while len(pending)<3 and time.monotonic()<deadline and consecutive<12:
   try:w=next(iterator)
   except StopIteration:return
   pending[pool.submit(fetch,w)]=w
 fill()
 while pending:
  done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
  for future in done:
   pending.pop(future);word,rows,error=future.result();count+=1
   for r in rows:entries.setdefault(hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),r)
   if error:state['failures'][word]=error;consecutive+=1
   else:completed.add(word);state['failures'].pop(word,None);consecutive=0
   if count%250==0:checkpoint(True)
  fill()
checkpoint(True)
if state['remaining_count']:print('Checkpoint saved. Dispatch the same workflow again to retry pending headwords.',flush=True)
