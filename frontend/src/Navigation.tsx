import { BASE, at } from "./base";
import { useState } from "react";
import { FormDialog } from "./FormDialog";

const icons:Record<string,string>={
  overview:"M3 4h18v12H3z M8 20h8 M12 16v4",
  requests:"M5 3h14v18H5z M8 8h8 M8 12h8 M8 16h5",
  status:"M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l3 3",
  activity:"M3 12h4l3-8 4 16 3-8h4",
  approvals:"M9 3h6v4H9z M7 5H5v16h14V5h-2 M8 14l3 3 5-6",
  accounts:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M17 4a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-4",
  setup:"M4 7h16 M4 17h16 M8 4v6 M16 14v6",
  guide:"M12 5v16 M3 3l9 2 9-2v16l-9 2-9-2z",
  audit:"M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h8 M8 18h4",
};
export function Navigation({items,active,onNavigate}:{items:{id:string;label:string;count?:number}[];active:string;onNavigate:(id:string)=>void}) {
  const [open,setOpen]=useState(false);
  const pending=items.some(item=>item.count);
  return <>
    <button type="button" className={`nav-trigger${pending?" has-updates":""}`} aria-label="เปิดเมนูหลัก" aria-expanded={open} aria-haspopup="dialog" onClick={()=>setOpen(true)}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="M4 6h16 M4 12h16 M4 18h16"/></svg></button>
    {open&&<FormDialog title="เมนูหลัก" className="nav-drawer" dismissOutside onClose={()=>setOpen(false)}>
      <div className="nav-drawer-heading"><a className="brand" href={BASE}><img src={at("portal-mark.svg")} alt="" width="36" height="36"/><span>ICT - VM Portal</span></a><button type="button" className="nav-close" aria-label="ปิดเมนูหลัก" onClick={()=>setOpen(false)}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="m6 6 12 12 M18 6 6 18"/></svg></button></div>
      <nav aria-label="เมนูหลัก">{items.map(item=><button key={item.id} type="button" aria-current={active===item.id?"page":undefined} className={active===item.id?"selected":""} onClick={()=>{setOpen(false);onNavigate(item.id);window.scrollTo({top:0,behavior:"instant"});}}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={icons[item.id]??icons.requests}/></svg><span>{item.label}</span>{!!item.count&&<span className="nav-count">{item.count}</span>}</button>)}</nav>
    </FormDialog>}
  </>;
}
