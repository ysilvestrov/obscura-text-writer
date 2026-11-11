// BUILD-EDITION-001: what the build edition allows. The server enforces the limit; this only keeps the forms honest.
const FULL={edition:'full',max_rating:{sexual:2,violence:2,themes:2},version:'',support_url:'',waitlist_url:'',report_url:''};
let pending=null;
// One request per page. A failed request means "show everything": the server still rejects what is not allowed.
export function appInfo(){
  pending??=fetch('/api/app-info').then(response=>response.ok?response.json():FULL).catch(()=>FULL);
  return pending;
}
// Levels a rating select offers. A stored level above the limit stays visible so the form shows the real value.
export function allowedLevels(max,current){
  const levels=[];
  for(let level=0;level<=max;level++)levels.push(level);
  if(current!==null&&current!==undefined&&current>max)levels.push(current);
  return levels;
}
export function limited(maxRating){return Object.values(maxRating).some(level=>level<2)}
