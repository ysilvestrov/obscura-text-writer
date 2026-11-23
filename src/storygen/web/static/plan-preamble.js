import {live,msg,t,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {registerSettingsForm,settingsChanged,settingsSaved,withSettingsSave} from './settings-workspace.js';
// PLAN-PREAMBLE: the plan preamble (global author notes) is edited after import; a save is a new plan version.
// The form shares the settings dirty registry: leaving or an external reload warns about an unsaved preamble, and
// withSettingsSave locks every settings field while the request is in flight, so nothing typed meanwhile is lost.
const root=document.querySelector('[data-story-id]'),form=document.querySelector('#plan-preamble-form');
if(root&&form){
  const id=root.dataset.storyId,area=form.elements.text,button=form.querySelector('button'),status=form.querySelector('[data-plan-preamble-status]');
  let state=null;
  function sync(){button.disabled=!state||!state.editable||area.disabled||area.value.trim()===state.text.trim()}
  async function load(){
    state=await api(`/api/stories/${id}/plan-preamble`);
    area.value=state.text;area.disabled=!state.editable;
    uiText(status,'textContent',()=>state.editable?'':t(state.reason==='no_plan'?'plan_preamble.no_plan':'plan_preamble.no_scenes'));
    registerSettingsForm('plan-preamble',{form,label:live(()=>t('plan_preamble.title')),section:'writing',reset:load});
    settingsSaved('plan-preamble');
    sync();
  }
  area.addEventListener('input',sync);
  form.addEventListener('settings-unlocked',sync);
  form.onsubmit=async event=>{
    event.preventDefault();if(!state||button.disabled)return;
    try{
      await withSettingsSave('plan-preamble',async()=>{
        const result=await api(`/api/stories/${id}/plan-preamble`,json('PUT',{text:area.value,expected_plan_version_id:state.plan_version_id}));
        await load();
        notice(msg(result.changed?'plan_preamble.saved':'plan_preamble.unchanged'));
      });
    }catch(error){
      // A refused or conflicting save keeps the author's text in the field: nothing was written.
      notice(error.message,'error');settingsChanged('plan-preamble');
    }
  };
  load().catch(error=>notice(error.message,'error'));
}
