export const normalize=s=>String(s??'').normalize('NFC').replace(/[\u0591-\u05c7]/g,'').replace(/[^\u05d0-\u05ea\p{L}\p{N}\s]/gu,'').toLocaleLowerCase().replace(/\s+/g,' ').trim();
export const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function searchIndex(rows,query,{filter='all',exact=false,offset=0,limit=40}={}){
 const q=normalize(query);if(!q)return {results:[],total:0};const heb=/[א-ת]/.test(q),words=q.split(' '),out=[];
 for(const r of rows){
  if(filter==='BDB'&&!r.lex.startsWith('BDB'))continue;
  if(filter==='local'&&!['local','user','translation','api','history','editorial'].includes(r.kind))continue;
  if(!['all','BDB','local'].includes(filter)&&r.lex!==filter)continue;
  const aliases=r.aliases||[normalize(r.hw)];const direct=aliases.includes(q),hw=normalize(r.hw);if(exact&&hw!==q)continue;let score=direct?(hw===q?0:11):99;
  if(!exact&&!direct){if(aliases.some(a=>a.startsWith(q)))score=5;else if(aliases.some(a=>a.includes(q)))score=9;else if(words.every(w=>(r.text||'').includes(w)))score=20;}
  if(score===99)continue;if(r.kind==='catalog')score+=.5;else if(r.lex==='Jastrow Dictionary')score-=.2;
  out.push({...r,score});
 }
 out.sort((a,b)=>a.score-b.score||a.hw.localeCompare(b.hw,'he')||a.id.localeCompare(b.id));
 return {results:out.slice(offset,offset+limit),total:out.length};
}
export async function fetchJSON(url){const r=await fetch(url);if(!r.ok)throw new Error(`HTTP ${r.status}: ${url}`);if(url.endsWith('.gz')){if(!globalThis.DecompressionStream)throw new Error('Dieser Browser unterstützt keine gzip-Dekomprimierung. Bitte einen aktuellen Browser verwenden.');return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json();}return r.json();}
export async function fetchBytes(url){const r=await fetch(url);if(!r.ok)throw new Error(`HTTP ${r.status}`);return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();}
export function gematria(word){const letters='אבגדהוזחטיכלמנסעפצקרשת',fin={'ך':'כ','ם':'מ','ן':'נ','ף':'פ','ץ':'צ'},vals=[1,2,3,4,5,6,7,8,9,10,20,30,40,50,60,70,80,90,100,200,300,400],big={'ך':500,'ם':600,'ן':700,'ף':800,'ץ':900},names=['אלף','בית','גימל','דלת','הא','ואו','זין','חית','טית','יוד','כף','למד','מם','נון','סמך','עין','פא','צדי','קוף','ריש','שין','תו'];const clean=normalize(word).replace(/[^א-ת]/g,''),a=[...clean].map(c=>({c,i:letters.indexOf(fin[c]||c)})).filter(x=>x.i>=0),v=a.map(x=>vals[x.i]),sum=x=>x.reduce((s,y)=>s+y,0),std=sum(v),reduce=n=>n===0?0:1+(n-1)%9,milui=sum(a.map(x=>sum([...names[x.i]].map(c=>vals[letters.indexOf(fin[c]||c)]||0))));return {'Mispar Hechrachi':std,'Mispar Gadol':sum(a.map(x=>big[x.c]||vals[x.i])),'Mispar Katan':sum(v.map(reduce)),'Mispar Siduri':sum(a.map(x=>x.i+1)),'Mispar Perati':sum(v.map(x=>x*x)),'Mispar Kidmi':sum(a.map(x=>sum(vals.slice(0,x.i+1)))),'Mispar Boneh':sum(v.map((_,i)=>sum(v.slice(0,i+1)))),'Mispar Musafi':std+a.length,'Mispar Kolel':std+1,'Mispar Katan Mispari':reduce(std),'Mispar Milui':milui,'Mispar HaNeelam':milui-std,'Mispar HaAkhor':sum(a.map(x=>22-x.i)),'AtBash':sum(a.map(x=>vals[21-x.i])),'AlBam':sum(a.map(x=>vals[(x.i+11)%22])),'AvGad':sum(a.map(x=>vals[(x.i+1)%22])),letters:a.length};}
export function validateBackup(data){if(!data||data.schema!=='beit-hamillon-backup-v1'||!Array.isArray(data.records))throw new Error('Keine gültige Beit-haMillon-Sicherung.');for(const r of data.records){if(!r||typeof r.key!=='string'||!['note:','bookmark:','remote:','collector:','recent'].some(k=>r.key.startsWith(k)))throw new Error('Ungültiger Sicherungseintrag.');}return data.records;}
