import assert from 'node:assert/strict';
const {diagnostic,setLocale}=await import('../../../src/storygen/web/static/i18n.js');
await setLocale('en');
const cases=[
  ['«Dawn», заголовок: таблицю пропущено разом з текстом у ній','«Dawn», heading: the table was skipped together with the text in it'],
  ['«Dawn», абзац 3: виноску не імпортовано','«Dawn», paragraph 3: the footnote was not imported'],
  ['Фрагмент «Dusk», заголовок: виноску не імпортовано','Fragment «Dusk», heading: the footnote was not imported'],
  ['Фрагмент «Dusk», абзац 2: малюнок або фігуру не імпортовано','Fragment «Dusk», paragraph 2: the picture or shape was not imported'],
  ['Абзац 7 документа: вбудований об’єкт не імпортовано','Paragraph 7 of the document: the embedded object was not imported'],
  ['«Dawn»: «Dawn», абзац 1: малюнок або фігуру не імпортовано','«Dawn»: «Dawn», paragraph 1: the picture or shape was not imported'],
  ['«Dawn»: Примітки понад межі не імпортовано: 3.','«Dawn»: Comments over the limit were not imported: 3.'],
  ['«Dawn»: сцену не імпортовано — прозу сцени змінено після зведення','«Dawn»: the scene was not imported — the scene prose was changed after the summary'],
  ['«Dawn»: сцену не імпортовано — Твір змінився після зведення; перегляньте його ще раз','«Dawn»: the scene was not imported — The story changed after the summary; review the file again'],
  ['«Dawn»: сцену не імпортовано — disk error','«Dawn»: the scene was not imported — disk error'],
  ['Файл має бути до 20 MiB','The file must be at most 20 MiB'],
];
for(const [uk,en] of cases)assert.equal(diagnostic(uk),en);
console.log('Editor import diagnostics passed');
