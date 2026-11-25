import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

// The open menu stays inside the window and no container clips it: every item is on top.
async function inside(page,menu){
  const box=await menu.boundingBox(),{width,height}=page.viewportSize();
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width);
  expect(box.y).toBeGreaterThanOrEqual(0);expect(box.y+box.height).toBeLessThanOrEqual(height);
  for(const item of await menu.getByRole('menuitemradio').all())
    expect(await item.evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2));})).toBe(true);
}

// MEMORY-SELECT-S08: the memory table's Type column marks an entry for selection; a core slot has no control.
test('memory kind is saved at once and slots stay core',async({page,request})=>{
  const fixture=await(await request.post('/test-core-review')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.first_scene_id}&material=memory`);
  const table=page.locator('#memory-view table.memory-table');
  const thread=table.locator('tbody tr').filter({hasText:'Хто стукав?'});
  await expect(thread).toBeVisible();
  await expect(table.locator('tbody tr').filter({hasText:'Халат'})).toContainText('Ядро (слот)');
  // The closed control is a compact icon button; the legend above the table names the icons.
  await expect(page.locator('#memory-view .memory-kind-legend')).toContainText('Тип запису:');
  await expect(page.locator('#memory-view .memory-kind-legend')).toContainText('Атмосфера');
  const button=thread.getByRole('button',{name:'Тип запису «Хто стукав?»: Авто',exact:true});
  await expect(button).toHaveAttribute('aria-haspopup','menu');
  expect((await button.boundingBox()).width).toBeLessThanOrEqual(64);
  const menu=thread.getByRole('menu');
  await expect(menu).toBeHidden();
  await button.click();
  await expect(menu).toBeVisible();
  await expect(menu.getByRole('menuitemradio')).toHaveText(['Авто','Ядро','Атмосфера'].map(name=>new RegExp(`^${name}`)));
  await expect(menu.getByRole('menuitemradio',{name:/^Авто/})).toHaveAttribute('aria-checked','true');
  await inside(page,menu);
  await page.screenshot({path:`docs/images/memory-kind-menu-${test.info().project.name}.png`});
  await menu.getByRole('menuitemradio',{name:/^Ядро/}).click();
  await expect(menu).toBeHidden();
  await expect.poll(async()=>Object.values((await(await request.get(`/api/stories/${fixture.story_id}`)).json()).story.memory_kind_overrides)).toEqual(['core']);
  const core=thread.getByRole('button',{name:'Тип запису «Хто стукав?»: Ядро',exact:true});
  await expect(core).toBeFocused();
  // Keyboard: arrows open the menu and move, Escape closes it without a change, Enter picks.
  await core.press('ArrowDown');
  await expect(menu.getByRole('menuitemradio',{name:/^Ядро/})).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();await expect(core).toBeFocused();
  await core.press('ArrowDown');await page.keyboard.press('ArrowDown');
  await expect(menu.getByRole('menuitemradio',{name:/^Атмосфера/})).toBeFocused();
  await page.keyboard.press('Enter');
  await expect.poll(async()=>Object.values((await(await request.get(`/api/stories/${fixture.story_id}`)).json()).story.memory_kind_overrides)).toEqual(['atmosphere']);
  await expect(thread.getByRole('button',{name:'Тип запису «Хто стукав?»: Атмосфера',exact:true})).toBeFocused();
  // A click outside closes the menu.
  await thread.getByRole('button',{name:/Атмосфера$/}).click();await expect(menu).toBeVisible();
  await page.locator('#memory-view .memory-kind-legend').click();await expect(menu).toBeHidden();
  await page.reload();
  await expect(table.locator('tbody tr').filter({hasText:'Хто стукав?'}).getByRole('button',{name:/Атмосфера$/})).toBeVisible();
  // In focus mode Escape closes only the open menu; focus mode stays until the next Escape.
  const workspace=page.locator('#workspace');
  await page.locator('#workspace-focus').click();await expect(workspace).toHaveClass(/focus-mode/);
  await thread.getByRole('button',{name:/Атмосфера$/}).click();await expect(menu).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();await expect(workspace).toHaveClass(/focus-mode/);
  await page.keyboard.press('Escape');await expect(workspace).not.toHaveClass(/focus-mode/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`docs/images/memory-kind-${test.info().project.name}.png`,fullPage:true});
});

// MEMORY-SELECT-S08: a window just above the phone layout, and a short one, keep the menu whole and usable.
test('memory kind menu stays inside a narrow or short window',async({page,request})=>{
  const fixture=await(await request.post('/test-core-review')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.first_scene_id}&material=memory`);
  const thread=page.locator('#memory-view table.memory-table tbody tr').filter({hasText:'Хто стукав?'});
  const button=thread.getByRole('button',{name:'Тип запису «Хто стукав?»: Авто',exact:true}),menu=thread.getByRole('menu');
  for(const size of [{width:760,height:900},{width:760,height:240}]){
    // Centred in a short window the menu fits neither below nor above the button: it is moved into the window.
    // The keyboard opens it without the scroll a pointer click would add before pressing.
    await page.setViewportSize(size);await button.evaluate(el=>{el.scrollIntoView({block:'center'});el.focus({preventScroll:true});});
    await page.keyboard.press('ArrowDown');await expect(menu).toBeVisible();
    await inside(page,menu);
    await page.keyboard.press('Escape');await expect(menu).toBeHidden();
  }
});
