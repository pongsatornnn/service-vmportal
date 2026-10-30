import { FormEvent, useEffect, useState } from "react";
import { ActionMenu } from "./ActionMenu";
import { confirmAction } from "./Dialogs";
import { explainError } from "./errors";
import { FormDialog } from "./FormDialog";
import { HelpTip } from "./HelpTip";
import { ResourcePicker } from "./ResourcePicker";
import { thaiTime } from "./time";
import { Toast } from "./Toast";
import type { Template } from "./types";
import { wholeNumber } from "./wholeNumber";

type API = <T>(path: string, body?: unknown) => Promise<T>;
type Draft = {name:string;description:string;vmid:string;disk_device:string;min_disk_gb:string};
type Choices = {templates:{id:number;name:string}[];disks:{id:string;minimum_gib:number|null}[];boot_disk:string|null};
type Saved = {values:{url:string;token_id:string;ca_pem:string;node:string}};

const empty:Draft={name:"",description:"",vmid:"",disk_device:"",min_disk_gb:""};
// One state per template: users can request it only when it is verified and enabled.
const stateOf=(t:Template)=>!t.verified?{state:"needs_review",label:"ยังไม่ผ่านการตรวจสอบ"}:t.enabled?{state:"succeeded",label:"เปิดให้ขอ"}:{state:"cancelled",label:"ตรวจผ่าน · ปิดอยู่"};

export function TemplateManager({api}:{api:API}) {
  const [templates,setTemplates]=useState<Template[]|null>(null);
  const [editing,setEditing]=useState<Template|"new"|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  async function load(){try{setTemplates(await api<Template[]>("/templates"));}catch(e){setError(explainError(e));}}
  useEffect(()=>{void load();},[]);
  async function run(work:()=>Promise<unknown>,done:string){
    if(busy)return;setBusy(true);setError("");
    try{await work();setNotice(done);await load();}catch(e){setError(explainError(e));await load();}finally{setBusy(false);}
  }
  const verify=(t:Template)=>run(()=>api(`/admin/templates/${t.id}/verify`,{}),`ตรวจสอบ ${t.name} ผ่านแล้ว เปิดให้ขอได้`);
  const toggle=(t:Template)=>run(()=>api(`/admin/templates/${t.id}/enabled`,{enabled:!t.enabled}),t.enabled?`ปิด ${t.name} แล้ว ผู้ใช้จะไม่เห็นในฟอร์มขอ`:`เปิดให้ผู้ใช้ขอ ${t.name} แล้ว`);
  async function remove(t:Template){
    if(!(await confirmAction(`ลบ Template "${t.name}" ออกจาก Portal? ผู้ใช้จะเลือกไม่ได้อีก VM ที่สร้างไปแล้วไม่กระทบ และประวัติคำขอยังแสดงชื่อเดิม (ไม่ลบ Template ใน Proxmox)`)))return;
    await run(()=>api(`/admin/templates/${t.id}/delete`,{}),`ลบ ${t.name} แล้ว`);
  }
  return <section className="panel template-manager">
    <div className="section-head"><div className="help-heading"><h2>Template ที่ให้ผู้ใช้เลือก</h2><HelpTip label="เกี่ยวกับ Template">ตั้งชื่อที่ผู้ใช้เห็น เช่น Ubuntu 24.04 แล้วผูกกับ Template VMID ใน Proxmox กดตรวจสอบให้ผ่านก่อนจึงเปิดให้ขอได้ หากแก้ VMID, Boot disk หรือ Disk ขั้นต่ำ หรือเปลี่ยนการเชื่อมต่อ Proxmox ต้องตรวจสอบใหม่ คำขอที่อนุมัติแล้วใช้ค่าตอนอนุมัติเสมอ</HelpTip></div><button type="button" className="primary" disabled={busy} onClick={()=>setEditing("new")}>+ เพิ่ม Template</button></div>
    {error&&<p className="alert error" role="alert">{error}</p>}<Toast message={notice} onClose={()=>setNotice("")}/>
    {templates===null?<p className="muted">กำลังโหลด…</p>:!templates.length?<div className="empty">ยังไม่มี Template กด "+ เพิ่ม Template" เพื่อเริ่ม ผู้ใช้จะยังขอ VM ไม่ได้จนกว่าจะมี Template ที่เปิดให้ขอ</div>:
      templates.map(t=>{const {state,label}=stateOf(t);return <article className="request template-row" key={t.id}>
        <div className="request-card-head"><strong className="request-card-title">{t.name}</strong><span className={`badge status-badge ${state}`}>{label}</span></div>
        <p className="request-card-summary">VMID {t.vmid} · {t.disk_device} · Disk ขั้นต่ำ {t.min_disk_gb}&nbsp;GiB{t.requests?` · ใช้ในคำขอ ${t.requests} รายการ`:""}{t.in_use?` (รออนุมัติ ${t.in_use})`:""}</p>
        {t.description&&<p className="template-description">{t.description}</p>}
        {t.verified&&t.verified_at&&<p className="job-times">ตรวจผ่านเมื่อ {thaiTime(t.verified_at)}</p>}
        <div className="template-actions">
          {!t.verified&&<button type="button" className="primary" disabled={busy} onClick={()=>void verify(t)}>ตรวจสอบ</button>}
          {t.verified&&<button type="button" className={t.enabled?"":"primary"} disabled={busy} onClick={()=>void toggle(t)}>{t.enabled?"ปิดไม่ให้ขอ":"เปิดให้ขอ"}</button>}
          <ActionMenu className="template-menu" label="จัดการ" ariaLabel={`จัดการ ${t.name}`}>
            <button type="button" disabled={busy} onClick={()=>setEditing(t)}>แก้ไข</button>
            {t.verified&&<button type="button" disabled={busy} onClick={()=>void verify(t)}>ตรวจสอบอีกครั้ง</button>}
            <button type="button" className="danger menu-danger" disabled={busy||t.in_use>0} onClick={()=>void remove(t)}>{t.in_use?"ลบไม่ได้ (มีคำขอรออนุมัติ)":"ลบ Template"}</button>
          </ActionMenu>
        </div>
      </article>;})}
    {editing&&<TemplateForm api={api} template={editing==="new"?null:editing} onClose={()=>setEditing(null)} onSaved={async(saved,needsCheck)=>{setEditing(null);setNotice(needsCheck?`บันทึก ${saved.name} แล้ว กดตรวจสอบก่อนเปิดให้ขอ`:`บันทึก ${saved.name} แล้ว`);await load();}}/>}
  </section>;
}

