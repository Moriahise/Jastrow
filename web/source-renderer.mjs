// Parse in an inert document, rebuild only formatting, then add word actions.
// Original source bytes are never changed.
export function renderSourceHTML(source){
 const parsed=new DOMParser().parseFromString(String(source??''),'text/html');
 const allowed=new Set(['B','STRONG','BIG','SMALL','I','EM','SUP','SUB','SPAN','BR','P','DIV','OL','UL','LI','BLOCKQUOTE','H1','H2','H3','H4','H5','H6','U','S']);
 const blocked=new Set(['SCRIPT','STYLE','IFRAME','OBJECT','EMBED','TEMPLATE','SVG','MATH','FORM','INPUT','BUTTON','TEXTAREA','SELECT','NOSCRIPT']);
 const box=document.createElement('div');
 function clean(node,parent){
  if(node.nodeType===3){parent.append(document.createTextNode(node.textContent));return;}
  if(node.nodeType!==1||blocked.has(node.tagName))return;
  let target=parent;
  if(allowed.has(node.tagName)){
   target=document.createElement(node.tagName.toLowerCase());
   const dir=node.getAttribute('dir'),lang=node.getAttribute('lang');
   if(['rtl','ltr','auto'].includes(dir))target.dir=dir;
   if(['he','en','de','arc'].includes(lang))target.lang=lang;
   parent.append(target);
  }
  for(const child of node.childNodes)clean(child,target);
 }
 for(const node of parsed.body.childNodes)clean(node,box);
 // Adjacent inline tags can divide a word (e.g. ה<b>עריות</b>).
 // Keep its full spelling on every clickable fragment.
 const pieces=[];let text='';
 const blocks=new Set(['BR','P','DIV','OL','UL','LI','BLOCKQUOTE','H1','H2','H3','H4','H5','H6']);
 function collect(node){
  if(node.nodeType===3){pieces.push({node,start:text.length,end:text.length+node.textContent.length});text+=node.textContent;return;}
  if(blocks.has(node.tagName))text+='\n';
  for(const child of node.childNodes)collect(child);
  if(blocks.has(node.tagName))text+='\n';
 }
 collect(box);
 const words=[...text.matchAll(/[\u05d0-\u05ea][\u0591-\u05c7\u05d0-\u05ea]*/gu)].map(m=>({word:m[0],start:m.index,end:m.index+m[0].length}));
 let wordIndex=0;
 for(const piece of pieces){
  const fragment=document.createDocumentFragment();let cursor=piece.start;
  while(wordIndex<words.length&&words[wordIndex].end<=piece.start)wordIndex++;
  for(let i=wordIndex;i<words.length&&words[i].start<piece.end;i++){
   const w=words[i],a=Math.max(w.start,piece.start),b=Math.min(w.end,piece.end);
   if(a>cursor)fragment.append(document.createTextNode(text.slice(cursor,a)));
   const token=document.createElement('span');token.className='token';token.dataset.word=w.word;token.tabIndex=0;token.setAttribute('role','button');token.textContent=text.slice(a,b);fragment.append(token);cursor=b;
  }
  if(cursor<piece.end)fragment.append(document.createTextNode(text.slice(cursor,piece.end)));
  piece.node.replaceWith(fragment);
 }
 return box.innerHTML;
}
