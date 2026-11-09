// Ghost Mode (#55): the same block split as storygen/authoring/ghost.py::ghost_blocks.
// Both are checked against tests/fixtures/ghost_blocks.json; offsets are in LF-normalized text.
export const GHOST_MIN_BLOCK_CHARS=160;
const SEPARATORS=new Set(['***','* * *','---','___']);
const HEADING=/^#{1,6}(\s|$)/;

export const normalizeText=text=>text.replace(/\r\n/g,'\n').replace(/\r/g,'\n');

function paragraphs(text){
  const out=[],gap=/\n\s*\n/g;let position=0,match;
  const take=stop=>{
    const chunk=text.slice(position,stop),stripped=chunk.trim();
    if(stripped){const lead=chunk.length-chunk.trimStart().length;out.push([position+lead,position+lead+stripped.length]);}
  };
  while((match=gap.exec(text))){take(match.index);position=match.index+match[0].length;}
  take(text.length);
  return out;
}

export function ghostBlocks(source){
  const text=normalizeText(source),blocks=[];
  let current=[],fragmentStart=0;
  const size=parts=>parts.reduce((sum,[start,end])=>sum+end-start,0);
  const close=boundary=>{
    if(!current.length)return;
    const short=boundary&&size(current)<GHOST_MIN_BLOCK_CHARS;
    const heading=HEADING.test(text.slice(current[0][0],current[0][1]));
    const last=blocks[blocks.length-1];
    if(short&&!heading&&blocks.length>fragmentStart&&last.kind==='text'){blocks.pop();blocks.push({kind:'text',start:last.start,end:current[current.length-1][1]});}
    else blocks.push({kind:'text',start:current[0][0],end:current[current.length-1][1]});
    current=[];
  };
  for(const [start,end] of paragraphs(text)){
    const body=text.slice(start,end);
    if(SEPARATORS.has(body)){close(true);blocks.push({kind:'separator',start,end});fragmentStart=blocks.length;continue;}
    if(HEADING.test(body)&&current.length)close(true);
    current.push([start,end]);
    if(size(current)>=GHOST_MIN_BLOCK_CHARS)close(false);
  }
  close(true);
  return blocks;
}
