import { ReactNode, useEffect, useRef } from "react";

export function FormDialog({title,busy=false,onClose,children,className="",dismissOutside=false}:{title:string;busy?:boolean;onClose:()=>void;children:ReactNode;className?:string;dismissOutside?:boolean}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const outsidePress=useRef(false);
  function outside(x:number,y:number){const r=dialog.current?.getBoundingClientRect();return !!r&&(x<r.left||x>r.right||y<r.top||y>r.bottom);}
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null;
    const element=dialog.current;
    element?.showModal();
    return ()=>{element?.close();if(previous?.isConnected)previous.focus();};
  },[]);
  return <dialog ref={dialog} className={`confirmation-dialog management-dialog ${className}`} aria-label={title} aria-busy={busy} onPointerDown={e=>{outsidePress.current=e.target===e.currentTarget&&outside(e.clientX,e.clientY);}} onClick={e=>{if(dismissOutside&&!busy&&outsidePress.current&&e.target===e.currentTarget&&outside(e.clientX,e.clientY))onClose();outsidePress.current=false;}} onCancel={e=>{e.preventDefault();if(!busy)onClose();}}>{children}</dialog>;
}
