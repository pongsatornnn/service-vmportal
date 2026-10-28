import { FormDialog } from "./FormDialog";
import { explainError } from "./errors";
import { FormEvent, useState } from "react";
import type { User } from "./types";
import { wholeNumber } from "./wholeNumber";
type API = <T>(path: string, body?: unknown) => Promise<T>;
export function QuotaForm({api,users,onClose,onDone}: {api: API;users: User[];onClose:()=>void;onDone:()=>void}) {
  const user=users[0];
  const title=users.length===1?`สิทธิ์ใช้ทรัพยากรของ ${user.username}`:`กำหนดสิทธิ์ใช้ทรัพยากร ${users.length} คน`;
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  async function save(e: FormEvent<HTMLFormElement>){
    e.preventDefault();const data=new FormData(e.currentTarget);setBusy(true);setError("");
    try{await api(users.length===1?`/admin/users/${user.id}/quota`:"/admin/users/quota/bulk",{...Object.fromEntries(["quota_vms","quota_cpu","quota_ram","quota_disk"].map(k=>[k,Number(data.get(k))])),...(users.length>1?{user_ids:users.map(u=>u.id)}:{})});onDone();}catch(e){setError(explainError(e));}finally{setBusy(false);}
  }
  return <FormDialog title={title} busy={busy} onClose={onClose}><section className="panel quota-editor"><div className="section-head"><h3>{title}</h3><button type="button" disabled={busy} onClick={onClose}>ปิด</button></div>{users.length>1&&<p>ใช้ค่าเดียวกันกับทุกบัญชีที่เลือก: {users.map(u=>u.username).join(", ")} หากมีบัญชีใดใช้ทรัพยากรเกินค่าใหม่ จะไม่บันทึกทั้งชุด</p>}<form onSubmit={save}><div className="fields">{([
    ["quota_vms","จำนวน VM",1000],["quota_cpu","vCPU รวม",10000],["quota_ram","RAM รวม (MiB)",100000000],["quota_disk","Disk รวม (GiB)",10000000]
  ] as const).map(([key,label,max])=><label key={key}>{label}<input name={key} {...wholeNumber} min={0} max={max} defaultValue={Math.max(...users.map(u=>u[key]))} required/></label>)}</div>{error&&<p role="alert" className="error">{error}</p>}<button className="primary" disabled={busy}>บันทึกสิทธิ์ใช้ทรัพยากร</button></form></section></FormDialog>;
}
