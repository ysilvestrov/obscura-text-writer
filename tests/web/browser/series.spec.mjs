import {test,expect} from '../../../frontend/browser-test.mjs';

// SERIES-S07 in the browser: the series list, the series screen (variant B), «Нова книга серії», the book settings
// form (neutral book). «Оновити з попередньої книги» needs a finished book: tests/series and the manual procedure.
test.use({locale:'uk-UA'});
// Both projects share one fixture server, so series titles carry the project name.
const name=title=>`${title} ${test.info().project.name}`;
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();

async function seriesWithBook(request,title){
  const {story_id}=await(await request.post('/test-fixture')).json();
  const item=await(await request.post('/api/series',{data:{title}})).json();
  const story=(await view(request,story_id)).story;
  const put=await request.patch(`/api/stories/${story_id}/series`,{data:{series_id:item.id,number:1,expected_revision:story.revision}});
  expect(put.ok(),await put.text()).toBeTruthy();
  return {item,story_id};
}

test('the library links to the series list where a series is created',async({page})=>{
  await page.goto('/');
  await page.getByRole('link',{name:'Серії'}).click();
  await expect(page).toHaveURL(/\/series$/);
  await page.getByLabel('Назва серії').fill(name('Морська сага'));
  await page.getByRole('button',{name:'Створити серію'}).click();
  await expect(page.locator('#series-title')).toHaveText(name('Морська сага'));
});

test('the series screen shows both orders and creates the next book',async({page,request})=>{
  const {item,story_id}=await seriesWithBook(request,name('Сага екрана'));
  await page.goto(`/series/${item.id}`);
  await expect(page.locator('#series-books .series-book')).toHaveCount(1);
  await expect(page.locator('#series-books .series-book').first()).toContainText('перша книга серії');
  await expect(page.locator('#series-axis li')).toHaveCount(1);
  await expect(page.locator('#series-axis li').first()).toContainText('точка відліку');
  await expect(page.locator('#series-delete')).toBeDisabled();
  await page.locator('#series-new-book').click();
  await page.locator('dialog input').fill('Книга 2');
  await page.locator('dialog').getByRole('button',{name:'Підтвердити'}).click();
  await expect(page).toHaveURL(/\/stories\//);
  await expect(page.locator('#story-series')).toContainText(`Серія «${name('Сага екрана')}», книга 2`);
  const books=(await(await request.get(`/api/series/${item.id}`)).json()).books;
  expect(books.map(b=>b.number)).toEqual([1,2]);
  expect(books[0].id).toBe(story_id);
});

test('the book settings put a book into a series',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  await request.post('/api/series',{data:{title:name('Сага налаштувань')}});
  await page.goto(`/stories/${story_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  const form=page.locator('#story-series-form');
  await expect(form).toBeVisible();
  await form.locator('select[name="series_id"]').selectOption({label:name('Сага налаштувань')});
  await form.locator('input[name="number"]').fill('1');
  await form.locator('input[name="start"]').fill('Рік 0, опора 1');
  await form.getByRole('button',{name:'Зберегти'}).click();
  await expect(page.locator('#notice')).toContainText('Серію збережено');
  const series=(await view(request,story_id)).series;
  expect([series.title,series.number,series.start.offset]).toEqual([name('Сага налаштувань'),1,'Рік 0']);
  await expect(form.locator('[data-series-status]')).toContainText('перша книга серії');
});

test('a prequel reviews the facts of later books and saves the marks',async({page,request})=>{
  const {prequel_id}=await(await request.post('/test-series-prequel')).json();
  await page.goto(`/stories/${prequel_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  const form=page.locator('#story-series-form');
  await expect(form.locator('[data-series-status]')).toContainText('Приквел');
  await form.getByRole('button',{name:'Переглянути факти пізніших книг'}).click();
  const dialog=page.locator('#series-facts-dialog');
  await expect(dialog.locator('.series-fact')).toHaveCount(2);
  const clothes=dialog.locator('.series-fact',{hasText:'Халат'});
  await expect(clothes).toContainText('Книга 1');
  await expect(clothes.getByLabel('Майбутнє')).toBeChecked();
  await expect(dialog.getByRole('button',{name:'Зберегти позначки'})).toBeDisabled();
  await clothes.getByLabel('Минуле').check();
  await expect(dialog.locator('[data-facts-changed]')).toHaveText('Змінено: 1');
  await dialog.getByRole('button',{name:'Зберегти позначки'}).click();
  await page.locator('dialog.app-dialog').getByRole('button',{name:'Зберегти позначки'}).click();
  await expect(page.locator('#notice')).toContainText('Позначки збережено');
  const facts=(await(await request.get(`/api/stories/${prequel_id}/series/facts`)).json()).facts;
  expect(facts.map(f=>[f.text,f.decision])).toEqual([['Сусід пішов','future'],['Халат','past']]);
});
