import { ReactNode, useState } from "react";
import { FormDialog } from "./FormDialog";

// label: a shorter button text where the panel heading already names the list.
export function HistoryPopup({title,label,count,children}:{title:string;label?:string;count:number;children:ReactNode}) {
  const [open,setOpen]=useState(false);
  return <div className="history-control">
    <button type="button" aria-label={`${title} (${count})`} onClick={()=>setOpen(true)}>{label??title} ({count})</button>
    {open&&<FormDialog title={title} onClose={()=>setOpen(false)} className="history-dialog" dismissOutside><section className="panel history-content">
      <div className="section-head"><h2>{title}</h2><button type="button" onClick={()=>setOpen(false)}>ปิด</button></div>
      <div className="history-body">{count?children:<div className="empty">ยังไม่มีประวัติ</div>}</div>
    </section></FormDialog>}
  </div>;
}
