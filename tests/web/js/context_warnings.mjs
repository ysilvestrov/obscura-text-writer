import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {confirmationText}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/run-readiness.js'));
const text=confirmationText({roles:{writer:{provider:'local',model:'fake'}},calls:1,warnings:['Часову доступність не перевірено']});
assert.ok(text.includes('Часову доступність не перевірено'));
