import {test,expect} from '../../../frontend/browser-test.mjs';

// DATA-010-S02 in the browser: one confirmed press in the story menu accepts all waiting prose (neutral text).
test.use({locale:'uk-UA'});

test('the story menu accepts all waiting prose as the author\'s',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Маяк'}})).json();
  for(const title of ['Ранок','Вечір']){
    const scene=await(await request.post(`/api/stories/${story.id}/scenes`,{data:{title}})).json();
    const saved=await request.post(`/api/scenes/${scene.id}/prose`,{data:{text:title+': світло на воді.',expected_revision:scene.revision}});
    expect(saved.ok(),await saved.text()).toBeTruthy();
  }
  const view=await(await request.get(`/api/stories/${story.id}`)).json();
  const moved=await request.put(`/api/stories/${story.id}/scene-order`,{data:{scene_ids:view.scenes.map(s=>s.id).reverse(),expected_revision:(view.story??view).revision}});
  expect(moved.ok(),await moved.text()).toBeTruthy();
  await page.goto(`/stories/${story.id}`);
  await page.locator('#story-menu-toggle').click();
  const button=page.locator('#story-menu-accept-prose');
  await expect(button).toBeVisible();
  await expect(button).toHaveText('Прийняти всю прозу як авторську');
  await button.click();
  const dialog=page.locator('dialog[open]');
  await expect(dialog).toContainText('Прийняти прозу 2 сцен як авторську: «Вечір», «Ранок»?');
  await dialog.getByRole('button',{name:'Прийняти прозу'}).click();
  // The menu closes on the click; the server list empties once the acceptance lands.
  await expect.poll(async()=>(await(await request.get(`/api/stories/${story.id}/prose-acceptance`)).json()).scenes).toEqual([]);
  await page.locator('#story-menu-toggle').click();
  await expect(button).toBeHidden();
});
