// Tab-scoped only: no passwords or provider credentials are stored here.
const key='vmportal.session';
export function loadSession(){try{return sessionStorage.getItem(key)??'';}catch{return '';}}
export function saveSession(token:string){try{if(token)sessionStorage.setItem(key,token);else sessionStorage.removeItem(key);}catch{/* Login still works when browser storage is disabled. */}}
const pages=['overview','requests','status','activity','approvals','accounts','setup','guide','audit','password'];
export type SettingsSection='connection'|'templates'|'session';
export function loadView():{tab:string;settingsSection:SettingsSection}|null{
 try{const value=JSON.parse(sessionStorage.getItem('vmportal.view')??'null');return value&&pages.includes(value.tab)?{tab:value.tab,settingsSection:['session','templates'].includes(value.settingsSection)?value.settingsSection:'connection'}:null;}catch{return null;}
}
export function saveView(tab:string,settingsSection:SettingsSection){try{sessionStorage.setItem('vmportal.view',JSON.stringify({tab,settingsSection}));}catch{}}
export function clearView(){try{sessionStorage.removeItem('vmportal.view');}catch{}}
