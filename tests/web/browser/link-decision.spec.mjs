import {test,expect} from '../../../frontend/browser-test.mjs';

// VALID-LINKS-S08 in the browser: an unchecked brief and prose of the open scene offer the author's approval.
test.use({locale:'uk-UA'});

test('the author approves the brief and the prose of a scene',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Маяк'}})).json();
  let scene=await(await request.post(`/api/stories/${story.id}/scenes`,{data:{title:'Ранок'}})).json();
  const brief={objective:'Світло на воді',beats:['Маяк'],constraints:[],proposed_changes:[]};
  let saved=await request.post(`/api/scenes/${scene.id}/brief`,{data:{text:JSON.stringify(brief),expected_revision:scene.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  scene=(await saved.json()).scene;
  saved=await request.post(`/api/scenes/${scene.id}/prose`,{data:{text:'Ранок: світло на воді.',expected_revision:scene.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  await page.goto(`/stories/${story.id}?scene=${scene.id}&material=prose`);
  const panel=page.locator('#link-attention');
  await expect(panel).toContainText('Завдання не підтверджено');
  await expect(panel).toContainText('Проза не підтверджена');
  await panel.getByRole('button',{name:'Затвердити завдання'}).click();
  await expect(panel).not.toContainText('Завдання не підтверджено');
  await panel.getByRole('button',{name:'Затвердити відповідність'}).click();
  await expect(panel).toBeHidden();
  const view=await(await request.get(`/api/stories/${story.id}`)).json();
  expect(view.material_status[scene.id].links.brief.source).toBe('author');
  expect(view.material_status[scene.id].links.prose.source).toBe('author');
});
