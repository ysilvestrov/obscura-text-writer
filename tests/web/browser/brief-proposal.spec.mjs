import {test,expect} from '../../../frontend/browser-test.mjs';

test('pending brief is visible and needs explicit acceptance before draft',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);
  await page.locator('#mode-tabs [data-mode="brief"]').click();
  await expect.poll(async()=>{try{return JSON.parse(await page.locator('#editor').inputValue()).objective;}catch{return null;}}).toBe('Нове завдання для перегляду');
  await expect(page.locator('#workspace-primary')).toBeDisabled();
  await expect(page.locator('#brief-proposal')).toContainText('Уточнити емоційний акцент.');
  await page.locator('#brief-proposal').screenshot({path:`../artifacts/brief-proposal/${test.info().project.name}.png`});
  await page.locator('#save-text').click();await expect(page.locator('#save-state')).toHaveText(/Збережено|Saved/);
  const saved=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();expect(saved.scene.heads.brief).toBe(f.old_brief_id);
  const accept=page.locator('#brief-proposal button');await expect(accept).toBeEnabled();await accept.click();
  await expect(page.locator('#brief-proposal')).toBeHidden();
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  expect((await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief).not.toBe(f.old_brief_id);
});


test('manual changes must be saved before accepting the exact displayed version',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  const accept=page.locator('#brief-proposal button');await expect(accept).toBeEnabled();
  const brief=JSON.parse(await page.locator('#editor').inputValue());brief.objective='Авторське уточнення';await page.locator('#editor').fill(JSON.stringify(brief));
  await expect(accept).toBeDisabled();await page.locator('#save-text').click();await expect(page.locator('#save-state')).toHaveText(/Збережено|Saved/);
  const versions=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();const latest=versions.versions.filter(v=>v.kind==='brief').at(-1);expect(latest.id).not.toBe(f.proposal_id);
  await expect(accept).toBeEnabled();await accept.click();await expect(page.locator('#brief-proposal')).toBeHidden();
  expect((await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief).toBe(latest.id);
});

test('accept conflict keeps the reviewed text and never selects another version',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  const accept=page.locator('#brief-proposal button');await expect(accept).toBeEnabled();const original=await page.locator('#editor').inputValue();
  const data=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  const changed=await request.patch(`/api/scenes/${f.scene_id}`,{data:{story_id:f.story_id,expected_revision:data.scene.revision,title:'Інша назва'}});expect(changed.ok()).toBeTruthy();
  await accept.click();await expect(page.locator('#notice')).toHaveAttribute('data-kind','error');
  await expect(page.locator('#editor')).toHaveValue(original);
  expect((await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief).toBe(f.old_brief_id);
});


test('new proposal refreshes an open brief without changing the head or overwriting typing',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();let showNew=false;
  await page.route(`**/api/scenes/${f.scene_id}/versions`,async route=>{
    const response=await route.fetch(),data=await response.json();if(!showNew)data.versions=data.versions.filter(v=>v.id!==f.proposal_id);
    await route.fulfill({response,json:data});
  });
  await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  await expect.poll(async()=>{try{return JSON.parse(await page.locator('#editor').inputValue()).objective;}catch{return null;}}).toBe('Старе завдання');
  showNew=true;await page.evaluate(async()=>{const editor=await import('/static/editor.js');await editor.refresh();});
  await expect.poll(async()=>{try{return JSON.parse(await page.locator('#editor').inputValue()).objective;}catch{return null;}}).toBe('Нове завдання для перегляду');
  expect((await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief).toBe(f.old_brief_id);
  await page.locator('#editor').fill('Незбережена авторська правка');
  await page.evaluate(async()=>{const editor=await import('/static/editor.js');await editor.refresh();});
  await expect(page.locator('#editor')).toHaveValue('Незбережена авторська правка');
  await page.unrouteAll({behavior:'wait'});
});

test('acceptance follows refreshed run state without switching tabs',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  const accept=page.locator('#brief-proposal button');await expect(accept).toBeEnabled();
  await page.evaluate(async()=>{const {state}=await import('/static/editor.js');state.workspaceRuns=[{state:'running'}];document.dispatchEvent(new CustomEvent('workspace-run-state'))});
  await expect(accept).toBeDisabled();
  await page.evaluate(async()=>{const {state}=await import('/static/editor.js');state.workspaceRuns=[{state:'needs_review'}];document.dispatchEvent(new CustomEvent('workspace-readiness'))});
  await expect(accept).toBeEnabled();
});

test('saving edits to an accepted brief requires acceptance before starting a draft',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  await page.locator('#brief-proposal button').click();await expect(page.locator('#brief-proposal')).toBeHidden();
  const accepted=(await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief;
  const brief=JSON.parse(await page.locator('#editor').inputValue());brief.objective='Нова авторська правка';await page.locator('#editor').fill(JSON.stringify(brief));
  let posts=0;await page.route('**/api/runs',async route=>{if(route.request().method()==='POST'){posts++;await route.fulfill({status:400,json:{detail:'Unexpected draft'}})}else await route.continue()});
  await page.locator('#workspace-primary').click();
  await expect(page.locator('#brief-proposal')).toBeVisible();await expect(page.locator('#brief-proposal button')).toBeEnabled();
  await expect(page.locator('#workspace-primary')).toBeDisabled();expect(posts).toBe(0);
  expect((await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief).toBe(accepted);
});
