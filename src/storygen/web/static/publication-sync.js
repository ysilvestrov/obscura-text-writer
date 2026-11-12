// MCP-BRIDGE-S31: what the open publication page does when it finds changes made elsewhere (a chat, another window).
// Pure: the page reads the card and the signature library on return and asks this function.
const libraryKey=items=>JSON.stringify((items||[]).map(item=>[item.id,item.revision,item.archived_at||null]).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0));

export function externalPublicationChange({loadedRevision,freshRevision,formDirty,busy,loadedLibrary,freshLibrary,libraryDirty}){
  const cardChanged=freshRevision!==loadedRevision;
  const libraryChanged=libraryKey(loadedLibrary)!==libraryKey(freshLibrary);
  // A clean card reload brings the library with it; edited fields or a save in progress are never overwritten.
  const reloadCard=cardChanged&&!formDirty&&!busy&&!libraryDirty;
  const warnCard=cardChanged&&!reloadCard;
  return {reloadCard,warnCard,reloadLibrary:!reloadCard&&libraryChanged&&!libraryDirty};
}

// The card save sends the revision of every chosen signature: a fresh library must refresh those revisions too.
export function withLibraryRevisions(revisions,library){
  return {...revisions,...Object.fromEntries((library||[]).map(item=>[item.id,item.revision]))};
}
