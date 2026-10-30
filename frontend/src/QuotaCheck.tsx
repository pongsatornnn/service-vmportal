import type { Dashboard } from "./types";

export type Draft={cpu:number;ram:number;disk:number};
export const defaultDraft:Draft={cpu:2,ram:2048,disk:25};
// The request form starts blank: fields show placeholders until the user types.
export const emptyDraft:Draft={cpu:0,ram:0,disk:0};
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

const cardLabels:Record<string,string>={vms:"VM",cpu:"vCPU",ram:"RAM · MiB",disk:"Disk · GiB"};
const number=(value:number)=>value.toLocaleString("th-TH");

// Quota cards: used or reserved so far (pending requests included). On the
// request form the bar also shows what this request would take.
export function QuotaCards({dashboard,draft}:{dashboard:Dashboard;draft?:Draft}) {
  const rows=quotaShortfall(dashboard,draft??defaultDraft);
  return <>
    <div className={`stats quota-cards${draft?" is-request":""}`}>
      {rows.map(row=>{
        const asking=!!draft;
        const share=(value:number)=>row.quota>0?Math.min(value/row.quota,1)*100:100;
        const usedPct=share(row.used),askPct=!asking?0:row.over?100-usedPct:share(row.asked);
        const note=!asking?`เหลือ ${number(row.left)}`:row.over?(row.key==="vms"?"ครบโควตาแล้ว":`เกิน: ขอ ${number(row.asked)} เหลือ ${number(row.left)}`):`คำขอนี้ +${number(row.asked)} · เหลือ ${number(row.left-row.asked)}`;
        return <section className={`panel stat quota-card${asking&&row.over?" over":""}`} key={row.key}>
          <span>{cardLabels[row.key]}</span>
          <strong>{number(row.used)}<small> / {number(row.quota)}</small></strong>
          <div className="quota-bar" role="img" aria-label={`${cardLabels[row.key]} ใช้หรือจองแล้ว ${row.used}${asking?` คำขอนี้ ${row.asked}`:""} จาก ${row.quota}`}><span className="used" style={{width:`${usedPct}%`}}/>{asking&&<span className="asking" style={{width:`${askPct}%`}}/>}</div>
          <small className="quota-note">{note}</small>
        </section>;
      })}
    </div>
    {draft&&<p className="quota-legend"><span className="used">ใช้/จองแล้ว (รวมคำขอรออนุมัติ)</span><span className="asking">คำขอนี้</span></p>}
  </>;
}
