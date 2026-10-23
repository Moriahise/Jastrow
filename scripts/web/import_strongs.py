"""Lossless projection of the pinned Open Scriptures Hebrew/Aramaic OSIS XML."""
import html,re,xml.etree.ElementTree as ET
NS={'o':'http://www.bibletechnologies.net/2003/OSIS/namespace'}
XML_LANG='{http://www.w3.org/XML/1998/namespace}lang'
LEXICON="Strong's Hebrew & Aramaic"
COMMIT='0acd2f251c2d35ff8db2dece4e0593979d3ac223'
SOURCE='https://github.com/openscriptures/strongs'
CREATOR='Based on the work of Larry Pierce at the Online Bible'
CREATOR_URL='http://www.blueletterbible.org/contact/contact_gen.cfm'
def inline(node):
 text=html.escape(node.text or '')
 for child in node:
  tag=child.tag.rsplit('}',1)[-1]
  if tag=='w':
   ref=child.get('src','');label=''.join(child.itertext()).strip() or child.get('lemma','')
   if ref.isdigit():
    number='H'+str(int(ref));label=number+(' · '+label if label else '')
    value='<a href="#" data-ref="Strong '+number+'">'+html.escape(label)+'</a>'
   else:value=html.escape(label or child.get('gloss',''))
  elif tag in ['hi','catchWord']:value='<i>'+inline(child)+'</i>'
  else:value=inline(child)
  text+=value+html.escape(child.tail or '')
 return text.strip()
def outline(items):
 senses=[];stack=[]
 for item in items:
  value=inline(item);match=re.match(r'^(\d+[a-z]?(?:\d+[a-z]?)*)[).]\s*',value)
  if not match:senses.append({'definition':value});stack=[];continue
  label=match[1];sense={'label':label,'definition':value[match.end():]}
  tokens=re.findall(r'\d+|[a-z]',label)
  while stack and not (tokens[:len(re.findall(r'\d+|[a-z]',stack[-1][0]))]==re.findall(r'\d+|[a-z]',stack[-1][0]) and len(tokens)>len(re.findall(r'\d+|[a-z]',stack[-1][0]))):stack.pop()
  if stack:stack[-1][1].setdefault('senses',[]).append(sense)
  else:senses.append(sense)
  stack.append((label,sense))
 return senses
def load_strongs(path):
 root=ET.parse(path).getroot();work=root.find('.//o:work[@osisWork="Strong"]',NS)
 assert work.findtext('o:rights',namespaces=NS)=='Public Domain'
 result=[]
 for entry in root.findall('.//o:div[@type="entry"]',NS):
  word=entry.find('o:w',NS);number=entry.get('n');sid='H'+number
  assert word.get('ID')==sid
  notes={}
  for note in entry.findall('o:note',NS):notes.setdefault(note.get('type'),[]).append(inline(note))
  raw={'headword':word.get('lemma') or word.text,'parent_lexicon':LEXICON,'strong_id':sid,'strong_number':number,'transliteration':word.get('xlit',''),'pronunciation':word.get('POS',''),'language_code':word.get(XML_LANG,''),'content':{'morphology':word.get('morph',''),'senses':outline(entry.findall('o:list/o:item',NS))},'etymology':' '.join(notes.get('exegesis',[])),'strong_definition':' '.join(notes.get('explanation',[])),'translation':' '.join(notes.get('translation',[])),'editorial_notes':notes.get('x-typo',[]),'source_entry_xml':ET.tostring(entry,encoding='unicode'),'parent_lexicon_details':{'name':LEXICON,'source':'Open Scriptures on GitHub','source_url':SOURCE,'attribution':CREATOR,'attribution_url':CREATOR_URL,'original_author':'James Strong','xml_editors':['David Troidl','David Instone-Brewer'],'license':'Public Domain (Hebrew OSIS XML header)','source_commit':COMMIT}}
  result.append(raw)
 assert len(result)==8674 and {r['strong_id'] for r in result}=={'H'+str(n) for n in range(1,8675)}
 return result
