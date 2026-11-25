import {t,uiText,uiAttr} from './i18n.js';
// MEMORY-SELECT-S08: the memory table's type mark as a compact icon button with a menu (auto / core / atmosphere).
const SVG='http://www.w3.org/2000/svg';
export const KINDS=[['','memory.kind_auto'],['core','memory.kind_core'],['atmosphere','memory.kind_atmosphere']];
const SHAPES={
  '':[['path',{d:'M12 3l1.9 5.6L19.5 10.5l-5.6 1.9L12 18l-1.9-5.6L4.5 10.5l5.6-1.9z'}]],
  core:[['circle',{cx:'12',cy:'12',r:'8'}],['circle',{cx:'12',cy:'12',r:'3.5',fill:'currentColor'}]],
  atmosphere:[['path',{d:'M7.5 18h9a4 4 0 0 0 .6-7.95A5.5 5.5 0 0 0 6.6 11.2 3.4 3.4 0 0 0 7.5 18z'}]],
};
export function kindIcon(value){
  const svg=document.createElementNS(SVG,'svg');
  for(const [name,value2] of Object.entries({viewBox:'0 0 24 24',width:'18',height:'18',fill:'none',stroke:'currentColor','stroke-width':'1.8','stroke-linejoin':'round','aria-hidden':'true',class:'memory-kind-icon'}))svg.setAttribute(name,value2);
  for(const [tag,attrs] of SHAPES[value]??SHAPES['']){const shape=document.createElementNS(SVG,tag);for(const [name,value2] of Object.entries(attrs))shape.setAttribute(name,value2);svg.append(shape);}
  return svg;
}
const labelKey=value=>(KINDS.find(([kind])=>kind===value)??KINDS[0])[1];
// Legend above the table: the three icons with their names, so a closed button needs no text.
export function kindLegend(){
  const legend=document.createElement('p');legend.className='hint memory-kind-legend';
  const title=document.createElement('span');uiText(title,'textContent',()=>t('memory.kind_legend'));legend.append(title);
  for(const [value,key] of KINDS){const item=document.createElement('span');item.className='memory-kind-legend-item';const text=document.createElement('span');uiText(text,'textContent',()=>t(key));item.append(kindIcon(value),text);legend.append(item);}
  return legend;
}
export function kindMenu({value,text,disabled,onPick}){
  const box=document.createElement('div');box.className='memory-kind-box';
  const button=document.createElement('button');button.type='button';button.className='secondary memory-kind';button.disabled=disabled;
  button.setAttribute('aria-haspopup','menu');button.setAttribute('aria-expanded','false');
  uiAttr(button,'aria-label',()=>t('memory.kind_button',{p0:text,p1:t(labelKey(value))}));uiAttr(button,'title',()=>t(labelKey(value)));
  button.dataset.kind=value;
  const caret=document.createElement('span');caret.className='memory-kind-caret';caret.setAttribute('aria-hidden','true');caret.textContent='▾';
  button.append(kindIcon(value),caret);
  const menu=document.createElement('div');menu.className='memory-kind-menu';menu.setAttribute('role','menu');menu.hidden=true;
  uiAttr(menu,'aria-label',()=>t('memory.kind_label',{p0:text}));
  const items=KINDS.map(([kind,key])=>{
    const item=document.createElement('button');item.type='button';item.className='memory-kind-item';item.setAttribute('role','menuitemradio');
    item.setAttribute('aria-checked',String(kind===value));item.tabIndex=-1;item.dataset.kind=kind;
    const label=document.createElement('span');uiText(label,'textContent',()=>t(key));
    const mark=document.createElement('span');mark.className='memory-kind-check';mark.setAttribute('aria-hidden','true');mark.textContent=kind===value?'✓':'';
    item.append(kindIcon(kind),label,mark);
    item.onclick=event=>{event.stopPropagation();close(false);if(kind!==value)onPick(kind);else button.focus();};
    menu.append(item);return item;
  });
  const outside=event=>{if(!box.contains?.(event.target))close(false);};
  // The table wrapper scrolls sideways and would clip an absolute menu: the open menu is fixed to the window,
  // under the button (above it when there is no room below), and follows the button when the page scrolls or resizes.
  const follow=()=>place();
  function place(){
    if(!button.getBoundingClientRect)return;
    const anchor=button.getBoundingClientRect(),own=menu.getBoundingClientRect(),gap=4,edge=8;
    const width=globalThis.innerWidth,height=globalThis.innerHeight;
    const left=Math.max(edge,Math.min(anchor.right-own.width,width-own.width-edge));
    // Below the button; above it when only that side has room; otherwise clamped into the window.
    const below=anchor.bottom+gap,above=anchor.top-gap-own.height;
    const wanted=below+own.height>height-edge&&above>=edge?above:below;
    const top=Math.max(edge,Math.min(wanted,height-own.height-edge));
    menu.style.left=`${left}px`;menu.style.top=`${top}px`;
  }
  function open(){
    if(button.disabled||!menu.hidden)return;
    menu.hidden=false;button.setAttribute('aria-expanded','true');place();
    document.addEventListener('pointerdown',outside,true);
    globalThis.addEventListener?.('resize',follow);globalThis.addEventListener?.('scroll',follow,true);
    (items.find(item=>item.dataset.kind===value)||items[0]).focus({preventScroll:true});
  }
  function close(refocus=true){
    if(menu.hidden)return;
    menu.hidden=true;button.setAttribute('aria-expanded','false');
    document.removeEventListener?.('pointerdown',outside,true);
    globalThis.removeEventListener?.('resize',follow);globalThis.removeEventListener?.('scroll',follow,true);
    if(refocus)button.focus();
  }
  button.onclick=()=>menu.hidden?open():close();
  button.onkeydown=event=>{if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();open();}};
  menu.onkeydown=event=>{
    const index=items.indexOf(document.activeElement);
    const move=step=>{event.preventDefault();items[(index+step+items.length)%items.length].focus({preventScroll:true});};
    if(event.key==='ArrowDown')move(1);
    else if(event.key==='ArrowUp')move(-1);
    else if(event.key==='Home'){event.preventDefault();items[0].focus({preventScroll:true});}
    else if(event.key==='End'){event.preventDefault();items.at(-1).focus({preventScroll:true});}
    else if(event.key==='Escape'){event.preventDefault();close();}
    else if(event.key==='Tab')close(false);
  };
  box.append(button,menu);
  return {box,button,menu,items,open,close};
}
