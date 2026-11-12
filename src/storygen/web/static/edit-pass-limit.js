// Per-story browser preference for the editor pass limit; survives a reload (e.g. returning from settings).
export const DEFAULT_EDIT_PASS_LIMIT=5;
const valid=value=>Number.isInteger(value)&&value>=1&&value<=10;
const key=storyId=>'obscura.edit-pass-limit.v1.'+storyId;
function browserStorage(){try{return globalThis.localStorage;}catch{return null;}}
export function readEditPassLimit(storyId,storage=browserStorage()){
  if(!storyId)return DEFAULT_EDIT_PASS_LIMIT;
  try{const value=Number(storage?.getItem(key(storyId)));return valid(value)?value:DEFAULT_EDIT_PASS_LIMIT;}catch{return DEFAULT_EDIT_PASS_LIMIT;}
}
export function rememberEditPassLimit(storyId,value,storage=browserStorage()){
  if(!storyId||!valid(value)||!storage)return false;
  try{storage.setItem(key(storyId),String(value));return true;}catch{return false;}
}
