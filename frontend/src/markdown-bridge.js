import {Schema} from 'prosemirror-model';
import {fromMarkdown} from 'mdast-util-from-markdown';
import {toMarkdown} from 'mdast-util-to-markdown';
import {SourceMappingError} from './source-map.js';

export const schema = new Schema({
  nodes: {
    doc: {content: 'block+'},
    paragraph: {group: 'block', content: 'inline*', attrs: {sourceId: {default: null}}, toDOM: () => ['p', 0]},
    text: {group: 'inline'},
    hard_break: {group: 'inline', inline: true, selectable: false, toDOM: () => ['br']},
    opaque: {
      group: 'block', atom: true, selectable: true,
      attrs: {sourceId: {default: null}, source: {default: ''}},
      leafText: node => node.attrs.source,
      toDOM: node => ['pre', {'data-opaque': 'true', contenteditable: 'false'}, node.attrs.source],
    },
  },
  marks: {
    strong: {toDOM: () => ['strong', 0]},
    em: {toDOM: () => ['em', 0]},
  },
});

const punctuation = /^[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]$/;
const supported = node => ['paragraph', 'text', 'strong', 'emphasis', 'break'].includes(node.type)
  && (!node.children || node.children.every(supported));

/** Decode one lexical unit, retaining its exact source extent. No substring search. */
function lexicalUnits(raw, offset, plain = false) {
  const units = [];
  for (let index = 0; index < raw.length;) {
    let length = String.fromCodePoint(raw.codePointAt(index)).length;
    let value = raw.slice(index, index + length);
    const softBreak=!plain&&/^[ \t]*(?:\r\n|[\r\n])[ \t]*/.exec(raw.slice(index));
    if(softBreak){length=softBreak[0].length;value='\n';}
    else if (!plain && value === '\\' && punctuation.test(raw[index + 1] || '')) {
      length = 2; value = raw[index + 1];
    } else if (!plain && value === '&') {
      const entity = /^(?:&#[0-9]{1,7};|&#x[0-9a-f]{1,6};|&[a-z][a-z0-9]+;)/i.exec(raw.slice(index));
      if (entity) {
        const parsed = fromMarkdown(entity[0]);
        value = parsed.children[0]?.children[0]?.value ?? entity[0];
        length = entity[0].length;
      }
    } else if (value === '\r') {
      length = raw[index + 1] === '\n' ? 2 : 1; value = '\n';
    }
    units.push({value, sourceFrom: offset + index, sourceTo: offset + index + length});
    index += length;
  }
  return units;
}

function inlineNodes(ast, source, position, segments, marks = []) {
  const nodes = [];
  for (const child of ast.children || []) {
    if (child.type === 'text') {
      const raw = source.slice(child.position.start.offset, child.position.end.offset);
      const units = lexicalUnits(raw, child.position.start.offset);
      const visible = child.value.replace(/\r\n|\r/g, '\n');
      if (units.map(unit => unit.value).join('') !== visible) throw new SourceMappingError('Text decoding has no exact source map');
      for (const unit of units) {
        segments.push({...unit, from: position, to: position + unit.value.length});
        position += unit.value.length;
      }
      if (visible) nodes.push(schema.text(visible, marks));
    } else if (child.type === 'break') {
      nodes.push(schema.nodes.hard_break.create());
      segments.push({from: position, to: position + 1, sourceFrom: child.position.start.offset, sourceTo: child.position.end.offset});
      position++;
    } else {
      const mark = schema.marks[child.type === 'strong' ? 'strong' : 'em'].create();
      const nested = inlineNodes(child, source, position, segments, [...marks, mark]);
      nodes.push(...nested.nodes); position = nested.position;
    }
  }
  return {nodes, position};
}

function plainBlocks(source) {
  const blocks = [];
  const delimiter = /\r?\n[\t ]*\r?\n|\r(?!\n)[\t ]*\r(?!\n)/g;
  let from = 0;
  for (const match of source.matchAll(delimiter)) {
    blocks.push({start: from, end: match.index}); from = match.index + match[0].length;
  }
  blocks.push({start: from, end: source.length});
  return blocks;
}

function markdownBlocks(source) {
  const ast = fromMarkdown(source).children;
  const blocks = [];
  const empty = offset => ({type: 'paragraph', children: [], position: {start: {offset}, end: {offset}}});
  if (!ast.length) blocks.push(empty(0));
  let prior = 0;
  for (let index = 0; index <= ast.length; index++) {
    const next = ast[index];
    const until = next ? next.position.start.offset : source.length;
    const ends = [...source.slice(prior, until).matchAll(/\r\n|[\r\n]/g)];
    const extras = Math.floor(Math.max(0, ends.length - (index && next ? 2 : 0)) / 2);
    for (let count = 0; count < extras; count++) {
      const leading = index === 0 && next;
      const at = leading ? count * 2 - 1 : (count + 1) * 2 - 1;
      const offset = leading && count === 0 ? 0 : prior + ends[at].index + ends[at][0].length;
      blocks.push(empty(offset));
    }
    if (next) {blocks.push(next); prior = next.position.end.offset;}
  }
  return blocks;
}

export function loadDocument(source, contentFormat = 'plain') {
  if (typeof source !== 'string' || !['plain', 'markdown'].includes(contentFormat)) throw new TypeError('Invalid author text');
  const segments = [], opaque = [], blocks = [], nodes = [];
  const ast = contentFormat === 'markdown' ? markdownBlocks(source) : plainBlocks(source);
  let position = 0;
  for (const [index, block] of ast.entries()) {
    const from = contentFormat === 'markdown' ? block.position.start.offset : block.start;
    const to = contentFormat === 'markdown' ? block.position.end.offset : block.end;
    const attrs = {sourceId: `block-${index}`};
    let node;
    if (contentFormat === 'plain') {
      const raw = source.slice(from, to);
      const units = lexicalUnits(raw, from, true);
      const visible = units.map(unit => unit.value).join('');
      node = schema.nodes.paragraph.create(attrs, visible ? schema.text(visible) : null);
      let offset = position + 1;
      for (const unit of units) {
        segments.push({...unit, from: offset, to: offset + unit.value.length}); offset += unit.value.length;
      }
    } else if (supported(block)) {
      node = schema.nodes.paragraph.create(attrs, inlineNodes(block, source, position + 1, segments).nodes);
    } else {
      node = schema.nodes.opaque.create({...attrs, source: source.slice(from, to)});
      opaque.push({from: position, to: position + node.nodeSize});
    }
    blocks.push({from, to, node, id: attrs.sourceId}); nodes.push(node); position += node.nodeSize;
  }
  if (!nodes.length) nodes.push(schema.nodes.paragraph.create({sourceId: 'empty'}));
  const doc = schema.nodes.doc.create(null, nodes);
  return {doc, source, content_format: contentFormat, blocks, sourceMap: {source, doc, segments, opaque}};
}

function inlineAst(node) {
  const children = [];
  node.forEach(child => {
    if (child.type.name === 'hard_break') {children.push({type: 'break'}); return;}
    let ast = {type: 'text', value: child.text};
    for (const mark of [...child.marks].reverse()) ast = {type: mark.type.name === 'strong' ? 'strong' : 'emphasis', children: [ast]};
    children.push(ast);
  });
  return children;
}

function semantic(node) {
  if (node.type.name === 'text') return {type: 'text', text: node.text, marks: node.marks.map(mark => mark.type.name).sort()};
  if (node.type.name === 'opaque') return {type: 'opaque', source: node.attrs.source};
  const children = []; node.forEach(child => children.push(semantic(child)));
  return {type: node.type.name, children};
}

function serializeBlock(node) {
  if (node.type.name === 'opaque') return node.attrs.source;
  // An empty paragraph uses an empty source block; its separation is handled by the bridge.
  if (!node.content.size) return '';
  const source = toMarkdown({type: 'root', children: [{type: 'paragraph', children: inlineAst(node)}]}, {emphasis: '_', strong: '*'}).replace(/\n$/, '');
  const reparsed = loadDocument(source, 'markdown');
  if (JSON.stringify(semantic(reparsed.doc.firstChild)) !== JSON.stringify(semantic(node))) {
    throw new SourceMappingError('Edited Markdown does not reproduce the document');
  }
  return source;
}

export function serializeDocument(doc, baseline) {
  if (doc.eq(baseline.doc)) return {source: baseline.source, sourceMap: baseline.sourceMap, content_format: baseline.content_format};
  const nodes = []; doc.forEach(node => nodes.push(node));
  const ids = nodes.map(node => node.attrs.sourceId);
  const previous = new Map(baseline.blocks.map((block, index) => [block.id, {...block, index}]));
  const newline = baseline.source.includes('\r\n') ? '\r\n' : '\n';
  let source = '', prior = null;
  for (const node of nodes) {
    const old = ids.filter(id => id === node.attrs.sourceId).length === 1 ? previous.get(node.attrs.sourceId) : null;
    if (prior !== null) source += old && prior && old.index === prior.index + 1
      ? baseline.source.slice(prior.to, old.from) : newline + newline;
    else if (old?.index === 0) source += baseline.source.slice(0, old.from);
    const reusable = baseline.content_format === 'markdown' && old?.node.eq(node);
    source += reusable ? baseline.source.slice(old.from, old.to) : serializeBlock(node).replace(/\r?\n/g, newline);
    prior = old ?? false;
  }
  if (prior && prior.index === baseline.blocks.length - 1) source += baseline.source.slice(prior.to);
  const loaded = loadDocument(source, 'markdown');
  if (JSON.stringify(semantic(loaded.doc)) !== JSON.stringify(semantic(doc))) {
    throw new SourceMappingError('Serialized Markdown does not reproduce the document');
  }
  // Exact semantic equivalence also guarantees identical ProseMirror positions.
  return {source, sourceMap: loaded.sourceMap, content_format: 'markdown'};
}
