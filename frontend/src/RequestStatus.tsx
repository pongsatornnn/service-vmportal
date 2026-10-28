import { useEffect, useRef, useState } from "react";
import { HistoryPopup } from "./HistoryPopup";
import { DetailFacts, DetailRow, lastStep, RequestCard, Timeline, type Step } from "./RequestCard";
import { thaiTime } from "./time";
import { describeRequest, RequestOutcome, requestSteps, type RequestKind } from "./RequestProgress";
import { latestJob, requestKey, type StatusSection } from "./requestUpdates";
import type { Deletion, Job, PasswordReset, User, VM, VMRequest } from "./types";

type Row={key:string;id:number;ownerId:number;title:string;kind:RequestKind;status:string;vm?:VM;job?:Job;reason?:string|null;decidedBy?:string|null;purpose:string|null;summary:string;specs?:[string,string][];cancel?:boolean;createdAt?:string;decidedAt?:string|null};
// On phones the tab strip scrolls sideways; keep the chosen tab in view
// without moving the page itself.
export function revealSelectedTab(strip:HTMLElement|null){
  const tab=strip?.querySelector<HTMLElement>(".selected");
  if(!strip||!tab)return;
  const left=tab.offsetLeft-strip.offsetLeft,right=left+tab.offsetWidth;
  if(left<strip.scrollLeft)strip.scrollLeft=left;
  else if(right>strip.scrollLeft+strip.clientWidth)strip.scrollLeft=right-strip.clientWidth;
}
export const statusSections:[StatusSection,string][]=[["create","สร้าง VM"],["delete","ลบ VM"],["reset","รีเซ็ตรหัส VM"]];

