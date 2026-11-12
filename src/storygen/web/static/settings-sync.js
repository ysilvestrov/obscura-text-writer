// MCP-BRIDGE-S38: what the open settings page does when it finds changes made elsewhere (a chat, another window).
// Pure: the page reads the settings and the evaluator on return and asks these functions.
import {settingsSignature} from './settings-state.js';

// Only what the page shows: the story revision moves with every scene and title change, the evaluator block is runtime state.
export function settingsContentKey(settings,evaluator){
  const data=settings||{},story=data.story||{};
  const {block,revision,...evaluatorSettings}=evaluator||{};
  return settingsSignature({roles:data.roles??null,profile:data.profile??null,prompts:data.prompts??null,prepare_prompt:data.prepare_prompt??null,
    prompt_contracts:data.prompt_contracts??null,prepare_prompt_contract:data.prepare_prompt_contract??null,
    target_words:story.target_words??null,language:story.language??null,content_rating:story.content_rating??null,
    evaluator:evaluator?evaluatorSettings:null});
}

export function externalSettingsChange({loadedKey,freshKey,unsaved,busy}){
  const changed=loadedKey!==null&&freshKey!==loadedKey;
  // Unsaved edits or a save in progress are never thrown away by a reload.
  const reload=changed&&!unsaved&&!busy;
  return {reload,warn:changed&&!reload};
}

// A story whose evaluator is not configured answers 400; that is "no evaluator", not a failed check.
export async function readSettingsContent(api,storyId){
  const [settings,evaluator]=await Promise.all([api(`/api/stories/${storyId}/settings`),
    api(`/api/stories/${storyId}/evaluator`).catch(error=>{if(error?.status===400)return null;throw error})]);
  return settingsContentKey(settings,evaluator);
}
