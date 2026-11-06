import {test,expect} from '../../../frontend/browser-test.mjs';
async function writing(page){
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
}

test('writing target saves, resets, switches language and detects remote target conflict',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}/settings`);await writing(page);
  const target=page.locator('#profile-form [name="target_words"]');
  await expect(target).toHaveValue('7000');
  await target.fill('25000');await page.locator('[data-ui-locale="uk"]').click();
  await expect(target).toHaveValue('25000');
  await page.locator('#settings-save').click();await expect(page.locator('#settings-save')).toBeDisabled();
  await expect.poll(async()=>(await(await request.get(`/api/stories/${f.story_id}/settings`)).json()).story.target_words).toBe(25000);
  await target.fill('26000');page.once('dialog',d=>d.accept());await page.locator('#settings-reset').click();await expect(target).toHaveValue('25000');
  await page.screenshot({path:`docs/images/writing-target-${test.info().project.name}.png`,fullPage:true});
  await target.fill('27000');
  const latest=await(await request.get(`/api/stories/${f.story_id}/settings`)).json();
  await request.put(`/api/stories/${f.story_id}/settings`,{data:{expected_revision:latest.story.revision,target_words:28000}});
  await page.locator('#settings-save').click();await expect(page.locator('#settings-save-status')).toContainText(/змін|changed/i);
  await expect(target).toHaveValue('27000');
});
