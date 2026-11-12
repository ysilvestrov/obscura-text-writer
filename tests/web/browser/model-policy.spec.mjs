// MODEL-003/MODEL-004: consent checkbox and refusal mark under the chosen model of a role.
import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
// Consent and marks are global for role + endpoint + model: every test uses its own model IDs.
const unique=name=>`${name}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;
// Private: the Venice picker hides rows below Private by default.
const option=(id,uncensored=null)=>({id,name:id,context_tokens:65536,max_output_tokens:4096,tariff:null,uncensored,privacy:'private',tee:false,supports_schema:null});
const LABEL='Я погоджуюся, що ця модель отримуватиме запити для творів із рейтингом вище 0, і відповідаю за наслідки.';

async function openWriter(page,{storyId,provider='openrouter',catalog}){
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:catalog}}));
  await page.goto(`/stories/${storyId}/settings`);await page.locator('[data-settings-role=writer]').click();
  const form=page.locator('form[data-role=writer]'),picker=form.locator('.model-picker');
  await form.locator('[name=provider]').selectOption(provider);
  await form.locator('.discover').click();
  return {form,picker,model:form.locator('[name=model]'),consent:picker.getByLabel(LABEL),warn:picker.locator('[data-model-consent]'),refusal:picker.locator('[data-model-refusal]'),
    pick:async id=>{await picker.locator(`tbody tr[data-model-id="${id}"]`).click();await expect(form.locator('[name=model]')).toHaveValue(id)}};
}
const story=async request=>(await(await request.post('/test-fixture')).json()).story_id;

test('consent for an OpenRouter model is stored at once and does not follow another model',async({page,request})=>{
  const first=unique('pol-a'),second=unique('pol-b'),catalog=[option(first),option(second)],storyId=await story(request);
  let view=await openWriter(page,{storyId,catalog});
  await view.pick(first);
  await expect(view.consent).toBeVisible();await expect(view.consent).toBeEnabled();await expect(view.consent).not.toBeChecked();
  await expect(view.warn).toContainText('Згода діє для цієї ролі й моделі в усіх творах.');
  const put=page.waitForRequest(r=>r.method()==='PUT'&&r.url().endsWith('/api/model-policy/consent'));
  await view.consent.check();
  expect((await put).postDataJSON()).toMatchObject({role:'writer',provider:'openrouter',model:first});
  await expect(view.consent).toBeChecked();
  // Not a role setting: no name, so the form draft and its save never carry it.
  expect(await view.consent.getAttribute('name')).toBeNull();
  // Review Focus 4: another model shows its own state, not the old checkbox.
  await view.pick(second);
  await expect(view.consent).toBeEnabled();await expect(view.consent).not.toBeChecked();
  await page.reload();
  view=await openWriter(page,{storyId,catalog});
  await view.pick(first);await expect(view.consent).toBeEnabled();await expect(view.consent).toBeChecked();
  await view.pick(second);await expect(view.consent).toBeEnabled();await expect(view.consent).not.toBeChecked();
});

test('venice shows the checkbox only for a model without Uncensored; local never',async({page,request})=>{
  const plain=unique('pol-ven'),free=unique('pol-unc');
  const view=await openWriter(page,{storyId:await story(request),provider:'venice',catalog:[option(plain,false),option(free,true)]});
  await view.pick(plain);await expect(view.consent).toBeVisible();
  await view.pick(free);await expect(view.warn).toBeHidden();
  await view.form.locator('[name=provider]').selectOption('local');
  await view.model.fill(unique('pol-local'));await view.model.blur();
  await expect(view.warn).toBeHidden();
});

test('a saved Venice model shows no consent warning before the model list is loaded',async({page,request})=>{
  const plain=unique('pol-saved'),storyId=await story(request);
  const current=await(await request.get(`/api/stories/${storyId}/settings`)).json();
  const settings={...current.roles.writer,provider:{...current.roles.writer.provider,provider:'venice',model:plain,base_url:'https://api.venice.ai/api/v1',key_env:'VENICE_API_KEY'}};
  const saved=await request.put(`/api/stories/${storyId}/settings`,{data:{role:'writer',settings,expected_revision:current.story.revision}});
  expect(saved.ok()).toBeTruthy();
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:[option(plain,false)]}}));
  await page.goto(`/stories/${storyId}/settings`);await page.locator('[data-settings-role=writer]').click();
  const form=page.locator('form[data-role=writer]'),warn=form.locator('.model-picker [data-model-consent]');
  await expect(form.locator('[name=model]')).toHaveValue(plain);
  // Uncensored is unknown until the catalog is loaded: no false warning for the saved model.
  await expect(warn).toBeHidden();
  await form.locator('.discover').click();
  await expect(warn).toBeVisible();
});

test('a failed consent request keeps the previous state and shows the error',async({page,request})=>{
  const id=unique('pol-err');
  const view=await openWriter(page,{storyId:await story(request),catalog:[option(id)]});
  await page.route('**/api/model-policy/consent',route=>route.fulfill({status:500,json:{detail:'Сховище недоступне'}}));
  await view.pick(id);await expect(view.consent).toBeEnabled();
  await view.consent.click();
  await expect(view.picker.locator('[data-model-policy-error]')).toHaveText('Сховище недоступне');
  await expect(view.consent).not.toBeChecked();
});

test('a recorded refusal shows the red notice; clearing removes it, choosing another opens the list',async({page,request})=>{
  const id=unique('pol-ref');
  await request.post('/test-model-refusal',{data:{role:'writer',provider:'openrouter',model:id,rating:[0,2,1]}});
  const view=await openWriter(page,{storyId:await story(request),catalog:[option(id),option(unique('pol-other'))]});
  await view.pick(id);
  await expect(view.refusal).toBeVisible();
  await expect(view.refusal).toContainText('Модель відмовила через зміст на запиті з рейтингом сексуальний зміст 0, насильство 2, жорсткі теми 1. Виклики з таким самим або вищим рейтингом заблоковано.');
  const panel=view.picker.locator('.model-picker-panel');
  await view.picker.locator('[data-model-chosen] button').click();await expect(panel).toBeHidden();
  await view.refusal.getByRole('button',{name:'Вибрати іншу модель'}).click();await expect(panel).toBeVisible();
  const del=page.waitForRequest(r=>r.method()==='DELETE'&&r.url().includes('/api/model-policy/refusal?'));
  await view.refusal.getByRole('button',{name:'Зняти позначку'}).click();
  expect(new URL((await del).url()).searchParams.get('model')).toBe(id);
  await expect(view.refusal).toBeHidden();
  await page.locator('[data-ui-locale=en]').click();
  await expect(view.picker.getByLabel('I agree that this model will receive requests for works rated above 0, and I take responsibility for the consequences.')).toBeVisible();
});

test('classifier settings carry the consent block for the editor role',async({page,request})=>{
  const id=unique('pol-cls');
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:[option(id,false)]}}));
  await page.goto(`/stories/${await story(request)}/settings`);await page.locator('[data-settings-role=editor]').click();
  const form=page.locator('form[data-role=editor]');
  await form.locator('details:has([name=classification_enabled]) > summary').click();
  await form.locator('[name=classification_enabled]').check();
  const fields=form.locator('.classification-fields');
  await fields.getByRole('button',{name:'Отримати список моделей'}).click();
  await fields.locator(`tbody tr[data-model-id="${id}"]`).click();
  const put=page.waitForRequest(r=>r.method()==='PUT'&&r.url().endsWith('/api/model-policy/consent'));
  await fields.getByLabel(LABEL).check();
  expect((await put).postDataJSON()).toMatchObject({role:'editor',provider:'venice',model:id});
});
