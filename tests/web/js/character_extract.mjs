import {pathToFileURL} from 'node:url';
// CHARACTER-EXTRACT (R-51): the accept body from the default selection and from a selection without the new card.
const root=process.argv[2];
const {acceptBody,defaultSelection}=await import(pathToFileURL(root+'/src/storygen/web/static/character-extract.js'));
const proposal={fingerprint:'f',
  cards:[{key:'n1',name:'Марко',other_names:[{name:'Марк',suggested:true},{name:'сторож',suggested:false}],quotes:[]}],
  name_updates:[{card_id:'A',names:[{name:'Оленка',suggested:true}]},{card_id:'B',names:[{name:'пані',suggested:false}]}],
  protagonist:{ref:'A',scores:[1]},casts:[{scene_id:'s1',mode:'set',participants:['A','n1']}],
  locations:[{scene_id:'s1',mode:'set',places:[{ref:'new',path:'Пірс',new:true,suggested:true},{ref:'l2',path:'Маяк / ліхтарна',new:false,suggested:false}]},
             {scene_id:'s2',mode:'add',places:[{ref:'l1',path:'Маяк',new:false,suggested:true}]}]};
const strip=body=>{const {run_id,fingerprint,dry_run,...rest}=body;if(run_id!=='r'||fingerprint!=='f'||dry_run!==true)throw new Error('envelope');return rest};
const selection=defaultSelection(proposal);
const result={default:strip(acceptBody(proposal,selection,'r',true))};
selection.cards.delete('n1');selection.names.delete('u:A:Оленка');selection.protagonist=false;selection.casts.clear();
selection.places.delete('s2\nМаяк');selection.places.add('s1\nМаяк / ліхтарна');
result.without_card=strip(acceptBody(proposal,selection,'r',true));
// A proposal from before places has none and sends none.
const {locations,...old}=proposal;
result.old=strip(acceptBody(old,defaultSelection(old),'r',true)).locations;
process.stdout.write(JSON.stringify(result));
