import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
globalThis.document={querySelector:()=>null,addEventListener:()=>{}};
const {modelMetadataLabel}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/model-catalog.js'));
const {diagnostic,setLocale}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/i18n.js'));
const model={context_tokens:200000,max_output_tokens:24000,tariff:{input_per_million:'0.07',output_per_million:'0.4',request_usd:'0',kind:'manual',expires_at:'2026-01-01T00:00:00Z'}};
assert.match(modelMetadataLabel(model,Date.parse('2026-11-06T00:00:00Z')),/прострочений/);
assert.match(modelMetadataLabel(null),/Тариф невідомий/);
assert.doesNotMatch(modelMetadataLabel({...model,tariff:{...model.tariff,expires_at:'bad'}}),/0.07/);
setLocale('en');
assert.match(modelMetadataLabel(model,Date.parse('2026-11-06T00:00:00Z')),/Manual tariff/);
assert.match(modelMetadataLabel(model),/1,000,000/);
assert.equal(diagnostic('HTTP 429: Перевищено ліміт частоти запитів провайдера. Автоматичного повтору немає.'),'HTTP 429: Provider request rate limit exceeded. No automatic retry.');
assert.match(diagnostic('Контекст 262144 перевищує ліміт вибраної моделі 200000 токенів. Змініть налаштування; автоматичного повтору немає.'),/Context 262144 exceeds/);

setLocale('uk');
assert.equal(diagnostic('HTTP 429: Provider request rate limit exceeded. No automatic retry.'),'HTTP 429: Перевищено ліміт частоти запитів провайдера. Автоматичного повтору немає.');
