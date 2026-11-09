import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

async function open(page,request){
  const fixture=await(await request.post('/test-core-review')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=memory`);
  const panel=page.locator('#memory-view .core-review');
  await expect(panel.locator('.core-review-row').first()).toBeVisible();
  return {fixture,panel};
}
const row=(panel,text)=>panel.locator('.core-review-row').filter({hasText:text});
const changes=panel=>panel.locator('section.core-review-group');
const quiet=panel=>panel.locator('details.core-review-quiet');

test('changes are expanded, unchanged rows collapsed, confirm without edits',async({page,request})=>{
  const {fixture,panel}=await open(page,request);
  await expect(changes(panel).locator('.core-review-row')).toHaveCount(3);
  await expect(row(changes(panel),'Анна · одяг')).toContainText('було: Халат');
  await expect(row(changes(panel),'Анна · одяг')).toContainText('стало: Пальто');
  await expect(row(changes(panel),'Анна · при собі')).toContainText('Причина: Ключ більше не згадано');
  await expect(row(changes(panel),'Хто стукав?')).toContainText('Розв’язка: Стукав сусід');
  await expect(quiet(panel)).not.toHaveAttribute('open','');
  await expect(row(quiet(panel),'Анна · місце')).toBeHidden();
  await expect(panel.locator('.core-review-state')).toHaveText('Не підтверджено');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`docs/images/core-review-${test.info().project.name}.png`,fullPage:true});
  const before=(await(await request.get(`/api/scenes/${fixture.scene_id}/core-review`)).json()).memory_version_id;
  await panel.getByRole('button',{name:'Підтвердити',exact:true}).click();
  await expect(panel.locator('.core-review-state')).toContainText('Підтверджено');
  const after=await(await request.get(`/api/scenes/${fixture.scene_id}/core-review`)).json();
  expect(after.memory_version_id).toBe(before);expect(after.confirmation.by).toBe('author');
});

test('keep previous on an unknown slot creates a version where the slot is unchanged',async({page,request})=>{
  const {fixture,panel}=await open(page,request);
  const before=(await(await request.get(`/api/scenes/${fixture.scene_id}/core-review`)).json()).memory_version_id;
  await row(panel,'Анна · при собі').getByRole('button',{name:'Лишити попереднє'}).click();
  await expect(row(panel,'Анна · при собі')).toContainText('Чернетка: лишити попереднє');
  await panel.getByRole('button',{name:'Підтвердити з правками (1)'}).click();
  await expect(panel.locator('.core-review-state')).toContainText('Підтверджено');
  await quiet(panel).locator('summary').click();
  await expect(row(quiet(panel),'Анна · при собі')).toContainText('стало: Ключ');
  await expect(row(quiet(panel),'Анна · при собі')).toContainText('без змін');
  const after=await(await request.get(`/api/scenes/${fixture.scene_id}/core-review`)).json();
  expect(after.memory_version_id).not.toBe(before);
  expect(after.slots.find(s=>s.slot==='carried')).toMatchObject({status:'unchanged',after:'Ключ'});
  // Without the model answer of the new version keep is no longer offered.
  await expect(row(panel,'Анна · одяг').getByRole('button',{name:'Лишити попереднє'})).toBeDisabled();
  await expect(row(panel,'Хто стукав?').getByRole('button',{name:'Вписати…'})).toHaveCount(0);
});

test('write in with a quote from an earlier scene',async({page,request})=>{
  const {panel}=await open(page,request);
  const clothing=row(panel,'Анна · одяг');
  await clothing.getByRole('button',{name:'Вписати…'}).click();
  const entry=clothing.locator('.core-review-entry');
  await expect(entry.getByLabel('Сцена цитати')).toHaveValue(await entry.getByLabel('Сцена цитати').locator('option').nth(1).getAttribute('value'));
  await expect(entry.getByRole('radio',{name:'Стукав сусід.'})).toBeVisible();
  await expect(entry.getByRole('radio',{name:'Без цитати'})).toBeChecked();
  await expect(entry.locator('.core-review-hint')).toBeVisible();
  await entry.getByLabel('Сцена цитати').selectOption({label:'1. Ранок'});
  await expect(entry.getByRole('radio',{name:'Анна в халаті.'})).toBeVisible();
  await entry.getByLabel('Пошук фрагмента').fill('ключ');
  await expect(entry.getByRole('radio',{name:'Анна в халаті.'})).toHaveCount(0);
  await expect(entry.getByRole('radio',{name:'У кишені ключ.'})).toBeVisible();
  await entry.getByLabel('Пошук фрагмента').fill('');
  await entry.getByRole('radio',{name:'Анна в халаті.'}).check();
  await expect(entry.locator('.core-review-hint')).toBeHidden();
  await entry.getByLabel('Значення').fill('Халат під пальтом');
  await entry.getByRole('button',{name:'Застосувати'}).click();
  await expect(clothing).toContainText('Чернетка: Халат під пальтом — цитата зі сцени 1: «Анна в халаті.»');
  await panel.getByRole('button',{name:'Підтвердити з правками (1)'}).click();
  await expect(panel.locator('.core-review-state')).toContainText('Підтверджено');
  await expect(row(changes(panel),'Анна · одяг')).toContainText('стало: Халат під пальтом');
  await expect(row(changes(panel),'Анна · одяг')).toContainText('запис автора');
  await expect(row(changes(panel),'Анна · одяг')).not.toContainText('читачеві невідомо');
});

test('write in without a quote is unknown to the reader; cancel keeps the draft',async({page,request})=>{
  const {panel}=await open(page,request);
  const clothing=row(panel,'Анна · одяг');
  await clothing.getByRole('button',{name:'Вписати…'}).click();
  await clothing.locator('.core-review-entry').getByLabel('Значення').fill('Не те');
  await clothing.getByRole('button',{name:'Скасувати'}).click();
  await expect(clothing.locator('.core-review-entry')).toHaveCount(0);
  await expect(clothing.locator('.core-review-draft')).toHaveCount(0);
  await expect(panel.getByRole('button',{name:'Підтвердити',exact:true})).toBeVisible();
  await clothing.getByRole('button',{name:'Вписати…'}).click();
  const entry=clothing.locator('.core-review-entry');
  await entry.getByLabel('Сцена цитати').selectOption({label:'1. Ранок'});
  await expect(entry.getByRole('radio',{name:'Анна в халаті.'})).toBeVisible();
  await entry.getByRole('radio',{name:'Без цитати'}).check();
  await entry.getByLabel('Значення').fill('Плащ');
  await entry.getByRole('button',{name:'Застосувати'}).click();
  await expect(clothing).toContainText('Чернетка: Плащ — без цитати, читачеві невідомо');
  await panel.getByRole('button',{name:'Підтвердити з правками (1)'}).click();
  await expect(panel.locator('.core-review-state')).toContainText('Підтверджено');
  await expect(row(changes(panel),'Анна · одяг')).toContainText('стало: Плащ');
  await expect(row(changes(panel),'Анна · одяг').locator('.core-review-reader-unknown')).toHaveText('читачеві невідомо');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('refreshing the table asks before dropping a core draft',async({page,request})=>{
  const {panel}=await open(page,request);
  const clothing=row(panel,'Анна · одяг');
  await clothing.getByRole('button',{name:'Вписати…'}).click();
  await clothing.locator('.core-review-entry').getByLabel('Значення').fill('Шарф');
  await clothing.getByRole('button',{name:'Застосувати'}).click();
  await expect(clothing.locator('.core-review-draft')).toContainText('Шарф');
  await page.locator('#memory-view').getByRole('button',{name:'Оновити таблицю'}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toBeVisible();
  await dialog.locator('.app-dialog-actions button').first().click();
  await expect(dialog).toHaveCount(0);
  await expect(row(panel,'Анна · одяг').locator('.core-review-draft')).toContainText('Шарф');
  await expect(panel.getByRole('button',{name:'Підтвердити з правками (1)'})).toBeVisible();
  await page.locator('#memory-view').getByRole('button',{name:'Оновити таблицю'}).click();
  await dialog.locator('.app-dialog-actions button').last().click();
  await expect(dialog).toHaveCount(0);
  await expect(panel.locator('.core-review-draft')).toHaveCount(0);
  await expect(panel.getByRole('button',{name:'Підтвердити',exact:true})).toBeVisible();
});

test('a conflict shows the server message and reloads the panel',async({page,request})=>{
  const {fixture,panel}=await open(page,request);
  const current=await(await request.get(`/api/scenes/${fixture.scene_id}/core-review`)).json();
  // Another tab confirms with an edit first: the head this panel loaded is no longer current.
  const saved=await request.post(`/api/scenes/${fixture.scene_id}/core-review`,{data:{expected_revision:current.revision,memory_version_id:current.memory_version_id,
    edits:[{kind:'slot',character_id:'A',slot:'location',action:'set',text:'Кухня'}]}});
  expect(saved.ok()).toBeTruthy();
  await row(panel,'Анна · при собі').getByRole('button',{name:'Лишити попереднє'}).click();
  await panel.getByRole('button',{name:'Підтвердити з правками (1)'}).click();
  await expect(page.locator('#notice')).toContainText('Пам’ять сцени вже змінилась');
  await expect(row(changes(panel),'Анна · місце')).toContainText('стало: Кухня');
  await expect(panel.locator('.core-review-draft')).toHaveCount(0);
});
