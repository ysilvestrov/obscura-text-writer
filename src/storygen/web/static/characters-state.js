export class CharacterBuffer{
  cards=[];revision=null;dirty=false;saving=false;epoch=0;loadToken=0;previewToken=0;
  beginLoad(){return ++this.loadToken}
  loaded(data,token){
    if(token!==this.loadToken||this.dirty||this.saving)return false;
    this.cards=structuredClone(data.cards);this.revision=data.revision;this.epoch++;return true;
  }
  changed(){this.dirty=true;this.epoch++;this.loadToken++}
  beginSave(){
    if(this.saving)throw new Error('Зачекайте завершення збереження');
    this.saving=true;this.loadToken++;return {epoch:this.epoch,cards:structuredClone(this.cards),expected_revision:this.revision};
  }
  saved(data,snapshot){
    this.saving=false;
    if(this.epoch!==snapshot.epoch)return false;
    this.cards=structuredClone(data.cards);this.revision=data.revision;this.dirty=false;this.epoch++;return true;
  }
  failed(){this.saving=false}
  previewRequest(scene_id){return {token:++this.previewToken,epoch:this.epoch,scene_id}}
  previewCurrent(request,scene_id){return request.token===this.previewToken&&request.epoch===this.epoch&&request.scene_id===scene_id}
}
