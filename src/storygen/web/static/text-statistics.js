export function textStatistics(text){
  return {characters:Array.from(text).length,words:(text.normalize('NFC').match(/[\p{L}\p{N}]+(?:['’ʼ\-‐‑][\p{L}\p{N}]+)*/gu)||[]).length};
}
