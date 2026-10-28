import { HelpTip } from "./HelpTip";
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
type Options = {input?: boolean; expected?: string; required?: boolean; danger?: boolean};
function ask(message: string, options: Options = {}): Promise<string | null> {
  return new Promise(resolve => {
    const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const previous=document.activeElement as HTMLElement|null;
    let settled=false;
    function finish(value:string|null){if(settled)return;settled=true;resolve(value);setTimeout(()=>{root.unmount();host.remove();if(previous?.isConnected)previous.focus();},0);}
    function Popup(){
      const dialog=useRef<HTMLDialogElement>(null),[value,setValue]=useState('');
      useEffect(()=>{dialog.current?.showModal();return()=>dialog.current?.close();},[]);
      const valid=options.expected!==undefined?value===options.expected:!options.required||!!value.trim();
      function confirm(){if(valid){const result=value;setValue("");finish(result);}}
      return <dialog ref={dialog} className="confirmation-dialog" aria-labelledby="confirmation-title" aria-describedby="confirmation-message" onCancel={e=>{e.preventDefault();finish(null);}}>
        <h2 id="confirmation-title">{options.danger?'ยืนยันคำสั่งสำคัญ':'ยืนยันการดำเนินการ'}</h2><p id="confirmation-message">{message}</p>
        <div className="dialog-fields" data-form-type="other">
          {options.input&&<label><span className="field-title">{options.expected!==undefined?'พิมพ์ชื่อเครื่องให้ตรง':'รายละเอียด / เหตุผล'}{options.expected!==undefined&&<HelpTip label="วิธีพิมพ์ชื่อยืนยัน">ต้องตรงกับ {options.expected} ทุกตัวอักษร</HelpTip>}</span>
            {options.expected!==undefined?<input autoFocus type="text" value={value} onChange={e=>setValue(e.target.value)} required maxLength={2000} autoComplete="off" autoCapitalize="none" spellCheck={false} data-lpignore="true" data-1p-ignore="true" onKeyDown={e=>{if(e.key==="Enter"&&!e.nativeEvent.isComposing){e.preventDefault();confirm();}}}/>:<textarea autoFocus value={value} onChange={e=>setValue(e.target.value)} required={options.required} maxLength={2000} autoComplete="off" data-lpignore="true" data-1p-ignore="true"/>}
          </label>}
          <div className="dialog-actions"><button type="button" autoFocus={!options.input} onClick={()=>finish(null)}>ยกเลิก</button><button className={options.danger?'danger-solid':'primary'} disabled={!valid} type="button" onClick={confirm}>ยืนยัน</button></div>
        </div>
      </dialog>;
    }
    root.render(<Popup/>);
  });
}
export async function confirmAction(message:string){return (await ask(message,{danger:true}))!==null;}
export function promptAction(message:string, options:Options={}){return ask(message,{input:true,...options});}
