import {test,expect} from '../../../frontend/browser-test.mjs';

// R20-WORKSPACE: the run line above the editor is one summary line; details open on click, a failure opens by itself.
test('a finished run collapses to one line and opens its details on click',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  const response=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:fixture.scene_id,mode:'edit_loop'}}});
  const id=(await response.json()).id;
  await page.route(`**/api/runs/${id}`,async route=>{const response=await route.fetch(),data=await response.json();data.run.warning='Synthetic collapsed warning';await route.fulfill({response,json:data})});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const status=page.locator('#run-status'),summary=status.locator('.run-summary');
  await expect(summary).toContainText('synthetic-no-changes');await expect(summary).toContainText('⚠');
  await expect(summary).toHaveAttribute('aria-expanded','false');
  await expect(status.getByText('Synthetic collapsed warning')).toBeHidden();
  // One summary line with the inline timer: the box stays within about three lines of the status font.
  await expect.poll(()=>status.evaluate(el=>el.getBoundingClientRect().height/parseFloat(getComputedStyle(el).fontSize))).toBeLessThan(4.5);
  await summary.click();
  await expect(summary).toHaveAttribute('aria-expanded','true');
  await expect(status.getByText('Synthetic collapsed warning')).toBeVisible();
  await summary.click();
  await expect(status.getByText('Synthetic collapsed warning')).toBeHidden();
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
