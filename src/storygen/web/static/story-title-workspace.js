import {api,json} from './api.js';
import {state} from './editor.js';
import {installStoryTitle} from './story-title.js';
installStoryTitle({root:document.querySelector('#workspace'),state,api,json});
