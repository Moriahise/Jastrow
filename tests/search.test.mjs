import{test}from'node:test';import assert from'node:assert/strict';import{readFileSync}from'node:fs';import{gunzipSync}from'node:zlib';import{normalize,searchIndex,gematria,validateBackup,mergeIndex,hebrewBaseForms}from'../web/core.mjs';
const rows=JSON.parse(gunzipSync(readFileSync(new URL('../web/data/index.json.gz',import.meta.url))));
test('Niqqud, cantillation and punctuation do not prevent Hebrew lookup',()=>{assert.equal(normalize('תּוֹרָה'),'תורה');const r=searchIndex(rows,'תּוֹרָה',{exact:true});assert(r.total>0);assert(r.results.every(x=>normalize(x.hw)==='תורה'));});
test('Jastrow and Klein remain separately filterable',()=>{for(const filter of ['Jastrow Dictionary','Klein Dictionary']){const r=searchIndex(rows,'תורה',{exact:true,filter});assert(r.total>0);assert(r.results.every(x=>x.lex===filter&&!x.pending));}});
test('German and English meanings are searchable',()=>{for(const q of ['Licht','light','Lehre'])assert(searchIndex(rows,q).total>0,q);});
test('Missing Klein definitions are discoverable but explicitly marked',()=>{const pending=rows.find(r=>r.kind==='catalog');if(!pending){const meta=JSON.parse(readFileSync(new URL('../web/data/meta.json',import.meta.url)));assert.equal(meta.klein_pending,0);assert.equal(meta.klein_collection.complete,true);return;}const r=searchIndex(rows,pending.hw,{filter:'Klein Dictionary',exact:true,limit:200});assert(r.results.some(x=>x.id===pending.id&&x.pending));});
test('Filtering, no-match and stable pagination',()=>{assert.equal(searchIndex(rows,'zzzzunfindbarzzzz').total,0);const a=searchIndex(rows,'תורה',{limit:3}),b=searchIndex(rows,'תורה',{offset:3,limit:3});assert.equal(a.total,b.total);assert.equal(new Set([...a.results,...b.results].map(x=>x.id)).size,6);});
test('Gematria uses the Hebrew letters, including final forms',()=>{const g=gematria('תּוֹרָה');assert.equal(g['Mispar Hechrachi'],611);assert.equal(g.letters,4);assert.equal(gematria('מלך')['Mispar Hechrachi'],90);assert.equal(gematria('מלך')['Mispar Gadol'],570);assert.equal(Object.keys(g).length,17);});
test('Backups reject unrelated data and unknown record families',()=>{assert.throws(()=>validateBackup({}));assert.throws(()=>validateBackup({schema:'beit-hamillon-backup-v1',records:[{key:'bad'}]}));assert.equal(validateBackup({schema:'beit-hamillon-backup-v1',records:[{key:'note:test',value:{he:'תורה'}}]}).length,1);});

test('An imported definition replaces only its pending catalog result',()=>{const catalog=rows.find(r=>r.kind==='catalog')||{id:'pending-test',hw:'קטלוגבדיקה',lex:'Klein Dictionary',kind:'catalog',pending:true};const source=rows.some(r=>r.id===catalog.id)?rows:[...rows,catalog];const imported={...catalog,id:'remote-test',kind:'remote',pending:false,text:'downloaded definition'};const merged=mergeIndex(source,[imported]);assert(!merged.some(r=>r.id===catalog.id));assert(merged.some(r=>r.id==='remote-test'&&!r.pending));assert.equal(merged.length,source.length);});


test('Prefixed source word מאחות finds the existing Jastrow אחות entry',()=>{
 const result=searchIndex(rows,'מֵאָחוֹת',{filter:'Jastrow Dictionary'});
 assert(result.total>0);
 assert.equal(normalize(result.results[0].hw),'אחות');
 assert.equal(result.results[0].matchType,'prefix');
 assert.equal(result.results[0].strippedPrefix,'מ');
 assert.equal(result.results[0].matchedForm,'אחות');
 assert(!result.results.some(r=>normalize(r.hw)==='מאחות'));
});
test('Exact mode never silently substitutes a possible base form',()=>{
 const result=searchIndex(rows,'מאחות',{filter:'Jastrow Dictionary',exact:true});
 assert.equal(result.total,0);
 const direct=searchIndex(rows,'אחות',{filter:'Jastrow Dictionary',exact:true});
 assert(direct.total>0);assert(direct.results.every(r=>!r.matchType));
});
test('Prefix candidates preserve exact entries and do not stem English or short words',()=>{
 assert.deepEqual(hebrewBaseForms('light'),[]);assert.deepEqual(hebrewBaseForms('מאי'),[]);
 assert(hebrewBaseForms('ובתורה').some(f=>f.form==='תורה'&&f.prefix==='וב'));
 const fixture=[{id:'1',hw:'מאחות',lex:'Jastrow Dictionary'},{id:'2',hw:'אחות',lex:'Jastrow Dictionary'}];
 const result=searchIndex(fixture,'מאחות');assert.equal(result.results[0].id,'1');assert(!result.results[0].matchType);
 assert.equal(result.results[1].matchType,'prefix');
});

test('Published module URLs share the offline cache revision',()=>{
 const meta=JSON.parse(readFileSync(new URL('../web/data/meta.json',import.meta.url)));
 const revision=meta.cache_name.split('-').at(-1);
 for(const file of ['index.html','app.mjs','search-worker.mjs','sw.js']){
  const code=readFileSync(new URL('../web/'+file,import.meta.url),'utf8');
  const refs=[...code.matchAll(/[\"'](?:\.\/)?[\w-]+\.mjs(?:\?build=([0-9a-f]{16}))?[\"']/g)];
  assert(refs.length>0,file);
  assert(refs.every(m=>m[1]===revision),file+' module cache revision');
 }
});
