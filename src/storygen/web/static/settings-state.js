export function settingsSignature(value){
  if(Array.isArray(value))return '['+value.map(settingsSignature).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+settingsSignature(value[k])).join(',')+'}';
  return JSON.stringify(value);
}
export function settingsRoute(search){
  const query=new URLSearchParams(search),role=['planner','writer','editor','memory'].includes(query.get('role'))?query.get('role'):'planner';
  const section=['writing','models','evaluator','budget','profiles'].includes(query.get('section'))?query.get('section'):'models';
  return {section,role};
}
export class SettingsDrafts{
  records=new Map();
  register(key,value){this.records.set(key,{baseline:structuredClone(value),current:structuredClone(value),busy:false,error:null})}
  get(key){return this.records.get(key)}
  change(key,value){const r=this.get(key);if(r)r.current=structuredClone(value)}
  dirty(key){const r=this.get(key);return !!r&&settingsSignature(r.current)!==settingsSignature(r.baseline)}
  saved(key){const r=this.get(key);if(r){r.baseline=structuredClone(r.current);r.error=null}}
  rebase(key,fields){const r=this.get(key);if(r)for(const[k,v]of Object.entries(fields)){r.current[k]=structuredClone(v);r.baseline[k]=structuredClone(v)}}
  changedFields(key,names){const r=this.get(key);return !!r&&names.some(n=>settingsSignature(r.current[n])!==settingsSignature(r.baseline[n]))}
  reset(key){const r=this.get(key);r.current=structuredClone(r.baseline);r.error=null;return structuredClone(r.current)}
  setBusy(key,value){const r=this.get(key);if(r)r.busy=value}
  setError(key,error){const r=this.get(key);if(r)r.error=error}
  anyDirty(){return [...this.records.keys()].some(k=>this.dirty(k))}
  anyBusy(){return [...this.records.values()].some(r=>r.busy)}
}
