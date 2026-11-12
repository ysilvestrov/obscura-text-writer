import assert from 'node:assert/strict';
const {t,setLocale,getLocale,uiText,uiAttr,chooseLocale}=await import('../../../src/storygen/web/static/i18n.js');
assert.equal(chooseLocale(null,'en-US,en;q=0.8'),'en');assert.equal(chooseLocale('uk','en'),'uk');
assert.equal(chooseLocale(null,'en;q=0,fr'),'uk');assert.equal(t('ui.save'),'Зберегти');
const output={textContent:'',isConnected:true},input={value:'Авторський текст',selectionStart:3,selectionEnd:7,placeholder:'',isConnected:true};
uiText(output,'textContent',()=>t('ui.save'));uiText(input,'placeholder',()=>t('ui.save'));
await setLocale('en');assert.equal(getLocale(),'en');assert.equal(output.textContent,'Save');assert.equal(input.placeholder,'Save');
assert.equal(input.value,'Авторський текст');assert.equal(input.selectionStart,3);assert.equal(input.selectionEnd,7);
await setLocale('uk');assert.equal(output.textContent,'Зберегти');
console.log('Locale and live presentation bindings passed');

const {diagnostic,msg,labelEntries}=await import('../../../src/storygen/web/static/i18n.js');
const labels={get name(){return t('ui.save')}};let tuple=labelEntries(labels)[0][1];
uiText(output,'textContent',()=>tuple);await setLocale('en');assert.equal(output.textContent,'Save');
assert.equal(diagnostic('Матеріал не знайдено'),'Material not found');
assert.equal(diagnostic('<b>Рукопис автора</b>'),'<b>Рукопис автора</b>');

const catalog=(await import('../../../src/storygen/web/static/i18n.json',{with:{type:'json'}})).default;
const paramKey=Object.keys(catalog.uk).find(k=>catalog.uk[k]==='{p0}: {p1} · було: {p2}; тепер: {p3}');
assert.ok(t(paramKey,{p0:'{p1}',p1:'<author>',p2:'a',p3:'b'}).startsWith('{p1}: <author>'));
assert.ok(diagnostic('Некоректні дані: Спершу додайте план сцени 7').includes('7'));

const row={isConnected:true,children:[],get firstChild(){return this.children[0]},get textContent(){return this.children.map(n=>n.nodeValue).join('')},set textContent(value){this.children=[{nodeType:3,nodeValue:value,parentNode:this}]}};
uiText(row,'textContent',()=>t('ui.save'));const badge={nodeType:1,nodeValue:'badge',parentNode:row};row.children.push(badge);
await setLocale('uk');assert.ok(row.children.includes(badge),'a label update must preserve appended status children');
assert.equal(row.firstChild.nodeValue,'Зберегти');

const streamed={textContent:'',isConnected:true};
uiText(streamed,'textContent',()=>t('ui.save'));
uiText(streamed,'textContent',()=>(''));
streamed.textContent+='Авторський потік <b>буквально</b>';
setLocale('en');
assert.equal(streamed.textContent,'Авторський потік <b>буквально</b>');
setLocale('uk');
assert.equal(diagnostic('Некоректні дані: unknown cause'),'Некоректні дані: unknown cause');
assert.equal(diagnostic('Editor error: unknown cause'),'Помилка редактора: unknown cause');
setLocale('en');
assert.equal(diagnostic('Некоректні дані: unknown cause'),'Invalid data: unknown cause');

const {live}=await import('../../../src/storygen/web/static/i18n.js');
const {createTextEditor}=await import('../../../src/storygen/web/static/text-editor.js');
const {primaryAction}=await import('../../../src/storygen/web/static/workspace-state.js');
const {compactBudgetText}=await import('../../../src/storygen/web/static/workspace-links.js');
const state={mode:'draft',dirty:true,scene:{heads:{prose:'p'}}};
uiText(output,'textContent',()=>primaryAction(state).label);
input.addEventListener=()=>{};
createTextEditor(input).placeholder(live(()=>t('ui.save')));
const englishAction=output.textContent;
setLocale('uk');assert.notEqual(output.textContent,englishAction);assert.equal(input.placeholder,'Зберегти');
const budget={textContent:'',isConnected:true};
uiText(budget,'textContent',()=>compactBudgetText({exposure_nanos:125000000,limit_nanos:1000000000}));
const ukBudget=budget.textContent;setLocale('en');assert.notEqual(budget.textContent,ukBudget);
assert.ok(budget.textContent.includes('$0.125'));

// MODEL-003/MODEL-004: server block texts reach English UI users in English, role name included.
setLocale('en');
assert.equal(diagnostic('Модель «x/y» не має позначки Uncensored, а рейтинг цього запиту 2/0/0. Підтвердьте в налаштуваннях ролі «Письменник», що погоджуєтеся на виклики цієї моделі для дорослого змісту, або виберіть іншу модель.'),
  'Model “x/y” has no Uncensored mark, and this request is rated 2/0/0. Confirm in the “Writer” role settings that you agree to calls of this model for adult content, or choose another model.');
assert.equal(diagnostic('Некоректні дані: Модель «a/b» уже відмовила ролі «Пам’ять» через зміст на запиті з рейтингом 1/0/0. Виклики з рейтингом 2/0/0 заблоковано: зніміть позначку в налаштуваннях ролі або виберіть іншу модель.'),
  'Invalid data: Model “a/b” already refused the “Memory” role on content for a request rated 1/0/0. Calls rated 2/0/0 are blocked: clear the mark in the role settings or choose another model.');
setLocale('uk');
console.log('Model policy block diagnostics passed');
