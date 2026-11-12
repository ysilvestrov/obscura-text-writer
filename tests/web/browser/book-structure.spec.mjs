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
