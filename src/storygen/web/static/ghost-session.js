// Ghost Mode (#55): the rewrite session as plain data. No DOM; the mode UI drives it and the node test checks it.
// Block states: reading (AI text visible, nothing typed yet) -> writing (after the first change, even if erased again)
// <-> peek (only from writing: author text hidden, editing locked); skipped (explicit) -> back to reading/writing.
import {ghostBlocks,normalizeText,codePointSlice} from './ghost-blocks.js';

export const sessionKey=(sceneId,draftId)=>`ghost:${sceneId}:${draftId}`;

export function createSession({sceneId,draftId,format,text}){
  const source=normalizeText(text);
  return {version:1,sceneId,draftId,format,index:0,peeks:0,peekMs:0,pastesBlocked:0,
    blocks:ghostBlocks(source).map(block=>({kind:block.kind,source:codePointSlice(source,block.start,block.end),
      state:block.kind==='separator'?'separator':'reading',touched:false,text:''}))};
}

const current=session=>session.blocks[session.index];

export function input(session,text){
  const block=current(session);
  if(!block||block.kind!=='text'||block.state==='peek'||block.state==='skipped')return false;
  if(block.text===text&&block.touched)return false;
  block.text=text;
  if(!block.touched&&text===''&&block.state==='reading')return false;
  block.touched=true;block.state='writing';return true;
}

export function peekStart(session){
  const block=current(session);
  if(block?.state!=='writing')return false;
  block.state='peek';session.peeks+=1;return true;
}

export function peekEnd(session,elapsedMs=0){
  const block=current(session);
  if(block?.state!=='peek')return false;
  block.state='writing';session.peekMs+=Math.max(0,Math.round(elapsedMs));return true;
}

export function skip(session){
  const block=current(session);
  if(!block||block.kind!=='text'||block.state==='skipped')return false;
  if(block.state==='peek')block.state='writing';
  block.state='skipped';return true;
}

export function unskip(session){
  const block=current(session);
  if(block?.state!=='skipped')return false;
  block.state=block.touched?'writing':'reading';return true;
}

export function go(session,delta){
  const block=current(session);
  if(block?.state==='peek')return false;
  const next=Math.min(session.blocks.length-1,Math.max(0,session.index+delta));
  if(next===session.index)return false;
  session.index=next;return true;
}

export function blockPasted(session){session.pastesBlocked+=1;}

const textBlocks=session=>session.blocks.filter(block=>block.kind==='text');
export const skippedCount=session=>textBlocks(session).filter(block=>block.state==='skipped').length;
export const writtenCount=session=>textBlocks(session).filter(block=>['writing','peek'].includes(block.state)&&block.text.trim()).length;
export const doneBlock=block=>block.kind!=='text'||block.state==='skipped'||(block.state==='writing'&&!!block.text.trim());
export const canSave=session=>textBlocks(session).length>0&&textBlocks(session).every(doneBlock)&&writtenCount(session)>0;
export const hasWork=session=>textBlocks(session).some(block=>block.touched||block.state==='skipped');

export function resultText(session){
  return session.blocks.filter(block=>block.kind==='separator'||block.state==='writing').map(block=>block.kind==='separator'?block.source:block.text.trim()).filter(Boolean).join('\n\n');
}

export function clientStats(session){
  return {peeks:session.peeks,peek_ms:session.peekMs,pastes_blocked:session.pastesBlocked,blocks_skipped:skippedCount(session)};
}

// Storage is injected so the model works without localStorage; every access is guarded.
export function saveSession(storage,session){
  try{
    const copy={...session,blocks:session.blocks.map(block=>({...block,state:block.state==='peek'?'writing':block.state}))};
    storage?.setItem(sessionKey(session.sceneId,session.draftId),JSON.stringify(copy));return true;
  }catch{return false;}
}

export function loadSession(storage,sceneId,draftId){
  try{
    const raw=storage?.getItem(sessionKey(sceneId,draftId));if(!raw)return null;
    const data=JSON.parse(raw);
    if(data?.version!==1||data.sceneId!==sceneId||data.draftId!==draftId||!Array.isArray(data.blocks))return null;
    return data;
  }catch{return null;}
}

export function findSession(storage,sceneId){
  try{
    for(let i=0;i<(storage?.length||0);i++){const key=storage.key(i);if(key?.startsWith(`ghost:${sceneId}:`))return key.slice(`ghost:${sceneId}:`.length);}
  }catch{}
  return null;
}

export function dropSession(storage,sceneId,draftId){try{storage?.removeItem(sessionKey(sceneId,draftId));}catch{}}

export function ghostStatsText(stats,t){
  if(!stats)return '';
  const overlap=stats.overlap_4gram===null||stats.overlap_4gram===undefined?'—':`${Math.round(stats.overlap_4gram*100)} %`;
  return t('ghost.stats',{p0:stats.blocks_written,p1:stats.blocks,p2:stats.blocks_skipped,p3:overlap,p4:stats.peeks,p5:Math.round(stats.peek_ms/1000),p6:stats.pastes_blocked});
}
