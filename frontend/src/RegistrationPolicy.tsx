const punctuation = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
export function passwordChecks(value:string,minLength=8){return [
 {label:`อย่างน้อย ${minLength} ตัวอักษร`,met:Array.from(value).length>=minLength&&Array.from(value).length<=128},
 {label:'ตัวพิมพ์ใหญ่ A–Z',met:/[A-Z]/.test(value)},
 {label:'ตัวพิมพ์เล็ก a–z',met:/[a-z]/.test(value)},
 {label:'ตัวเลข 0–9',met:/[0-9]/.test(value)},
 {label:'อักขระพิเศษ เช่น ! @ # $ %',met:Array.from(value).some(c=>punctuation.includes(c))},
];}
export function passwordValid(value:string,minLength=8){return passwordChecks(value,minLength).every(c=>c.met)&&!/[\x00-\x1f\x7f]/.test(value);}
export function registrationPasswordValid(value:string){return passwordValid(value);}
export function PasswordChecklist({value,minLength=8,checks=passwordChecks(value,minLength)}:{value:string;minLength?:number;checks?:{label:string;met:boolean}[]}){return <ul className="password-checklist" aria-label="เงื่อนไขรหัสผ่าน" aria-live="polite">{checks.map(c=><li key={c.label} className={c.met?'met':''}><span aria-hidden="true">{c.met?'✓':'○'}</span><span>{c.label}<span className="sr-only">{c.met?' ผ่าน':' ยังไม่ครบ'}</span></span></li>)}</ul>;}
