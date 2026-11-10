import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'en-US'});

// STORY-LANGUAGE-S08: the story language is chosen at creation, editable in settings until model material exists,
// a scene can override the prose language, and English prose is not offered for evaluation.
test('story and scene language in the interface',async({page,request})=>{
  await page.goto('/');
  const form=page.locator('#new-story');
  await form.getByLabel('Title').fill(`Pier ${Date.now()}`);
  await form.getByLabel('Story language').selectOption('en');
  await form.getByRole('button').click();
  await expect(page).toHaveURL(/\/stories\//);
  const storyId=page.url().split('/stories/')[1].split(/[?/#]/)[0];
  expect((await(await request.get(`/api/stories/${storyId}`)).json()).story.language).toBe('en');
  await expect(page.locator('a[download="obscura-plan.md"]')).toHaveAttribute('href','/static/templates/story-plan-en.md');

  await request.post(`/api/stories/${storyId}/scenes`,{data:{title:'Arrival',beats:'Scene 1: Arrival\nCharacters: Anna'}});
  await page.goto(`/stories/${storyId}/settings#writing`);
  const language=page.locator('#story-language-form select[name=language]');
  await expect(language).toHaveValue('en');
  await expect(language).toBeEnabled();
  await request.post(`/test-language-lock/${storyId}`);
  await page.reload();
  await expect(language).toBeDisabled();
  await expect(page.locator('#story-language-help')).toContainText('is fixed');

  await page.goto(`/stories/${storyId}`);
  // Scene settings live in a collapsed panel: open it the way the author does.
  await page.locator('#scene-settings').locator('xpath=ancestor::details[1]/summary').click();
  const prose=page.locator('#scene-settings select[name=prose_language]');
  await expect(prose).toHaveValue('story');
  await expect(prose.locator('option[value=story]')).toHaveText('As the story (English)');
  const evaluate=page.locator('#evaluation-panel button',{hasText:'Evaluate scene'});
  await expect(evaluate).toBeDisabled();
  await expect(evaluate).toHaveAttribute('title',/English scenes are not evaluated/);
  await prose.selectOption('uk');
  await page.locator('#scene-settings').getByRole('button',{name:'Save'}).first().click();
  await expect.poll(async()=>(await(await request.get(`/api/stories/${storyId}`)).json()).scenes[0].prose_language).toBe('uk');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
