import assert from 'node:assert/strict';
const {diagnostic,setLocale}=await import('../../../src/storygen/web/static/i18n.js');
await setLocale('en');
const cases=[
  ['Розділ 3 (2): довгий абзац без меж','Розділ 3 (2): a long paragraph with no breaks'],
  ["Глава: вступ: Частина сцени не вміститься в ліміти пам'яті навіть після поділу",'Глава: вступ: A part of the scene will not fit the memory limits even after splitting'],
  ['Розділ 3: щось інше','Розділ 3: щось інше'],
  ['Коментарі Word не імпортуються: 3','Word comments are not imported: 3'],
];
for(const [uk,en] of cases)assert.equal(diagnostic(uk),en);
await setLocale('uk');
assert.equal(diagnostic('Розділ 3 (2): a long paragraph with no breaks'),'Розділ 3 (2): довгий абзац без меж');
console.log('Manuscript import diagnostics passed');
