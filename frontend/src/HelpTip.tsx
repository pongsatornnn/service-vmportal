import { ReactNode, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
export function HelpTip({label,children,id:providedId}:{label:string;children:ReactNode;id?:string}){
 const unique=useId(),id=providedId??unique;
 const [pinned,setPinned]=useState(false),[hover,setHover]=useState(false),[focused,setFocused]=useState(false),[position,setPosition]=useState({top:0,left:0});
 const anchor=useRef<HTMLSpanElement>(null),panel=useRef<HTMLSpanElement>(null);const open=pinned||hover||focused;
 function close(){setPinned(false);setHover(false);setFocused(false);}
 useLayoutEffect(()=>{if(!open)return;function place(){if(!anchor.current||!panel.current)return;const r=anchor.current.getBoundingClientRect(),w=panel.current.offsetWidth,h=panel.current.offsetHeight,pad=12;setPosition({left:Math.max(pad,Math.min(r.left-12,window.innerWidth-w-pad)),top:r.bottom+8+h<=window.innerHeight-pad?r.bottom+8:Math.max(pad,r.top-h-8)});}place();window.addEventListener('resize',place);window.addEventListener('scroll',place,true);return()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);};},[open]);
 useEffect(()=>{if(!open)return;function outside(e:PointerEvent){const target=e.target as Node;if(!anchor.current?.contains(target)&&!panel.current?.contains(target))close();}function escape(e:KeyboardEvent){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();}}document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};},[open]);
 return <span className="help-tip-anchor">
  <span ref={anchor} role="button" tabIndex={0} className="help-circle" onMouseEnter={()=>{if(window.matchMedia("(hover: hover)").matches)setHover(true);}} onMouseLeave={()=>setHover(false)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();setPinned(v=>!v);}}} aria-label={label} aria-expanded={open} aria-controls={id} onClick={e=>{e.preventDefault();e.stopPropagation();setPinned(v=>!v);}} onFocus={e=>{if(e.currentTarget.matches(':focus-visible'))setFocused(true);}} onBlur={()=>setFocused(false)}><span aria-hidden="true">?</span></span>
  {createPortal(<span id={id} ref={panel} role="tooltip" hidden={!open} className="help-tip-panel" style={{top:position.top,left:position.left}}>{children}</span>,anchor.current?.closest('dialog')??document.body)}
 </span>;
}
