import {test,expect} from '../../../frontend/browser-test.mjs';

for(const mode of ['brief','draft'])test(`save and run dispatches after editing ${mode}`,async({page,request})=>{
  const f=await(await request.post('/test-editor-no-changes')).json();
  if(mode==='brief'){
    const data=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
    const saved=await request.post(`/api/scenes/${f.scene_id}/brief`,{data:{expected_revision:data.scene.revision,text:JSON.stringify({objective:'Спостерігати зорі.',beats:['Вечір у парку.'],constraints:[],proposed_changes:[]})}});
    expect(saved.ok()).toBe(true);
  }
  const dispatches=[];let confirmations=0;
  await page.route('**/api/runs',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    dispatches.push(route.request().postDataJSON());
    await route.fulfill({status:503,json:{detail:'Synthetic dispatch captured; no model called'}});
  });
  page.on('dialog',async dialog=>{confirmations++;await dialog.accept();});
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=${mode}`);
  await expect(page.locator(`#mode-tabs [data-mode="${mode}"]`)).toHaveAttribute('aria-selected','true');
  const text=mode==='brief'?JSON.stringify({objective:'Помітити нове сузір’я.',beats:['Вечір у парку.'],constraints:[],proposed_changes:[]}):'Лєра побачила нове сузір’я.';
  const editor=page.locator(mode==='brief'?'#editor':'.rich-text-surface .ProseMirror');
  await expect(editor).toBeEditable();await editor.fill(text);
  await expect(page.locator('#save-state')).toContainText(/Незбережені|Unsaved/);
  await page.locator('#workspace-primary').click();
  await expect.poll(()=>dispatches.length).toBe(1);
  expect(confirmations).toBe(1);
  const data=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  const saved=await(await request.get(`/api/versions/${data.scene.heads[mode]}`)).json();
  if(mode==='brief')expect(JSON.parse(saved.text)).toEqual(JSON.parse(text));else expect(saved.text).toBe(text);
  expect(dispatches[0].request.mode).toBe(mode==='brief'?'stage':'edit_loop');
  if(mode==='draft')expect(dispatches[0].request.editor_source_version_id).toBe(saved.version.id);
});
