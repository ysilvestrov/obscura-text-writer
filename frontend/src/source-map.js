/** Server offsets are Unicode code points; ProseMirror/mdast use UTF-16. */
export function codepointOffset(source, offset) {
  if (!Number.isInteger(offset) || offset < 0 || offset > source.length) throw new RangeError('Invalid UTF-16 offset');
  if (offset && offset < source.length && /[\uD800-\uDBFF]/u.test(source[offset - 1]) && /[\uDC00-\uDFFF]/u.test(source[offset])) {
    throw new RangeError('Offset splits a surrogate pair');
  }
  return [...source.slice(0, offset)].length;
}

export function utf16Offset(source, offset) {
  if (!Number.isInteger(offset) || offset < 0) throw new RangeError('Invalid codepoint offset');
  const points = [...source];
  if (offset > points.length) throw new RangeError('Invalid codepoint offset');
  return points.slice(0, offset).join('').length;
}

export class SourceMappingError extends Error {}

export function toSourceRange({from, to}, map) {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from >= to) throw new SourceMappingError('Select nonempty text');
  if (map.opaque.some(range => from < range.to && to > range.from)) {
    throw new SourceMappingError('Cannot annotate opaque Markdown');
  }
  const start = map.segments.find(segment => segment.from === from);
  const end = map.segments.findLast(segment => segment.to === to);
  if (!start || !end || start.sourceFrom >= end.sourceTo) throw new SourceMappingError('Selection has no exact source boundaries');
  return {
    start: codepointOffset(map.source, start.sourceFrom),
    end: codepointOffset(map.source, end.sourceTo),
    source_quote: map.source.slice(start.sourceFrom, end.sourceTo),
    display_quote: map.doc.textBetween(from, to, '\n\n', '\n'),
  };
}

export function toDocumentRange({start,end},map){
  const left=utf16Offset(map.source,start),right=utf16Offset(map.source,end);
  const first=map.segments.find(unit=>unit.sourceFrom===left);
  const last=map.segments.findLast(unit=>unit.sourceTo===right);
  if(!first||!last)throw new SourceMappingError('Source has no exact document boundaries');
  const range={from:first.from,to:last.to};
  const verified=toSourceRange(range,map);
  if(verified.start!==start||verified.end!==end)throw new SourceMappingError('Source boundaries do not round-trip');
  return range;
}
