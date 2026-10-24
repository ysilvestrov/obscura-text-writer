const commands=new Map();
export function registerWorkspaceCommand(name,handler){commands.set(name,handler)}
export async function invokeWorkspaceCommand(name,payload){
  const handler=commands.get(name);
  if(!handler)throw new Error('Дія ще завантажується; спробуйте ще раз');
  return handler(payload);
}
