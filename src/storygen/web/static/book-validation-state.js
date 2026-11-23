// R-44 book validation, design §12: pure rules of the story menu item; book-validation.js renders them.
const PENDING=new Set(['unchecked','discrepancy','unavailable']);

// The menu counts the scenes the run would visit: those with any link in unchecked, discrepancy or unavailable
// (server: audit_run.book_pending and the preview's `invalid_scenes`), whatever the scene's validity, so a brief-only
// (`incomplete`) scene with an unchecked brief link counts. An item without `links` counts as 0.
export function invalidSceneCount(materialStatus){
  return Object.values(materialStatus||{}).filter(item=>Object.values(item?.links||{}).some(link=>PENDING.has(link?.status))).length;
}

// The label key and state of the item: unknown before the view loads, «Книга валідна» and inactive at 0.
export function bookMenuState(count){
  if(!Number.isInteger(count))return {key:'book_validation.menu',params:{},disabled:true};
  if(count===0)return {key:'book_validation.valid',params:{},disabled:true};
  return {key:'book_validation.menu_count',params:{p0:count},disabled:false};
}
