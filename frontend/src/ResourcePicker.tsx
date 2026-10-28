import { useEffect, useRef, useState } from "react";
type Option={value:string;label:string};
export function ResourcePicker({id,label,value,options,onChange,onCommit,numeric=false,min,max,pattern,disabled=false}:{id:string;label:string;value:string;options:Option[];onChange:(value:string)=>void;onCommit?:(value:string)=>void;numeric?:boolean;min?:number;max?:number;pattern?:string;disabled?:boolean}) {
  const [manual,setManual]=useState(false);
  const input=useRef<HTMLInputElement>(null),select=useRef<HTMLSelectElement>(null),initial=useRef(value);
  useEffect(()=>{if(manual)input.current?.focus();},[manual]);
  useEffect(()=>{
    const number=Number(value);
    const invalid=numeric&&value!==''&&(!Number.isInteger(number)||(min!==undefined&&number<min)||(max!==undefined&&number>max));
    select.current?.setCustomValidity(invalid?`กรุณาระบุ ${label} เป็นจำนวนเต็ม${min!==undefined?` ตั้งแต่ ${min}`:''}${max!==undefined?` ถึง ${max}`:''}`:'');
  },[value,numeric,min,max,manual,label]);
  const choices=Array.from(new Map(options.map(option=>[option.value,option])).values());
  if(!manual&&choices.length)return <div className="resource-picker"><select ref={select} id={id} aria-label={label} required disabled={disabled} value={value} onChange={e=>{
    if(e.target.value===':manual:'){setManual(true);return;}
    onChange(e.target.value);onCommit?.(e.target.value);
  }}><option value="" disabled>เลือกรายการ</option>{value&&!choices.some(option=>option.value===value)&&<option value={value}>{value} · ค่าปัจจุบัน</option>}{choices.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}<option value=":manual:">กรอกค่าเอง…</option></select></div>;
  return <div className="resource-picker editable"><input ref={input} id={id} aria-label={label} type={numeric?'number':'text'} min={min} max={max} pattern={pattern} required disabled={disabled} value={value} onFocus={()=>{initial.current=value;setManual(true);}} onChange={e=>onChange(e.target.value)} onBlur={e=>{if(e.target.value!==initial.current)onCommit?.(e.target.value);}}/>{choices.length>0&&<button type="button" aria-label={`เลือกรายการ ${label}`} disabled={disabled} onClick={()=>setManual(false)}>▾</button>}</div>;
}
