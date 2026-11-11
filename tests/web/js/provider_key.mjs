import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {keyStatusKey,validKeyName,needsKey}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/provider-key.js'));
const state=(source,stored,store_available=true)=>({name:'X_KEY',source,stored,store_available});
assert.equal(keyStatusKey(state(null,false)),'keys.status.none');
assert.equal(keyStatusKey(state('store',true)),'keys.status.store');
assert.equal(keyStatusKey(state('env',false)),'keys.status.env');
assert.equal(keyStatusKey(state('env',true)),'keys.status.env_and_store');
assert.equal(keyStatusKey(state(null,false,false)),'keys.status.unavailable');
// A key from the environment is reported as such even when the store is unavailable.
assert.equal(keyStatusKey(state('env',false,false)),'keys.status.env');
for(const name of ['OPENROUTER_API_KEY','VENICE_API_KEY','ABC','MY_KEY_2'])assert.equal(validKeyName(name),true,name);
for(const name of ['','A','lower_KEY','WITH-DASH','path','X'.repeat(65),' VENICE_API_KEY'])assert.equal(validKeyName(name),false,name);
assert.deepEqual(['openrouter','venice','local','codex_cli'].map(needsKey),[true,true,false,false]);
