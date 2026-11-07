// Рендер списку порушень формату відповіді пам’яті. Тексти — лише textContent; сервер зберігає сирі шляхи (`$`, `operations[i]`, `<категорія>.<дія>[i]`, індекси з 0), мітки формуються тут і локалізуються через t().
export function operationLabel(path,t){
  const raw=String(path);
  if(raw==='$')return t('memory.violation.path.response');
  let m=/^operations\[(\d+)\]$/.exec(raw);
  if(m)return t('memory.violation.path.operation',{p0:Number(m[1])+1});
  m=/^([a-z_]+\.[a-z_]+)\[(\d+)\]$/.exec(raw);
  if(m)return t('memory.violation.path.element',{p0:m[1],p1:Number(m[2])+1});
  return raw;
}
export function violationDetails(violations,{t}){
  const items=Array.isArray(violations?.items)?violations.items:[];
  if(!items.length)return null;
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
  const total=Number.isFinite(violations.total)?violations.total:items.length;
  const box=node('details'),list=node('ul');box.className='memory-violations';
  box.append(node('summary',t('memory.violations.title',{p0:total})),list);
  for(const item of items){
    const key=`memory.violation.${item.code}`,label=t(key),code=label===key?String(item.code):label;
    list.append(node('li',`${operationLabel(item.operation,t)} · ${code}`));
  }
  if(total>items.length)list.append(node('li',t('memory.violations.more',{p0:total-items.length})));
  return box;
}
