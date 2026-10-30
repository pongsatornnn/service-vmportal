import { ResourcePicker } from "./ResourcePicker";
import { NetworkPicker } from "./NetworkPicker";
import { Toast } from "./Toast";
import { PasswordChecklist, passwordValid } from "./RegistrationPolicy";
import { HelpTip } from "./HelpTip";
import { explainError } from "./errors";
import { confirmAction } from "./Dialogs";
import React, { useEffect, useRef, useState } from "react";

const resourceHelp:Record<string,string>={
 node:"ชื่อโฮสต์ Proxmox ที่จะสร้าง VM ดูจากรายการ Node ด้านซ้ายของ Proxmox และกรอกให้ตรงตัวพิมพ์ เช่น Node3 ผู้ใช้จะเลือก Node เองไม่ได้",
 pool:"กลุ่ม VM สำหรับจัดขอบเขตทรัพยากรและสิทธิ์ของ Portal ดูที่ Datacenter → Permissions → Pools เช่น Portal-Service ระบบส่ง Pool นี้ทุกครั้งที่ Clone",
 storage:"Storage ที่เก็บ Disk ของ VM ที่สร้างใหม่ เช่น local-lvm ดูที่ Datacenter → Storage ต้องรองรับ Disk image และมีพื้นที่ว่างเพียงพอ การ์ดพื้นที่ VM บน Dashboard อ่านจาก Storage นี้",
 secondary_bridge:"การ์ดเครือข่ายใบที่สอง (net1) สำหรับ VM ที่สร้างใหม่ รับ IP แบบ DHCP เช่นเดียวกับขาหลัก เว้นว่างเพื่อใช้ใบเดียว ต้องเลือก Bridge ที่อยู่ใน allowlist และมี DHCP หากต้องการ IP อัตโนมัติ",
 bridge:"เครือข่ายที่การ์ด Network ของ VM จะเชื่อมต่อ ดูที่ Node → System → Network เช่น VLAN48 ต้องมี Bridge นี้อยู่จริง และอยู่ใน Bridge allowlist หากใช้ DHCP ต้องมี DHCP ในเครือข่ายนั้นด้วย",
 bridge_allowlist:"รายชื่อ Bridge ที่ Backend อนุญาต คั่นหลายค่าด้วย comma เช่น VLAN48,VLAN49 ค่า Network Bridge ด้านบนต้องอยู่ในรายการนี้ ช่องนี้ไม่ได้สร้าง Bridge บน Proxmox ให้ ต้องเตรียมไว้ก่อน",
};
type API = <T>(path: string, body?: unknown) => Promise<T>;
export function BootstrapSetup({
  api,
  complete,
}: {
  api: API;
  complete: () => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [adminPassword,setAdminPassword]=useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if(!passwordValid(String(data.get("password")??""),12))throw new Error("กรุณาตั้งรหัสผ่านให้ครบตาม checklist ทุกข้อ");
      await api("/setup/bootstrap", {
        username: data.get("username"),
        password: data.get("password"),
        setup_token: data.get("setup_token"),
      });
      complete();
    } catch (e) {
      setError(explainError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="bootstrap-layout">
      <section className="panel">
        <h1>เริ่มตั้งค่าระบบ</h1>

        {error && (
          <div role="alert" className="alert error">
            {error}
          </div>
        )}
        <form onSubmit={submit}>
          <label>
            <span className="field-title">รหัสติดตั้งครั้งแรก<HelpTip label="เกี่ยวกับรหัสติดตั้ง">ใช้รหัสติดตั้งที่ได้รับจากผู้ดูแล Server</HelpTip></span>
            <input
              name="setup_token"
              type="password"
              required
              autoComplete="off"
            />
          </label>
          <label>
            <span className="field-title">Admin username<HelpTip label="ข้อกำหนด Admin username">3–32 ตัวอักษร: a–z, 0–9, จุด, ขีดกลาง หรือขีดล่าง</HelpTip></span>
            <input
              name="username"
              type="text"
              minLength={3}
              maxLength={32}
              required
              autoComplete="username"
            />
          </label>
          <label>
            Admin password
            <input
              name="password"
              type="password"
              minLength={12}
              maxLength={128}
              required
              autoComplete="new-password"
              aria-describedby="bootstrap-password-rules"
              onChange={e=>setAdminPassword(e.target.value)}
            />
          </label>
          <div id="bootstrap-password-rules"><PasswordChecklist value={adminPassword} minLength={12}/></div>
          <button className="primary" disabled={busy}>
            สร้าง Admin และเริ่ม Setup
          </button>
        </form>
      </section>
    </main>
  );
}

type Values = {
  mode: "mock" | "real";
  url: string;
  token_id: string;
  ca_pem: string;
  node: string;
  pool: string;
  template: number;
  storage: string;
  bridge: string;
  secondary_bridge: string;
  network_bridges: string[];
  bridge_allowlist: string[];
  template_disk_gb: number;
  disk_device: string;
  ssh_password_snippet: string;
};
type State = {
  values: Partial<Values>;
  has_token_secret: boolean;
  revision: number;
  connection_verified: boolean;
  enabled: boolean;
};
const defaults: Values = {
  mode: "real",
  url: "",
  token_id: "",
  ca_pem: "",
  node: "",
  pool: "",
  template: 9000,
  storage: "",
  bridge: "",
  secondary_bridge: "",
  network_bridges: [],
  bridge_allowlist: [],
  template_disk_gb: 20,
  disk_device: "scsi0",
  ssh_password_snippet: "",
};
type Resources = {
  nodes:string[]; pools:string[]; storages:string[]; bridges:string[];
  templates:{id:number;name:string}[];
  disks:{id:string;minimum_gib:number|null}[]; boot_disk:string|null;
  warnings:Record<string,string>;
};
const resourceNames:Record<string,string>={nodes:"Node",pools:"Pool",storages:"Storage",bridges:"Bridge",templates:"Template",disks:"Disk ของ Template"};
export function ConnectionSetup({
  api,
  changed,
}: {
  api: API;
  changed: () => Promise<void>;
}) {
  const [state, setState] = useState<State | null>(null);
  const [values, setValues] = useState<Values>(defaults);
  const [secret, setSecret] = useState("");
  const [connectionOpen,setConnectionOpen]=useState(false);
  const [resources,setResources]=useState<Resources|null>(null);
  const [discovering,setDiscovering]=useState(false);
  const [discoveryError,setDiscoveryError]=useState("");
  const [knownNodes,setKnownNodes]=useState<string[]>([]);
  const selectedNode=useRef("");
  const discoverySequence=useRef(0);
  useEffect(()=>()=>{discoverySequence.current+=1;},[]);
  function invalidateResources(){discoverySequence.current+=1;setResources(null);setDiscovering(false);setDiscoveryError("");}
  async function discover(next=values,autofill=true){
    const sequence=++discoverySequence.current;
    setDiscovering(true);setDiscoveryError("");
    try {
      const result=await api<Resources>("/admin/settings/resources",{url:next.url,token_id:next.token_id,token_secret:secret||null,ca_pem:next.ca_pem,node:next.node||null,template:null});
      if(sequence!==discoverySequence.current)return;
      setResources(result);
      if(result.nodes.length)setKnownNodes(result.nodes);
      // Fill blank fields Proxmox leaves no choice about; the rest keep their placeholders.
      if(autofill&&!next.node&&result.nodes.length===1){selectedNode.current=result.nodes[0];selectResource("node",result.nodes[0],next);return;}
      if(autofill)setValues(current=>{
        const only=(list:string[])=>list.length===1?list[0]:"";
        const networks=current.network_bridges.some(Boolean)?current.network_bridges:only(result.bridges)?[only(result.bridges)]:current.network_bridges;
        const updated={...current,storage:current.storage||only(result.storages),pool:current.pool||only(result.pools),network_bridges:networks,bridge:networks[0]||"",secondary_bridge:networks[1]||""};
        if(updated.storage!==current.storage||updated.pool!==current.pool||networks!==current.network_bridges)setDirty(true);
        return updated;
      });
    } catch(e){if(sequence===discoverySequence.current){setResources(null);setDiscoveryError(explainError(e));}}
    finally{if(sequence===discoverySequence.current)setDiscovering(false);}
  }
  function selectResource(key:"node"|"pool"|"storage",value:string,base=values){
    let next={...base,[key]:value};
    if(key==="node")next={...next,storage:"",bridge:"",secondary_bridge:"",network_bridges:[""],bridge_allowlist:[]};
    setValues(next);setDirty(true);
    if(key==="node"){setResources(old=>old?{...old,storages:[],bridges:[],templates:[],disks:[],boot_disk:null}:null);void discover(next);}
  }
  function resourceOptions(key:string):{value:string;label:string}[]{
    if(!resources)return [];
    const list=key==="node"?resources.nodes:key==="pool"?resources.pools:key==="storage"?resources.storages:[];
    return list.map(value=>({value,label:value}));
  }
  function resourceSelect(key:"node"|"pool"|"storage",label:string){
    const options=resourceOptions(key),current=String(values[key]||"");
    return <ResourcePicker id={`setup-${key}`} label={label} value={current} options={options} pattern="[A-Za-z0-9_.-]{1,63}" placeholder={key==="storage"?"local-lvm":"Portal-Service"} disabled={busy||discovering} onChange={value=>{setValues(old=>({...old,[key]:value}));setDirty(true);}}/>;

  }

  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    let active=true;
    api<State>("/admin/settings")
      .then((s) => {
        if(!active)return;
        setState(s);
        const networks=s.values.network_bridges?.length?s.values.network_bridges:[s.values.bridge||"",...(s.values.secondary_bridge?[s.values.secondary_bridge]:[])].filter(Boolean);
        const loaded={ ...defaults, ...s.values,network_bridges:networks };
        setValues(loaded);
        selectedNode.current=loaded.node;
        setConnectionOpen(!s.revision);
        if(loaded.mode==="real"&&s.has_token_secret&&loaded.ca_pem)void discover(loaded,false);
      })
      .catch((e) => {if(active)setError(explainError(e));});
    return()=>{active=false;};
  }, []);
  const [operation,setOperation]=useState<"save"|"check"|"enable"|"pause"|null>(null);
  async function action(work: () => Promise<void>, operation: "save"|"check"|"enable"|"pause"="save") {
    setBusy(true);
    setOperation(operation);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(explainError(e));
      try { setState(await api<State>("/admin/settings")); } catch { setState(null); }
      await changed().catch(()=>undefined);
    } finally {
      setBusy(false);
      setOperation(null);
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    await action(async () => {
      if(values.mode==="real"&&(!values.ca_pem.trim()||(!secret&&!state?.has_token_secret))){setConnectionOpen(true);throw new Error("กรุณากรอก Token Secret และอัปโหลดใบรับรอง CA ในข้อมูลการเชื่อมต่อก่อน");}
      let saved=false;
      if(!values.network_bridges.length||values.network_bridges.some(bridge=>!bridge))throw new Error("กรุณาเลือกอย่างน้อย 1 เครือข่าย และเลือก Bridge ให้ครบทุกขา");
      if(dirty||!state?.revision){
        const {template:_template,template_disk_gb:_disk,disk_device:_device,...connection}=values;
        const result=await api<State>("/admin/settings",{...connection,token_secret:secret||null,bridge_allowlist:Array.from(new Set(values.network_bridges.filter(Boolean)))});
        setState(result);setValues(current=>({...current,...result.values}));setSecret("");setDirty(false);saved=true;
      }
      setOperation("check");
      let result:{mode:string};
      try{result=await api<{mode:string}>("/admin/settings/check",{});}catch(error){throw new Error(`${saved?"บันทึกค่าแล้ว แต่ตรวจสอบยังไม่ผ่าน":"ตรวจสอบยังไม่ผ่าน"}: ${explainError(error)}`);}
      const verified=await api<State>("/admin/settings");setState(verified);
      setNotice(verified.enabled?"ตรวจการเชื่อมต่อสำเร็จ ระบบเปิดใช้งานอยู่":result.mode==="mock"?"บันทึกและตรวจสอบโหมดจำลองแล้ว":"บันทึกและตรวจสอบสำเร็จ พร้อมเปิดใช้งานระบบ");
      await changed();
    });
  }
  const field = <K extends keyof Values>(key: K, value: Values[K]) => {
    if(["url","token_id","ca_pem","node"].includes(key))invalidateResources();
    setValues((old) => ({ ...old, [key]: value }));
    setDirty(true);
  };
  async function activate(enabled: boolean) {
    if (
      enabled &&
      !(await confirmAction(
        values.mode === "real"
          ? "ยืนยันเปิดคำสั่งจริงบน Proxmox? งานที่อนุมัติและค้างอยู่จะเริ่มทำงานได้ รวมถึง Clone และ Power commands"
          : "เปิดใช้งานระบบจำลอง?",
      ))
    )
      return;
    await action(async () => {
      setState(
        await api<State>("/admin/settings/activation", {
          enabled,
          confirm_real_execution: enabled && values.mode === "real",
        }),
      );
      setNotice(
        enabled
          ? "เปิดใช้งานแล้ว"
          : "พักการรับงานใหม่แล้ว งานที่กำลังทำจะดำเนินต่อจนจบ",
      );
      await changed();
    }, enabled?"enable":"pause");
  }
  return (
    <div className="setup-grid simple-setup setup-with-controls">
      <section className="panel setup-editor">

        <div className="setup-page-heading"><div><h2>ตั้งค่า Proxmox</h2><p className="muted">เลือกต้นแบบและเครือข่ายสำหรับ VM ใหม่</p></div></div>

        {error && (
          <div className="alert error" role="alert">
            {error}
          </div>
        )}
        <Toast message={notice} onClose={()=>setNotice("")}/>
        <form id="proxmox-settings-form" autoComplete="off" data-form-type="other" onInvalidCapture={e=>{const details=(e.target as HTMLElement).closest("details");if(details)details.open=true;}} onSubmit={save}>
          <fieldset className="setup-form-fields" disabled={busy}>
          <details className="setup-connection-details" open={connectionOpen} onToggle={e=>setConnectionOpen(e.currentTarget.open)}>
            <summary><span>ข้อมูลการเชื่อมต่อ</span><small>{state?.has_token_secret?"ตั้งค่าไว้แล้ว · กดเพื่อแก้ไข":"ระบุ Endpoint, Token และ CA"}</small></summary>
          <div className="setup-connection-grid">
          <label className="connection-endpoint">
            ที่อยู่ Proxmox
            <input
              aria-label="API endpoint"
              pattern="https://.*"
              title="ใช้ https://ชื่อเครื่องหรือ IP:พอร์ต"
              type="url"
              value={values.url}
              required
              placeholder="https://proxmox.lan:8006"
              onChange={(e) => field("url", e.target.value)}
            />
          </label>
          <label>
            API Token ID
            <input
              value={values.token_id}
              placeholder="vmportal@pve!portal-api"
              required
              onChange={(e) => field("token_id", e.target.value)}
              autoComplete="off"
            />
          </label>
          <label>
            API Token Secret
            <input
              type="password"
              value={secret}
              onChange={(e) => {
                invalidateResources();
                setSecret(e.target.value);
                setDirty(true);
              }}
              autoComplete="off" data-lpignore="true" data-1p-ignore="true"
              maxLength={4096}
              placeholder={
                state?.has_token_secret
                  ? "ตั้งค่าแล้ว — เว้นว่างเพื่อเก็บค่าเดิม"
                  : "กรอก Secret จาก Proxmox"
              }
            />

          </label>
          </div>
          <div className="ca-certificate">
            <span className="field-title">ใบรับรอง Proxmox (CA)<HelpTip label="เกี่ยวกับ Trusted CA">ใช้ไฟล์ใบรับรอง .pem หรือ .crt ที่เชื่อถือได้ ระบบตรวจ CA และชื่อ/IP ของ Server ทุกครั้ง</HelpTip></span>
            <div className="ca-location"><strong>ไฟล์ CA มาตรฐานของ Proxmox</strong><code>/etc/pve/pve-root-ca.pem</code><p>เปิด Proxmox → เลือก Node → Shell แล้วใช้คำสั่ง</p><code>cat /etc/pve/pve-root-ca.pem</code><p>คัดลอกเนื้อหาไปที่ “วางข้อความใบรับรองเอง” หรืออัปโหลดไฟล์นี้</p><small>หากใช้ใบรับรององค์กร ให้ใช้ CA ของผู้ออกใบรับรองนั้น</small></div>
            <input type="file" aria-label="อัปโหลดใบรับรอง CA" accept=".pem,.crt" onChange={e=>{
              const file=e.target.files?.[0];if(!file)return;
              if(file.size>65536){setError("ไฟล์ CA ใหญ่เกิน 64 KiB กรุณาเลือกไฟล์ใบรับรอง PEM ที่ถูกต้อง");return;}
              void file.text().then(text=>field("ca_pem",text));
            }}/>
            <small className="muted">{values.ca_pem.trim()?"มีข้อมูลใบรับรองแล้ว":"เลือกไฟล์ใบรับรองจาก Proxmox"}</small>
            <details className="ca-manual"><summary>วางข้อความใบรับรองเอง</summary><textarea aria-label="ใบรับรอง CA แบบ PEM" value={values.ca_pem} maxLength={65536} placeholder="-----BEGIN CERTIFICATE-----" onChange={e=>field("ca_pem",e.target.value)}/></details>
          </div>
          </details>
          <div className="resource-discovery">
            <div><h3>{discovering?"กำลังโหลดรายการ…":resources?"รายการพร้อมให้เลือก":"รายการจาก Proxmox"}</h3><p className="muted">{resources?"เลือกค่าด้านล่างได้เลย":"อ่าน Node, Template และเครือข่ายจากข้อมูลการเชื่อมต่อ"}</p></div>
            <button type="button" disabled={busy||discovering||values.mode!=="real"||!values.url||!values.token_id||!values.ca_pem||(!secret&&!state?.has_token_secret)} onClick={()=>{void discover();}} aria-label="โหลดรายการใหม่">{discovering?"กำลังโหลด…":"โหลดรายการใหม่"}</button>
            {values.mode==="real"&&(!values.ca_pem||(!secret&&!state?.has_token_secret))&&<p className="muted">กรอก Token และเลือกใบรับรองในข้อมูลการเชื่อมต่อด้านบนก่อนโหลดรายการ</p>}
            {values.mode!=="real"&&<p className="muted">ดึงรายการได้เมื่อเชื่อมต่อ Proxmox จริง</p>}
            {discoveryError&&<p className="error" role="alert">{discoveryError}</p>}
            {resources&&Object.entries(resources.warnings).map(([key,reason])=><p className="error" role="status" key={key}>{resourceNames[key]??key}: {reason==="permission"?"Token ไม่มีสิทธิ์อ่านรายการ":reason==="not_template"?"VM ที่เลือกยังไม่ใช่ Template":"อ่านรายการไม่สำเร็จ กรุณาตรวจการเชื่อมต่อแล้วลองใหม่"}</p>)}
          </div>
          <div className="setup-step-heading"><h3>เลือกที่สร้าง VM</h3><p className="muted">เลือก Node ก่อน แล้วเลือกที่เก็บ Disk และกลุ่ม VM ส่วน Template ตั้งค่าในแท็บ Template</p></div>
          <div className="fields setup-resource-fields">
            <label><span className="field-title">เครื่องแม่ข่าย (Node)<HelpTip label="เกี่ยวกับ Node">{resourceHelp.node}</HelpTip></span><ResourcePicker id="setup-node" label="Node" value={values.node} options={knownNodes.map(node=>({value:node,label:node}))} pattern="[A-Za-z0-9_.-]{1,63}" placeholder="pve" disabled={busy} onChange={value=>field("node",value)} onCommit={value=>{
              const node=value.trim();if(!node||!/^([A-Za-z0-9_.-]{1,63})$/.test(node))return;
              if(node===selectedNode.current){if(!resources&&!discovering)void discover({...values,node},false);return;}
              selectedNode.current=node;selectResource("node",node);
            }}/><small className="muted">เลือกจากรายการ หรือเลือกกรอกค่าเองเมื่ออ่านรายการไม่ได้</small></label>
            {([["storage","Storage"],["pool","Resource Pool"]] as const).map(([key,label])=><label key={key}><span className="field-title">{key==="storage"?"ที่เก็บ Disk (Storage)":"กลุ่ม VM (Pool)"}<HelpTip label={`เกี่ยวกับ ${label}`}>{resourceHelp[key]}</HelpTip></span>{resourceSelect(key,label)}</label>)}
          </div>
          <NetworkPicker networks={values.network_bridges} choices={resources?.bridges??[]} busy={busy||discovering} onChange={networks=>{
            setValues(current=>({...current,network_bridges:networks,bridge:networks[0]||"",secondary_bridge:networks[1]||""}));setDirty(true);
          }}/>
          <div className="setup-preview"><strong>สรุปสำหรับ VM ใหม่</strong><p>{values.node||"ยังไม่เลือก Node"} · {values.storage||"ยังไม่เลือก Storage"} · Template ตั้งค่าในแท็บ Template</p><p>{values.network_bridges.map((bridge,index)=>`ขา ${index+1}: ${bridge||"ยังไม่เลือก Bridge"}`).join(" · ")} · DHCP ทุกขา</p></div>
          </fieldset>
        </form>
      </section>
      <section className="panel setup-status setup-control-panel">
        <h2>ควบคุมระบบ</h2>
        <span className={`badge ${state?.enabled?"ready":"pending"}`}>{state?.enabled?"เปิดใช้งานอยู่":"ระบบพักการทำงาน"}</span>
        <ol className="setup-readiness">
          <li className={state?.revision?"complete":""}>บันทึกการตั้งค่า{state?.revision?"แล้ว":"ก่อน"}</li>
          <li className={state?.connection_verified?"complete":""}>{state?.connection_verified?"ตรวจการเชื่อมต่อผ่านแล้ว":"รอตรวจการเชื่อมต่อ"}</li>
          <li className={state?.enabled?"complete":""}>{state?.enabled?"เปิดรับงานแล้ว":"รอเปิดใช้งานระบบ"}</li>
        </ol>
          <div className="setup-save-panel">
            <span className="setup-save-hint">{dirty?"มีค่าที่ยังไม่บันทึก":state?.connection_verified?"การตั้งค่าปัจจุบันผ่านการตรวจสอบแล้ว":"บันทึกและตรวจสอบการเชื่อมต่อ"}</span>
            <button type="submit" form="proxmox-settings-form" className="primary setup-check" disabled={busy||discovering||!state||!values.network_bridges.length||values.network_bridges.some(bridge=>!bridge)}>{busy?(operation==="check"?"กำลังตรวจสอบ…":"กำลังบันทึก…"):dirty||!state?.revision?"บันทึกและตรวจสอบ":"ตรวจการเชื่อมต่อ"}</button>
          </div>
        <div className="setup-action-hint" role="status">{dirty?"บันทึกและตรวจสอบค่าใหม่ก่อนเปิดใช้งาน":state?.enabled?"ระบบกำลังรับงานตามค่าที่บันทึกไว้":state?.connection_verified?"ตรวจสอบผ่านแล้ว กดเปิดใช้งานได้":"บันทึกและตรวจสอบให้ผ่านก่อนเปิดใช้งาน"}</div>
        <div className="setup-system-actions">
          <button type="button" className="primary setup-enable" disabled={busy||discovering||dirty||!state?.connection_verified||state.enabled} onClick={()=>void activate(true)}>{state?.enabled?"เปิดใช้งานอยู่":"เปิดใช้งานระบบ"}</button>
          <button type="button" className="danger-solid setup-pause" disabled={busy||!state?.enabled} onClick={()=>void activate(false)}>{state?.enabled?"พักระบบ":"พักการทำงานอยู่"}</button>
        </div>
        <p className="muted">การเปิดระบบอนุญาตให้งานที่ Admin อนุมัติเริ่มทำงานได้</p>
      </section>
    </div>
  );
}
