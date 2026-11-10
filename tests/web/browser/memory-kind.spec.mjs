import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

// MEMORY-SELECT-S08: the memory table's Type column marks an entry for selection; a core slot has no control.
test('memory kind is saved at once and slots stay core',async({page,request})=>{
  const fixture=await(await request.post('/test-core-review')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.first_scene_id}&material=memory`);
  const table=page.locator('#memory-view table.memory-table');
  const thread=table.locator('tbody tr').filter({hasText:'Хто стукав?'});
  await expect(thread).toBeVisible();
  await expect(table.locator('tbody tr').filter({hasText:'Халат'})).toContainText('Ядро (слот)');
  const select=thread.getByRole('combobox',{name:'Тип запису «Хто стукав?»'});
  await expect(select).toHaveValue('');
  await select.selectOption('core');
  await expect(select).toBeEnabled();
  await expect.poll(async()=>Object.values((await(await request.get(`/api/stories/${fixture.story_id}`)).json()).story.memory_kind_overrides)).toEqual(['core']);
  await page.reload();
  await expect(table.locator('tbody tr').filter({hasText:'Хто стукав?'}).getByRole('combobox')).toHaveValue('core');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`docs/images/memory-kind-${test.info().project.name}.png`,fullPage:true});
});
