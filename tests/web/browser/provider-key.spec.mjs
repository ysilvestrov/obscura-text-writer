import {test,expect} from '../../../frontend/browser-test.mjs';

// SECURITY-002: the fixture server keeps keys in memory; every test starts from an empty, available store.
test.use({locale:'uk-UA'});
const VALUE='sk-browser-synthetic-0001';
const reset=(request,data={})=>request.post('/test-secret-store',{data});
test.beforeEach(async({request})=>{await reset(request,{env:{OPENROUTER_API_KEY:null,VENICE_API_KEY:null}})});
test.afterEach(async({request})=>{await reset(request,{env:{OPENROUTER_API_KEY:null,VENICE_API_KEY:null}})});

const openRole=async(page,request,role='planner')=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}/settings`);
  await page.locator(`[data-settings-role="${role}"]`).click();
  const form=page.locator(`form[data-role="${role}"]`);
  await expect(form.locator('[name="model"]')).toBeVisible();
  return {form,block:form.locator('.provider-key'),status:form.locator('.provider-key-status'),story_id:f.story_id};
};

test('key block is absent for the local provider and appears for a cloud one',async({page,request})=>{
  const {form,block,status}=await openRole(page,request);
  await form.locator('[name="provider"]').selectOption('local');
  await expect(block).toBeHidden();
  await form.locator('[name="provider"]').selectOption('openrouter');
  await expect(block).toBeVisible();
  await expect(status).toHaveText('Ключ не задано.');
  await expect(block.locator('button',{hasText:'Зберегти ключ'})).toBeDisabled();
  await expect(block.locator('button',{hasText:'Видалити збережений ключ'})).toBeDisabled();
});

test('saving a key shows only its state, never the value, and does not dirty the settings form',async({page,request})=>{
  const {form,block,status}=await openRole(page,request);
  await form.locator('[name="provider"]').selectOption('openrouter');
  await expect(status).toHaveText('Ключ не задано.');
  // Selecting the provider changed the form; save it so that the key block alone is under test.
  const stored=page.waitForResponse(r=>r.url().includes('/settings')&&r.request().method()==='PUT');
  await form.locator('[name="model"]').fill('synthetic-model');
  await page.locator('#settings-save').click();await stored;
  await expect(page.locator('#settings-save')).toBeDisabled();
  const bodies=[];
  page.on('response',async response=>{if(response.url().includes('/api/'))bodies.push(await response.text().catch(()=>''))});
  const input=block.locator('.provider-key-input');
  await input.fill(VALUE);
  await expect(page.locator('#settings-save')).toBeDisabled();
  const saved=page.waitForResponse(r=>r.url().includes('/api/provider-keys/OPENROUTER_API_KEY')&&r.request().method()==='PUT');
  await block.locator('button',{hasText:'Зберегти ключ'}).click();
  expect((await saved).ok()).toBe(true);
  await expect(status).toHaveText('Ключ збережено. Ключ збережено у сховищі Windows.');
  await expect(input).toHaveValue('');
  await expect(page.locator('#settings-save')).toBeDisabled();
  expect(await page.content()).not.toContain(VALUE);
  expect(bodies.join('\n')).not.toContain(VALUE);
  // The state survives a reload; the value does not come back.
  await page.reload();
  await page.locator('[data-settings-role="planner"]').click();
  await expect(status).toHaveText('Ключ збережено у сховищі Windows.');
  await expect(input).toHaveValue('');
  await page.locator('[data-ui-locale="en"]').click();
  await expect(status).toHaveText('The key is saved in the Windows credential store.');
  await page.locator('[data-ui-locale="uk"]').click();
  await block.locator('button',{hasText:'Видалити збережений ключ'}).click();
  await expect(status).toHaveText('Збережений ключ видалено. Ключ не задано.');
});

test('state follows the variable name and the environment',async({page,request})=>{
  await reset(request,{env:{VENICE_API_KEY:'env-synthetic'}});
  const {form,block,status}=await openRole(page,request);
  await form.locator('[name="provider"]').selectOption('venice');
  await expect(status).toHaveText('Ключ задано змінною середовища.');
  const name=form.locator('[name="key_env"]');
  await name.evaluate(el=>{el.closest('details').open=true});
  await name.fill('MY_OTHER_KEY');
  await expect(status).toHaveText('Ключ не задано.');
  await name.fill('not a name');
  await expect(status).toHaveText('Назва змінної з ключем має складатися з великих латинських літер, цифр і підкреслень.');
  await expect(block.locator('.provider-key-input')).toBeDisabled();
  await name.fill('VENICE_API_KEY');
  await expect(status).toHaveText('Ключ задано змінною середовища.');
  await block.locator('.provider-key-input').fill(VALUE);
  await block.locator('button',{hasText:'Зберегти ключ'}).click();
  await expect(status).toHaveText('Ключ збережено. Ключ задано змінною середовища; збережений у сховищі не використовується.');
});

test('a machine without a credential store says so and disables saving',async({page,request})=>{
  await reset(request,{available:false});
  const {form,block,status}=await openRole(page,request);
  await form.locator('[name="provider"]').selectOption('openrouter');
  await expect(status).toHaveText('Сховище ключів недоступне; задайте ключ змінною середовища.');
  await expect(block.locator('.provider-key-input')).toBeDisabled();
  await expect(block.locator('button',{hasText:'Зберегти ключ'})).toBeDisabled();
});

test('evaluator connection has the same key block',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('evaluator');
  else await page.locator('[data-settings-nav="evaluator"]').click();
  const section=page.locator('#evaluator-settings');
  await section.locator('[name$="provider"]').first().selectOption('venice');
  await expect(section.locator('.provider-key-status').first()).toHaveText('Ключ не задано.');
});
