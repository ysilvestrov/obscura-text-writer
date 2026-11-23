// R-44 book validation, design §12: pure rules of the story menu item; book-validation.js renders them.
const INVALID=new Set(['unchecked','discrepancy']);

// The menu counts the scenes the author sees as invalid in the story view. The preview's `invalid_scenes` counts the
// scenes the run would visit, which may differ (an `incomplete` scene, a scene whose only pending link is unavailable).
export function invalidSceneCount(materialStatus){
  return Object.values(materialStatus||{}).filter(item=>INVALID.has(item?.validity)).length;
}

// The label key and state of the item: unknown before the view loads, «Книга валідна» and inactive at 0.
export function bookMenuState(count){
  if(!Number.isInteger(count))return {key:'book_validation.menu',params:{},disabled:true};
  if(count===0)return {key:'book_validation.valid',params:{},disabled:true};
  return {key:'book_validation.menu_count',params:{p0:count},disabled:false};
}