export function RequestStatus({me,admin,users,requests,deletions,resets,vms,jobs,section,setSection,unseen,markSeen,recentlySeen,busy,onCancelReset,onNewRequest}:{
  me:User;admin:boolean;users:User[];requests:VMRequest[];deletions:Deletion[];resets:PasswordReset[];vms:VM[];jobs:Job[];
  section:StatusSection;setSection:(section:StatusSection)=>void;unseen:Set<string>;markSeen:(section:StatusSection)=>void;recentlySeen:(key:string)=>boolean;
  busy:boolean;onCancelReset:(id:number)=>void;onNewRequest:()=>void;
}) {
  // Keep "ใหม่" marks for this visit even after the updates are recorded as seen.
  const tabs=useRef<HTMLDivElement>(null);
  useEffect(()=>revealSelectedTab(tabs.current),[section]);
  const [fresh,setFresh]=useState<Set<string>>(new Set());
  const waiting=[...unseen].filter(key=>key.startsWith(section+"-"));
  useEffect(()=>{
    if(!waiting.length)return;
    setFresh(previous=>new Set([...previous,...waiting]));
    markSeen(section);
  },[section,waiting.join(",")]);
  const owner=(id:number)=>users.find(u=>u.id===id)?.username??`ผู้ใช้ #${id}`;
  const vmName=(id:number)=>vms.find(v=>v.id===id)?.hostname??`VM #${id}`;
  const rows:Record<StatusSection,Row[]>={
    create:requests.map(r=>{const vm=vms.find(v=>v.request_id===r.id);return {key:requestKey("create",r.id),id:r.id,ownerId:r.owner_id,title:r.hostname,kind:"provision" as const,status:r.status,vm,job:latestJob(jobs,vm?.id,"provision"),reason:r.reason,decidedBy:r.decided_by_name,createdAt:r.created_at,decidedAt:r.decided_at,purpose:r.request_reason,summary:`${owner(r.owner_id)} · ${r.cpu}\u00a0vCPU · ${r.ram}\u00a0MiB · ${r.disk}\u00a0GiB`,specs:[...(r.template_name?[["Template",r.template_name] as [string,string]]:[]),["เข้าเครื่องด้วย",r.auth_method==="password"?"Password":"SSH Key"],...(r.guest_username?[["บัญชีในเครื่อง VM",r.guest_username] as [string,string]]:[])]};}),
    delete:deletions.map(d=>({key:requestKey("delete",d.id),id:d.id,ownerId:d.owner_id,title:vmName(d.vm_id),kind:"delete" as const,status:d.status,vm:vms.find(v=>v.id===d.vm_id),job:latestJob(jobs,d.vm_id,"delete"),reason:d.decision_reason,decidedBy:d.decided_by_name,createdAt:d.created_at,decidedAt:d.decided_at,purpose:d.reason,summary:`${owner(d.owner_id)} · คำขอ #${d.id}`})),
    reset:resets.map(r=>({key:requestKey("reset",r.id),id:r.id,ownerId:r.owner_id,title:vmName(r.vm_id),kind:"reset_password" as const,status:r.status,vm:vms.find(v=>v.id===r.vm_id),job:jobs.find(j=>j.id===r.job_id),reason:r.decision_reason,decidedBy:r.decided_by_name,createdAt:r.created_at,decidedAt:r.decided_at,purpose:r.reason,summary:`${owner(r.owner_id)} · คำขอ #${r.id}`,cancel:r.status==="pending"&&r.owner_id===me.id})),
  };
  const sorted=(list:Row[])=>[...list].sort((a,b)=>b.id-a.id);
  const done=(row:Row)=>describeRequest(row.status,row.kind,row.vm,row.job).done;
  const current=sorted(rows[section]);
  // A finished request stays until its result is viewed, then one more hour.
  const visible=current.filter(row=>!done(row)||fresh.has(row.key)||unseen.has(row.key)||recentlySeen(row.key));
  const history=current.filter(row=>!visible.includes(row));
  const render=(row:Row)=>{
    const {state,label}=describeRequest(row.status,row.kind,row.vm,row.job);
    const steps:Step[]=requestSteps(row.status,row.createdAt,row.decidedAt,row.job);const latest=lastStep(steps);
    return <RequestCard key={row.key} className={`status-row${fresh.has(row.key)?" is-updated":""}`} title={row.title} state={state} label={label}
      flag={fresh.has(row.key)&&<span className="badge update-badge">อัปเดตใหม่</span>} summary={<>{row.summary}{latest&&<span className="summary-time"> · {thaiTime(latest)}</span>}</>}
      details={<>
        <RequestOutcome status={row.status} kind={row.kind} vm={row.vm} job={row.job} reason={row.reason} decidedBy={row.decidedBy}/>
        <DetailFacts items={[`คำขอ #${row.id}`,...(row.specs??[]).map(([name,value])=>`${name} ${value}`)]}/>
        <DetailRow label="เหตุผลที่ขอ">{row.purpose??"คำขอเดิมยังไม่มีข้อมูลเหตุผล"}</DetailRow>
        <Timeline steps={steps}/>
      </>}
      actions={row.cancel&&<button disabled={busy} onClick={()=>onCancelReset(row.id)}>ยกเลิกคำขอรีเซ็ต</button>}/>;
  };
  const label=statusSections.find(([id])=>id===section)![1];
  return <>
    <div ref={tabs} className="section-tabs status-tabs" role="tablist" aria-label="ประเภทคำขอ">
      {statusSections.map(([id,name])=>{const count=[...unseen].filter(key=>key.startsWith(id+"-")).length;return <button key={id} role="tab" aria-selected={section===id} className={section===id?"selected":""} onClick={()=>setSection(id)}>{name}{count>0&&<span className="nav-count" aria-label={`อัปเดตใหม่ ${count} รายการ`}>{count}</span>}</button>;})}
    </div>
    <section className="panel">
      <div className="section-head"><h2>คำขอ{label}{admin?"":" ของฉัน"}</h2><div className="actions">{section==="create"&&<button onClick={onNewRequest}>+ ขอสร้าง VM</button>}<HistoryPopup title={`ประวัติคำขอ${label}`} label="ประวัติ" count={history.length}>{history.map(render)}</HistoryPopup></div></div>
      {visible.map(render)}
      {!visible.length&&<div className="empty">{section==="create"?"ยังไม่มีคำขอที่กำลังดำเนินการ":section==="delete"?"ยังไม่มีคำขอลบ VM ที่กำลังดำเนินการ ขอลบได้จากเมนูจัดการของ VM":"ยังไม่มีคำขอรีเซ็ตรหัสที่กำลังดำเนินการ ขอได้จากเมนูจัดการของ VM"}</div>}
    </section>
  </>;
}
