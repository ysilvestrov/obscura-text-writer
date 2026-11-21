// DOCS-SITE-S11: docs/site/consent.js loads Google tags only after consent.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const code=readFileSync(process.argv[2]+'/docs/site/consent.js','utf-8');
const DAY=24*3600*1000;
const NOW=Date.parse('2026-11-21T12:00:00Z');

function element(tag){
  const el={tag,children:[],attributes:{},listeners:{},hidden:false,textContent:'',
    setAttribute(name,value){this.attributes[name]=String(value)},
    getAttribute(name){return name in this.attributes?this.attributes[name]:null},
    appendChild(child){this.children.push(child);return child},
    addEventListener(type,fn){this.listeners[type]=fn},
    focus(){this.focused=true}};
  return el;
}

function find(root,predicate){
  if(predicate(root))return root;
  for(const child of root.children||[]){const hit=find(child,predicate);if(hit)return hit}
  return null;
}

function run({stored,storage=true,session={},hash='',lang='uk',cookie='',host='obscurawriter.com',dataLayer}={}){
  const saved={};const sessionSaved={...session};const cookies=[];let reloaded=0;let clickListener=null;
  const head=element('head'),body=element('body');
  const local=storage?{getItem:key=>key==='obscura.site.consent'?(stored===undefined?null:JSON.stringify(stored)):null,
    setItem:(key,value)=>{saved[key]=JSON.parse(value)}}:null;
  const sessionStore=storage?{getItem:key=>sessionSaved[key]??null,setItem:(key,value)=>{sessionSaved[key]=value}}:null;
  const script=element('script');
  Object.assign(script.attributes,{'data-ads':'AW-123','data-conversion':'abcLabel','data-ga4':'G-ABC','data-privacy':'privacy.html'});
  const document={
    currentScript:script,head,body,
    documentElement:{lang},
    createElement:element,
    createTextNode:text=>({text,children:[]}),
    addEventListener:(type,fn)=>{if(type==='click')clickListener=fn},
    get cookie(){return cookie},
    set cookie(value){cookies.push(value)},
  };
  const window={
    get localStorage(){if(!local)throw new Error('SecurityError');return local},
    get sessionStorage(){if(!sessionStore)throw new Error('SecurityError');return sessionStore},
    location:{hash,hostname:host,reload:()=>{reloaded++}},
  };
  if(dataLayer)window.dataLayer=dataLayer;
  class FixedDate extends Date{
    constructor(...args){if(args.length)super(...args);else super(NOW)}
    static now(){return NOW}
  }
  vm.runInNewContext(code,{window,document,Date:FixedDate,JSON,String,encodeURIComponent});
  const banner=()=>find(body,el=>el.className==='consent-banner');
  return {
    window,head,body,saved,sessionSaved,cookies,banner,
    get reloaded(){return reloaded},
    tags:()=>head.children.filter(el=>el.tag==='script'),
    layer:()=>JSON.parse(JSON.stringify((window.dataLayer||[]).map(args=>Array.from(args)))),
    press:choice=>find(banner(),el=>el.attributes&&el.attributes['data-consent']===choice).listeners.click(),
    open:()=>clickListener({target:{closest:selector=>selector==='[data-consent-open]'?{}:null}}),
  };
}

const granted={v:1,choice:'granted',at:new Date(NOW-DAY).toISOString()};
const denied={v:1,choice:'denied',at:new Date(NOW-DAY).toISOString()};

// No choice yet: the banner with equal Accept and Reject, and nothing for Google.
{
  const page=run();
  assert.equal(page.tags().length,0);
  assert.equal(page.window.dataLayer,undefined);
  const banner=page.banner();
  assert.ok(banner&&!banner.hidden);
  const buttons=banner.children.filter(el=>el.tag==='button');
  assert.deepEqual(buttons.map(b=>[b.attributes['data-consent'],b.className,b.textContent]),
    [['granted','consent-choice','Прийняти'],['denied','consent-choice','Відхилити']]);
  assert.equal(find(banner,el=>el.tag==='a').href,'privacy.html');
}

