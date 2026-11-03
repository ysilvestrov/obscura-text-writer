import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {loadDocument, serializeDocument, toSourceRange, codepointOffset, utf16Offset, schema}
  from '../../../src/storygen/web/static/rich-editor-engine.js';

const fixtures = JSON.parse(readFileSync(new URL('../../fixtures/markdown-authoring.json', import.meta.url)));
for (const fixture of fixtures) {
  const loaded = loadDocument(fixture.source, fixture.format);
  const result = serializeDocument(loaded.doc, loaded);
  assert.equal(result.source, fixture.source, fixture.name);
  assert.equal(result.content_format, fixture.format);
  for (const segment of loaded.sourceMap.segments) {
    const selected = toSourceRange({from: segment.from, to: segment.to}, loaded.sourceMap);
    assert.equal(selected.source_quote, fixture.source.slice(segment.sourceFrom, segment.sourceTo));
    assert.equal(selected.display_quote, segment.value ?? '\n');
  }
}
const repeated = loadDocument('Вона **знала**. Вона **знала**.', 'markdown');
const selected = toSourceRange({from: 18, to: 23}, repeated.sourceMap);
assert.equal(selected.source_quote, 'знала');
assert.equal(selected.start, 23); // source includes both pairs of Markdown delimiters before this occurrence
assert.equal(selected.display_quote, 'знала');

const unicode = 'а👩🏽‍💻е́';
for (let cp = 0; cp <= [...unicode].length; cp++) {
  assert.equal(codepointOffset(unicode, utf16Offset(unicode, cp)), cp);
}
assert.throws(() => codepointOffset('😀', 1), /surrogate/i);
const escaped = loadDocument('А \\* &amp; &#x1F600; Б', 'markdown');
assert.equal(escaped.doc.textContent, 'А * & 😀 Б');
assert.equal(toSourceRange({from: 3, to: 4}, escaped.sourceMap).source_quote, '\\*');
assert.equal(toSourceRange({from: 5, to: 6}, escaped.sourceMap).source_quote, '&amp;');
assert.equal(toSourceRange({from: 7, to: 9}, escaped.sourceMap).source_quote, '&#x1F600;');

const baseline = loadDocument('Перший.\r\n\r\nДругий &amp; **жирний**.\r\n', 'markdown');
const changed = baseline.doc.copy(schema.nodes.doc.create(null, [
  schema.nodes.paragraph.create(baseline.doc.child(0).attrs, schema.text('Змінений.')),
  baseline.doc.child(1),
]).content);
const saved = serializeDocument(changed, baseline);
assert.equal(saved.source, 'Змінений.\r\n\r\nДругий &amp; **жирний**.\r\n');
const legacy = loadDocument('*літеральне*', 'plain');
const formatted = schema.nodes.doc.create(null, schema.nodes.paragraph.create(
  legacy.doc.firstChild.attrs, schema.text('*літеральне*', [schema.marks.strong.create()]),
));
const formattedSource = serializeDocument(formatted, legacy);
assert.equal(formattedSource.content_format, 'markdown');
assert.equal(loadDocument(formattedSource.source, 'markdown').doc.textContent, '*літеральне*');
assert.equal(loadDocument(formattedSource.source, 'markdown').doc.firstChild.firstChild.marks[0].type.name, 'strong');
const opaque = loadDocument('[Лінк](https://example.org) ![Фото](https://example.org/a.png)', 'markdown');
assert.equal(opaque.doc.firstChild.type.name, 'opaque');
assert.throws(() => toSourceRange({from: 0, to: 1}, opaque.sourceMap), /opaque/i);

// Editing a legacy paragraph must not turn literal syntax elsewhere into formatting.
const oldPlain = loadDocument('Початок.\r\n\r\n*Літерально* &amp;\r\nрядок.', 'plain');
const oldEdited = schema.nodes.doc.create(null, [
  schema.nodes.paragraph.create(oldPlain.doc.firstChild.attrs, schema.text('Новий початок.')),
  oldPlain.doc.child(1),
]);
const migrated = serializeDocument(oldEdited, oldPlain);
assert.equal(loadDocument(migrated.source, 'markdown').doc.child(1).textContent, '*Літерально* &amp;\nрядок.');
// Newly inserted/empty paragraphs have exact visual/source mapping after save.
const blank = loadDocument('Один.\n\nДва.', 'markdown');
const withBlank = schema.nodes.doc.create(null, [blank.doc.firstChild, schema.nodes.paragraph.create(), blank.doc.child(1)]);
const withBlankSaved = serializeDocument(withBlank, blank);
assert.equal(loadDocument(withBlankSaved.source, 'markdown').doc.childCount, 3);

// Every fixture survives a real edit without losing unrelated visible text/marks.
for (const fixture of fixtures) {
  const loaded = loadDocument(fixture.source, fixture.format);
  let changed = false;
  function visit(node) {
    if (!changed && node.isText) {changed = true; return schema.text('X' + node.text, node.marks);}
    if (node.isLeaf) return node;
    const children = []; node.forEach(child => children.push(visit(child)));
    if (!changed && node.type.name === 'paragraph' && !children.length) {children.push(schema.text('X')); changed = true;}
    return node.type.create(node.attrs, children, node.marks);
  }
  const edited = visit(loaded.doc);
  if (changed) {
    let saved;
    try {saved = serializeDocument(edited, loaded);} catch (error) {throw new Error(fixture.name, {cause: error});}
    assert.equal(loadDocument(saved.source, saved.content_format).doc.textContent, edited.textContent, fixture.name);
  }
}
console.log(`Bridge: ${fixtures.length} no-op fixtures, ranges, Unicode, edit preservation and opaque safety passed`);
