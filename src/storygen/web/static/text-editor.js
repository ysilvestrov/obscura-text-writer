// The serialized source is authoritative. A future Markdown view implements this boundary.
export function createTextEditor(element){
  return {
    read:()=>element.value,
    write:text=>{element.value=text},
    placeholder:text=>{element.placeholder=text},
    readOnly:value=>{element.readOnly=value},
    visible:value=>{element.hidden=!value},
    focus:()=>element.focus(),
    onInput:handler=>element.addEventListener('input',handler)
  };
}
