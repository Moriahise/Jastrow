import{escapeHTML as E}from'./core.mjs';
const topics=[
 {names:['Torah & Lernen','Torah & learning','תורה ולימוד'],words:['תורה','הלכה','משנה','תלמוד','מצוה','חכמה']},
 {names:['Zeit & Festtage','Time & festivals','זמן ומועדים'],words:['שבת','יום','חודש','שנה','מועד','פסח']},
 {names:['Mensch & Gemeinschaft','People & community','אדם וקהילה'],words:['אדם','אב','אם','אח','אחות','בית']},
 {names:['Natur & Schöpfung','Nature & creation','טבע ובריאה'],words:['אור','מים','ארץ','שמים','עץ','רוח']}
];
export function renderStudy(t,lang){const i=['de','en','he'].indexOf(lang),words=topics.flatMap(x=>x.words),day=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Vienna'}).format(new Date()),seed=[...day].reduce((n,c)=>n*31+c.charCodeAt(0),0)>>>0,word=words[seed%words.length];
 document.getElementById('daily-word').innerHTML=`<div><div class="eyebrow">${E(t('dailyword'))} · ${E(day)}</div><button class="daily-headword" lang="he" data-word="${word}">${word}</button><p>${E(t('dailyhint'))}</p></div><button class="primary" data-word="${word}">${E(t('search'))}</button>`;
 document.getElementById('topic-cards').innerHTML=topics.map(x=>`<section class="card topic"><h2>${E(x.names[i])}</h2><div class="word-cloud">${x.words.map(w=>`<button lang="he" data-word="${w}">${w}</button>`).join('')}</div></section>`).join('');
 document.getElementById('dictionary-guide').innerHTML=['Jastrow','Klein','BDB','Strong’s'].map((name,n)=>`<article><h3>${name}</h3><p>${E(t(['dictionaryguideJ','dictionaryguideK','dictionaryguideB','dictionaryguideS'][n]))}</p></article>`).join('');
 document.getElementById('browse-alphabet').innerHTML=[...'אבגדהוזחטיכלמנסעפצקרשת'].map(c=>`<button data-word="${c}" lang="he">${c}</button>`).join('');
}
