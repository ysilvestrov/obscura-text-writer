import {test,expect} from '../../../frontend/browser-test.mjs';

// MEMORY-MERGE-S04 in the browser: the merge window in the memory panel of a meeting scene (neutral example: arcs A and B
// dress Anna differently before they meet in scene 4).
test.use({locale:'uk-UA'});
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();

async function openMerge(page,request){
  const fixture=await(await request.post('/test-memory-merge')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_ids[3]}&material=memory`);
  const section=page.locator('#memory-merge');
  await expect(section).toBeVisible();
  return {fixture,section};
}

// A no-op structure save: the story revision moves on, nothing else changes.
async function bumpRevision(request,storyId){
  const data=await view(request,storyId);
  const parts=data.book_structure.parts.map(part=>({id:part.id,title:part.title,arcs:part.arcs.map(arc=>({id:arc.id,title:arc.title,protagonist_id:arc.protagonist_id||null}))}));
  const scene_arcs=Object.fromEntries(data.scenes.map(scene=>[scene.id,scene.arc_ids.length===1?scene.arc_ids[0]:scene.arc_ids]));
  const put=await request.put(`/api/stories/${storyId}/structure`,{data:{expected_revision:data.story.revision,parts,scene_arcs}});
  expect(put.ok(),await put.text()).toBeTruthy();
}

test('the merge window lists heads and the conflict',async({page,request})=>{
  const {section}=await openMerge(page,request);
  await expect(section.locator('h3')).toHaveText('Злиття пам’яті');
  await expect(section.locator('.memory-merge-state')).toHaveText('Не підтверджено');
  await expect(section.locator('.memory-merge-heads li')).toHaveText(['2. Сцена 2 — A','3. Сцена 3 — B']);
  const row=section.locator('.memory-merge-row');
  await expect(row).toHaveCount(1);
  await expect(row.getByRole('radio')).toHaveCount(3);
  await expect(row).toContainText('Анна в куртці');
  await expect(row).toContainText('Анна в плащі');
  await expect(section.getByRole('button',{name:'Підтвердити злиття'})).toBeDisabled();
  await expect(section).toContainText('Виберіть значення для кожного конфлікту');
});

test('choosing a head confirms the merge',async({page,request})=>{
  const {fixture,section}=await openMerge(page,request);
  await section.getByRole('radio',{name:/Анна в плащі/}).check();
  await section.getByRole('button',{name:'Підтвердити злиття'}).click();
  await expect(page.locator('#notice')).toContainText('Злиття пам’яті підтверджено');
  await expect(section.locator('.memory-merge-state')).toHaveText('Актуальне');
  await expect(section.getByRole('radio',{name:/Анна в плащі/})).toBeChecked();
  const merge=await(await request.get(`/api/stories/${fixture.story_id}/memory-merges?scene_id=${fixture.scene_ids[3]}`)).json();
  expect(merge.carried).toEqual({'slot:c1:clothing':{choice:fixture.scene_ids[2]}});
});

test('an author value is saved',async({page,request})=>{
  const {fixture,section}=await openMerge(page,request);
  await section.getByRole('radio',{name:'Своє значення'}).check();
  await section.getByRole('textbox',{name:'Своє значення'}).fill('Анна в шубі');
  await section.getByRole('button',{name:'Підтвердити злиття'}).click();
  await expect(page.locator('#notice')).toContainText('Злиття пам’яті підтверджено');
  const merge=await(await request.get(`/api/stories/${fixture.story_id}/memory-merges?scene_id=${fixture.scene_ids[3]}`)).json();
  expect(merge.carried).toEqual({'slot:c1:clothing':{choice:'author',text:'Анна в шубі'}});
});

test('a revision conflict keeps the choice',async({page,request})=>{
  const {fixture,section}=await openMerge(page,request);
  await section.getByRole('radio',{name:/Анна в куртці/}).check();
  await bumpRevision(request,fixture.story_id);
  await section.getByRole('button',{name:'Підтвердити злиття'}).click();
  await expect(page.locator('#notice')).toContainText('перегляньте злиття заново');
  await expect(section.getByRole('radio',{name:/Анна в куртці/})).toBeChecked();
  await section.getByRole('button',{name:'Підтвердити злиття'}).click();
  await expect(page.locator('#notice')).toContainText('Злиття пам’яті підтверджено');
});

test('a scene waiting for the merge links to it',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-merge')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_ids[3]}&material=plan`);
  const open=page.locator('#memory-merge-open');
  await expect(open).toHaveText('Відкрити злиття пам’яті');
  await open.click();
  await expect(page.locator('#memory-merge')).toBeVisible();
  await expect(page.locator('#memory-merge')).toBeFocused();
});
