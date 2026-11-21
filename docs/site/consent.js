// Cookie consent and Google tags of the user-guide site (DOCS-SITE-S11). The build adds this script only when the
// manifest has an `ads` section. Before "Accept" nothing goes to Google; after it the Google tag (gtag.js) loads with
// Consent Mode v2 granted and the Google Ads and GA4 configs, and a return from the waitlist (#waitlist-ok) sends the
// conversion once per tab. The choice lives in localStorage (no cookie); "Cookie settings" reopens the banner, and a
// withdrawal deletes the Google cookies of the site and reloads the page to unload the tag.
(function(){
  var KEY='obscura.site.consent',SENT='obscura.site.waitlist-sent',VERSION=1,MAX_AGE=365*24*3600*1000;
  var TEXT={
    uk:{text:'Сайт використовує cookies Google для вимірювання реклами й відвідувань, лише якщо ви погодитеся. ',
        more:'Докладніше',accept:'Прийняти',reject:'Відхилити',label:'Згода на cookies'},
    en:{text:'The site uses Google cookies to measure ads and visits, only if you agree. ',
        more:'Learn more',accept:'Accept',reject:'Reject',label:'Cookie consent'}
  };
  var script=document.currentScript;
  if(!script)return;
  var ads=script.getAttribute('data-ads'),label=script.getAttribute('data-conversion'),ga4=script.getAttribute('data-ga4');
  var privacy=script.getAttribute('data-privacy')||'privacy.html';
  var words=TEXT[document.documentElement.lang]||TEXT.en;
  var banner=null,loaded=false;

  function storage(name){try{return window[name]}catch(e){return null}}
  function read(){
    var store=storage('localStorage');if(!store)return null;
    try{
      var value=JSON.parse(store.getItem(KEY));
      if(!value||value.v!==VERSION||(value.choice!=='granted'&&value.choice!=='denied'))return null;
      var at=Date.parse(value.at);
      if(!(at<=Date.now())||Date.now()-at>MAX_AGE)return null;
      return value.choice;
    }catch(e){return null}
  }
  function write(choice){
    var store=storage('localStorage');
    try{if(store)store.setItem(KEY,JSON.stringify({v:VERSION,choice:choice,at:new Date().toISOString()}))}catch(e){}
  }
  function gtag(){window.dataLayer.push(arguments)}
  function load(){
    if(loaded)return;loaded=true;
    window.dataLayer=window.dataLayer||[];
    gtag('consent','default',{ad_storage:'granted',ad_user_data:'granted',ad_personalization:'granted',analytics_storage:'granted'});
    gtag('js',new Date());
    gtag('config',ads);
    gtag('config',ga4);
    var tag=document.createElement('script');
    tag.async=true;
    tag.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(ads);
    document.head.appendChild(tag);
    conversion();
  }
  function conversion(){
    if(window.location.hash!=='#waitlist-ok')return;
    var session=storage('sessionStorage');
    try{if(session&&session.getItem(SENT))return}catch(e){}
    gtag('event','conversion',{send_to:ads+'/'+label});
    gtag('event','sign_up');
    try{if(session)session.setItem(SENT,'1')}catch(e){}
  }
  function forget(){
    // _ga, _ga_<id> (GA4) and _gcl_* (Google Ads) on this host and on the parent domain gtag.js uses.
    var host=window.location.hostname,domains=['',host];
    var parts=host.split('.');if(parts.length>2)domains.push(parts.slice(-2).join('.'));
    String(document.cookie||'').split(';').forEach(function(item){
      var name=item.split('=')[0].trim();
      if(!/^(_ga|_ga_.+|_gcl_.+)$/.test(name))return;
      domains.forEach(function(domain){
        document.cookie=name+'=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'+(domain?'; domain='+domain:'');
      });
    });
  }
  function choose(choice){
    var before=read();
    write(choice);hide();
    if(choice==='granted'){load();return}
    if(before==='granted'||loaded){forget();window.location.reload()}
  }
  function hide(){if(banner)banner.hidden=true}
  function show(){
    if(!banner){
      banner=document.createElement('section');
      banner.className='consent-banner';
      banner.setAttribute('role','dialog');
      banner.setAttribute('aria-label',words.label);
      banner.setAttribute('tabindex','-1');
      var text=document.createElement('p');
      text.appendChild(document.createTextNode(words.text));
      var link=document.createElement('a');link.href=privacy;link.textContent=words.more;
      text.appendChild(link);
      banner.appendChild(text);
      [['granted',words.accept],['denied',words.reject]].forEach(function(item){
        var button=document.createElement('button');
        button.type='button';button.className='consent-choice';button.textContent=item[1];
        button.setAttribute('data-consent',item[0]);
        button.addEventListener('click',function(){choose(item[0])});
        banner.appendChild(button);
      });
      document.body.appendChild(banner);
    }
    banner.hidden=false;
    if(banner.focus)banner.focus();
  }

  document.addEventListener('click',function(event){
    var open=event.target&&event.target.closest?event.target.closest('[data-consent-open]'):null;
    if(open)show();
  });
  var choice=read();
  if(choice==='granted')load();
  else if(choice!=='denied')show();
})();
