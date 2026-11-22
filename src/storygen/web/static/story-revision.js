// Panels of one tab that each keep the story revision for CAS (memory kinds, timeline summaries, locations).
// A write here moves the revision by one; the others follow only when that write is the sole change since they loaded,
// so a change from another tab still shows as a conflict.
const followers=new Set();
export function followRevision(read){followers.add(read)}
export function announceRevision(storyId,revision){
  for(const read of followers){
    const panel=read();
    if(panel&&panel.storyId===storyId&&panel.get()===revision-1)panel.set(revision);
  }
}
