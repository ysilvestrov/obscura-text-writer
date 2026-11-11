import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();
const rating=(sexual,violence,themes)=>({sexual,violence,themes});
// The scene panel lives in a collapsed details block on both layouts; opening it is not layout specific.
const openPanel=async page=>{
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  await expect(page.locator('#scene-rating')).toBeVisible();
};
const axisSelects=form=>['sexual','violence','themes'].map(axis=>form.locator(`select[name="${axis}"]`));

test('author overrides the scene rating and returns to the story rating',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  const story=(await view(request,story_id)).story;
  const set=await request.put(`/api/stories/${story_id}/content-rating`,{data:{content_rating:rating(1,0,0),expected_revision:story.revision}});
  expect(set.ok()).toBeTruthy();
  const source=async()=>(await view(request,story_id)).scene_ratings[scene_id];
  expect(await source()).toEqual({effective:rating(1,0,0),source:'story'});

  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await openPanel(page);
  const form=page.locator('#scene-rating');
  const [sexual,violence,themes]=axisSelects(form);
  await expect(form.locator('legend')).toHaveText('Віковий рейтинг сцени');
  await expect(form.getByLabel('Як у твору (сексуальний зміст 1, насильство 0, жорсткі теми 0)')).toBeChecked();
  for(const select of [sexual,violence,themes])await expect(select).toBeDisabled();

  await form.getByLabel('Власний рейтинг').check();
  await expect(sexual).toBeEnabled();
  await sexual.selectOption('0');await violence.selectOption('2');await themes.selectOption('0');
  await form.getByRole('button',{name:'Зберегти рейтинг сцени'}).click();
  await expect(page.locator('#notice')).toContainText('Рейтинг сцени збережено');
  expect(await source()).toEqual({effective:rating(0,2,0),source:'scene'});

  await page.reload();
  await openPanel(page);
  await expect(form.getByLabel('Власний рейтинг')).toBeChecked();
  await expect(sexual).toHaveValue('0');await expect(violence).toHaveValue('2');await expect(themes).toHaveValue('0');

  const bodies=[];
  page.on('request',req=>{if(req.method()==='PUT'&&req.url().endsWith('/content-rating'))bodies.push(req.postDataJSON())});
  await form.getByLabel(/^Як у твору/).check();
  await form.getByRole('button',{name:'Зберегти рейтинг сцени'}).click();
  await expect(page.locator('#notice')).toContainText('Рейтинг сцени збережено');
  expect(bodies).toHaveLength(1);
  expect(bodies[0].content_rating).toBeNull();
  expect(await source()).toEqual({effective:rating(1,0,0),source:'story'});
  await expect(form.getByLabel(/^Як у твору/)).toBeChecked();

  // Stale revision: the rating written outside the page must survive a save from the stale page.
  const scene=(await view(request,story_id)).scenes.find(s=>s.id===scene_id);
  const outside=await request.put(`/api/scenes/${scene_id}/content-rating`,{data:{story_id,content_rating:rating(0,0,2),expected_revision:scene.revision}});
  expect(outside.ok()).toBeTruthy();
  await form.getByLabel('Власний рейтинг').check();
  await violence.selectOption('1');
  await form.getByRole('button',{name:'Зберегти рейтинг сцени'}).click();
  await expect(page.locator('#notice')).toHaveAttribute('data-kind','error');
  expect(await source()).toEqual({effective:rating(0,0,2),source:'scene'});
});

const selectScene=async(page,index)=>{
  if(test.info().project.name==='mobile'){
    const option=await page.locator('#scene-select-mobile option').nth(index).getAttribute('value');await page.locator('#scene-select-mobile').selectOption(option);
  }else await page.locator('#scene-list .scene-item').nth(index).click();
};
const selectedSceneId=page=>page.evaluate(async()=>(await import('/static/editor.js')).state.scene?.id??null);

test('a slow scene rating save does not pull the selection back to its scene',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  const second=await(await request.post(`/api/stories/${story_id}/scenes`,{data:{title:'Друга сцена',beats:'Прогулянка.'}})).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await expect(page.locator('#scene-list .scene-item')).toHaveCount(2);
  await openPanel(page);
  let release;const held=new Promise(resolve=>{release=resolve});
  await page.route('**/content-rating',async route=>{await held;await route.continue()});
  const form=page.locator('#scene-rating');
  await form.getByLabel('Власний рейтинг').check();
  await form.getByRole('button',{name:'Зберегти рейтинг сцени'}).click();
  await selectScene(page,1);
  await expect.poll(()=>selectedSceneId(page)).toBe(second.id);
  release();
  await expect(page.locator('#notice')).toContainText('Рейтинг сцени збережено');
  expect(await selectedSceneId(page)).toBe(second.id);
  expect((await view(request,story_id)).scene_ratings[scene_id].source).toBe('scene');
});

test('the rating form disappears when no scene is selected',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await openPanel(page);
  await page.evaluate(async()=>{
    const {state}=await import('/static/editor.js');
    state.scene=null;document.dispatchEvent(new CustomEvent('story-refreshed'));
  });
  await expect(page.locator('#scene-rating')).toHaveCount(0);
});

test('scene of an unrated story shows "not set" and can still get its own rating',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-unrated')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await openPanel(page);
  const form=page.locator('#scene-rating');
  await expect(form.getByLabel('Як у твору (не задано)')).toBeChecked();
  const [sexual,violence,themes]=axisSelects(form);
  await form.getByLabel('Власний рейтинг').check();
  await sexual.selectOption('1');await violence.selectOption('0');await themes.selectOption('2');
  await form.getByRole('button',{name:'Зберегти рейтинг сцени'}).click();
  await expect(page.locator('#notice')).toContainText('Рейтинг сцени збережено');
  expect((await view(request,story_id)).scene_ratings[scene_id]).toEqual({effective:rating(1,0,2),source:'scene'});
});

test('scene rating axes explain themselves in help tips',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await openPanel(page);
  const form=page.locator('#scene-rating');
  await form.getByLabel('Власний рейтинг').check();
  for(const [axis,name,phrase] of [['sexual','Сексуальний зміст','вік від 18 років'],['violence','Насильство','бійки, поранення'],['themes','Жорсткі теми','«насильство» — що показано з тілом']]){
    await expect(form.getByLabel(name,{exact:true})).toHaveAttribute('name',axis);
    const tip=form.locator(`#scene-rating-help-${axis}`);
    await expect(tip).toBeHidden();
    await form.locator(`button[aria-describedby="scene-rating-help-${axis}"]`).focus();
    await expect(tip).toBeVisible();
    await expect(tip).toContainText(phrase);
    await expect(tip).toContainText(/0 — .+1 — .+2 — /);
  }
});
