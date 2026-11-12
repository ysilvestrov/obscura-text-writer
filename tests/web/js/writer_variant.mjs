import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
globalThis.document={querySelector:()=>null,addEventListener:()=>{}};
const {variantPayload,variantBase}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/writer-variant.js'));
const {t,setLocale}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/i18n.js'));
const form=(enabled,values={},base=null)=>({writerVariantBase:base,elements:Object.fromEntries(Object.entries({
  variant_enabled:{checked:enabled},response_mode:'json_schema',variant_provider:'venice',variant_base_url:'https://api.venice.ai/api/v1',variant_model:'e2ee-glm',
  variant_context_tokens:'32768',variant_max_output_tokens:'4096',variant_max_input_chars:'60000',variant_temperature:'0.6',variant_timeout:'240',...values,
}).map(([name,value])=>[name,typeof value==='object'?value:{value}]))});
// MODEL-001 S02 (UI): an unchecked toggle means no variant; the writer save then clears it.
assert.equal(variantPayload(form(false)),null);
// A checked toggle gives the variant with numeric limits and the writer's shared response mode.
const payload=variantPayload(form(true));
assert.deepEqual({...payload,provider:undefined},{provider:undefined,context_tokens:32768,max_output_tokens:4096,max_input_chars:60000,temperature:0.6,timeout:240});
assert.deepEqual(payload.provider,{provider:'venice',model:'e2ee-glm',base_url:'https://api.venice.ai/api/v1',key_env:null,timeout:240,response_mode:'json_schema',include_usage:false});
// An empty timeout uses the provider default.
assert.equal(variantPayload(form(true,{variant_timeout:''})).timeout,null);
assert.equal(variantPayload(form(true,{variant_timeout:''})).provider.timeout,null);
// Stored provider options of the same provider survive a save; another provider starts clean.
const base={provider:{provider:'venice',model:'old',base_url:'https://api.venice.ai/api/v1',key_env:'MY_VENICE',timeout:180,include_usage:true,response_mode:'prompt_json',venice_disable_thinking:true}};
const kept=variantPayload(form(true,{},base)).provider;
assert.equal(kept.key_env,'MY_VENICE');assert.equal(kept.venice_disable_thinking,true);assert.equal(kept.include_usage,true);assert.equal(kept.model,'e2ee-glm');assert.equal(kept.response_mode,'json_schema');
const other=variantPayload(form(true,{variant_provider:'openrouter',variant_base_url:'https://openrouter.ai/api/v1'},base)).provider;
assert.equal(other.key_env,null);assert.equal(other.venice_disable_thinking,undefined);
// No stored variant: a variant of the main provider keeps its connection options (Venice flags, key name); another provider starts clean.
const main={provider:'venice',model:'main',base_url:'https://api.venice.ai/api/v1',key_env:'MAIN_VENICE',timeout:180,include_usage:true,response_mode:'json_schema',venice_disable_thinking:true,venice_reasoning_effort:'low'};
const fresh=variantPayload(form(true,{},variantBase({provider:main}))).provider;
assert.equal(fresh.key_env,'MAIN_VENICE');assert.equal(fresh.include_usage,true);assert.equal(fresh.venice_disable_thinking,true);assert.equal(fresh.venice_reasoning_effort,'low');assert.equal(fresh.model,'e2ee-glm');
assert.equal(variantPayload(form(true,{variant_provider:'openrouter'},variantBase({provider:main}))).provider.key_env,null);
assert.deepEqual(variantBase({provider:main,low_rating_variant:base}),base);
assert.equal(t('writer.variant.toggle'),'Окрема модель для сцен рівня 0–1');
assert.equal(t('writer.variant.hint'),'Необов’язково. Якщо не задано, всі сцени пише основна модель. Сцени, де хоч одна вісь рейтингу дорівнює 2, завжди пише основна модель.');
assert.equal(t('writer.variant.main_hint'),'Основна модель пише всі сцени, включно з рівнем 2.');
setLocale('en');
assert.equal(t('writer.variant.toggle'),'Separate model for scenes rated 0–1');
assert.equal(t('writer.variant.hint'),'Optional. If not set, the main model writes every scene. Scenes where any rating axis is 2 are always written by the main model.');
assert.equal(t('writer.variant.main_hint'),'The main model writes every scene, including level 2.');
