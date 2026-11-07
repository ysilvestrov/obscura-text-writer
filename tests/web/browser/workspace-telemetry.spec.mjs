import {test,expect} from '../../../frontend/browser-test.mjs';

test('draft displays editor and planned calls before starting',async({page,request},testInfo)=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const telemetry=page.locator('#workspace-telemetry');
  await expect(telemetry).toHaveText(/^(local \/ synthetic-no-changes · up to 5 calls|local \/ synthetic-no-changes · до 5 викл\.)$/);
  await expect(telemetry).not.toContainText('⚠');
  await page.locator('[data-ui-locale="uk"]').click();await expect(telemetry).toHaveText('local / synthetic-no-changes · до 5 викл.');
  await page.locator('[data-ui-locale="en"]').click();await expect(telemetry).toHaveText('local / synthetic-no-changes · up to 5 calls');
  await page.locator('#edit-pass-limit').evaluate(el=>{el.value='3';el.dispatchEvent(new Event('input',{bubbles:true}))});
  await expect(telemetry).toHaveText('local / synthetic-no-changes · up to 3 calls');
  await page.locator('#workspace-primary').focus();
  await expect(page.locator('#workspace-telemetry-details')).toBeVisible();
  await page.screenshot({path:testInfo.outputPath('telemetry.png')});
  await page.locator('[data-mode="memory"]').click();
  await expect(telemetry).toBeHidden();
});

test('legacy run with no saved plan is explicitly unknown',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  const response=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:fixture.scene_id,mode:'edit_loop'}}});
  const id=(await response.json()).id;
  await page.route(`**/api/runs/${id}`,async route=>{const response=await route.fetch(),data=await response.json();data.run.planned_telemetry=null;await route.fulfill({response,json:data})});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#run-status')).toContainText(/невідомо|unknown/i);
});

test('sidebar retains the planned model after reload',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  await page.locator('#workspace-primary').click();
  await expect(page.locator('#run-status')).toContainText('synthetic-no-changes');
  await page.reload();
  await expect(page.locator('#run-status')).toContainText('synthetic-no-changes');
});

test('keyboard can open telemetry when the primary action is disabled',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#workspace-telemetry')).toContainText('synthetic-no-changes');
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  await page.evaluate(()=>{document.querySelector('#workspace-primary').disabled=true});
  await page.locator('#workspace-telemetry').focus();
  await expect(page.locator('#workspace-telemetry-details')).toBeVisible();
});

for(const [mode,stage,role] of [['plan','brief','planner'],['brief','draft','writer'],['draft','edit_loop','editor'],['prose','memory','memory']]){
  test(`${mode} shows its model and warning before a single-click start`,async({page,request})=>{
    const fixture=await(await request.post('/test-editor-no-changes')).json();let calls=0,dialogs=0;
    await page.route('**/api/stories/*/readiness*',async route=>{const response=await route.fetch(),data=await response.json();data.operations[stage]={...data.operations[stage],ready:true,roles:{[role]:{provider:'local',model:`synthetic-${role}`}},calls:1,warnings:['Synthetic warning']};await route.fulfill({response,json:data})});
    await page.route('**/api/runs',async route=>{if(route.request().method()!=='POST')return route.continue();calls++;await route.fulfill({status:400,json:{detail:'Synthetic stop'}})});
    page.on('dialog',async dialog=>{dialogs++;await dialog.dismiss()});
    await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=${mode}`);
    const telemetry=page.locator('#workspace-telemetry');await expect(telemetry).toContainText(`synthetic-${role}`);await expect(telemetry).toContainText('⚠');
    await telemetry.focus();await expect(page.locator('#workspace-telemetry-details')).toContainText('Synthetic warning');
    await expect(page.locator('#workspace-primary')).toBeEnabled();await page.locator('#workspace-primary').click();await expect.poll(()=>calls).toBe(1);expect(dialogs).toBe(0);
  });
}

test('primary readiness requests only its operation and expands on demand',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  const operations=[];
  page.on('request',req=>{if(req.url().includes('/readiness?'))operations.push(new URL(req.url()).searchParams.get('operation'))});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  expect(operations).toContain('edit_loop');
  expect(operations).not.toContain(null);
  await page.locator('details.workspace-extra > summary').click();
  await expect.poll(()=>operations.includes(null)).toBe(true);
});

test('changing modes while readiness is pending does not overlap or show stale telemetry',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  let release,started;const blocked=new Promise(resolve=>release=resolve),entered=new Promise(resolve=>started=resolve);
  let inflight=0,peak=0,held=false;
  await page.route('**/api/stories/*/readiness*',async route=>{
    inflight++;peak=Math.max(peak,inflight);
    try{
      if(!held&&new URL(route.request().url()).searchParams.get('operation')==='edit_loop'){held=true;started();await blocked}
      const response=await route.fetch();await route.fulfill({response});
    }finally{inflight--}
  });
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await entered;
  await page.locator('[data-mode="plan"]').click();
  release();
  await expect(page.locator('#workspace-telemetry')).not.toContainText('synthetic-no-changes');
  await expect.poll(()=>inflight).toBe(0);
  expect(peak).toBe(1);
});
