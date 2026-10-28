import { HelpTip } from "./HelpTip";
import { explainError } from "./errors";
import { useEffect, useState } from 'react';
import type { Runtime } from './types';
type Health={node:string;mode:string;cpu_percent:number;cpu_count:number;memory_used:number;memory_total:number;storage_name:string;storage_used:number|null;storage_total:number|null;storage_available:number|null;storage_error:string|null;uptime_seconds:number;sampled_at:string};
type API=<T>(path:string,body?:unknown)=>Promise<T>;
export const gib=(bytes:number)=>`${(bytes/1073741824).toLocaleString('th-TH',{maximumFractionDigits:1})} GiB`;
export const diskSize=(bytes:number)=>bytes>=1000000000000?`${(bytes/1000000000000).toLocaleString('th-TH',{maximumFractionDigits:2})} TB`:`${(bytes/1000000000).toLocaleString('th-TH',{maximumFractionDigits:1})} GB`;
export function ResourceUsage({runtime}:{runtime?:Runtime}){
 if(!runtime||runtime.cpu_percent===undefined)return <span className="muted">—</span>;
 const percent=runtime.memory_total?Math.min(100,(runtime.memory_used??0)/runtime.memory_total*100):0;
 return <div className="vm-resource"><span>CPU {runtime.cpu_percent.toFixed(1)}%</span><progress aria-label="CPU ของ VM" value={runtime.cpu_percent} max={100}/><span>RAM {gib(runtime.memory_used??0)} / {gib(runtime.memory_total??0)}</span><progress aria-label="RAM ของ VM" value={percent} max={100}/></div>;
}
export function SystemHealth({api}:{api:API}){
 const [data,setData]=useState<Health|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let active=true;
  async function load(){setBusy(true);try{const value=await api<Health>('/admin/system-health');if(active){setData(value);setError('');}}catch(e){if(active)setError(explainError(e));}finally{if(active)setBusy(false);}}
  void load();const timer=setInterval(()=>void load(),20000);return()=>{active=false;clearInterval(timer);};
 },[]);
 const ram=data?.memory_total?data.memory_used/data.memory_total*100:0;
 return <section className="panel system-health"><div className="section-head"><h2>สุขภาพ Proxmox {data?.node}</h2>{data&&<span className={`badge ${error?'needs_review':'ready'}`}>{error?'ข้อมูลไม่เป็นปัจจุบัน':data.mode==='mock'?'ข้อมูลจำลอง':'เชื่อมต่อแล้ว'}</span>}</div>
  {error&&<p className="alert warning" role="alert">{error}</p>}
  {!data&&!error&&<p role="status">กำลังอ่านสถานะ Proxmox…</p>}
  {data&&<><div className="health-grid"><article><span>CPU · {data.cpu_count} logical CPUs</span><strong>{data.cpu_percent.toFixed(1)}%</strong><progress aria-label="CPU Proxmox" max={100} value={data.cpu_percent}/></article><article><span>RAM</span><strong>{ram.toFixed(1)}%</strong><progress aria-label="RAM Proxmox" max={100} value={ram}/><small>{gib(data.memory_used)} / {gib(data.memory_total)}</small></article><article><span>พื้นที่ VM · {data.storage_name}</span><strong>{data.storage_total&&data.storage_used!==null?(data.storage_used/data.storage_total*100).toFixed(1):'—'}{data.storage_total?'%':''}</strong>{data.storage_error?<small className="error">{data.storage_error}</small>:data.storage_total&&data.storage_used!==null?<><progress aria-label="พื้นที่ VM Proxmox" max={100} value={data.storage_used/data.storage_total*100}/><small>{diskSize(data.storage_used)} / {diskSize(data.storage_total)}</small><small>ว่าง {diskSize(data.storage_available??0)}</small></>:<small>ยังไม่มีข้อมูล Storage</small>}</article><article><span>Uptime</span><strong>{Math.floor(data.uptime_seconds/86400)} วัน</strong><small>{Math.floor(data.uptime_seconds%86400/3600)} ชั่วโมง</small></article></div><p className="health-updated muted">{busy?'กำลังอัปเดต…':`อ่านข้อมูลเมื่อ ${new Date(data.sampled_at).toLocaleTimeString('th-TH')}`} <HelpTip label="เกี่ยวกับข้อมูลสุขภาพ">อัปเดตทุก 20 วินาที ข้อมูล Node รวมการใช้ทรัพยากรทั้งหมดบนโฮสต์ พื้นที่ VM อ่านจาก Storage ใน Setup</HelpTip></p></>}
 </section>;
}
