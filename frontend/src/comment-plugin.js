import {Plugin,PluginKey,EditorState} from 'prosemirror-state';
import {Decoration,DecorationSet} from 'prosemirror-view';
import {Step,StepResult} from 'prosemirror-transform';
import {history,isHistoryTransaction,closeHistory} from 'prosemirror-history';

const key=new PluginKey('obscura-author-comments');
let bindingSequence=0;
const bind=item=>item.binding?item:{...item,binding:'attachment-'+(++bindingSequence)};
const geometry=item=>({id:item.id,binding:item.binding,from:item.from,to:item.to,state:item.state,reason:item.reason,origin:item.origin});
const jsonItem=item=>({...item,origin:item.origin?{...item.origin,doc:item.origin.doc?.toJSON()}:null});
const fromJSON=(schema,item)=>({...item,origin:item.origin?{...item.origin,doc:item.origin.doc?schema.nodeFromJSON(item.origin.doc):null}:null});

class GeometryStep extends Step{
  constructor(before,after){super();this.before=before;this.after=after;}
  apply(doc){return StepResult.ok(doc);}
  invert(){return new GeometryStep(this.after,this.before);}
  map(){return this;} // Local history only; no collaborative rebasing is enabled.
  toJSON(){return {stepType:'obscura-comment-geometry-v1',before:this.before.map(jsonItem),after:this.after.map(jsonItem)};}
  static fromJSON(schema,value){return new GeometryStep(value.before.map(item=>fromJSON(schema,item)),value.after.map(item=>fromJSON(schema,item)));}
}
Step.jsonID('obscura-comment-geometry-v1',GeometryStep);

function assertRanges(items,doc){
  if(new Set(items.map(item=>item.id)).size!==items.length)throw new Error('Duplicate annotation ID');
  const active=items.filter(item=>item.state==='valid').sort((a,b)=>a.from-b.from);
  if(active.some(item=>!Number.isInteger(item.from)||!Number.isInteger(item.to)||item.from<0||item.to>doc.content.size||item.from>=item.to))throw new Error('Invalid annotation range');
  if(active.some((item,index)=>index&&item.from<active[index-1].to))throw new Error('Annotation ranges overlap');
}

function mapItem(item,step){
  if(!Number.isInteger(item.from)||!Number.isInteger(item.to))return item;
  const map=step.getMap();let touched=false;
  map.forEach((left,right)=>{if(left===right?left>item.from&&left<item.to:left<item.to&&right>item.from)touched=true;});
  // Mark changes have empty position maps, but still change the annotated text.
  if(['addMark','removeMark'].includes(step.toJSON().stepType)&&step.from<item.to&&step.to>item.from)touched=true;
  const from=map.map(item.from,1),to=map.map(item.to,-1);
  return {...item,from:Math.min(from,to),to:Math.max(from,to),
    state:touched?'needs_review':item.state,reason:touched?'modified':item.reason};
}

export const commentAnnotations=state=>key.getState(state)?.items||[];
export function replaceCommentAnnotations(transaction,items,{silent=false}={}){
  return closeHistory(transaction.setMeta(key,{items:items.map(bind),silent}).setMeta('addToHistory',false));
}

export function createCommentPlugin(options={}){
  return new Plugin({
    key,
    state:{
      init:(_config,state)=>{const items=(options.initial||[]).map(bind);assertRanges(items,state.doc);return {items,silent:true};},
      apply(transaction,current){
        const replacement=transaction.getMeta(key);
        if(replacement){assertRanges(replacement.items,transaction.doc);return {items:replacement.items,silent:replacement.silent};}
        if(!transaction.docChanged)return current;
        const recorded=transaction.steps.filter(step=>step instanceof GeometryStep);
        let items=current.items.map(item=>{
          const snapshots=recorded.map(step=>step.after.find(value=>value.id===item.id));
          if(recorded.length&&snapshots.every(value=>value&&value.binding===item.binding))return {...item,...snapshots.at(-1)};
          for(const step of transaction.steps)if(!(step instanceof GeometryStep))item=mapItem(item,step);
          return item;
        });
        if(isHistoryTransaction(transaction))items=items.map(item=>{
          if(item.state==='needs_review'&&item.origin?.doc?.eq(transaction.doc)){
            return {...item,from:item.origin.from,to:item.origin.to,state:'valid',reason:null};
          }
          return item;
        });
        const conflicted=new Set();
        for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
          const a=items[i],b=items[j];
          if(a.state==='valid'&&b.state==='valid'&&a.from<b.to&&b.from<a.to){conflicted.add(a.id);conflicted.add(b.id);}
        }
        items=items.map(item=>conflicted.has(item.id)?{...item,state:'needs_review',reason:'history_overlap'}:item);
        assertRanges(items,transaction.doc);
        return {items,silent:false};
      },
    },
    appendTransaction(transactions,before,after){
      if(!transactions.some(tr=>tr.docChanged)||transactions.some(tr=>tr.getMeta(key)||tr.getMeta('comments-recorded')||isHistoryTransaction(tr)))return null;
      const old=commentAnnotations(before),updated=commentAnnotations(after);
      if(!old.some((item,index)=>item.from!==updated[index]?.from||item.to!==updated[index]?.to||item.state!==updated[index]?.state))return null;
      return after.tr.step(new GeometryStep(old.map(geometry),updated.map(geometry))).setMeta('comments-recorded',true);
    },
    props:{
      decorations(state){
        return DecorationSet.create(state.doc,commentAnnotations(state).filter(item=>Number.isInteger(item.from)&&item.from<item.to&&item.to<=state.doc.content.size)
          .map(item=>Decoration.inline(item.from,item.to,{'class':'author-comment'+(item.state==='needs_review'?' author-comment-pending':''),'data-comment-id':item.id})));
      },
      handleDOMEvents:{click(_view,event){
        const element=event.target?.closest?.('[data-comment-id]');
        if(!element)return false;
        event.preventDefault();options.onClick?.(element.dataset.commentId,event);return true;
      }},
    },
    view(){return {update(view,previous){
      const current=key.getState(view.state),old=key.getState(previous);
      if(current.items!==old.items&&!current.silent)options.onChange?.(current.items);
    }};},
  });
}

export function createCommentEditorState(doc,initial=[]){
  return EditorState.create({doc,plugins:[history(),createCommentPlugin({initial})]});
}
