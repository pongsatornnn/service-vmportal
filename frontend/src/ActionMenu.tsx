import { ReactNode, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function ActionMenu({label, ariaLabel, children, className=""}: {label: string; ariaLabel: string; children: ReactNode; className?: string}) {
  const [open,setOpen]=useState(false),[position,setPosition]=useState({top:0,left:0,maxHeight:400});
  const trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null);const id=useId();
  function close(restore=false){setOpen(false);if(restore)trigger.current?.focus();}
  useLayoutEffect(()=>{
    if(!open)return;
    function place(){
      if(!trigger.current||!panel.current)return;
      const rect=trigger.current.getBoundingClientRect();const gap=8,pad=12;
      const width=panel.current.offsetWidth;const available=window.innerHeight-pad*2;
      const height=Math.min(panel.current.scrollHeight,available);
      const top=rect.bottom+gap+height<=window.innerHeight-pad?rect.bottom+gap:Math.max(pad,rect.top-gap-height);
      setPosition({top,left:Math.max(pad,Math.min(rect.right-width,window.innerWidth-width-pad)),maxHeight:available});
    }
    place();const first=panel.current?.querySelector<HTMLButtonElement>('button:not(:disabled)');first?.focus();
    window.addEventListener('resize',place);window.addEventListener('scroll',place,true);
    return()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);};
  },[open]);
  useEffect(()=>{
    if(!open)return;
    function outside(event: PointerEvent){const target=event.target as Node;if(!trigger.current?.contains(target)&&!panel.current?.contains(target))close();}
    function escape(event: KeyboardEvent){if(event.key==='Escape'){event.preventDefault();close(true);}}
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};
  },[open]);
  return <div className={`action-dropdown ${className}`}><button ref={trigger} id={`${id}-trigger`} type="button" className="dropdown-trigger" aria-label={ariaLabel} aria-expanded={open} aria-controls={open?id:undefined} onClick={()=>setOpen(v=>!v)} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();setOpen(true);}}}><span className="dropdown-label">{label}</span><span className="dropdown-chevron" aria-hidden="true"/></button>
    {open&&createPortal(<div id={id} ref={panel} role="group" aria-labelledby={`${id}-trigger`} className="dropdown-panel" style={{position:'fixed',top:position.top,left:position.left,maxHeight:position.maxHeight}} onClick={e=>{const button=(e.target as HTMLElement).closest('button');if(button&&!button.disabled)close(true);}} onKeyDown={e=>{
      const items=Array.from(panel.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')??[]);const at=items.indexOf(document.activeElement as HTMLButtonElement);
      if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?items.length-1:e.key==='ArrowDown'?(at+1)%items.length:(at-1+items.length)%items.length;items[next]?.focus();}
      if(e.key==='Tab'&&((e.shiftKey&&at===0)||(!e.shiftKey&&at===items.length-1))){e.preventDefault();close(true);}
    }}>{children}</div>,document.body)}
  </div>;
}
