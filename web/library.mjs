import{sections as sourceSections}from'./source-navigation.mjs';
import{fetchJSON,fetchBytes,escapeHTML as E,normalize}from'./core.mjs';
import{renderSourceHTML}from'./source-renderer.mjs';
const $=id=>document.getElementById(id);
const categoryNames={Tanakh:['Tanach','Tanakh','תנ״ך'],Mishnah:['Mischna','Mishnah','משנה'],Talmud:['Talmud','Talmud','תלמוד'],Midrash:['Midrasch','Midrash','מדרש'],Halakhah:['Halacha','Halakhah','הלכה'],Kabbalah:['Kabbala','Kabbalah','קבלה'],Liturgy:['Gebet','Liturgy','תפילה'],'Jewish Thought':['Jüdisches Denken','Jewish thought','מחשבת ישראל'],Chasidut:['Chassidut','Chasidut','חסידות'],Musar:['Mussar','Musar','מוסר'],Responsa:['Responsen','Responsa','שו״ת'],Tosefta:['Tosefta','Tosefta','תוספתא'],Reference:['Nachschlagewerke','Reference','ספרי עזר']};
export function createLibrary({t,language,lookup,download,onContext}){
 let sources=[],works=[],catalogLoaded=false,page=0,rows=[],reader=null,epoch=0;
 const cache=new Map(),structures=new Map();
 const label=s=>language()==='he'?(s.he_title||s.title):s.title;
 function categoryName(c){return categoryNames[c]?.[['de','en','he'].indexOf(language())]||c;}
 async function init(allSources){sources=allSources;await loadCatalog();refresh();}
 async function loadCatalog(){if(catalogLoaded)return;const c=await fetchJSON('data/library.json.gz');works=c.works;catalogLoaded=true;}
 function refresh(){
  const old=$('source-category').value,categories=[...new Set(['Talmud',...works.map(w=>w.categories[0])])].sort();
  $('source-category').innerHTML=`<option value="">${E(t('allcategories'))}</option>`+categories.map(c=>`<option value="${E(c)}">${E(categoryName(c))}</option>`).join('');$('source-category').value=old;
  $('library-stats').innerHTML=`<span><b>${sources.length}</b> ${E(t('localtexts'))}</span><span><b>${works.length.toLocaleString()}</b> ${E(t('works'))}</span><span>HE · EN</span>`;
  renderCards();if(reader)renderReader();
 }
 function renderCards(){
  const q=normalize($('source-filter').value).split(' ').filter(Boolean),cat=$('source-category').value,availability=$('source-availability').value;
  const localTitles=new Set(sources.map(s=>s.title));
  const candidates=[...sources.map(s=>({...s,local:true,category:s.category})),...works.filter(w=>!localTitles.has(w.title)).map(w=>({...w,local:false,category:w.categories[0]}))];
  rows=candidates.filter(s=>(!cat||s.category===cat)&&(availability!=='local'||s.local)&&(availability!=='online'||!s.local)&&q.every(word=>normalize(s.title+' '+(s.he_title||'')+' '+s.category+' '+(s.edition||'')).includes(word)));
  const total=Math.max(1,Math.ceil(rows.length/18));page=Math.max(0,Math.min(page,total-1));
  $('source-cards').innerHTML=rows.slice(page*18,page*18+18).map((s,i)=>`<article class="source-card"><span class="availability ${s.local?'hosted':'network'}">${E(t(s.local?'localbadge':'onlinebadge'))}</span><h3><button data-book="${page*18+i}" dir="auto">${E(label(s))}</button></h3><p dir="auto" lang="he">${E(language()==='he'?s.title:s.he_title||'')}</p><div class="source-card-meta"><span>${E(categoryName(s.category))}</span><span>${E(s.local?s.edition||s.language:Object.keys(s.languages).join(' · '))}</span></div></article>`).join('')||`<p>${E(t('nomatch'))}</p>`;
  $('library-page').textContent=`${page+1} / ${total} · ${rows.length.toLocaleString()}`;$('library-prev').disabled=page===0;$('library-next').disabled=page+1===total;
  $('library-status').textContent=t('onlinehint');
 }
 async function linesFor(s){if(!cache.has(s.id)){cache.set(s.id,new TextDecoder().decode(await fetchBytes(s.url)).replace(/^\uFEFF/,'').split(/\r?\n/));if(cache.size>5)cache.delete(cache.keys().next().value);}return cache.get(s.id);}
 async function openLocal(sid,line){
  const request=++epoch,s=sources.find(s=>s.id===+sid);if(!s)return;
  $('source-reader').hidden=false;$('paste-area').hidden=true;$('reader').textContent=t('loadtext');
  try{const lines=await linesFor(s);if(request!==epoch)return;const toc=s.toc.length?s.toc:[{label:s.title,line:0}];let section=0;if(line!==undefined)for(let i=0;i<toc.length;i++)if(toc[i].line<=line)section=i;
   reader={local:true,source:s,lines,toc,section,title:label(s),mark:line};renderReader();showReader();
  }catch(e){$('reader').textContent=e.message;}
 }
 function showReader(){requestAnimationFrame(()=>{const mark=reader?.mark!==undefined?$('reader').querySelector(`[data-line="${reader.mark}"]`):null;(mark||$('source-reader')).scrollIntoView({block:mark?'center':'start',behavior:'smooth'});});}
 function renderReader(){
  if(!reader)return;
  $('source-reader').hidden=false;$('reader-title').textContent=reader.title;$('reader-provider').textContent=reader.local?t('localbadge'):reader.pasted?t('pastetext'):'Sefaria · '+t('onlinebadge');
  $('reader-edition').hidden=!reader.local;$('reader-section').hidden=!reader.local&&!reader.sections?.length;$('reader-language').hidden=!!reader.local||!!reader.pasted;$('reference-form').hidden=!!reader.local||!!reader.pasted;
  if(reader.local){
   const {source:s,toc,section,lines}=reader;
   const variants=sources.filter(x=>x.title===s.title);
   $('reader-edition').innerHTML=variants.map(v=>`<option value="${v.id}" ${v.id===s.id?'selected':''}>${E(v.edition||v.language)}</option>`).join('');
   $('reader-section').innerHTML=toc.map((x,i)=>`<option value="${i}" ${i===section?'selected':''}>${E(x.label)}</option>`).join('');
   const start=toc[section].line,end=toc[section+1]?.line??lines.length;
   $('reader').innerHTML=lines.slice(start,end).map((line,i)=>!line.trim()?'':/^Daf /.test(line)?`<div class="ref">${E(line)}</div>`:`<div class="line" data-line="${start+i}" dir="auto"><small class="line-number" aria-hidden="true">${start+i+1}</small><div class="source-content">${renderSourceHTML(line)}</div></div>`).join('');
   $('reader-position').textContent=toc[section].label;$('reader-prev').disabled=section===0;$('reader-next').disabled=section===toc.length-1;
   $('reader-meta').textContent=s.edition+' · '+(s.language==='he'?'עברית / ארמית':'English');$('reader-original').href='https://www.sefaria.org/'+encodeURIComponent(s.title.replace('Steinsaltz on ','Steinsaltz on '));
   $('source-original').hidden=false;
   if(reader.mark!==undefined){const marked=$('reader').querySelector(`[data-line="${reader.mark}"]`);if(marked)marked.classList.add('source-highlight');}
  }else{
   if(reader.sections?.length)$('reader-section').innerHTML=reader.sections.map((s,i)=>`<option value="${i}" ${reader.ref===s.ref?'selected':''}>${E(language()==='he'?s.he:s.en)}</option>`).join('');
   $('reader').innerHTML=(reader.segments||[]).filter(Boolean).map((s,i)=>`<div class="line" data-line="${i}" dir="auto"><small class="line-number" aria-hidden="true">${i+1}</small><div class="source-content">${renderSourceHTML(s)}</div></div>`).join('');
   $('reader-position').textContent=reader.ref||reader.title;$('reader-prev').disabled=!reader.prev;$('reader-next').disabled=!reader.next;
   $('reader-meta').textContent=reader.meta||'';$('reader-original').hidden=!!reader.pasted;$('reader-original').href=reader.url||'#';$('source-original').hidden=!!reader.pasted;
  }
  $('reader-original').hidden=!!reader.pasted;
 }
 function flatten(x,out=[]){if(typeof x==='string')out.push(x);else if(Array.isArray(x))for(const v of x)flatten(v,out);return out;}
 async function sectionsFor(book){
  if(!structures.has(book.title)){const title=encodeURIComponent(book.title);structures.set(book.title,Promise.all([fetchJSON('https://www.sefaria.org/api/shape/'+title),fetchJSON('https://www.sefaria.org/api/v2/raw/index/'+title).catch(()=>null)]).then(([shape,index])=>sourceSections(shape,index)).catch(()=>[]));}
  return structures.get(book.title);
 }
 async function openOnline(book,reference){
  const request=++epoch;let ref=reference||(book.title+(book.categories?.[0]==='Talmud'?' 2a':' 1'));
  const lang=$('reader-language').value||'he';if(book.languages&&!book.languages[lang==='he'?'Hebrew':'English'])$('reader-language').value=book.languages.Hebrew?'he':'en';
  $('source-reader').hidden=false;$('paste-area').hidden=true;$('reader').textContent=t('loadtext');$('reader-title').textContent=ref;showReader();
  try{
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),25000);
   const sections=await sectionsFor(book);if(!reference&&sections[0])ref=sections[0].ref;
   let data;try{const r=await fetch('https://www.sefaria.org/api/texts/'+encodeURIComponent(ref)+'?context=0&commentary=0&pad=0',{credentials:'omit',referrerPolicy:'no-referrer',signal:controller.signal});if(!r.ok)throw Error('HTTP '+r.status);data=await r.json();}finally{clearTimeout(timer);}
   if(request!==epoch)return;if(data.error||!data.ref)throw Error(t('refhint'));
   const he=$('reader-language').value==='he',segments=flatten(data[he?'he':'text']);if(!segments.some(s=>s.trim()))throw Error(t('networkerror'));
   reader={local:false,book,sections,title:language()==='he'?data.heRef||data.ref:data.ref,ref:data.ref,segments,prev:data.prev,next:data.next,url:'https://www.sefaria.org/'+encodeURIComponent(data.ref.replaceAll(' ','_')),meta:[he?data.heVersionTitle:data.versionTitle,he?data.heLicense:data.license].filter(Boolean).join(' · ')};
   $('reference-input').value=data.ref;renderReader();
  }catch(e){if(request!==epoch)return;$('reader').textContent=t('networkerror')+' '+e.message;$('reference-form').hidden=false;$('reference-input').value=ref;$('reader-language').hidden=false;reader={local:false,book,title:ref,ref,segments:[],pasted:false};renderReader();$('reader').textContent=t('networkerror')+' '+e.message;}
 }
 function bind(id,event,fn){$(id).addEventListener(event,fn);}
 bind('source-filter','input',()=>{page=0;renderCards();});bind('source-category','change',()=>{page=0;renderCards();});bind('source-availability','change',()=>{page=0;renderCards();});
 bind('library-prev','click',()=>{page--;renderCards();});bind('library-next','click',()=>{page++;renderCards();});
 bind('source-cards','click',e=>{const b=e.target.closest('[data-book]');if(!b)return;const book=rows[+b.dataset.book];if(book.local)openLocal(book.id);else openOnline(book);});
 bind('reader-edition','change',()=>openLocal(+$('reader-edition').value));bind('reader-section','change',()=>{if(reader.local){reader.section=+$('reader-section').value;reader.mark=undefined;renderReader();}else if(reader.sections?.length)openOnline(reader.book,reader.sections[+$('reader-section').value].ref);});
 for(const [id,direction]of[['reader-prev',-1],['reader-next',1]])bind(id,'click',()=>{if(reader.local){reader.section+=direction;reader.mark=undefined;renderReader();}else openOnline(reader.book,direction<0?reader.prev:reader.next);showReader();});
 bind('reader-language','change',()=>{if(reader&&!reader.local&&!reader.pasted)openOnline(reader.book,reader.ref);});
 bind('reference-form','submit',e=>{e.preventDefault();openOnline(reader?.book||{title:$('reference-input').value},$('reference-input').value);});
 bind('reader-close','click',()=>{$('source-reader').hidden=true;});
 bind('reader-paste','click',()=>{$('paste-area').hidden=false;$('source-reader').hidden=true;$('paste-area').scrollIntoView({behavior:'smooth'});});
 bind('studio-render','click',()=>{++epoch;reader={pasted:true,title:t('pastetext'),segments:$('studio-input').value.split('\n')};$('paste-area').hidden=true;renderReader();showReader();});
 function wordAction(e){const token=e.target.closest('[data-word]');if(!token)return;if(e.type==='keydown'&&!['Enter',' '].includes(e.key))return;e.preventDefault();const line=token.closest('[data-line]');reader.mark=Number(line?.dataset.line);onContext(reader.title);lookup(token.dataset.word);}
 bind('reader','click',wordAction);bind('reader','keydown',wordAction);
 bind('source-original','click',async()=>{if(reader?.local){const bytes=await fetchBytes(reader.source.url);download(reader.source.title+'.txt',bytes);}else if(reader)download(reader.title+'.txt',reader.segments.join('\n'),'text/plain;charset=utf-8');});
 return{init,refresh,openLocal,resume(){if(reader){renderReader();showReader();}},hasReader:()=>!!reader};
}
