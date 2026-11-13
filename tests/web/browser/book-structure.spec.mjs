import {test,expect} from '../../../frontend/browser-test.mjs';

// BOOK-STRUCTURE-S06 and BUILD-EDITION-001-S08 in the browser: grouped scene list, arc field, structure panel, banner.
test.use({locale:'uk-UA'});
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();

async function structuredBook(request){
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  for(const title of ['Друга сцена','Третя сцена']){
    expect((await request.post(`/api/stories/${story_id}/scenes`,{data:{title}})).ok()).toBeTruthy();
  }
  const data=await view(request,story_id);
  const [first,second,third]=data.scenes.map(scene=>scene.id);
  const parts=[{id:'p1',title:'Дім',arcs:[{id:'a1',title:'Ранок'},{id:'a2',title:''}]},{id:'p2',title:'',arcs:[{id:'b1',title:''}]}];
  const put=await request.put(`/api/stories/${story_id}/structure`,{data:{expected_revision:data.story.revision,parts,scene_arcs:{[first]:'a1',[second]:'a1',[third]:'b1'}}});
  expect(put.ok(),await put.text()).toBeTruthy();
  return {story_id,scene_id:first,second};
}

test('a structured book groups the scene list by parts and arcs',async({page,request})=>{
  const {story_id,scene_id}=await structuredBook(request);
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  if(test.info().project.name==='mobile'){
    const groups=page.locator('#scene-select-mobile optgroup');
    await expect(groups).toHaveCount(2);
    expect(await groups.evaluateAll(items=>items.map(item=>item.label))).toEqual(['Дім','Частина 2']);
  }else{
    await expect(page.locator('#scene-list .scene-group-part')).toHaveText(['Дім','Частина 2']);
    await expect(page.locator('#scene-list .scene-group-arc')).toHaveText(['Ранок']);
    await expect(page.locator('#scene-list .scene-item')).toHaveCount(3);
    await expect(page.locator('#scene-list .scene-item.active')).toContainText('1.');
  }
});

test('a flat book shows no group headings',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await expect(page.locator('#scene-list .scene-item').first()).toBeAttached();
  await expect(page.locator('#scene-list .scene-group')).toHaveCount(0);
  await expect(page.locator('#scene-select-mobile optgroup')).toHaveCount(0);
});

test('the arc field in scene parameters saves at once',async({page,request})=>{
  const {story_id,second}=await structuredBook(request);
  await page.goto(`/stories/${story_id}`);
  if(test.info().project.name==='mobile')await page.locator('#scene-select-mobile').selectOption(second);
  else await page.locator('#scene-list .scene-item').nth(1).click();
  await expect(page.locator('#scene-title')).toHaveText('Друга сцена');
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  const select=page.locator('#scene-arc select[name="arc_id"]');
  await expect(select).toHaveValue('a1');
  await select.selectOption('a2');
  await expect(page.locator('#notice')).toContainText('Арку сцени змінено');
  expect((await view(request,story_id)).scenes.find(scene=>scene.id===second).arc_id).toBe('a2');
});

test('meeting arcs are ticked and saved',async({page,request})=>{
  // MEMORY-MERGE harness: the other arcs of the scene's part are checkboxes; a tick saves arc_ids at once.
  const {story_id,second}=await structuredBook(request);
  await page.goto(`/stories/${story_id}`);
  if(test.info().project.name==='mobile')await page.locator('#scene-select-mobile').selectOption(second);
  else await page.locator('#scene-list .scene-item').nth(1).click();
  await expect(page.locator('#scene-title')).toHaveText('Друга сцена');
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  const group=page.getByRole('group',{name:'Сцена зустрічі з арками'});
  await group.getByRole('checkbox',{name:'Арка 2'}).check();
  await expect(page.locator('#notice')).toContainText('Арку сцени змінено');
  expect((await view(request,story_id)).scenes.find(scene=>scene.id===second).arc_ids).toEqual(['a1','a2']);
  await page.reload();
  if(test.info().project.name==='mobile')await page.locator('#scene-select-mobile').selectOption(second);
  else await page.locator('#scene-list .scene-item').nth(1).click();
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  await expect(page.getByRole('group',{name:'Сцена зустрічі з арками'}).getByRole('checkbox',{name:'Арка 2'})).toBeChecked();
  // A main arc of another part ends the meeting: one arc, no checkboxes left.
  await page.locator('#scene-arc select[name="arc_id"]').selectOption('b1');
  await expect.poll(async()=>(await view(request,story_id)).scenes.find(scene=>scene.id===second).arc_ids).toEqual(['b1']);
  await expect(page.getByRole('group',{name:'Сцена зустрічі з арками'})).toHaveCount(0);
});

test('the structure panel renames a part with one save',async({page,request})=>{
  const {story_id}=await structuredBook(request);
  await page.goto(`/stories/${story_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  const panel=page.locator('#book-structure');
  await expect(panel.locator('.book-structure-part')).toHaveCount(2);
  await panel.locator('.book-structure-part').nth(1).locator('.book-structure-row-part input').fill('Дорога');
  await panel.getByRole('button',{name:'Зберегти структуру'}).click();
  await expect(page.locator('#notice')).toContainText('Структуру книги збережено');
  expect((await view(request,story_id)).book_structure.parts.map(part=>part.title)).toEqual(['Дім','Дорога']);
});

test('the structure panel saves an arc protagonist',async({page,request})=>{
  // BOOK-LINEAGE-S04: the arc field lists the cards and «Герой книги»; the choice survives a reload.
  const {story_id}=await structuredBook(request);
  const cards=['Анна','Богдан'].map(name=>({schema_version:2,id:null,name,entries:[{id:null,text:'Опис',availability:'timeless',origin:'author'}]}));
  const saved=await request.put(`/api/stories/${story_id}/characters`,{data:{cards,expected_revision:(await view(request,story_id)).story.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  const bohdan=Object.entries((await view(request,story_id)).character_names).find(([,name])=>name==='Богдан')[0];
  await page.goto(`/stories/${story_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  const field=page.locator('#book-structure').getByRole('combobox',{name:'Протагоніст арки «Арка 1»',exact:true});
  await expect(field.locator('option')).toHaveText(['Герой книги','Анна','Богдан']);
  await field.selectOption({label:'Богдан'});
  await page.locator('#book-structure').getByRole('button',{name:'Зберегти структуру'}).click();
  await expect(page.locator('#notice')).toContainText('Структуру книги збережено');
  const ids=(await view(request,story_id)).book_structure.parts.map(part=>part.arcs.map(arc=>arc.protagonist_id));
  expect(ids).toEqual([[null,null],[bohdan]]);
  await page.reload();
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  await expect(page.locator('#book-structure').getByRole('combobox',{name:'Протагоніст арки «Арка 1»',exact:true})).toHaveValue(bohdan);
});

test.describe('store edition',()=>{
  test.afterEach(async({request})=>{await request.post('/test-build-edition',{data:{edition:'full'}})});
  test('a structured book is read-only and has no structure panel',async({page,request})=>{
    const {story_id,scene_id}=await structuredBook(request);
    await request.post('/test-build-edition',{data:{edition:'store'}});
    await page.goto(`/stories/${story_id}?scene=${scene_id}`);
    await expect(page.locator('#book-readonly')).toHaveText('Ця книга має частини чи арки; у цій збірці вона доступна лише для читання й експорту');
    await page.goto(`/stories/${story_id}/settings`);
    await expect(page.locator('#rating-form')).toBeAttached();
    await expect(page.locator('#book-structure')).toHaveCount(0);
  });
});
