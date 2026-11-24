import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {installEditorImport} from './editor-import.js';
installEditorImport({state,api,json,notice,document,refresh,selectScene,invokeWorkspaceCommand});
