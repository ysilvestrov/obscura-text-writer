import {t,uiText,uiAttr} from './i18n.js';
const engineModule=globalThis.document?.documentElement?.style
  ? await import('./rich-editor-engine.js') : null;
const instances=new WeakMap();

/** One owner per host, shared by workspace, statistics, memory and trash. */
export function createTextEditor(element){
  if(instances.has(element))return instances.get(element);
  let engine=null,wrapper=null,host=null,toolbar=null,shown=true,locked=false;
  let metadata={material:'plan',content_format:'plain',version_id:null};
  let baselineText='',baselineFormat='plain',sourceRef=null,commentHandlers={};
  const inputHandlers=new Set(),transactionHandlers=new Set(),buttons=new Map();
  const emit=()=>{for(const handler of inputHandlers)handler()};
  element.addEventListener('input',emit);
  function visibility(){element.hidden=!shown||!!engine;if(wrapper)wrapper.hidden=!shown||!engine;}
  function update(){
    if(!engine)return;
    const marks=engine.view.state.storedMarks||engine.view.state.selection.$from.marks();
    for(const [name,button]of buttons){button.hidden=name==='comment'&&(!commentHandlers.onCreate||metadata.material!=='draft');button.disabled=locked||(name==='comment'?!engine.canComment().allowed:name==='undo'?!engine.canUndo():name==='redo'?!engine.canRedo():!engine.canToggle(name));if(['strong','em'].includes(name))button.setAttribute('aria-pressed',String(marks.some(mark=>mark.type.name===name)));}
    engine.view.dom.dataset.empty=String(engine.view.state.doc.textContent.length===0);
  }
  function mount(){
    if(wrapper)return;
    const doc=element.ownerDocument;
    wrapper=doc.createElement('section');wrapper.className='rich-text-surface';
    toolbar=doc.createElement('div');toolbar.className='rich-text-toolbar';toolbar.setAttribute('role','toolbar');uiAttr(toolbar,'aria-label',()=>t('authoring.formatting'));
    host=doc.createElement('div');host.className='rich-text-host';wrapper.append(toolbar,host);element.after(wrapper);
    const icons={comment:'M3 4h14v10H8l-5 4V4',undo:'M6 4 2 8l4 4M2 8h8a5 5 0 0 1 0 10',redo:'m14 4 4 4-4 4m4-4h-8a5 5 0 0 0 0 10'};
    for(const [name,key]of [['strong','authoring.bold'],['em','authoring.italic'],['comment','comments.create'],['undo','authoring.undo'],['redo','authoring.redo']]){
      const button=doc.createElement('button');button.type='button';button.className='secondary';uiAttr(button,'aria-label',()=>t(key));uiAttr(button,'title',()=>t(key));
      if(icons[name]){
        const svg=doc.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 20 22');svg.setAttribute('aria-hidden','true');
        const path=doc.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',icons[name]);svg.append(path);button.append(svg);
      }else{const glyph=doc.createElement(name==='strong'?'strong':'em');glyph.textContent=name==='strong'?'B':'I';button.append(glyph);}
      button.onpointerdown=event=>event.preventDefault();
      button.onclick=()=>{if(locked||!engine)return;if(name==='comment'){commentHandlers.onCreate?.();return;}if(name==='undo'||name==='redo')engine[name]();else engine.toggle(name);engine.focus();update();};
      toolbar.append(button);buttons.set(name,button);
    }
  }
  const adapter={
    read:()=>engine?engine.snapshot().source:element.value,
    write(text,options={}){
      const next={material:options.material||'plan',content_format:options.content_format||'plain',version_id:options.version_id||null};
      const useRich=engineModule&&element.ownerDocument&&['draft','prose'].includes(next.material);
      if(engine&&useRich&&JSON.stringify(metadata)===JSON.stringify(next)&&engine.snapshot().source===text)return;
      if(useRich)engineModule.loadDocument(text,next.content_format);
      engine?.destroy();engine=null;
      metadata=next;baselineText=text;baselineFormat=next.content_format;sourceRef=options.source_ref||null;element.value=text;
      if(useRich){
        mount();host.replaceChildren();
        engine=engineModule.createRichEditor(host,{source:text,content_format:next.content_format,source_ref:sourceRef,readOnly:locked,
          onCommentClick:(...args)=>commentHandlers.onClick?.(...args),onCommentsChange:(...args)=>commentHandlers.onChange?.(...args),
          onInput:emit,onTransaction:(...args)=>{update();for(const handler of transactionHandlers)handler(...args);}});
        engine.view.dom.setAttribute('role','textbox');engine.view.dom.setAttribute('aria-multiline','true');
        engine.view.dom.setAttribute('aria-labelledby',element.getAttribute('aria-labelledby')||'scene-title');update();
      }
      visibility();
    },
    snapshot:()=>engine?{...metadata,...engine.snapshot()}:{source:element.value,...metadata},
    identity:()=>({...metadata}),
    markSaved(snapshot){if(engine)engine.markSaved(snapshot);baselineText=snapshot.source;baselineFormat=snapshot.content_format;sourceRef=snapshot.source_ref||sourceRef;metadata={...metadata,content_format:snapshot.content_format,version_id:snapshot.version_id??metadata.version_id};},
    isDirty(){const value=adapter.snapshot();return value.source!==baselineText||value.content_format!==baselineFormat;},
    sourceRef:()=>sourceRef,
    setCommentHandlers(handlers){commentHandlers=handlers;update();},
    canComment:()=>engine?.canComment()||{allowed:false},
    prepareComment:id=>engine?.prepareComment(id),
    upsertComment:comment=>engine?.upsertComment(comment),
    removeComment:id=>engine?.removeComment(id),
    captureComments:()=>engine?.captureComments()||[],
    setComments:(notes,options)=>engine?.setComments(notes,options),
    commentQuote:id=>engine?.commentQuote(id)||'',
    selectComment:id=>engine?.selectComment(id),
    placeholder(text){uiText(element,'placeholder',()=>text);if(engine)uiAttr(engine.view.dom,'data-placeholder',()=>text);},
    readOnly(value){locked=Boolean(value);element.readOnly=locked;engine?.readOnly(locked);update();},
    isReadOnly:()=>locked,
    visible(value){shown=Boolean(value);visibility();},
    focus:()=>engine?engine.focus():element.focus(),
    selection:()=>engine?engineModule.toSourceRange(engine.selection(),engine.snapshot().sourceMap):null,
    onInput(handler){inputHandlers.add(handler);return()=>inputHandlers.delete(handler);},
    onTransaction(handler){transactionHandlers.add(handler);return()=>transactionHandlers.delete(handler);},
    visibleText:()=>engine?engine.view.state.doc.textBetween(0,engine.view.state.doc.content.size,'\n\n','\n'):element.value,
  };
  instances.set(element,adapter);return adapter;
}
