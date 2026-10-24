import{fetchJSON,searchIndex,publicLexicon}from'./core.mjs';
let rows=[];
self.onmessage=async({data:d})=>{try{
 if(d.type==='init'){rows=(await fetchJSON('data/index.json.gz')).filter(r=>publicLexicon(r.lex));postMessage({type:'ready',count:rows.length});}
 else if(d.type==='search')postMessage({type:'results',request:d.request,...searchIndex(rows,d.query,d.options)});
}catch(e){postMessage({type:'error',request:d.request,error:e.message});}};
