// Рендер списку порушень формату відповіді пам’яті. Тексти — лише textContent; мітки операцій вже людські (з сервера).
export function violationDetails(violations,{t}){
  const items=Array.isArray(violations?.items)?violations.items:[];
  if(!items.length)return null;
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
  const total=Number.isFinite(violations.total)?violations.total:items.length;
  const box=node('details'),list=node('ul');box.className='memory-violations';
  box.append(node('summary',t('memory.violations.title',{p0:total})),list);
  for(const item of items){
    const key=`memory.violation.${item.code}`,label=t(key),code=label===key?String(item.code):label;
    list.append(node('li',`${item.operation} · ${code}`));
  }
  if(total>items.length)list.append(node('li',t('memory.violations.more',{p0:total-items.length})));
  return box;
}
