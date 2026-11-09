import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const root=new URL('../../../',import.meta.url);
const {ghostBlocks}=await import(new URL('src/storygen/web/static/ghost-blocks.js',root));
const vectors=JSON.parse(readFileSync(new URL('tests/fixtures/ghost_blocks.json',root),'utf8'));
assert.ok(vectors.length>=8);
for(const vector of vectors)assert.deepEqual(ghostBlocks(vector.text),vector.blocks,vector.name);
