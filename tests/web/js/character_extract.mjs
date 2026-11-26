import {pathToFileURL} from 'node:url';
// CHARACTER-EXTRACT (R-51): the accept body from the default selection and from a selection without the new card.
const root=process.argv[2];
const {acceptBody,defaultSelection}=await import(pathToFileURL(root+'/src/storygen/web/static/character-extract.js'));
const proposal={fingerprint:'f',
  cards:[{key:'n1',name:'Марко',other_names:[{name:'Марк',suggested:true},{name:'сторож',suggested:false}],quotes:[]}],
  name_updates:[{card_id:'A',names:[{name:'Оленка',suggested:true}]},{card_id:'B',names:[{name:'пані',suggested:false}]}],
  protagonist:{ref:'A',scores:[1]},casts:[{scene_id:'s1',mode:'set',participants:['A','n1']}]};
const strip=body=>{const {run_id,fingerprint,dry_run,...rest}=body;if(run_id!=='r'||fingerprint!=='f'||dry_run!==true)throw new Error('envelope');return rest};
const selection=defaultSelection(proposal);
const result={default:strip(acceptBody(proposal,selection,'r',true))};
selection.cards.delete('n1');selection.names.delete('u:A:Оленка');selection.protagonist=false;selection.casts.clear();
result.without_card=strip(acceptBody(proposal,selection,'r',true));
process.stdout.write(JSON.stringify(result));
