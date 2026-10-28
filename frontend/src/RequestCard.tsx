import { ReactNode, useId, useState } from "react";
import { thaiTime } from "./time";

// One line of facts with the status up front; the rest opens on demand.
export function RequestCard({title,state,label,summary,details,actions,className="",flag}:{
  title:string;state:string;label:string;summary:ReactNode;details?:ReactNode;actions?:ReactNode;className?:string;flag?:ReactNode;
}) {
  const [open,setOpen]=useState(false);const id=useId();
  return <article className={`request request-card ${className}`}>
    <div className="request-card-head"><strong className="request-card-title">{title}</strong>{flag}<span className={`badge status-badge ${state}`}>{label}</span></div>
    <p className="request-card-summary">{summary}</p>
    {details&&<button type="button" className="link details-toggle" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(v=>!v)}>{open?"ซ่อนรายละเอียด":"ดูรายละเอียด"}<span className="dropdown-chevron" aria-hidden="true"/></button>}
    {details&&<div id={id} className="request-details" hidden={!open}>{details}</div>}
    {actions&&<div className="actions request-card-actions">{actions}</div>}
  </article>;
}

// The sentence a reader most needs (a reason, an admin message) set apart from the rest.
export function Highlight({tone="info",title,children}:{tone?:"info"|"danger"|"success"|"warning";title:string;children:ReactNode}) {
  return <div className={`detail-highlight ${tone}`}><strong>{title}</strong><p>{children}</p></div>;
}

// Short facts on one wrapping line: "คำขอ #5 · Password · บัญชีในเครื่อง dev".
export function DetailFacts({items}:{items:(ReactNode|false|null|undefined)[]}) {
  return <p className="detail-facts">{items.filter(Boolean).map((item,index)=><span key={index}>{item}</span>)}</p>;
}

// Each step with the moment it happened, in Thai time: ส่งคำขอ → อนุมัติ → เสร็จ.
export type Step=[string,string|null|undefined];
export function Timeline({steps}:{steps:Step[]}) {
  const shown=steps.filter((step):step is [string,string]=>!!step[1]);
  if(!shown.length)return null;
  return <ol className="timeline">{shown.map(([label,at])=><li key={label}><span>{label}</span> <time dateTime={at}>{thaiTime(at)}</time></li>)}</ol>;
}
export const lastStep=(steps:Step[])=>[...steps].reverse().find(step=>step[1])?.[1];

export function DetailRow({label,children}:{label:string;children:ReactNode}) {
  return <p className="detail-row"><span>{label}</span> {children}</p>;
}
