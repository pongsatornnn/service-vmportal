import { useEffect, useRef } from "react";
import { revealSelectedTab } from "./RequestStatus";
import { promptAction } from "./Dialogs";
import { HistoryPopup } from "./HistoryPopup";
import { statusLabel } from "./labels";
import { DetailFacts, DetailRow, Highlight, lastStep, RequestCard, Timeline } from "./RequestCard";
import { requestSteps } from "./RequestProgress";
import { thaiTime } from "./time";
import type { User, VM, VMRequest, Deletion, PasswordReset } from "./types";

type API = <T>(path: string, body?: unknown) => Promise<T>;
export type ApprovalSection="users"|"create"|"delete"|"reset";
const sections:[ApprovalSection,string][]=[["users","บัญชีผู้ใช้"],["create","สร้าง VM"],["delete","ลบ VM"],["reset","รีเซ็ตรหัส VM"]];
const decided=(status:string,name?:string|null)=>name&&status!=="pending"?<p className="decided-by">{status==="rejected"?"ปฏิเสธ":status==="cancelled"?"ยกเลิก":"อนุมัติ"}โดย Admin <strong>{name}</strong></p>:null;
// Submission and decision times, plus the latest of them for the one-line summary.
const timed=(summary:string,status:string,createdAt?:string,decidedAt?:string|null)=>{const steps=requestSteps(status,createdAt,decidedAt);const latest=lastStep(steps);return {summary:<>{summary}{latest&&<span className="summary-time"> · {thaiTime(latest)}</span>}</>,timeline:<Timeline steps={steps}/>};};
const hidden=["Admin confirmed hostname","Admin confirmed account cascade"];
// The admin's own words: why it was refused, or a note left with the decision.
const verdict=(status:string,reason?:string|null)=>{const text=reason?.trim();if(!text||hidden.includes(text))return null;return <Highlight tone={status==="rejected"?"danger":"info"} title={status==="rejected"?"เหตุผลที่ไม่อนุมัติ":"ผลพิจารณา"}>{text}</Highlight>;};
export function ApprovalInbox({users, requests, deletions, resets, vms, api, busy, decide, act, refresh, section, setSection}: {
  users: User[]; requests: VMRequest[]; deletions: Deletion[]; resets: PasswordReset[]; vms: VM[]; api: API; busy: boolean;
  decide: (path: string, approve: boolean) => Promise<void>; act: (fn: () => Promise<void>) => Promise<void>; refresh: () => Promise<void>;
  section: ApprovalSection; setSection: (section: ApprovalSection) => void;
}) {
  const rows=(history:boolean)=>({
    waitingUsers:users.filter(u=>history?u.status==="rejected":u.status==="pending"),
    create:requests.filter(r=>history?r.status!=="pending":r.status==="pending"),
    remove:deletions.filter(r=>{
      const active=r.status==="pending"||(r.status==="approved"&&vms.some(v=>v.id===r.vm_id&&v.status==="needs_review"));
      return history?!active:active;
    }),
    passwords:resets.filter(r=>history?!["pending","needs_review"].includes(r.status):["pending","needs_review"].includes(r.status)),
  });
  const owner=(id:number)=>users.find(u=>u.id===id)?.username??`Owner #${id}`;
  function renderContent(history:boolean){
    const all=rows(history);
    const waitingUsers=section==="users"?all.waitingUsers:[],create=section==="create"?all.create:[],remove=section==="delete"?all.remove:[],passwords=section==="reset"?all.passwords:[];
    const empty=!waitingUsers.length&&!create.length&&!remove.length&&!passwords.length;
    return <>
    {empty && <div className="empty">ไม่มีรายการรออนุมัติในหมวดนี้</div>}
    {waitingUsers.map(u=><RequestCard key={`user-${u.id}`} title={u.username} state={u.status} label={statusLabel(u.status)} summary={[`${u.first_name} ${u.last_name}`.trim(),"สมัครบัญชีใหม่"].filter(Boolean).join(" · ")}
      actions={u.status==="pending"&&<><button className="primary" disabled={busy} onClick={()=>void decide(`/admin/users/${u.id}/decision`,true)}>อนุมัติบัญชี</button><button disabled={busy} onClick={()=>void decide(`/admin/users/${u.id}/decision`,false)}>ปฏิเสธบัญชี</button></>}/>)}
    {create.map(r=><RequestCard key={`create-${r.id}`} title={r.hostname} state={r.status} label={statusLabel(r.status)} summary={timed(`${owner(r.owner_id)} · ${r.cpu}\u00a0vCPU · ${r.ram}\u00a0MiB · ${r.disk}\u00a0GiB`,r.status,r.created_at,r.decided_at).summary}
      details={<>{decided(r.status,r.decided_by_name)}{verdict(r.status,r.reason)}<DetailFacts items={[`คำขอ #${r.id}`,r.template_name&&`Template ${r.template_name}`,`เข้าเครื่องด้วย ${r.auth_method==="password"?"Password":"SSH Key"}`,r.guest_username&&`บัญชีในเครื่อง ${r.guest_username}`]}/><DetailRow label="เหตุผลที่ขอสร้าง">{r.request_reason??"คำขอเดิมยังไม่มีข้อมูลเหตุผล"}</DetailRow>{timed("",r.status,r.created_at,r.decided_at).timeline}</>}
      actions={r.status==="pending"&&<><button className="primary" disabled={busy} onClick={()=>void decide(`/admin/vm-requests/${r.id}/decision`,true)}>อนุมัติสร้าง VM</button><button disabled={busy} onClick={()=>void decide(`/admin/vm-requests/${r.id}/decision`,false)}>ปฏิเสธสร้าง VM</button></>}/>)}
    {remove.map(d=>{const vm=vms.find(v=>v.id===d.vm_id);const retry=d.status==="approved"&&vm?.status==="needs_review";return <RequestCard key={`delete-${d.id}`} title={vm?.hostname??`VM #${d.vm_id}`} state={retry?"needs_review":d.status} label={retry?"ลบไม่สำเร็จ · ต้องตรวจสอบ":statusLabel(d.status)} summary={timed(`${owner(d.owner_id)} · คำขอ #${d.id}`,d.status,d.created_at,d.decided_at).summary}
      details={<>{decided(d.status,d.decided_by_name)}{verdict(d.status,d.decision_reason)}{retry&&<Highlight tone="warning" title="ก่อนลองใหม่">ตรวจ Task ก่อน หากเดิมถูกปฏิเสธเพราะ VM ยังเปิดอยู่ ให้ Shutdown บน Proxmox แล้วลองใหม่ ระบบจะตรวจซ้ำก่อนรับงาน</Highlight>}<DetailRow label="เหตุผลที่ขอลบ">{d.reason}</DetailRow>{timed("",d.status,d.created_at,d.decided_at).timeline}</>}
      actions={<>{d.status==="pending"&&<><button className="danger" disabled={busy||!vm} onClick={async ()=>{if(!vm)return;const name=await promptAction(`อนุมัติลบ VM ถาวร: ${vm.hostname}`,{expected:vm.hostname,danger:true});if(name===null)return;void act(async()=>{await api(`/admin/deletion-requests/${d.id}/decision`,{approve:true,reason:"Admin confirmed hostname",confirm_hostname:name});await refresh();});}}>อนุมัติลบ</button><button disabled={busy} onClick={()=>void decide(`/admin/deletion-requests/${d.id}/decision`,false)}>ปฏิเสธลบ</button></>}
        {retry&&vm&&<button disabled={busy} onClick={async ()=>{const name=await promptAction(`ลองลบ VM ถาวรอีกครั้ง: ${vm.hostname}`,{expected:vm.hostname,danger:true});if(name===null)return;void act(async()=>{await api(`/admin/deletion-requests/${d.id}/retry`,{confirm_hostname:name});await refresh();});}}>ตรวจและลองลบอีกครั้ง (Admin)</button>}</>}/>;})}
    {passwords.map(r=><RequestCard key={`password-${r.id}`} title={vms.find(v=>v.id===r.vm_id)?.hostname??`VM #${r.vm_id}`} state={r.status} label={statusLabel(r.status)} summary={timed(`${owner(r.owner_id)} · คำขอ #${r.id}`,r.status,r.created_at,r.decided_at).summary}
      details={<>{decided(r.status,r.decided_by_name)}{verdict(r.status,r.decision_reason)}{r.status==="needs_review"&&<Highlight tone="warning" title="ผลคำสั่งไม่แน่นอน">ต้องตรวจ Guest ก่อนส่งคำขอใหม่ รหัสผ่านที่ส่งไว้ถูกลบจาก Portal แล้ว</Highlight>}<DetailRow label="เหตุผลที่ขอรีเซ็ต">{r.reason}</DetailRow>{timed("",r.status,r.created_at,r.decided_at).timeline}</>}
      actions={r.status==="pending"&&<><button className="primary" disabled={busy} onClick={()=>void decide(`/admin/vm-password-resets/${r.id}/decision`,true)}>อนุมัติรีเซ็ตรหัส VM</button><button disabled={busy} onClick={()=>void decide(`/admin/vm-password-resets/${r.id}/decision`,false)}>ปฏิเสธรีเซ็ต</button><button disabled={busy} onClick={()=>void act(async()=>{await api(`/vm-password-resets/${r.id}/cancel`,{});await refresh();})}>ยกเลิกคำขอ</button></>}/>)}
    </>;
  }
  const pick=(r:ReturnType<typeof rows>,id:ApprovalSection)=>id==="users"?r.waitingUsers:id==="create"?r.create:id==="delete"?r.remove:r.passwords;
  const active=rows(false),old=rows(true);
  // Open on the first queue that has work unless a redirect chose one with items.
  useEffect(()=>{
    if(pick(active,section).length)return;
    const first=sections.find(([id])=>pick(active,id).length);
    if(first)setSection(first[0]);
  },[]);
  const tabs=useRef<HTMLDivElement>(null);
  useEffect(()=>revealSelectedTab(tabs.current),[section]);
  const label=sections.find(([id])=>id===section)![1];
  return <>
    <div ref={tabs} className="section-tabs approval-tabs" role="tablist" aria-label="ประเภทคำขอที่รออนุมัติ">
      {sections.map(([id,name])=>{const count=pick(active,id).length;return <button key={id} role="tab" aria-selected={section===id} className={section===id?"selected":""} onClick={()=>setSection(id)}>{name}{count>0&&<span className="nav-count" aria-label={`รออนุมัติ ${count} รายการ`}>{count}</span>}</button>;})}
    </div>
    <section className="panel approval-inbox"><div className="section-head"><h2>รออนุมัติ · {label}</h2><HistoryPopup title="ประวัติคำขอ" label="ประวัติ" count={pick(old,section).length}>{renderContent(true)}</HistoryPopup></div>
      {renderContent(false)}
    </section>
  </>;
}
