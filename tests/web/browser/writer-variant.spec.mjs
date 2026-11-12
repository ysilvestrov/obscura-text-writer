// MODEL-001 S02 (UI): optional writer model for scenes rated 0–1, with its own consent block.
import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
// Consent is global for role + endpoint + model: every test uses its own model IDs.
const unique=name=>`${name}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;
const option=(id,uncensored=null)=>({id,name:id,context_tokens:65536,max_output_tokens:4096,tariff:null,uncensored,privacy:'private',tee:false,supports_schema:null});
const LABEL='Я погоджуюся, що ця модель отримуватиме запити для творів із рейтингом вище 0, і відповідаю за наслідки.';
const TOGGLE='Окрема модель для сцен рівня 0–1';

async function openWriter(page,storyId,catalog){
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:catalog}}));
  await page.goto(`/stories/${storyId}/settings`);await page.locator('[data-settings-role=writer]').click();
  const form=page.locator('form[data-role=writer]'),block=form.locator('[data-writer-variant]');
  return {form,block,toggle:block.getByLabel(TOGGLE),fields:block.locator('.writer-variant-fields'),picker:block.locator('.model-picker')};
}
const story=async request=>(await(await request.post('/test-fixture')).json()).story_id;
const save=async page=>{
  const put=page.waitForResponse(r=>r.request().method()==='PUT'&&/\/api\/stories\/[^/]+\/settings$/.test(r.url()));
  await page.locator('#settings-save').click();const response=await put;expect(response.ok()).toBeTruthy();return response.request().postDataJSON();
};

test('the variant is optional, saved with its limits, restored after reload and cleared when unchecked',async({page,request})=>{
  const id=unique('var-unc'),storyId=await story(request);
  let view=await openWriter(page,storyId,[option(id,true)]);
  await expect(view.form).toContainText('Основна модель пише всі сцени, включно з рівнем 2.');
  await expect(view.block).toContainText('Сцени, де хоч одна вісь рейтингу дорівнює 2, завжди пише основна модель.');
  await expect(view.toggle).not.toBeChecked();await expect(view.fields).toBeHidden();
  await view.toggle.check();await expect(view.fields).toBeVisible();
  await view.fields.locator('[name=variant_provider]').selectOption('venice');
  await expect(view.fields.locator('[name=variant_base_url]')).toHaveValue('https://api.venice.ai/api/v1');
  await view.fields.getByRole('button',{name:'Отримати список моделей'}).click();
  await view.picker.locator(`tbody tr[data-model-id="${id}"]`).click();
  await expect(view.fields.locator('[name=variant_model]')).toHaveValue(id);
  // The main model is not touched by the variant picker.
  await expect(view.form.locator('[name=model]')).toHaveValue('synthetic-rewrite');
  for(const[name,value]of [['variant_context_tokens','32768'],['variant_max_output_tokens','4096'],['variant_max_input_chars','60000'],['variant_temperature','0.6'],['variant_timeout','240']])
    await view.fields.locator(`[name=${name}]`).fill(value);
  const body=await save(page);
  expect(body.settings.low_rating_variant).toMatchObject({provider:{provider:'venice',model:id},context_tokens:32768,max_output_tokens:4096,max_input_chars:60000,temperature:0.6,timeout:240});
  await page.reload();
  view=await openWriter(page,storyId,[option(id,true)]);
  await expect(view.toggle).toBeChecked();await expect(view.fields).toBeVisible();
  await expect(view.fields.locator('[name=variant_model]')).toHaveValue(id);
  await expect(view.fields.locator('[name=variant_provider]')).toHaveValue('venice');
  await expect(view.fields.locator('[name=variant_context_tokens]')).toHaveValue('32768');
  await expect(view.fields.locator('[name=variant_temperature]')).toHaveValue('0.6');
  await expect(view.fields.locator('[name=variant_timeout]')).toHaveValue('240');
  await view.toggle.uncheck();await expect(view.fields).toBeHidden();
  expect((await save(page)).settings.low_rating_variant).toBeNull();
  const stored=await(await request.get(`/api/stories/${storyId}/settings`)).json();
  expect(stored.roles.writer.low_rating_variant).toBeNull();
  expect(stored.roles.writer.provider.model).toBe('synthetic-rewrite');
});

test('the variant model without Uncensored gets its own consent block for role writer',async({page,request})=>{
  const plain=unique('var-plain'),free=unique('var-free');
  const view=await openWriter(page,await story(request),[option(plain,false),option(free,true)]);
  await view.toggle.check();
  await view.fields.locator('[name=variant_provider]').selectOption('venice');
  await view.fields.getByRole('button',{name:'Отримати список моделей'}).click();
  await view.picker.locator(`tbody tr[data-model-id="${plain}"]`).click();
  const consent=view.picker.getByLabel(LABEL);
  await expect(consent).toBeVisible();await expect(consent).toBeEnabled();await expect(consent).not.toBeChecked();
  const put=page.waitForRequest(r=>r.method()==='PUT'&&r.url().endsWith('/api/model-policy/consent'));
  await consent.check();
  expect((await put).postDataJSON()).toMatchObject({role:'writer',provider:'venice',model:plain});
  await expect(consent).toBeChecked();
  await view.picker.locator(`tbody tr[data-model-id="${free}"]`).click();
  await expect(view.picker.locator('[data-model-consent]')).toBeHidden();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
