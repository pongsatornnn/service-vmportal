import { ResourcePicker } from "./ResourcePicker";
import { useState } from "react";
import { HelpTip } from "./HelpTip";

export function NetworkPicker({networks,choices,busy,onChange}:{networks:string[];choices:string[];busy:boolean;onChange:(networks:string[])=>void}) {
  const [custom,setCustom]=useState(false);
  const selected=networks.filter(Boolean);
  const options=Array.from(new Set([...choices,...selected]));
  const rows=networks.length?networks:[""];
  return <fieldset className="network-picker" disabled={busy}>
    <legend><span className="field-title">เครือข่ายของ VM<HelpTip label="เกี่ยวกับ Network Bridge">เลือก Bridge ที่ต้องการเชื่อมต่อ หนึ่ง Bridge ที่เลือกเพิ่มการ์ดหนึ่งใบ ทุกขารับ IP แบบ DHCP โดยต้องมี DHCP ในเครือข่ายนั้น มีผลกับ VM ใหม่เท่านั้น หากต้องใช้ Bridge เดิมหลายใบ ให้เปิดกำหนดแต่ละขาเอง</HelpTip></span></legend>
    <div className="network-picker-heading"><p>ติ๊กเครือข่ายที่ต้องการใช้</p><span className="badge">{selected.length} ขา · DHCP</span></div>
    {!custom?<div className="network-options">{options.map(bridge=>{
      const count=selected.filter(value=>value===bridge).length;
      return <label className={`network-option${count?" selected":""}`} key={bridge}>
        <input type="checkbox" aria-label={`ใช้เครือข่าย ${bridge}`} checked={count>0} disabled={!count&&selected.length>=32} onChange={e=>onChange(e.target.checked?[...selected,bridge]:selected.filter(value=>value!==bridge))}/>
        <span><strong>{bridge}</strong><small>{count>1?`${count} ขา · `:""}รับ IP อัตโนมัติ{!choices.includes(bridge)?" · ค่าปัจจุบัน":""}</small></span>
        {count>0&&<span className="network-selected-mark" aria-hidden="true">✓</span>}
      </label>;
    })}</div>:<>
      <div className="network-rows">{rows.map((bridge,index)=><div className="network-choice" key={index}>
        <span className="network-number">ขา {index+1}</span>
        <label className="sr-only" htmlFor={`network-${index}`}>Bridge ของขา {index+1}</label>
        <ResourcePicker id={`network-${index}`} label={`Bridge ของขา ${index+1}`} value={bridge} options={options.map(value=>({value,label:value}))} pattern="[A-Za-z0-9_.-]{1,63}" placeholder="vmbr0" disabled={busy} onChange={value=>onChange(rows.map((previous,i)=>i===index?value:previous))}/>

        <button type="button" className="network-remove" disabled={rows.length===1} aria-label={`ลบขา ${index+1}`} onClick={()=>onChange(rows.filter((_,i)=>i!==index))}>×</button>
      </div>)}</div>
      <div className="network-add-row"><button type="button" className="network-add" disabled={rows.length>=32||rows.some(value=>!value)} onClick={()=>onChange([...rows,""])}>+ เพิ่มขา</button></div>
    </>}
    {!selected.length&&<small className="network-selection-help">เลือกอย่างน้อย 1 เครือข่าย</small>}
    {<label className="checkbox-label network-custom-toggle"><input type="checkbox" checked={custom} onChange={e=>{setCustom(e.target.checked);if(!e.target.checked)onChange(selected);}}/>กำหนดแต่ละขาเอง</label>}
    {!choices.length&&<small className="muted">{options.length?"ใช้ค่าที่บันทึกไว้ กดโหลดรายการใหม่เพื่อดูเครือข่ายอื่น":"กำลังรอรายการเครือข่ายจาก Proxmox"}</small>}
  </fieldset>;
}
