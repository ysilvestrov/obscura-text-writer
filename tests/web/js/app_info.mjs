import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {allowedLevels,limited,appInfo}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/app-info.js'));
assert.deepEqual(allowedLevels(2,null),[0,1,2]);
assert.deepEqual(allowedLevels(1,0),[0,1]);
assert.deepEqual(allowedLevels(1,1),[0,1]);
// A level stored above the limit stays visible, so the form never shows a value the data does not have.
assert.deepEqual(allowedLevels(1,2),[0,1,2]);
assert.deepEqual(allowedLevels(0,2),[0,2]);
assert.equal(limited({sexual:1,violence:2,themes:2}),true);
assert.equal(limited({sexual:2,violence:2,themes:2}),false);
// A failed request falls back to the full edition instead of breaking the rating forms; the request is made once.
let calls=0;
globalThis.fetch=async()=>{calls++;throw new Error('offline')};
const info=await appInfo();
assert.deepEqual(info.max_rating,{sexual:2,violence:2,themes:2});
assert.equal(info.edition,'full');
await appInfo();
assert.equal(calls,1);
