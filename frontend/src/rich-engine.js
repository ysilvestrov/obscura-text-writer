import {EditorState,TextSelection} from 'prosemirror-state';
import {Slice} from 'prosemirror-model';
import {EditorView} from 'prosemirror-view';
import {baseKeymap, toggleMark} from 'prosemirror-commands';
import {history, undo, redo} from 'prosemirror-history';
import {keymap} from 'prosemirror-keymap';
import {loadDocument, serializeDocument, schema} from './markdown-bridge.js';
import {toSourceRange,toDocumentRange} from './source-map.js';
import {createCommentPlugin,commentAnnotations,replaceCommentAnnotations} from './comment-plugin.js';
export {loadDocument, serializeDocument, schema} from './markdown-bridge.js';
export {toSourceRange, toDocumentRange, codepointOffset, utf16Offset, SourceMappingError} from './source-map.js';
export {createCommentEditorState,commentAnnotations,replaceCommentAnnotations} from './comment-plugin.js';
export {undo as undoTransaction,redo as redoTransaction} from 'prosemirror-history';

/** DOM ownership stays here; the application consumes source snapshots, not HTML. */
export function createRichEditor(host, options = {}) {
  let baseline = loadDocument(options.source ?? '', options.content_format ?? 'plain');
  let sourceRef=options.source_ref||null,cachedDoc=null,cachedBaseline=null,cachedSnapshot=null;
  const snapshot=()=>{
    if(cachedDoc!==view.state.doc||cachedBaseline!==baseline){cachedDoc=view.state.doc;cachedBaseline=baseline;cachedSnapshot=serializeDocument(cachedDoc,baseline);}
    return cachedSnapshot;
  };
  let readOnly = Boolean(options.readOnly);
  const guard = command => (state, dispatch, editor) => !readOnly && command(state, dispatch, editor);
  const safeBase = Object.fromEntries(Object.entries(baseKeymap).map(([key, command]) => [key, guard(command)]));
  const view = new EditorView(host, {
    state: EditorState.create({doc: baseline.doc, plugins: [history(),createCommentPlugin({onClick:(...args)=>options.onCommentClick?.(...args),onChange:items=>options.onCommentsChange?.(items)}),keymap({'Mod-z': guard(undo), 'Mod-y': guard(redo), 'Shift-Mod-z': guard(redo), 'Mod-b': guard(toggleMark(schema.marks.strong)), 'Mod-i': guard(toggleMark(schema.marks.em))}), keymap(safeBase)]}),
    editable: () => !readOnly,
    dispatchTransaction(transaction) {
      const before = view.state;
      view.updateState(before.apply(transaction));
      options.onTransaction?.(transaction, before, view.state);
      if (transaction.docChanged) options.onInput?.();
    },
    // Paste is text-only; never import untrusted HTML, styles or remote images.
    handlePaste(_view, event) {
      if (readOnly) return true;
      const text = event.clipboardData?.getData('text/plain');
      if (text === undefined) return false;
      const parsed=loadDocument(text,'plain').doc;
      const nodes=[];parsed.forEach(node=>nodes.push(schema.nodes.paragraph.create(null,node.content)));
      const fragment=schema.nodes.doc.create(null,nodes).content;
      view.dispatch(view.state.tr.replaceSelection(new Slice(fragment,1,1)).scrollIntoView());return true;
    },
  });
  return {
    view,
    snapshot,
    markSaved(snapshot) {
      const loaded = loadDocument(snapshot.source, snapshot.content_format);
      loaded.doc = view.state.doc;
      loaded.sourceMap.doc = view.state.doc;
      loaded.blocks = loaded.blocks.map((block, index) => ({...block, node: view.state.doc.child(index), id: view.state.doc.child(index).attrs.sourceId}));
      baseline = loaded;
      sourceRef=snapshot.source_ref||sourceRef;
    },
    selection: () => ({from: view.state.selection.from, to: view.state.selection.to}),
    canComment(){
      const range=view.state.selection;
      if(readOnly||range.empty)return {allowed:false,reason:'select'};
      if(commentAnnotations(view.state).some(item=>Number.isInteger(item.from)&&range.from<item.to&&range.to>item.from))return {allowed:false,reason:'overlap'};
      try{toSourceRange(range,snapshot().sourceMap);return {allowed:true};}
      catch{return {allowed:false,reason:'unsupported'};}
    },
    prepareComment(id){
      const range={from:view.state.selection.from,to:view.state.selection.to};
      if(!this.canComment().allowed)throw new Error('Comment selection is unavailable');
      const current=snapshot(),anchor=toSourceRange(range,current.sourceMap);
      const saved=sourceRef?.sha256&&current.source===baseline.source&&current.content_format===baseline.content_format;
      return {id,...range,state:'valid',reason:null,origin:{doc:view.state.doc,...range,anchor,
        ref:saved?{version_id:sourceRef.id,sha256:sourceRef.sha256,content_format:sourceRef.content_format}:null,
        source:saved?null:{text:current.source,content_format:current.content_format}}};
    },
    upsertComment(candidate){
      if(readOnly||!candidate.origin?.doc?.eq(view.state.doc))throw new Error('Comment source changed');
      const items=commentAnnotations(view.state).filter(item=>item.id!==candidate.id);
      view.dispatch(replaceCommentAnnotations(view.state.tr,[...items,candidate]));
    },
    removeComment(id){if(!readOnly)view.dispatch(replaceCommentAnnotations(view.state.tr,commentAnnotations(view.state).filter(item=>item.id!==id)));},
    captureComments(){
      const current=snapshot();
      return commentAnnotations(view.state).map(item=>({id:item.id,anchor:item.state==='valid'
        ?{...toSourceRange(item,current.sourceMap),state:'valid',reason:null,origin:null}
        :{...item.origin.anchor,state:'needs_review',reason:item.reason||'modified',origin:item.origin.ref||null,
          ...(item.origin.source?{origin_source:item.origin.source}:{})}}));
    },
    setComments(notes,{mismatch=false}={}){
      const current=snapshot();
      const bindings=new Map(commentAnnotations(view.state).map(item=>[item.id,item.binding]));
      const items=(notes?.comments||[]).map(comment=>{
        const anchor=comment.anchor;
        const ref={version_id:notes.source_version_id,sha256:notes.source_sha256,content_format:notes.content_format};
        if(anchor.state==='needs_review'||mismatch)return {id:comment.id,binding:bindings.get(comment.id),from:null,to:null,state:'needs_review',reason:anchor.reason||'source_changed',origin:{anchor:{...anchor,origin:null},ref:anchor.origin||ref,source:null,doc:null}};
        const range=toDocumentRange(anchor,current.sourceMap);
        return {id:comment.id,binding:bindings.get(comment.id),...range,state:'valid',reason:null,origin:{doc:view.state.doc,...range,anchor:{...anchor,origin:null},ref,source:null}};
      });
      view.dispatch(replaceCommentAnnotations(view.state.tr,items,{silent:true}));
    },
    commentQuote(id){const item=commentAnnotations(view.state).find(item=>item.id===id);return item?.origin.anchor.display_quote||'';},
    selectComment(id){const item=commentAnnotations(view.state).find(item=>item.id===id);if(Number.isInteger(item?.from))view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc,item.from,item.to)));},
    readOnly(value) {readOnly = Boolean(value); view.setProps({editable: () => !readOnly});},
    isReadOnly: () => readOnly,
    canUndo: () => !readOnly && undo(view.state),
    canRedo: () => !readOnly && redo(view.state),
    canToggle: mark => !readOnly && toggleMark(schema.marks[mark])(view.state),
    toggle(mark) {if (readOnly) return false; return toggleMark(schema.marks[mark])(view.state, view.dispatch, view);},
    undo() {return !readOnly && undo(view.state, view.dispatch);},
    redo() {return !readOnly && redo(view.state, view.dispatch);},
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
