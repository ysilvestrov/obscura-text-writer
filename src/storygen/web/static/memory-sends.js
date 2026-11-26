import {t} from './i18n.js';
// R-49 (MANUSCRIPT-IMPORT-S16): «what the memory model receives» from the preview's `sends` (categories of the request sections).
// A light module: the workspace telemetry card and the memory dialog share it without importing each other.
const LABELS={memory_catalog:()=>t('memory_build.sends.memory_catalog'),places:()=>t('memory_build.sends.places'),series_facts:()=>t('memory_build.sends.series_facts')};
export function sendsText(sends,model){
  const items=sends.items.map(item=>item.key==='prose'?t('memory_build.sends.prose',{p0:item.scenes,p1:item.words}):(LABELS[item.key]?.()||item.key));
  return t('memory_build.sends.line',{p0:model,p1:items.join(', ')})+(sends.local?' '+t('memory_build.sends.local'):'');
}
