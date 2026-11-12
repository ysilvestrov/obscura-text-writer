// Pure logic for the model catalog picker: badges, filters and selectability.
export const PRIVACY_RANK={unknown:-1,anonymized:0,private:1,tee:2};
const MIN_RANK={any:-1,private:1,tee:2};

export function privacyLevel(model){
  if(model.tee)return 'tee';
  return Object.hasOwn(PRIVACY_RANK,model.privacy)?model.privacy:'unknown';
}

export function modelBadges(model){
  const kinds=[];
  if(model.uncensored===true)kinds.push('uncensored');
  kinds.push(privacyLevel(model));
  if(model.supports_schema===true)kinds.push('schema');
  return kinds.map(kind=>({kind,key:`models.badge_${kind}`}));
}

export const providerReportsPrivacy=provider=>provider==='venice';
export const schemaLocked=responseMode=>responseMode==='json_schema';

export function filterModels(models,{query='',uncensoredOnly=false,minPrivacy='any',schemaOnly=false}={},provider){
  const needle=String(query||'').trim().toLowerCase();
  const minRank=providerReportsPrivacy(provider)?(MIN_RANK[minPrivacy]??-1):-1;
  return models.filter(model=>{
    if(needle&&!`${model.id||''}`.toLowerCase().includes(needle)&&!`${model.name||''}`.toLowerCase().includes(needle))return false;
    if(uncensoredOnly&&model.uncensored!==true)return false;
    if(schemaOnly&&model.supports_schema!==true)return false;
    return PRIVACY_RANK[privacyLevel(model)]>=minRank;
  });
}

export function selectable(model,{provider,responseMode}={}){
  if(model===null||model===undefined)return {ok:true,reason:null};
  if(provider==='venice'&&model.uncensored!==true)return {ok:false,reason:'venice_uncensored_pending'};
  if(schemaLocked(responseMode)&&model.supports_schema!==true)return {ok:false,reason:'schema_required'};
  return {ok:true,reason:null};
}

export function formatPrice(usd){
  if(usd===null||usd===undefined||usd==='')return '—';
  const value=Number(usd);
  if(!Number.isFinite(value))return '—';
  const digits=value<10?2:1;
  return String(Number(value.toFixed(digits)));
}
