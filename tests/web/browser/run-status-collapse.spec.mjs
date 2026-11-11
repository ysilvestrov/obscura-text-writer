import {test,expect} from '../../../frontend/browser-test.mjs';

// R20-WORKSPACE: the run line above the editor is one summary line; details open on click, a failure opens by itself.
test('a finished run collapses to one line and opens its details on click',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  const response=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:fixture.scene_id,mode:'edit_loop'}}});
  const id=(await response.json()).id;
  await page.route(`**/api/runs/${id}`,async route=>{const response=await route.fetch(),data=await response.json();data.run.warning='Synthetic collapsed warning';await route.fulfill({response,json:data})});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const status=page.locator('#run-status'),summary=status.locator('.run-summary');
  await expect(summary).toContainText('synthetic-no-changes');await expect(summary.locator('.run-summary-mark')).toHaveText('⚠');
  await expect(summary).toHaveAttribute('aria-expanded','false');
  await expect(status.getByText('Synthetic collapsed warning')).toBeHidden();
  await summary.click();
  await expect(summary).toHaveAttribute('aria-expanded','true');
  await expect(status.getByText('Synthetic collapsed warning')).toBeVisible();
  await summary.click();
  await expect(status.getByText('Synthetic collapsed warning')).toBeHidden();
  await page.unrouteAll({behavior:'ignoreErrors'});
});

test('a running run with many long models keeps the mark and the timer on the summary line',async({page,request},testInfo)=>{
  const f=await(await request.post('/test-impact')).json();
  const long=n=>({provider:'synthetic-provider-with-a-long-name',model:`synthetic-model-${n}-with-a-very-long-identifier`});
  const run={id:'collapse-running-run',story_id:f.story_id,state:'running',warning:'Synthetic running warning',created_at:new Date(Date.now()-5000).toISOString(),cursor:0,tasks:[{stage:'impact_part',phase:'check',scene_id:f.scene_id}],request:{mode:'impact',stage:null},impact:{protocol:2},
    planned_telemetry:{roles:{planner:long(1),writer:long(2),editor:long(3),memory:long(4)},evaluator:long(5)}};
  await page.route(`**/api/stories/${f.story_id}/runs`,route=>route.fulfill({json:{runs:[run]}}));
  await page.route('**/api/runs/collapse-running-run',route=>route.fulfill({json:{run,attempts:[],partial:''}}));
  const sse=[{seq:1,type:'stage_finished',data:{attempt_id:'a1',state:'completed',usage:{prompt_tokens:3596,completion_tokens:3035,cost:{usd:0.0021,diem:0}}}},{seq:2,type:'stage_finished',data:{attempt_id:'a2',state:'completed',usage:{prompt_tokens:10,cost:{usd:0.003,diem:0}}}}].map(e=>`data: ${JSON.stringify(e)}\n\n`).join('');
  await page.route('**/api/runs/collapse-running-run/events',route=>route.fulfill({status:200,headers:{'content-type':'text/event-stream'},body:sse}));
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  const status=page.locator('#run-status'),summary=status.locator('.run-summary'),mark=summary.locator('.run-summary-mark'),elapsed=status.locator('.run-elapsed');
  await expect(elapsed).not.toBeEmpty({timeout:5000});
  await expect(mark).toBeVisible();
  const box=await status.boundingBox(),markBox=await mark.boundingBox(),summaryBox=await summary.boundingBox(),elapsedBox=await elapsed.boundingBox();
  expect(markBox.x+markBox.width).toBeLessThanOrEqual(box.x+box.width+1);
  expect(elapsedBox.width).toBeGreaterThan(20);expect(elapsedBox.x+elapsedBox.width).toBeLessThanOrEqual(box.x+box.width+1);
  // Buttons have a touch-size min-height, so compare the timer's middle with the summary's box, not the tops.
  const elapsedMiddle=elapsedBox.y+elapsedBox.height/2;
  expect(elapsedMiddle).toBeGreaterThan(summaryBox.y);expect(elapsedMiddle).toBeLessThan(summaryBox.y+summaryBox.height);
  expect(box.height).toBeLessThan(summaryBox.height*1.6);
  const cost=summary.locator('.run-summary-cost');
  await expect(cost).toHaveText('$0.0051 / $0.0030');
  await expect(cost).toHaveAttribute('title',/prompt_tokens.*10/);
  await expect(status).not.toContainText('prompt_tokens');
  await status.screenshot({path:testInfo.outputPath('run-status.png')});
  await page.unrouteAll({behavior:'ignoreErrors'});
});

test('a failed run shows its error at once and can be collapsed',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();
  const run={id:'collapse-failed-run',story_id:f.story_id,state:'failed',error:'Synthetic collapse failure',created_at:new Date().toISOString(),cursor:0,tasks:[{stage:'impact_part',phase:'check',scene_id:f.scene_id}],request:{mode:'impact',stage:null},impact:{protocol:2}};
  await page.route(`**/api/stories/${f.story_id}/runs`,route=>route.fulfill({json:{runs:[run]}}));
  await page.route('**/api/runs/collapse-failed-run',route=>route.fulfill({json:{run,attempts:[],partial:''}}));
  await page.route('**/api/runs/collapse-failed-run/readiness',route=>route.fulfill({json:{ready:false,reason:'Synthetic not ready'}}));
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  const status=page.locator('#run-status'),summary=status.locator('.run-summary');
  await expect(status.getByText('Synthetic collapse failure')).toBeVisible();
  await expect(summary).toHaveAttribute('aria-expanded','true');
  await expect(summary).not.toContainText('⚠');
  await summary.click();
  await expect(status.getByText('Synthetic collapse failure')).toBeHidden();
  await page.unrouteAll({behavior:'ignoreErrors'});
});
