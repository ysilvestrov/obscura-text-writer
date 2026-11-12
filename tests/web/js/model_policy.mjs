import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
globalThis.document={querySelector:()=>null,addEventListener:()=>{}};
const {consentVisible,refusalRatings}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/model-policy.js'));
const {t,setLocale}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/i18n.js'));
// MODEL-003: the consent checkbox is shown for any non-local model that is not explicitly Uncensored.
assert.equal(consentVisible({uncensored:true},'venice'),false);
assert.equal(consentVisible({uncensored:false},'venice'),true);
assert.equal(consentVisible(null,'openrouter'),true);
assert.equal(consentVisible({uncensored:null},'local'),false);
assert.equal(consentVisible(null,'local'),false);
assert.equal(consentVisible({uncensored:null},'openrouter'),true);
assert.equal(consentVisible({uncensored:true},'openrouter'),false);
// MODEL-004: every stored refusal vector is named in the notice.
assert.equal(refusalRatings([{rating:[0,2,1]}]),'сексуальний зміст 0, насильство 2, жорсткі теми 1');
assert.equal(refusalRatings([{rating:[2,0,0]},{rating:[0,1,0]}]),'сексуальний зміст 2, насильство 0, жорсткі теми 0; сексуальний зміст 0, насильство 1, жорсткі теми 0');
assert.equal(t('policy.consent_label'),'Я погоджуюся, що ця модель отримуватиме запити для творів із рейтингом вище 0, і відповідаю за наслідки.');
assert.equal(t('policy.consent_hint'),'Модель без позначки Uncensored може відмовити або пом’якшити відвертий зміст. Згода діє для цієї ролі й моделі в усіх творах.');
assert.equal(t('policy.refused',{p0:'X'}),'Модель відмовила через зміст на запиті з рейтингом X. Виклики з таким самим або вищим рейтингом заблоковано.');
assert.equal(t('policy.clear_refusal'),'Зняти позначку');
assert.equal(t('policy.choose_other'),'Вибрати іншу модель');
setLocale('en');
assert.equal(t('policy.consent_label'),'I agree that this model will receive requests for works rated above 0, and I take responsibility for the consequences.');
assert.equal(t('policy.consent_hint'),'A model without the Uncensored mark may refuse or soften explicit content. Consent applies to this role and model in all works.');
assert.equal(t('policy.refused',{p0:'X'}),'The model refused on content for a request rated X. Calls with the same or a higher rating are blocked.');
assert.equal(t('policy.clear_refusal'),'Clear the mark');
assert.equal(t('policy.choose_other'),'Choose another model');
assert.equal(refusalRatings([{rating:[0,2,1]}]),'sexual content 0, violence 2, hard themes 1');