// Accept: the choice is stored and the tag loads with Consent Mode v2 granted, js and both configs in this order.
{
  const page=run();
  page.press('granted');
  assert.equal(page.saved['obscura.site.consent'].choice,'granted');
  assert.equal(page.saved['obscura.site.consent'].at,new Date(NOW).toISOString());
  assert.ok(page.banner().hidden);
  assert.deepEqual(page.tags().map(t=>[t.src,t.async]),[['https://www.googletagmanager.com/gtag/js?id=AW-123',true]]);
  const layer=page.layer();
  assert.deepEqual(layer[0],['consent','default',{ad_storage:'granted',ad_user_data:'granted',ad_personalization:'granted',analytics_storage:'granted'}]);
  assert.equal(layer[1][0],'js');
  assert.deepEqual(layer.slice(2),[['config','AW-123'],['config','G-ABC']]);
}

// Reject: stored, banner hidden, no tag.
{
  const page=run();
  page.press('denied');
  assert.equal(page.saved['obscura.site.consent'].choice,'denied');
  assert.equal(page.tags().length,0);
  assert.equal(page.reloaded,0);
}

// A stored grant loads at once without a banner; a stored refusal shows nothing and loads nothing.
{
  const page=run({stored:granted});
  assert.equal(page.tags().length,1);
  assert.equal(page.banner(),null);
  const refused=run({stored:denied});
  assert.equal(refused.tags().length,0);
  assert.equal(refused.banner(),null);
}

// An old, future, foreign-version or broken choice asks again.
for(const stored of [{...granted,at:new Date(NOW-366*DAY).toISOString()},{...granted,at:new Date(NOW+DAY).toISOString()},
  {...granted,v:2},{v:1,choice:'maybe',at:granted.at},'broken']){
  const page=run({stored});
  assert.equal(page.tags().length,0,JSON.stringify(stored));
  assert.ok(page.banner());
}

// Return from the waitlist with consent: the conversion once per tab, after the configs.
{
  const page=run({stored:granted,hash:'#waitlist-ok'});
  assert.deepEqual(page.layer().slice(4),[['event','conversion',{send_to:'AW-123/abcLabel'}],['event','sign_up']]);
  assert.equal(page.sessionSaved['obscura.site.waitlist-sent'],'1');
  const again=run({stored:granted,hash:'#waitlist-ok',session:{'obscura.site.waitlist-sent':'1'}});
  assert.equal(again.layer().filter(args=>args[0]==='event').length,0);
  // Consent given on that page sends it then; without consent nothing is sent.
  const later=run({hash:'#waitlist-ok'});
  assert.equal(later.window.dataLayer,undefined);
  later.press('granted');
  assert.deepEqual(later.layer().filter(args=>args[0]==='event').map(args=>args[1]),['conversion','sign_up']);
  // Another result of the form is no conversion.
  assert.equal(run({stored:granted,hash:'#waitlist-error'}).layer().filter(args=>args[0]==='event').length,0);
}

// Cookie settings reopen the banner; withdrawing deletes Google cookies here and on the parent domain, then reloads.
{
  const page=run({stored:granted,cookie:'_ga=1; _ga_ABC=2; _gcl_au=3; other=4',host:'www.obscurawriter.com'});
  assert.equal(page.banner(),null);
  page.open();
  assert.ok(page.banner()&&!page.banner().hidden);
  page.press('denied');
  assert.equal(page.reloaded,1);
  const names=new Set(page.cookies.map(c=>c.split('=')[0]));
  assert.deepEqual([...names].sort(),['_ga','_ga_ABC','_gcl_au']);
  assert.ok(page.cookies.every(c=>c.includes('expires=Thu, 01 Jan 1970')));
  assert.ok(page.cookies.some(c=>c.endsWith('domain=obscurawriter.com')));
  assert.ok(page.cookies.some(c=>c.endsWith('domain=www.obscurawriter.com')));
}

// Without storage the banner shows, and Accept still loads the tag for this page.
{
  const page=run({storage:false});
  assert.ok(page.banner());
  page.press('granted');
  assert.equal(page.tags().length,1);
}

// English page texts.
{
  const page=run({lang:'en'});
  assert.deepEqual(page.banner().children.filter(el=>el.tag==='button').map(b=>b.textContent),['Accept','Reject']);
}

console.log('ok');
