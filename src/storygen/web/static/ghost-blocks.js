// Ghost Mode (#55): the same block split as storygen/authoring/ghost.py::ghost_blocks.
// Both are checked against tests/fixtures/ghost_blocks.json; offsets and lengths are Unicode code points
// (as in Python) of the LF-normalized text, not UTF-16 units: use codePointSlice to cut a block.
export const GHOST_MIN_BLOCK_CHARS=160;
const SEPARATORS=new Set(['***','* * *','---','___']);
const HEADING=/^#{1,6}(\s|$)/;

export const normalizeText=text=>text.replace(/\r\n/g,'\n').replace(/\r/g,'\n');

export const codePointSlice=(text,start,end)=>Array.from(text).slice(start,end).join('');

function codePoints(text){
  // map[i] = number of code points before UTF-16 index i
  const map=new Int32Array(text.length+1);let count=0;
  for(let i=0;i<text.length;i++){
    map[i]=count;
    const low=text.charCodeAt(i),high=i>0?text.charCodeAt(i-1):0;
    if(!(low>=0xDC00&&low<=0xDFFF&&high>=0xD800&&high<=0xDBFF))count++;
  }
  map[text.length]=count;return map;
}

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
  const text=normalizeText(source),blocks=[],cp=codePoints(text);
  let current=[],fragmentStart=0;
  const size=parts=>parts.reduce((sum,[start,end])=>sum+end-start,0);
  const close=boundary=>{
    if(!current.length)return;
    const short=boundary&&size(current)<GHOST_MIN_BLOCK_CHARS;
    const heading=current[0][2];
    const last=blocks[blocks.length-1];
    if(short&&!heading&&blocks.length>fragmentStart&&last.kind==='text'){blocks.pop();blocks.push({kind:'text',start:last.start,end:current[current.length-1][1]});}
    else blocks.push({kind:'text',start:current[0][0],end:current[current.length-1][1]});
    current=[];
  };
  for(const [from,to] of paragraphs(text)){
    const body=text.slice(from,to),start=cp[from],end=cp[to];
    if(SEPARATORS.has(body)){close(true);blocks.push({kind:'separator',start,end});fragmentStart=blocks.length;continue;}
    if(HEADING.test(body)&&current.length)close(true);
    current.push([start,end,HEADING.test(body)]);
    if(size(current)>=GHOST_MIN_BLOCK_CHARS)close(false);
  }
  close(true);
  return blocks;
}
