import assert from 'node:assert/strict';
const root=new URL('../../../src/storygen/web/static/',import.meta.url);
const {settingsContentKey:key,externalSettingsChange:decide,readSettingsContent}=await import(new URL('settings-sync.js',root));

const settings={story:{revision:3,config_revision:1,target_words:7000,language:'uk',content_rating:{sexual:0,violence:1,dark:0},title:'T'},
  roles:{writer:{provider:{provider:'local',model:'m'},temperature:0.7}},profile:{genre:'mystery',tone:''},prompts:{writer:'p'},
  prepare_prompt:'q',prompt_contracts:{writer:{stage:'draft'}},prepare_prompt_contract:null};
const evaluator={config:{model:'e'},block:{reason:'x'},revision:4};
const base=key(settings,evaluator);
// MCP-BRIDGE-S38: a new scene or a title change moves the story revision but not the settings.
assert.equal(key({...settings,story:{...settings.story,revision:9,title:'Other'}},{...evaluator,block:null,revision:5}),base,'revision, title and evaluator block are not settings');
const reversed=Object.fromEntries(Object.entries(settings).reverse().map(([k,v])=>[k,v&&typeof v==='object'?Object.fromEntries(Object.entries(v).reverse()):v]));
assert.equal(key(reversed,evaluator),base,'key order does not matter');
for(const [label,changed] of [
  ['rating',{...settings,story:{...settings.story,content_rating:{sexual:0,violence:2,dark:0}}}],
  ['language',{...settings,story:{...settings.story,language:'en'}}],
  ['target words',{...settings,story:{...settings.story,target_words:9000}}],
  ['role',{...settings,roles:{writer:{...settings.roles.writer,temperature:0.9}}}],
  ['profile',{...settings,profile:{...settings.profile,tone:'dry'}}],
  ['prompt',{...settings,prompts:{writer:'other'}}],
])assert.notEqual(key(changed,evaluator),base,label);
assert.notEqual(key(settings,{...evaluator,config:{model:'f'}}),base,'evaluator settings');

const none={reload:false,warn:false};
assert.deepEqual(decide({loadedKey:base,freshKey:base,unsaved:false,busy:false}),none);
assert.deepEqual(decide({loadedKey:base,freshKey:'x',unsaved:false,busy:false}),{reload:true,warn:false},'a clean page reloads');
assert.deepEqual(decide({loadedKey:base,freshKey:'x',unsaved:true,busy:false}),{reload:false,warn:true},'unsaved edits are kept');
assert.deepEqual(decide({loadedKey:base,freshKey:'x',unsaved:false,busy:true}),{reload:false,warn:true},'a save in progress is not interrupted');
assert.deepEqual(decide({loadedKey:null,freshKey:'x',unsaved:false,busy:false}),none,'nothing loaded yet');
// A story without an evaluator answers 400 "not configured": the page still watches its settings.
const failing=status=>Object.assign(new Error('x'),{status});
const fake=evaluatorAnswer=>async url=>{if(url.endsWith('/settings'))return settings;if(evaluatorAnswer instanceof Error)throw evaluatorAnswer;return evaluatorAnswer};
assert.equal(await readSettingsContent(fake(failing(400)),'S1'),key(settings,null),'no evaluator yet');
assert.equal(await readSettingsContent(fake(evaluator),'S1'),base);
await assert.rejects(readSettingsContent(fake(failing(500)),'S1'),'other failures are not hidden');
console.log('settings sync ok');
