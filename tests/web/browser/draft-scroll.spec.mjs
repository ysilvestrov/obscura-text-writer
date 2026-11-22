import {test,expect} from '../../../frontend/browser-test.mjs';

// WORKSPACE-PRIMARY-SCROLL: after the primary action creates a draft, the author sees the top of the draft, not the page below it.
test('creating a draft from the end of a long brief opens the draft from its top',async({page,request})=>{
  const fixture=await(await request.post('/test-draft-writer')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=brief`);
  const primary=page.locator('#workspace-primary');
  await expect(primary).toBeEnabled();
  // The author reads the long brief to its end and starts the draft from the sticky toolbar.
  await page.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));
  expect(await page.evaluate(()=>scrollY)).toBeGreaterThan(0);
  await primary.click();
  await expect(page.locator('#workspace-material')).toContainText('Абзац 60');
  const where=()=>page.evaluate(()=>({
    toolbar:document.querySelector('.workspace-sticky').getBoundingClientRect().bottom,
    material:document.querySelector('#workspace-material').getBoundingClientRect().top,
    first:[...document.querySelectorAll('#workspace-material p')].find(p=>p.textContent.startsWith('Абзац 1:'))?.getBoundingClientRect().top,
    height:innerHeight}));
  // The material starts right under the sticky tabs and toolbar: not hidden by them and not below the window.
  await expect.poll(async()=>{const w=await where();return Math.abs(w.material-w.toolbar)<=1&&w.first>=w.toolbar&&w.first<w.height}).toBe(true);
});

test('a draft whose top is already in view does not move the page',async({page,request})=>{
  const fixture=await(await request.post('/test-draft-writer')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=brief`);
  const primary=page.locator('#workspace-primary');
  await expect(primary).toBeEnabled();
  await page.evaluate(()=>scrollTo(0,0));
  await primary.click();
  await expect(page.locator('#workspace-material')).toContainText('Абзац 60');
  await expect.poll(()=>page.evaluate(()=>document.activeElement?.closest?.('#workspace-material')!==null)).toBe(true);
  expect(await page.evaluate(()=>scrollY)).toBe(0);
});
