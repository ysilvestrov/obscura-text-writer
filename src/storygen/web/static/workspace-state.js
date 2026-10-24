export const stages=[{mode:'plan',label:'План'},{mode:'brief',label:'Завдання'},{mode:'draft',label:'Чернетка'},
  {mode:'review',label:'Редактура'},{mode:'prose',label:'Проза'},{mode:'memory',label:'Пам’ять'}];
export function assertReadyDispatch(state,captured){
  if(state.scene?.id!==captured.sceneId||state.bufferEpoch!==captured.epoch||state.mode!==captured.mode||state.dirty||state.saving)
    throw new Error('Матеріал змінився під час перевірки; перевірте текст перед запуском');
  if((state.workspaceRuns||[]).some(run=>['queued','running','pause_requested','cancellation_requested'].includes(run.state)))
    throw new Error('Інший запуск уже виконується або стоїть у черзі; дочекайтеся його завершення');
}
export function primaryAction(state){
  const save=state.dirty?'Зберегти й ':'';
  const definitions={plan:{mode:'stage',stage:'brief',target:'brief',name:'завдання',label:'Зберегти й створити завдання'},
    brief:{mode:'stage',stage:'draft',target:'draft',name:'чернетки',label:'Зберегти й написати чернетку'},
    draft:{mode:'edit_loop',target:'prose',name:'редактури',label:'Зберегти й редагувати'},
    review:{action:'accept',label:'Прийняти вибране й перечитати'},
    prose:{mode:'stage',stage:'memory',target:'memory',name:'пам’яті',label:'Зберегти й оновити пам’ять'},
    memory:{action:'next',label:'Зберегти вибір і перейти далі'}};
  const result={...definitions[state.mode]};
  if(result.target&&state.scene?.heads[result.target])result.label=save+(state.dirty?'створити':'Створити')+' новий варіант '+result.name;
  return result;
}
export async function performPrimary({state,save,run,show,accept,next}){
  if(!state.scene||state.saving)throw new Error('Дочекайтеся збереження та оберіть сцену');
  if(state.bufferOrigin==='history'||state.mode==='blueprint')throw new Error('Спершу вийдіть із перегляду історичної версії');
  const captured={id:state.scene.id,mode:state.mode,epoch:state.bufferEpoch};
  if(state.dirty)await save();
  if(state.dirty||state.saving||state.scene?.id!==captured.id||state.mode!==captured.mode||state.bufferEpoch!==captured.epoch)
    throw new Error('Під час збереження з’явилися нові зміни; перевірте текст перед запуском');
  const action=primaryAction(state);
  if(action.action==='accept'){await accept();return;}
  if(action.action==='next'){await next();return;}
  if(!action.mode)throw new Error('Оберіть поточний матеріал сцени');
  if(action.mode==='edit_loop'){
    action.editor_source_head='draft';action.editor_source_version_id=state.scene.heads.draft;
  }
  await run(action);
}
