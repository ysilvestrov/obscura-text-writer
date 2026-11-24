import {test,expect} from '../../../frontend/browser-test.mjs';

// R16-SUGGEST-S07 in the browser: a book that does not fit the writer's window whole names the scenes the model reads
// before the run, «Запропонувати» stays enabled, and the proposal says what was read (neutral text, synthetic writer).
test.use({locale:'uk-UA'});

test('a long book shows the scene selection and gets a card proposal',async({page,request})=>{
  const fixture=await(await request.post('/test-long-book')).json();
  await page.goto(`/stories/${fixture.story_id}/publication`);
  const line=page.locator('#publication-suggestion-selection');
  await expect(line).toBeVisible();
  await expect(line).toHaveText('Книжка не вміщається у вікно моделі повністю: модель прочитає ідею твору й сцени 1–2 із 3 (до «Шторм»). '
    +'Межа — ліміт символів письменника; його можна підняти в налаштуваннях моделей.');
  const suggest=page.locator('#publication-suggest');
  await expect(suggest).toBeEnabled();
  await suggest.click();
  const proposal=page.locator('#publication-suggestions details').first();
  await expect(proposal).toBeAttached({timeout:15000});
  await proposal.locator('summary').click();
  await expect(proposal).toContainText('Прочитано: ідея й сцени 1–2 із 3');
  await expect(proposal).toContainText('Доглядачка маяка шукає брата.');
  const runs=(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  expect(runs.at(-1).request.expected_selection).toMatch(/^[a-f0-9]{64}$/);
});
