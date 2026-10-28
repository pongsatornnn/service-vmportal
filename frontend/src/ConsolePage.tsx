import { BASE, at } from "./base";
import { useEffect, useState } from 'react';
import { VMConsole } from './Console';
import { loadSession, saveSession } from './session';
import { readableError, explainError } from './errors';
export function ConsolePage({vmId}:{vmId:string}){
 const [session,setSession]=useState<{ticket:string;password:string}|null>(null),[error,setError]=useState(''),[closed,setClosed]=useState(false);
 useEffect(()=>{let active=true;const token=loadSession();
  async function open(){
   if(!token)throw new Error('กรุณาเข้าสู่ระบบที่หน้าหลัก แล้วเปิด Console ใหม่');
   if(!/^[1-9][0-9]{0,9}$/.test(vmId))throw new Error('หมายเลข VM ไม่ถูกต้อง กรุณาเปิด Console จากรายการ VM');
   let response:Response;try{response=await fetch(at(`api/vms/${vmId}/console`),{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:'{}'});}catch{throw new Error('เชื่อมต่อระบบไม่ได้ กรุณาตรวจเครือข่ายแล้วเปิด Console ใหม่');}
   const data=await response.json().catch(()=>({}));
   if(!response.ok){if(response.status===401)saveSession('');throw new Error(readableError(data,response.status,response.headers.get('X-Request-ID')));}
   if(typeof data?.ticket!=='string'||typeof data?.password!=='string')throw new Error('ข้อมูล Console ไม่สมบูรณ์ กรุณาปิดแท็บแล้วเปิดใหม่');
   if(active)setSession(data);
  }
  void open().catch(e=>{if(active)setError(explainError(e));});return()=>{active=false;};
 },[vmId]);
 return <main className="console-page"><header><a className="login-brand" href={BASE}><img src={at("portal-mark.svg")} width="36" height="36" alt=""/>ICT - VM Portal</a><span>Console · VM #{vmId.replace(/[^0-9]/g,'')}</span></header>{error&&<p className="alert error" role="alert">{error}</p>}{session?<VMConsole {...session} onClose={()=>{setSession(null);setClosed(true);}}/>:!error&&<p role="status">{closed?'ปิด Console แล้ว คุณสามารถปิดแท็บนี้ได้':'กำลังเปิด Console…'}</p>}</main>;
}
