import { useEffect, useRef, useState } from "react";

export function Toast({message,onClose}:{message:string;onClose:()=>void}) {
  const element=useRef<HTMLDivElement>(null);
  const close=useRef(onClose);
  close.current=onClose;
  const [paused,setPaused]=useState(false);
  useEffect(()=>{if(!message)setPaused(false);},[message]);
  useEffect(()=>{
    if(!message)return;
    const node=element.current;
    if(node?.showPopover){node.setAttribute('popover','manual');if(!node.matches(':popover-open'))node.showPopover();}
    if(paused)return;
    const timer=window.setTimeout(()=>close.current(),6000);
    return()=>window.clearTimeout(timer);
  },[message,paused]);
  if(!message)return null;
  return <div ref={element} className="save-toast" role="status" aria-live="polite" aria-atomic="true" onMouseEnter={()=>setPaused(true)} onMouseLeave={()=>setPaused(false)} onFocus={()=>setPaused(true)} onBlur={()=>setPaused(false)}>
    <span className="toast-check" aria-hidden="true">✓</span>
    <span className="toast-message">{message}</span>
    <button type="button" className="toast-close" aria-label="ปิดการแจ้งเตือน" onClick={onClose}>×</button>
  </div>;
}
