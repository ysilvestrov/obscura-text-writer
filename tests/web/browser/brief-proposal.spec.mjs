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

test('editing an accepted brief keeps acceptance when starting a draft',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  await page.locator('#brief-proposal button').click();await expect(page.locator('#brief-proposal')).toBeHidden();
  const accepted=(await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief;
  const brief=JSON.parse(await page.locator('#editor').inputValue());brief.objective='Нова авторська правка';await page.locator('#editor').fill(JSON.stringify(brief));
  let posts=0;await page.route('**/api/runs',async route=>{if(route.request().method()==='POST'){posts++;await route.fulfill({status:400,json:{detail:'Unexpected draft'}})}else await route.continue()});
  await page.locator('#workspace-primary').click();
  await expect.poll(()=>posts).toBe(1);await expect(page.locator('#brief-proposal')).toBeHidden();
  const data=(await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json());
  expect(data.scene.heads.brief).not.toBe(accepted);
  const saved=(await(await request.get(`/api/versions/${data.scene.heads.brief}`)).json());expect(JSON.parse(saved.text).objective).toBe('Нова авторська правка');
});


test('manual save of an accepted brief keeps acceptance',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  await page.locator('#brief-proposal button').click();await expect(page.locator('#brief-proposal')).toBeHidden();
  const before=(await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief;
  const brief=JSON.parse(await page.locator('#editor').inputValue());brief.objective='Власне уточнення';await page.locator('#editor').fill(JSON.stringify(brief));await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toHaveText(/Збережено|Saved/);await expect(page.locator('#brief-proposal')).toBeHidden();
  const head=(await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.brief;expect(head).not.toBe(before);
  const saved=(await(await request.get(`/api/versions/${head}`)).json());expect(JSON.parse(saved.text).objective).toBe('Власне уточнення');
});

test('typing during accepted brief save keeps acceptance on the next save',async({page,request})=>{
  const f=await(await request.post('/test-brief-proposal')).json();await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="brief"]').click();
  await page.locator('#brief-proposal button').click();await expect(page.locator('#brief-proposal')).toBeHidden();
  const editor=page.locator('#editor'),brief=JSON.parse(await editor.inputValue());brief.objective='Перша правка';await editor.fill(JSON.stringify(brief));
  let release,started;const waiting=new Promise(resolve=>started=resolve),gate=new Promise(resolve=>release=resolve);
  await page.route(`**/api/scenes/${f.scene_id}/brief`,async route=>{const response=await route.fetch();started();await gate;await route.fulfill({response})},{times:1});
  await page.locator('#save-text').click();await waiting;
  brief.objective='Правка під час збереження';await editor.fill(JSON.stringify(brief));release();
  await expect(page.locator('#save-state')).toContainText(/Незбережені|[Uu]nsaved/);
  await expect(page.locator('#brief-proposal')).toBeHidden();
  await page.locator('#save-text').click();await expect(page.locator('#save-state')).toHaveText(/Збережено|Saved/);
  await expect(page.locator('#brief-proposal')).toBeHidden();
  const versions=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();const saved=await(await request.get(`/api/versions/${versions.scene.heads.brief}`)).json();
  expect(JSON.parse(saved.text).objective).toBe('Правка під час збереження');
});

