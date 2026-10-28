import type { Dashboard } from "./types";

export type Draft={cpu:number;ram:number;disk:number};
export const defaultDraft:Draft={cpu:2,ram:2048,disk:25};
const items:[keyof Draft|"vms",string,string][]=[["vms","VM",""],["cpu","vCPU",""],["ram","RAM"," MiB"],["disk","Disk"," GiB"]];

// What is still free once approved VMs and pending requests are counted.
export function quotaShortfall(dashboard:Dashboard,draft:Draft){
  const reserved=dashboard.reserved??dashboard.usage;
  return items.map(([key,label,unit])=>{
    const quota=dashboard.user[`quota_${key}`],used=reserved[key]??0;
    const left=Math.max(quota-used,0);
    const asked=key==="vms"?1:draft[key];
    return {key,label,unit,quota,used,left,asked,over:asked>left};
  });
}

export function QuotaCheck({dashboard,draft}:{dashboard:Dashboard;draft:Draft}) {
  const rows=quotaShortfall(dashboard,draft);const over=rows.filter(row=>row.over);
  return <div className={`quota-check${over.length?" is-over":""}`} role={over.length?"alert":undefined}>
    <p className="quota-check-title">{over.length?"เกินโควตา ส่งคำขอไม่ได้":"โควตาที่ยังขอได้"} <span>(นับรวมคำขอที่รออนุมัติ)</span></p>
    <ul className="quota-bars">{rows.map(row=>{
      // Bar: already used or reserved, then what this request would add.
      const share=(value:number)=>row.quota>0?Math.min(value/row.quota,1)*100:100;
      const usedPct=share(row.used),askPct=row.over?100-usedPct:share(row.asked);
      const leftPct=row.quota>0?Math.round(row.left/row.quota*100):0;
      return <li key={row.key} className={row.over?"over":""}>
        <div className="quota-bar-label"><span>{row.label} <small>เหลือ {leftPct}%</small></span><span><strong>{row.left.toLocaleString("th-TH")}</strong> / {row.quota.toLocaleString("th-TH")}{row.unit}</span></div>
        <div className="quota-bar" role="img" aria-label={`${row.label} ใช้หรือจองแล้ว ${row.used} คำขอนี้ ${row.asked} จาก ${row.quota}${row.unit}`}><span className="used" style={{width:`${usedPct}%`}}/><span className="asking" style={{width:`${askPct}%`}}/></div>
      </li>;})}</ul>
    <p className="quota-legend"><span className="used">ใช้/จองแล้ว</span><span className="asking">คำขอนี้</span></p>
    {over.length>0&&<p className="quota-check-hint">{over.map(row=>row.key==="vms"?"จำนวน VM ครบโควตาแล้ว":`${row.label} ขอ ${row.asked.toLocaleString("th-TH")}${row.unit} แต่เหลือ ${row.left.toLocaleString("th-TH")}${row.unit}`).join(" · ")} กรุณาลดค่าที่ขอ หรือขอผู้ดูแลเพิ่มโควตา</p>}
  </div>;
}