function TemplateForm({api,template,onClose,onSaved}:{api:API;template:Template|null;onClose:()=>void;onSaved:(saved:Template,needsCheck:boolean)=>Promise<void>}) {
  const [draft,setDraft]=useState<Draft>(template?{name:template.name,description:template.description,vmid:String(template.vmid),disk_device:template.disk_device,min_disk_gb:String(template.min_disk_gb)}:empty);
  const [choices,setChoices]=useState<Choices|null>(null),[looking,setLooking]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  // Read the node's templates and the chosen one's disks with the saved connection.
  async function discover(vmid:string){
    setLooking(true);
    try{
      const saved=await api<Saved>("/admin/settings");const v=saved.values;
      if(!v?.url){setChoices(null);return;}
      const result=await api<Choices>("/admin/settings/resources",{url:v.url,token_id:v.token_id,token_secret:null,ca_pem:v.ca_pem,node:v.node||null,template:Number(vmid)>=100?Number(vmid):null});
      setChoices(result);
      if(Number(vmid)>=100&&result.disks.length){
        setDraft(old=>{const disk=result.disks.find(d=>d.id===(old.disk_device||result.boot_disk||""))??result.disks.find(d=>d.id===result.boot_disk)??result.disks[0];
          const minimum=disk?.minimum_gib??1;return {...old,disk_device:old.disk_device||disk.id,min_disk_gb:String(Math.max(Number(old.min_disk_gb)||0,minimum))};});
      }
    }catch{setChoices(null);}finally{setLooking(false);}
  }
  useEffect(()=>{void discover(draft.vmid);},[]);
  async function save(e:FormEvent){
    e.preventDefault();if(busy)return;setBusy(true);setError("");
    const body={name:draft.name,description:draft.description,vmid:Number(draft.vmid),disk_device:draft.disk_device,min_disk_gb:Number(draft.min_disk_gb)};
    try{
      const saved=await api<Template>(template?`/admin/templates/${template.id}`:"/admin/templates",body);
      await onSaved(saved,!saved.verified);
    }catch(err){setError(explainError(err));}finally{setBusy(false);}
  }
  const templateOptions=(choices?.templates??[]).map(t=>({value:String(t.id),label:`${t.id} · ${t.name||"Template"}`}));
  const diskOptions=(choices?.disks??[]).map(d=>({value:d.id,label:`${d.id}${d.minimum_gib?` · ${d.minimum_gib} GiB`:""}`}));
  const detected=choices?.disks.find(d=>d.id===draft.disk_device);
  const minimum=detected?.minimum_gib??1;
  const vmidChosen=Number(draft.vmid)>=100;
  return <FormDialog title={template?`แก้ไข ${template.name}`:"เพิ่ม Template"} busy={busy} onClose={onClose}><section className="panel template-form">
    <div className="section-head"><h2>{template?`แก้ไข ${template.name}`:"เพิ่ม Template"}</h2><button type="button" disabled={busy} onClick={onClose}>ปิด</button></div>
    {error&&<p className="alert error" role="alert">{error}</p>}
    <form onSubmit={save} autoComplete="off" data-form-type="other">
      <label><span className="field-title">ชื่อที่ผู้ใช้เห็น</span><input name="template_name" required maxLength={40} placeholder="Ubuntu 24.04" value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>
      <label><span className="field-title">คำอธิบายสั้น ๆ <span className="muted">(ไม่บังคับ)</span></span><input name="template_description" maxLength={200} placeholder="LTS พร้อม Docker" value={draft.description} onChange={e=>setDraft({...draft,description:e.target.value})}/></label>
      <label><span className="field-title">Template ใน Proxmox (VMID)</span><ResourcePicker id="template-vmid" label="Template VMID" value={draft.vmid} options={templateOptions} numeric min={100} max={999999999} placeholder="9000" disabled={busy} onChange={value=>setDraft({...draft,vmid:value,disk_device:"",min_disk_gb:""})} onCommit={value=>void discover(value)}/></label>
      <div className="fields">
        <label><span className="field-title">Boot disk</span><ResourcePicker id="template-disk" label="Boot disk" value={draft.disk_device} options={diskOptions} pattern="(scsi|sata|virtio)[0-9]{1,2}" placeholder="scsi0" disabled={busy} onChange={value=>setDraft({...draft,disk_device:value,min_disk_gb:String(Math.max(Number(draft.min_disk_gb)||0,(choices?.disks.find(d=>d.id===value)?.minimum_gib)??1))})}/></label>
        <label><span className="field-title">Disk ขั้นต่ำ (GiB)</span><input name="template_min_disk" {...wholeNumber} required min={minimum} max={2048} placeholder={String(Math.max(minimum,10))} value={draft.min_disk_gb} onChange={e=>setDraft({...draft,min_disk_gb:e.target.value})}/></label>
      </div>
      <p className={`template-detected${detected?" found":""}`} role="status">{looking?"กำลังอ่าน Boot disk และขนาด Disk จาก Proxmox…":!vmidChosen?"เลือก Template ก่อน ระบบจะดึง Boot disk และขนาด Disk จาก Proxmox ให้":detected?`ดึงจาก Proxmox แล้ว: Boot disk ${detected.id} ขนาด ${detected.minimum_gib??"ไม่ทราบ"} GiB · Disk ขั้นต่ำต้องไม่น้อยกว่านี้ ปรับให้มากขึ้นได้`:choices?"อ่านขนาด Disk ของ Template นี้ไม่ได้ กรุณากรอก Boot disk และ Disk ขั้นต่ำเอง":"อ่านรายการจาก Proxmox ไม่ได้ กรุณากรอก Boot disk และ Disk ขั้นต่ำเอง"}</p>
      <p className="muted template-form-note">{template?.verified?"ถ้าแก้ VMID, Boot disk หรือ Disk ขั้นต่ำ ต้องตรวจสอบใหม่และจะปิดให้ขอชั่วคราว":"บันทึกแล้วกดตรวจสอบก่อนเปิดให้ขอ"}</p>
      <button className="primary" disabled={busy}>{busy?"กำลังบันทึก…":"บันทึก Template"}</button>
    </form>
  </section></FormDialog>;
}
