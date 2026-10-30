import { BASE, at } from "./base";
import { Navigation } from "./Navigation";
import { HistoryPopup } from "./HistoryPopup";
import { SearchField } from "./SearchField";
import { Toast } from "./Toast";
import { SystemStatus } from "./SystemStatus";
import { HelpTip } from "./HelpTip";
import { confirmAction, promptAction } from "./Dialogs";
import { UsernameHelp } from "./UsernameHelp";
import { PasswordChecklist, passwordValid, registrationPasswordValid } from "./RegistrationPolicy";
import { loadSession, saveSession, loadView, saveView, clearView, type SettingsSection } from "./session";
import { readableError, jobError, explainError } from "./errors";
import { DeleteUserDialog } from "./DeleteUser";
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

// Mirrors backend recovery rules: before configuration the clone task is re-verified;
// after it, disk size and power state are observed before finishing.
const cloneResumeCheckpoints=["clone_accepted","configure_sending","resume_after_clone"];
const configuredResumeCheckpoints=["configure_complete","resume_after_configure",...["ssh_policy_verify","cloudinit_regenerate","resize","start"].flatMap(step=>["sending","accepted","complete"].map(phase=>`${step}_${phase}`))];
import { ActionMenu } from "./ActionMenu";
import { NewPasswordFields, PasswordForm, IssueRecoveryForm, VMPasswordForm } from "./Passwords";
import type { User, VM, Runtime, Deletion, VMRequest, Job, Audit, Dashboard, PasswordReset } from "./types";
import { SessionSettings } from "./SessionSettings";
import { AdminGuide } from "./AdminGuide";
import { UserGuide } from "./UserGuide";
import { statusLabel, operationLabel } from "./labels";
import { QuotaDefaultsForm } from "./QuotaDefaults";
import { QuotaForm } from "./QuotaForm";
import { ApprovalInbox, type ApprovalSection } from "./ApprovalInbox";
import { RequestStatus } from "./RequestStatus";
import { thaiTime } from "./time";
import { TemplateManager } from "./TemplateManager";
import type { Template } from "./types";
import { emptyDraft, QuotaCards, quotaShortfall, type Draft } from "./QuotaCheck";
import { jobDone, trackJobs, trackRequests, useRequestUpdates, type StatusSection } from "./requestUpdates";
import { AdminRoleForm, PrimaryAdminForm } from "./AdminRole";
import { ConsolePage } from "./ConsolePage";
import { SystemHealth, ResourceUsage } from "./SystemHealth";
import { BootstrapSetup, ConnectionSetup } from "./Setup";
import { wholeNumber } from "./wholeNumber";
import { GuestAccount } from "./GuestAccount";

function App() {
  const [registrationPassword,setRegistrationPassword]=useState("");
  const initialView=useRef(loadView());
  const [sessionReady,setSessionReady]=useState(false);
  const [deleteTarget,setDeleteTarget] = useState<User|null>(null);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [showQuotaDefaults,setShowQuotaDefaults]=useState(false);
  const [quotaTarget,setQuotaTarget] = useState<User[] | null>(null);
  const [selectedQuotaUsers,setSelectedQuotaUsers]=useState<number[]>([]);
  const [selectingUsers,setSelectingUsers]=useState(false);
  const [recoveryTarget, setRecoveryTarget] = useState<User | null>(null);
  const [primaryTarget, setPrimaryTarget] = useState<User | null>(null);
  const [guideSection, setGuideSection] = useState<"admin"|"user">("admin");
  const [roleTarget, setRoleTarget] = useState<User | null>(null);
  const [statusSection, setStatusSection] = useState<StatusSection>("create");
  const [approvalSection, setApprovalSection] = useState<ApprovalSection>("create");
  const [resetVM, setResetVM] = useState<VM | null>(null);
  const [passwordResets, setPasswordResets] = useState<PasswordReset[]>([]);
  const [vmSearch, setVMSearch] = useState("");
  const [runtime, setRuntime] = useState<Record<number, Runtime>>({});
  const [deletions, setDeletions] = useState<Deletion[]>([]);
  const [firstAdmin, setFirstAdmin] = useState<boolean | null>(null);
  const [token, setToken] = useState(loadSession);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [vms, setVMs] = useState<VM[]>([]),
    [requests, setRequests] = useState<VMRequest[]>([]),
    [jobs, setJobs] = useState<Job[]>([]);
  const [users, setUsers] = useState<User[]>([]),
    [logs, setLogs] = useState<Audit[]>([]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [register, setRegister] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>(()=>loadView()?.settingsSection??"connection");
  const [tab, setTab] = useState(()=>loadView()?.tab??"overview");
  useEffect(()=>{if(token&&sessionReady)saveView(tab,settingsSection);},[token,sessionReady,tab,settingsSection]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [requestError, setRequestError] = useState("");
  // Templates users may request now (verified and enabled), loaded with the form.
  const [offered, setOffered] = useState<Pick<Template,"id"|"name"|"description"|"min_disk_gb">[] | null>(null);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const chosenTemplate = offered?.find(t=>t.id===templateId);
  const [vmAuthMethod, setVmAuthMethod] = useState<"password" | "ssh_key">(
    "password",
  );
  const sessionEpoch = useRef(0);
  const activeToken = useRef(token);
  activeToken.current = token;
  function signOut() {
    sessionEpoch.current += 1;
    activeToken.current = "";
    setBusy(false);
    saveSession("");
    clearView();
    initialView.current=null;
    setSessionReady(false);
    setToken("");
    setDeleteTarget(null);
    setRecoveryTarget(null);
    setRoleTarget(null);
    setQuotaTarget(null);
    setShowQuotaDefaults(false);
    setSelectedQuotaUsers([]);
    setSelectingUsers(false);
    setResetVM(null);
    setPasswordResets([]);
    setRuntime({});
    setDeletions([]);
    setDashboard(null);
    setVMs([]);
    setRequests([]);
    setJobs([]);
    setUsers([]);
    setLogs([]);
    setTab("overview");
    setRecoveryMode(false);
    setRegistrationPassword("");
    setSettingsSection("connection");
    setVMSearch("");
  }
  useEffect(() => {
    fetch(at("api/setup/status"))
      .then((r) => {
        if (!r.ok) throw new Error("ตรวจสถานะระบบไม่ได้ กรุณาลองโหลดหน้าใหม่");
        return r.json();
      })
      .then((s) => setFirstAdmin(s.first_admin_required))
      .catch((e) => setError(explainError(e)));
  }, []);
  useEffect(() => {
    if (dashboard?.user.role === "admin" && !dashboard.setup?.enabled && !initialView.current)
      setTab("setup");
  }, [dashboard?.user.id]);

  async function api<T>(path: string, body?: unknown): Promise<T> {
    if (token !== activeToken.current) throw new Error("Session changed; retry after signing in");
    let response: Response;
    try { response = await fetch(at("api" + path), {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    }); } catch { throw new Error("เชื่อมต่อระบบไม่ได้ กรุณาตรวจเครือข่ายแล้วลองใหม่"); }
    let data;
    try { data = await response.json(); }
    catch { if(response.ok) throw new Error("ระบบส่งข้อมูลกลับมาไม่สมบูรณ์ กรุณาโหลดหน้าใหม่ หากยังพบปัญหาให้ติดต่อผู้ดูแล"); data = {}; }
    if(response.ok && (data===null || typeof data!=="object")) throw new Error("ระบบส่งข้อมูลกลับมาไม่สมบูรณ์ กรุณาโหลดหน้าใหม่หรือติดต่อผู้ดูแล");
    if (!response.ok) {
      if ((response.status === 401 || (response.status === 403 && path === "/dashboard")) && token && token === activeToken.current) {
        signOut();
      }
      throw new Error(readableError(data,response.status,response.headers.get("X-Request-ID")));
    }
    return data as T;
  }
  async function refresh() {
    if (!token || token !== activeToken.current) return;
    const epoch = sessionEpoch.current;
    const [d, v, r, j, deletionRows, resetRows] = await Promise.all([
      api<Dashboard>("/dashboard"),
      api<VM[]>("/vms"),
      api<VMRequest[]>("/vm-requests"),
      api<Job[]>("/jobs"),
      api<Deletion[]>("/deletion-requests"),
      api<typeof passwordResets>("/vm-password-resets"),
    ]);
    if (epoch !== sessionEpoch.current || token !== activeToken.current) return;
    setDeletions(deletionRows);
    setPasswordResets(resetRows);
    setDashboard(d);
    setVMs(v);
    setRequests(r);
    setJobs(j);
    if (d.user.role === "admin") {
      const [u, l] = await Promise.all([
        api<User[]>("/admin/users"),
        api<Audit[]>("/admin/audit-logs"),
      ]);
      if (epoch !== sessionEpoch.current || token !== activeToken.current) return;
      setUsers(u);
      setLogs(l);
      if(tab==="setup"&&!d.user.primary_admin) setTab("overview");
    } else if(!["overview","requests","status","activity","password","guide"].includes(tab)) setTab("overview");
    if(epoch===sessionEpoch.current&&token===activeToken.current)setSessionReady(true);
  }
  const runtimeKey = vms.map(v => `${v.id}:${v.status}`).join(",") + jobs.map(j => `${j.id}:${statusLabel(j.state)}`).join(",");
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const queue = vms.filter(v => v.status === "ready");
    // Three concurrent readers keep the full visible list current without a request burst.
    async function load() {
      while (!cancelled && queue.length) {
        const vm = queue.shift()!;
        try {
          const info = await api<Runtime>(`/vms/${vm.id}/runtime`);
          if (!cancelled) setRuntime(previous => ({...previous, [vm.id]: info}));
        } catch { /* A row can become unavailable while the list is refreshing. */ }
      }
    }
    void Promise.all([load(), load(), load()]);
    return () => { cancelled = true; };
  }, [token, runtimeKey]);
  useEffect(() => {
    if (!token) return;
    let alive = true;
    const run = () =>
      refresh().catch((e) => {
        if (alive) setError(explainError(e));
      });
    void run();
    const timer = setInterval(run, 10000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [token]);
  async function act(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(explainError(e));
      if(activeToken.current){try{await refresh();}catch{/* Keep the original action error. */}}
    } finally {
      setBusy(false);
    }
  }
  async function auth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await act(async () => {
      const body = {
        username: form.get("username"),
        password: form.get("password"),
      };
      if (register) {
        if(!registrationPasswordValid(String(form.get("password")??"")))throw new Error("กรุณาตั้งรหัสผ่านให้ครบตามเงื่อนไขความปลอดภัยทุกข้อ");
        if(form.get("password")!==form.get("confirm_password")) throw new Error("รหัสผ่านและช่องยืนยันรหัสผ่านไม่ตรงกัน");
        await api("/auth/register", {...body, first_name:form.get("first_name"), last_name:form.get("last_name"), confirm_password:form.get("confirm_password")});
        setRegister(false);
        setRegistrationPassword("");
        setNotice("ลงทะเบียนสำเร็จ กรุณารอ Admin อนุมัติบัญชี");
      } else {
        const result = await api<{ access_token: string }>("/auth/login", body);
        sessionEpoch.current += 1;
        activeToken.current = result.access_token;
        saveSession(result.access_token);
        setToken(result.access_token);
      }
    });
  }
  async function requestVM(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    // Problems show beside the submit button and focus the field; the page-top alert is off-screen here.
    const stop=(message:string,field:string)=>{setRequestError(message);form.querySelector<HTMLElement>(`[name="${field}"]`)?.focus();};
    setRequestError("");
    // Read the template from the form itself; state can lag a re-render behind the dropdown.
    const template=offered?.find(t=>t.id===Number(data.get("template")));
    if(!template){stop("กรุณาเลือก Template ก่อนส่งคำขอ","template");return;}
    const notWhole=["cpu","ram","disk"].find(k=>!/^\d+$/.test(String(data.get(k)??"").trim()));
    if(notWhole){stop("vCPU, RAM และ Disk ต้องเป็นจำนวนเต็มเท่านั้น",notWhole);return;}
    if(vmAuthMethod==="password"&&!passwordValid(String(data.get("vm_password")??""),12)){stop("รหัสผ่าน VM ยังไม่ครบตาม checklist ทุกข้อ","vm_password");return;}
    if (
      vmAuthMethod === "password" &&
      data.get("vm_password") !== data.get("vm_password_confirm")
    ) {
      stop("รหัสผ่าน VM และการยืนยันไม่ตรงกัน","vm_password_confirm");
      return;
    }
    await act(async () => {
      try{await api("/vm-requests", {
        request_reason: String(data.get("request_reason")??"").trim(),
        hostname: data.get("hostname"),
        cpu: Number(data.get("cpu")),
        ram: Number(data.get("ram")),
        disk: Number(data.get("disk")),
        guest_username: data.get("guest_username"),
        ssh_password_login: false,
        template_id: template.id,
        auth_method: vmAuthMethod,
        ssh_key: vmAuthMethod === "ssh_key" ? data.get("ssh_key") : undefined,
        vm_password:
          vmAuthMethod === "password" ? data.get("vm_password") : undefined,
      });}catch(e){setRequestError(explainError(e));return;}
      form.reset();
      setDraft(emptyDraft);
      setVmAuthMethod("password");
      setNotice("ส่งคำขอแล้ว รอ Admin อนุมัติ");
      showRequest("create");
      await refresh();
    });
  }
  useEffect(()=>{
    if(tab!=="requests"||!token)return;
    let active=true;
    // Admins receive every template (for management); a request may only use open, verified ones.
    const load=()=>api<(Template|Pick<Template,"id"|"name"|"description"|"min_disk_gb">)[]>("/templates").then(all=>{if(!active)return;const list=all.filter(t=>!("enabled" in t)||(t.enabled&&t.verified));setOffered(list);setTemplateId(current=>list.some(t=>t.id===current)?current:null);}).catch(()=>{if(active)setOffered([]);});
    void load();
    // Templates opened or closed elsewhere show up when the user returns to this tab.
    const reload=()=>{if(document.visibilityState==="visible")void load();};
    window.addEventListener("focus",reload);document.addEventListener("visibilitychange",reload);
    return()=>{active=false;window.removeEventListener("focus",reload);document.removeEventListener("visibilitychange",reload);};
  },[tab,token]);
  function chooseTemplate(id:number){
    setTemplateId(id);
    // Raise a typed disk size to the template minimum so the form stays valid; a blank field keeps its placeholder.
    const minimum=offered?.find(t=>t.id===id)?.min_disk_gb??1;
    const disk=document.querySelector<HTMLInputElement>('input[name="disk"]');
    if(disk&&disk.value!==""&&Number(disk.value)<minimum){disk.value=String(minimum);setDraft(old=>({...old,disk:minimum}));}
  }
  async function decide(path: string, approve: boolean) {
    const reason = await promptAction(
      approve ? "ยืนยันอนุมัติรายการนี้ ระบุเหตุผลได้ (เว้นว่างได้)" : "ยืนยันปฏิเสธรายการนี้ กรุณาระบุเหตุผล", {required: !approve},
    );
    if (reason === null) return;
    await act(async () => {
      await api(path, { approve, reason });
      await refresh();
    });
  }
  const admin = dashboard?.user.role === "admin";
  // Primary admins change the Proxmox setup and operate every VM; other admins
  // view everything and decide requests. Only the top admin grants primary rights.
  const primaryAdmin = admin && !!dashboard?.user.primary_admin;
  const topAdmin = admin && !!dashboard?.user.top_admin;
  const canManage = (vm: VM) => primaryAdmin || vm.owner_id === dashboard?.user.id;
  // User < Admin < primary < top: account actions only reach lower levels.
  const rank = (u: User) => u.role !== "admin" ? 0 : u.top_admin ? 3 : u.primary_admin ? 2 : 1;
  const below = (u: User) => admin && !!dashboard && rank(dashboard.user) > rank(u);
  // After submitting, admins land on the matching approval queue; users on their request status.
  function showRequest(section: StatusSection) {
    if (dashboard?.user.role === "admin") { setApprovalSection(section); setTab("approvals"); }
    else { setStatusSection(section); setTab("status"); }
  }
  const tracked = dashboard ? [...trackRequests(dashboard.user.id, requests, deletions, passwordResets, vms, jobs), ...trackJobs(jobs)] : [];
  const updates = useRequestUpdates(dashboard?.user.id, tracked, sessionReady, dashboard?.request_seen, seen => api("/me/request-seen", {entries: seen}));
  const updateCount = [...updates.unseen].filter(key=>!key.startsWith("job-")).length;
  // Finished jobs stay on the activity page until viewed, then for one more hour.
  const [freshJobs,setFreshJobs]=useState<Set<string>>(new Set());
  const unseenJobs=[...updates.unseen].filter(key=>key.startsWith("job-"));
  useEffect(()=>{
    if(tab!=="activity"||!unseenJobs.length)return;
    setFreshJobs(previous=>new Set([...previous,...unseenJobs]));
    updates.markSeen("job");
  },[tab,unseenJobs.join(",")]);
  const announced = useRef(0);
  useEffect(() => {
    if (updateCount > announced.current && tab !== "status") setNotice(`คำขอของคุณมีอัปเดต ${updateCount} รายการ ดูได้ที่หน้าสถานะคำขอ`);
    announced.current = updateCount;
  }, [updateCount]);
  const needsAttention = (job: Job) => job.state === "needs_review" && vms.some(v=>v.id===job.vm_id&&v.status!=="deleted") && !jobs.some(newer=>newer.vm_id===job.vm_id&&newer.id>job.id);
  const recoverableClones=jobs.filter(job=>job.operation==="provision"&&needsAttention(job)&&cloneResumeCheckpoints.includes(job.checkpoint));
  const recoverableProvisions=jobs.filter(job=>job.operation==="provision"&&needsAttention(job)&&[...cloneResumeCheckpoints,...configuredResumeCheckpoints].includes(job.checkpoint));
  async function resumeProvision(job:Job){
    const vm=vms.find(vm=>vm.id===job.vm_id);if(!vm)return;
    const configured=configuredResumeCheckpoints.includes(job.checkpoint);
    const name=await promptAction(configured?`ตรวจและทำต่อ ${vm.hostname} จากขั้นที่ค้าง ระบบจะตรวจขนาด Disk และสถานะเครื่องใน Proxmox ก่อน แล้วทำเฉพาะขั้นที่ยังไม่เสร็จ (ขยาย Disk / เปิดเครื่อง) โดยไม่ตั้งค่าหรือ Clone ใหม่`:`ตรวจและเตรียมเครื่อง ${vm.hostname} ต่อจาก Clone เดิม ระบบจะตั้งค่าเครื่อง ขยาย Disk และเปิดเครื่อง โดยไม่ Clone ใหม่`,{expected:vm.hostname});
    if(name===null)return;
    void act(async()=>{await api(`/admin/jobs/${job.id}/resume-clone`,{confirm_hostname:name});setNotice(configured?"รับงานทำต่อแล้ว ระบบกำลังดำเนินการขั้นที่เหลือ":"รับงานต่อจาก Clone เดิมแล้ว");await refresh();});
  }
  async function closeJob(job:Job){
    const vm=vms.find(vm=>vm.id===job.vm_id);if(!vm)return;
    const effect=job.operation==="provision"?"ระบบจะลบเครื่องที่สร้างค้างไว้ (ถ้ามี และต้องปิดเครื่องอยู่) แล้วคืนโควตาให้ผู้ใช้":job.operation==="delete"?"VM จะกลับเป็นพร้อมใช้งานและยกเลิกคำขอลบ":job.operation==="reset_password"?"คำขอรีเซ็ตรหัสผ่านจะถูกปิดเป็นไม่สำเร็จ":"งานนี้จะถูกปิดเป็นไม่สำเร็จ";
    const message=await promptAction(`ปิดงาน #${job.id} (${operationLabel(job.operation)}) เป็น "ไม่สำเร็จ" ${effect} ข้อความนี้จะแสดงให้ผู้ใช้เห็น กรุณาอธิบายสาเหตุและสิ่งที่ผู้ใช้ควรทำต่อ`,{required:true});
    if(message===null)return;
    const name=await promptAction(`ยืนยันปิดงานของ ${vm.hostname}`,{expected:vm.hostname});
    if(name===null)return;
    void act(async()=>{await api(`/admin/jobs/${job.id}/close`,{confirm_hostname:name,message});setNotice("ปิดงานและแจ้งผู้ใช้แล้ว");await refresh();});
  }

  const showJob = (j:Job) => ["queued","running"].includes(j.state)||needsAttention(j)||(jobDone(j)&&(freshJobs.has(`job-${j.id}`)||updates.unseen.has(`job-${j.id}`)||updates.recentlySeen(`job-${j.id}`)));
  const renderJob = (j:Job) => (
                  <article className="request" key={j.id}>
                    <div className="section-head">
                      <strong>
                        งาน #{j.id} · {operationLabel(j.operation)} · {vms.find(v=>v.id===j.vm_id)?.hostname??`VM #${j.vm_id}`}
                      </strong>
                      <span className={"badge status-badge " + j.state}>{statusLabel(j.state)}</span>
                    </div>
                    {j.created_at&&<p className="job-times">เริ่ม {thaiTime(j.created_at)}{j.finished_at&&` · ${j.state==="needs_review"?"หยุดเมื่อ":"เสร็จ"} ${thaiTime(j.finished_at)}`}</p>}
                    {admin && <details className="technical-details"><summary>รายละเอียดงาน</summary><p className="muted">Checkpoint: {j.checkpoint}</p></details>}
                    {j.operation==="provision"&&j.state==="needs_review"&&["clone_accepted","configure_sending","resume_after_clone"].includes(j.checkpoint)&&<p className="muted">Clone เครื่องไว้แล้ว แต่ยังเตรียมใช้งานไม่ครบ {admin?"กดตรวจและทำต่อจาก Clone เดิมด้านล่าง ระบบจะตรวจ Task และ VM ก่อนทำงานต่อ":"รอผู้ดูแลตรวจและทำต่อจากเครื่องเดิม ไม่ต้องส่งคำขอสร้างใหม่"}</p>}
                    {j.operation==="provision"&&j.state==="needs_review"&&configuredResumeCheckpoints.includes(j.checkpoint)&&<p className="muted">ตั้งค่าเครื่องเสร็จแล้ว แต่ขั้นขยาย Disk หรือเปิดเครื่องยังไม่ยืนยัน {admin?"กดตรวจและทำต่อด้านล่าง ระบบจะตรวจสถานะจริงใน Proxmox ก่อนทำเฉพาะขั้นที่เหลือ":"รอผู้ดูแลตรวจและทำต่อจากเครื่องเดิม ไม่ต้องส่งคำขอสร้างใหม่"}</p>}
                    {j.state==="failed"&&<p className="decision-reason"><strong>ข้อความจาก Admin{j.reviewed_by_name?` ${j.reviewed_by_name}`:""}:</strong> {j.user_message?.trim()||"กรุณาติดต่อผู้ดูแลระบบ"}</p>}
                    {j.state!=="failed"&&j.reviewed_by_name&&<p className="decided-by">สั่งทำต่อโดย Admin {j.reviewed_by_name}</p>}
                    {j.error && j.state!=="failed" && <p className="error">{jobError(j.error,j.operation)}</p>}
                    {j.error && admin && <details className="technical-details"><summary>ข้อมูลสำหรับผู้ดูแล</summary><small>{j.error}</small></details>}
                    {admin&&needsAttention(j)&&<div className="job-recovery-actions">
                      {recoverableProvisions.some(job=>job.id===j.id)&&<button className="primary" disabled={busy} onClick={()=>void resumeProvision(j)}>{recoverableClones.some(job=>job.id===j.id)?"ตรวจและทำต่อจาก Clone เดิม (Admin)":"ตรวจและทำต่อจากขั้นที่ค้าง (Admin)"}</button>}
                      <button className="danger" disabled={busy} onClick={()=>void closeJob(j)}>ทำต่อไม่ได้ · ปิดงานและแจ้งผู้ใช้ (Admin)</button>
                    </div>}

                  </article>

  );

  const approvalCount = users.filter(u => u.status === "pending").length + requests.filter(r => r.status === "pending").length + (primaryAdmin ? deletions.filter(r => r.status === "pending").length : 0) + passwordResets.filter(r => r.status === "pending").length;
  const titles: Record<string,string> = {overview:"เครื่องเสมือน",requests:"ขอสร้าง VM",status:"สถานะคำขอ",approvals:"รออนุมัติ",activity:"กิจกรรม",accounts:"ผู้ใช้",setup:"ตั้งค่า",guide:admin?"คู่มือ":"คู่มือการใช้งาน",audit:"บันทึกการใช้งาน",password:"รหัสผ่านของฉัน"};
  if (firstAdmin === null || (token && !sessionReady))
    return <div className="boot-screen"><main className="boot-card"><img src={at("portal-mark.svg")} width="52" height="52" alt=""/><h1>ICT - VM Portal</h1><p role="status">กำลังโหลดหน้าของคุณ…</p>{error&&<><p className="alert error" role="alert">{error}</p><button onClick={()=>window.location.reload()}>ลองใหม่</button><button onClick={signOut}>กลับไปเข้าสู่ระบบ</button></>}</main></div>;
  if (firstAdmin)
    return (
      <BootstrapSetup
        api={api}
        complete={() => {
          setFirstAdmin(false);
          setNotice("สร้าง Admin แล้ว กรุณาเข้าสู่ระบบเพื่อตั้งค่า Proxmox");
        }}
      />
    );
  return (
    <div className={token ? "layout" : "layout login-layout"}>
      <main>
        <header className={!token ? "login-heading" : "app-header"}>
          <div className="page-heading">
            {token&&<Navigation active={tab} items={["overview","requests","status","activity",...(admin?["approvals","accounts",...(primaryAdmin?["setup"]:[]),"guide","audit"]:["guide"])].map(id=>({id,label:titles[id],count:id==="approvals"?approvalCount:id==="status"?updateCount:undefined}))} onNavigate={id=>{setTab(id);if(id==="setup")setSettingsSection("connection");setNotice("");setError("");}}/>}
            <h1>
              {token ? titles[tab] : "ยินดีต้อนรับสู่ ICT - VM Portal"}
            </h1>
          </div>
          {token && (
            <div className="identity">
              <SystemStatus setup={dashboard?.setup} admin={admin} canSetup={primaryAdmin} onSetup={()=>{setTab("setup");setSettingsSection("connection");setNotice("");setError("");}}/>
              <ActionMenu className="account-menu" label={dashboard?.user.username ?? "บัญชีของฉัน"} ariaLabel="เมนูบัญชีของฉัน"><button onClick={() => setTab("password")}>เปลี่ยนรหัสผ่าน Portal</button>
              <button
                title="ออกจากระบบและยกเลิก Login ของบัญชีนี้ทุกอุปกรณ์"
                onClick={() => void act(async () => {
                  try { await api("/auth/logout", {}); signOut(); }
                  catch { signOut(); setError("ออกจากหน้าเว็บแล้ว แต่ยืนยันการยกเลิก Login ฝั่ง Server ไม่สำเร็จ"); }
                })}
              >
                ออกจากระบบ
              </button>
              </ActionMenu>
            </div>
          )}
        </header>
        {error && (
          <div role="alert" className="alert error">
            {error}
          </div>
        )}
        <Toast message={notice} onClose={()=>setNotice("")}/>
        {!token ? recoveryMode ? <>
          <PasswordForm api={api} recovery onDone={() => {setRecoveryMode(false); setNotice("ตั้งรหัส Portal ใหม่แล้ว กรุณาเข้าสู่ระบบ");}} />
          <button onClick={() => setRecoveryMode(false)}>กลับไป Login</button>
        </> : (
          <section className="auth panel login-card">
            <a className="login-brand" href={BASE}><img src={at("portal-mark.svg")} alt="" width="48" height="48"/><span>ICT - VM Portal</span></a>
            <div className="help-heading"><h2>{register ? "สมัครสมาชิก" : "เข้าสู่ระบบ"}</h2>{register&&<HelpTip label="เกี่ยวกับการสมัครสมาชิก">บัญชีต้องรอ Admin อนุมัติก่อนใช้งาน</HelpTip>}</div>

            <form onSubmit={auth}>
              {register&&<div className="fields"><label>ชื่อ<input name="first_name" required maxLength={100} autoComplete="given-name"/></label><label>นามสกุล<input name="last_name" required maxLength={100} autoComplete="family-name"/></label></div>}
              <div className="username-field">
                <div className="username-label"><label htmlFor="portal-username">ชื่อผู้ใช้</label>{register&&<UsernameHelp/>}</div>
                <input id="portal-username" name="username" pattern="[a-zA-Z0-9][a-zA-Z0-9_.\-]*" title="ใช้ a-z, 0-9, จุด, ขีดกลาง หรือขีดล่าง ความยาว 3–32 ตัว" minLength={3} maxLength={32} type="text" required autoComplete="username" aria-describedby={register?"registration-username-help":undefined}/>
              </div>
              <label>
                รหัสผ่าน
                <input
                  key={register?"signup-password":"login-password"}
                  onChange={e=>{if(register)setRegistrationPassword(e.target.value);}}
                  aria-describedby={register?"registration-password-rules":undefined}
                  name="password"
                  type="password"
                  minLength={register ? 8 : 1}
                  maxLength={128}
                  required
                  autoComplete={register ? "new-password" : "current-password"}
                />
              </label>
              {register&&<div id="registration-password-rules"><PasswordChecklist value={registrationPassword}/></div>}
              {register&&<label>ยืนยันรหัสผ่าน<input name="confirm_password" type="password" minLength={8} maxLength={128} required autoComplete="new-password"/></label>}

              <button className="primary" disabled={busy}>
                {busy ? "กำลังดำเนินการ…" : register ? "สมัครสมาชิก" : "เข้าสู่ระบบ"}
              </button>
            </form>
            <div className="login-links"><button className="link" onClick={() => {setRegister(!register);setRegistrationPassword("");setError("");}}>
              {register ? "มีบัญชีแล้ว? เข้าสู่ระบบ" : "สร้างบัญชีใหม่"}
            </button>
            <button className="link" onClick={() => {setRecoveryMode(true); setError("");}}>ลืมรหัสผ่าน</button></div>
          </section>
        ) : (
          <>
            {dashboard && ((tab === "overview" && !admin) || tab === "requests") && <QuotaCards dashboard={dashboard} draft={tab === "requests" ? draft : undefined}/>}
            {admin && tab === "overview" && <div className="stats admin-stats">{[
              ["VM ทั้งหมด",vms.filter(v => v.status!=="deleted").length],
              ["กำลังทำงาน",vms.filter(v=>v.status==="ready"&&runtime[v.id]?.power==="running").length],
              ["รออนุมัติ",approvalCount],
              ["งานต้องตรวจสอบ",jobs.filter(needsAttention).length],
            ].map(([label,value])=><section className="panel stat" key={String(label)}><span>{label}</span><strong>{value}</strong></section>)}</div>}
            {dashboard?.execution_mode === "mock" && <p className="muted">โหมดจำลอง — ไม่มีคำสั่งส่งไป Proxmox จริง</p>}
            {tab === "password" && <PasswordForm api={api} onDone={() => {signOut(); setNotice("เปลี่ยนรหัส Portal แล้ว กรุณา Login ใหม่");}} />}
            {primaryAdmin && tab === "setup" && <><div className="section-tabs">{([["connection","Proxmox"],["templates","Template"],["session","Session"]] as const).map(([id,name])=><button key={id} className={settingsSection===id?"selected":""} onClick={()=>setSettingsSection(id)}>{name}</button>)}</div>{settingsSection==="connection"?<ConnectionSetup api={api} changed={refresh}/>:settingsSection==="templates"?<TemplateManager api={api}/>:<SessionSettings api={api}/>}</>}
            {tab === "guide" && (admin ? <><div className="section-tabs">{([["admin","คู่มือผู้ดูแลระบบ"],["user","คู่มือผู้ใช้"]] as const).map(([id,name])=><button key={id} className={guideSection===id?"selected":""} onClick={()=>setGuideSection(id)}>{name}</button>)}</div>{guideSection==="admin"?<AdminGuide api={api}/>:<UserGuide/>}</> : <UserGuide/>)}
            {admin && tab === "approvals" && <ApprovalInbox canDelete={primaryAdmin} users={users} requests={requests} deletions={deletions} resets={passwordResets} vms={vms} api={api} busy={busy} decide={decide} act={act} refresh={refresh} section={approvalSection} setSection={setApprovalSection}/>}
            {tab === "overview" && (
              <>
                {admin&&<SystemHealth api={api}/>}
                <section className="panel">
                  <div className="section-head">
                    <div>
                      <h2>{admin ? "รายการ VM ใน Portal" : "VM ของฉัน"}</h2>

                    </div>
                    <div className="actions"><button onClick={() => setTab("requests")}>+ ขอสร้าง VM</button><HistoryPopup title="ประวัติ VM ที่ลบแล้ว" count={vms.filter(vm=>vm.status==="deleted").length}>
                    {vms.filter(vm=>vm.status==="deleted").map(vm=><article className="request" key={vm.id}><div className="section-head"><strong>{vm.hostname}</strong><span className="badge deleted">ลบแล้ว</span></div><p>VMID: {vm.vmid??"—"}</p>{admin&&<p>เจ้าของ: {users.find(u=>u.id===vm.owner_id)?.username??`#${vm.owner_id}`}</p>}</article>)}
                  </HistoryPopup></div>
                  </div>
                  <SearchField label="ค้นหา VM / VMID / Owner" placeholder="ค้นหาชื่อเครื่อง, VMID หรือ Owner ID" value={vmSearch} onChange={setVMSearch}/>

                  {resetVM && <VMPasswordForm api={api} vm={resetVM} onClose={() => setResetVM(null)} onDone={() => {setResetVM(null); showRequest("reset"); setNotice("ส่งคำขอรีเซ็ตรหัส VM แล้ว รอ Admin อนุมัติ"); void refresh();}} />}

                  <div className="table-wrap">
                    <table className="vm-table">
                      <thead>
                        <tr>
                          <th>เครื่อง</th>
                          <th>VMID</th>
                          <th>สถานะ</th>
                          <th>IP address</th>
                          <th>CPU / RAM</th>
                        <th>จัดการ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vms.filter(vm => vm.status !== "deleted" && `${vm.hostname} ${vm.vmid ?? ""} ${vm.owner_id}`.toLowerCase().includes(vmSearch.toLowerCase())).map((vm) => (
                          <tr key={vm.id}>
                            <td>
                              <strong>{vm.hostname}</strong>
                              {admin && <small>เจ้าของ: {users.find(u => u.id === vm.owner_id)?.username ?? `#${vm.owner_id}`}</small>}
                              {vm.status==="missing"&&<small className="error">ไม่พบเครื่องหลังตรวจสอบกับ Proxmox · สิทธิ์ใช้ทรัพยากรยังจองอยู่ รอผู้ดูแลยืนยัน</small>}
                            </td>
                            <td data-label="VMID">{vm.vmid ?? "—"}</td>
                            <td data-label="สถานะ">
                              <span className={"badge " + (vm.status !== "ready" ? vm.status : runtime[vm.id]?.power === "stopped" ? "stopped" : runtime[vm.id]?.power === "running" ? "ready" : "reading")}>
                                {vm.status === "ready" ? runtime[vm.id]?.power === "running" ? "กำลังทำงาน" : runtime[vm.id]?.power === "stopped" ? "ปิดเครื่อง" : "กำลังอ่านสถานะ" : vm.status === "deleted" ? "ลบแล้ว" : vm.status === "missing" ? "ไม่พบ VM ใน Proxmox" : vm.status === "needs_review" ? "ต้องตรวจสอบ" : "กำลังเตรียม"}
                              </span>
                            </td>
                            <td data-label="IP address"><div className="ip-cell-content">
                              <strong>{vm.status==="ready"?(runtime[vm.id]?.ips.join(", ") || "—"):"—"}</strong>

                            </div></td>
                            <td data-label="CPU / RAM"><ResourceUsage runtime={vm.status==="ready"?runtime[vm.id]:undefined}/></td>
                            <td><div className="vm-actions">
                              <ActionMenu className="vm-action-menu" label="จัดการ" ariaLabel={`จัดการ ${vm.hostname}`}>
                              {/* The account created in the VM is the owner's alone; the API withholds it from everyone else. */}
                              {vm.owner_id===dashboard?.user.id&&(()=>{const guest=requests.find(r=>r.id===vm.request_id)?.guest_username;return guest&&<GuestAccount name={guest}/>;})()}
                              {admin&&vm.status==="needs_review"&&recoverableProvisions.some(job=>job.vm_id===vm.id)&&<button disabled={busy} onClick={()=>void resumeProvision(recoverableProvisions.find(job=>job.vm_id===vm.id)!)}>{recoverableClones.some(job=>job.vm_id===vm.id)?"ตรวจและทำต่อจาก Clone เดิม (Admin)":"ตรวจและทำต่อจากขั้นที่ค้าง (Admin)"}</button>}
                              {admin&&vm.status==="needs_review"&&jobs.some(job=>job.vm_id===vm.id&&needsAttention(job))&&<button className="danger" disabled={busy} onClick={()=>void closeJob(jobs.find(job=>job.vm_id===vm.id&&needsAttention(job))!)}>ทำต่อไม่ได้ · ปิดงานและแจ้งผู้ใช้ (Admin)</button>}
                              <button type="button" aria-label={`อัปเดต IP / สถานะ ${vm.hostname}`} disabled={busy||(!["ready","missing","needs_review"].includes(vm.status)||vm.vmid===null)} onClick={()=>void act(async()=>{const presence=await api<{status:string}>(`/vms/${vm.id}/presence`,{});await refresh();if(presence.status==="ready"){const info=await api<Runtime>(`/vms/${vm.id}/runtime`);setRuntime(previous=>({...previous,[vm.id]:info}));}})}>{vm.status==="ready"?"อัปเดต IP":"ตรวจสถานะ"}</button>
                              {canManage(vm) && vm.status === "ready" && ["running","stopped"].includes(runtime[vm.id]?.power) && <button className={runtime[vm.id]?.power==="running"?"":"primary"} disabled={busy || jobs.some(j=>j.vm_id===vm.id&&["queued","running"].includes(j.state))} onClick={async()=>{const action=runtime[vm.id]?.power==="running"?"shutdown":"start";if(action==="shutdown"&&!(await confirmAction(`ยืนยันปิดเครื่อง ${vm.hostname}? กรุณาบันทึกงานใน VM ก่อนดำเนินการ`)))return;void act(async()=>{await api(`/vms/${vm.id}/actions`,{action});await refresh();});}}>{runtime[vm.id]?.power==="running"?"ปิดเครื่อง":"เปิดเครื่อง"}</button>}
                              {primaryAdmin&&(vm.status==="missing"||vm.can_confirm_external_deletion)&&<button className="danger" disabled={busy} onClick={async()=>{const name=await promptAction(`ยืนยันว่าคุณตรวจใน Proxmox แล้วว่า ${vm.hostname} ถูกลบจริง หาก Portal อ่านสถานะ Cluster ไม่ได้ จะใช้การยืนยันของคุณเพื่อปิดรายการและคืนสิทธิ์ใช้ทรัพยากร โดยไม่ส่งคำสั่งลบ VM`,{expected:vm.hostname,danger:true});if(name===null)return;void act(async()=>{await api(`/admin/vms/${vm.id}/confirm-external-deletion`,{confirm_hostname:name});setNotice("ยืนยันการลบจากภายนอกและคืนสิทธิ์ใช้ทรัพยากรแล้ว");await refresh();});}}>ยืนยันการลบจากภายนอก</button>}
                              {(canManage(vm)&&runtime[vm.id]?.power==="running"?["reboot","stop"]:[]).map((action) => (
                                <button
                                  disabled={
                                    busy ||
                                    vm.status !== "ready" ||
                                    jobs.some(
                                      (j) =>
                                        j.vm_id === vm.id &&
                                        ["queued", "running"].includes(j.state),
                                    )
                                  }
                                  className={action === "stop" ? "danger" : undefined}
                                  key={action}
                                  onClick={async () => {
                                    if (
                                      ["stop", "reboot"].includes(action) &&
                                      !(await confirmAction(
                                        action === "stop" ? `ยืนยันบังคับปิดเครื่อง ${vm.hostname} ทันที? งานที่ยังไม่บันทึกอาจสูญหาย` : `ยืนยัน Restart เครื่อง ${vm.hostname}? กรุณาบันทึกงานใน VM ก่อนดำเนินการ`,
                                      ))
                                    )
                                      return;
                                    void act(async () => {
                                      await api(`/vms/${vm.id}/actions`, {
                                        action,
                                      });
                                      await refresh();
                                    });
                                  }}
                                >
                                  {{start:"เปิดเครื่อง",shutdown:"ปิดเครื่อง",stop:"บังคับปิดเครื่อง",reboot:"Restart"}[action]}
                                </button>
                              ))}
                              {canManage(vm)&&<><button disabled={busy || vm.status !== "ready"} onClick={() => {
                                const tab=window.open('', '_blank');
                                if(!tab){setError("เบราว์เซอร์บล็อกแท็บใหม่ กรุณาอนุญาต popup สำหรับเว็บนี้แล้วลองอีกครั้ง");return;}
                                tab.opener=null;
                                tab.location.href=`${BASE}?console=${vm.id}`;
                              }}>Console / Shell ↗</button>
                              <button disabled={busy || vm.status !== "ready" || passwordResets.some(r => r.vm_id === vm.id && ["pending", "approved"].includes(r.status))} onClick={() => setResetVM(vm)}>ขอรีเซ็ตรหัส VM</button>
                              <button className="danger menu-danger" disabled={busy || vm.status !== "ready" || deletions.some(d => d.vm_id === vm.id && ["pending", "approved"].includes(d.status))} onClick={async () => {
                                const reason = await promptAction("ขอลบ VM · ปิดเครื่องก่อน แล้วรอ Admin อนุมัติ",{required:true,danger:true});
                                if (!reason) return;
                                void act(async () => {
                                  await api(`/vms/${vm.id}/deletion-requests`, {reason});
                                  setNotice("ส่งคำขอลบแล้ว รอ Admin อนุมัติ"); showRequest("delete"); await refresh();
                                });
                              }}>{vm.owner_id===dashboard?.user.id?"ขอลบ VM":"ขอลบ VM (ผู้ดูแลหลัก)"}</button></>}
                              </ActionMenu></div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!vms.some(vm => vm.status !== "deleted" && `${vm.hostname} ${vm.vmid ?? ""} ${vm.owner_id}`.toLowerCase().includes(vmSearch.toLowerCase())) && (
                      <div className="empty">
                        ไม่พบ VM ในรายการที่เลือก
                      </div>
                    )}
                  </div>

                </section>

              </>
            )}
            {tab === "requests" && (
              <div className="request-grid">
                <section className="panel">
                  <h2>ขอสร้าง Virtual machine</h2>
                  <form autoComplete="off" data-form-type="other" onSubmit={requestVM} onInput={e=>{setRequestError("");const form=e.currentTarget;const read=(name:string)=>Number((form.elements.namedItem(name) as HTMLInputElement|null)?.value)||0;setDraft({cpu:read("cpu"),ram:read("ram"),disk:read("disk")});}} onReset={()=>setDraft(emptyDraft)}>
                    <div className="template-choice">
                      <label htmlFor="vm-template" className="field-title">ระบบปฏิบัติการ (Template)</label>
                      {offered===null?<p className="muted">กำลังโหลด Template…</p>:!offered.length?<p className="alert warning">ยังไม่มี Template ที่เปิดให้ขอ กรุณาติดต่อผู้ดูแล</p>:<>
                        <select id="vm-template" name="template" required value={templateId??""} onInput={e=>chooseTemplate(Number(e.currentTarget.value))} onChange={e=>{if(e.target.value)chooseTemplate(Number(e.target.value));}}>
                          <option value="" disabled>เลือก Template</option>
                          {offered.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}
                        </select>
                        {chosenTemplate&&<small className="template-hint">{chosenTemplate.description?`${chosenTemplate.description} · `:""}Disk ขั้นต่ำ {chosenTemplate.min_disk_gb} GiB</small>}
                      </>}
                    </div>
                    <label htmlFor="vm-hostname">
                      <span className="field-title">Hostname<HelpTip id="hostname-format-help" label="รูปแบบ Hostname">ยาว 1–40 ตัวอักษร เริ่มด้วยตัวพิมพ์เล็ก a–z และใช้ได้เฉพาะ a–z, 0–9 หรือขีดกลาง (-) ไม่เว้นวรรค ไม่ใช้ตัวพิมพ์ใหญ่ จุด หรือขีดล่าง เช่น ubuntu-dev, web01 ตั้งซ้ำกับ VM อื่นได้ ระบบแยกเครื่องด้วย VMID</HelpTip></span>
                      <input id="vm-hostname" aria-label="Hostname" aria-describedby="hostname-format-help"
                        name="hostname"
                        placeholder="เช่น ubuntu-dev"
                        pattern={"[a-z][a-z0-9\\-]{0,39}"}
                        required
                        maxLength={40}
                      />
                    </label>
                    <div className="fields">
                      <label>
                        vCPU
                        <input
                          name="cpu"
                          {...wholeNumber}
                          min={1}
                          max={32}
                          placeholder="เช่น 2"
                          required
                        />
                      </label>
                      <label>
                        RAM (MiB)
                        <input
                          name="ram"
                          {...wholeNumber}
                          min={512}
                          max={131072}
                          placeholder="เช่น 2048"
                          required
                        />
                      </label>
                      <label>
                        Disk (GiB)
                        <input
                          name="disk"
                          {...wholeNumber}
                          min={chosenTemplate?.min_disk_gb??1}
                          max={2048}
                          placeholder={`เช่น ${Math.max(chosenTemplate?.min_disk_gb??10,10)}`}
                          required
                        />
                      </label>
                    </div>
                    <label htmlFor="vm-guest-username">
                      <span className="field-title">VM username<HelpTip label="ข้อกำหนด VM username">ไม่อนุญาต root หรือบัญชีระบบ</HelpTip></span>
                      <input id="vm-guest-username" aria-label="VM username"
                        name="guest_username"
                        placeholder="เช่น ubuntu"
                        required
                        minLength={3}
                        maxLength={32}
                        pattern="[a-z][a-z0-9_\-]{2,31}"
                        autoComplete="off"
                      />
                    </label>
                    <label>
                      วิธีเข้า VM
                      <select
                        value={vmAuthMethod}
                        onChange={(event) =>
                          setVmAuthMethod(
                            event.target.value as "password" | "ssh_key",
                          )
                        }
                      >
                        <option value="password">Password</option>
                        <option value="ssh_key">SSH public key</option>
                      </select>
                    </label>
                    {vmAuthMethod === "password" ? (
                      <NewPasswordFields guest passwordName="vm_password" confirmationName="vm_password_confirm" passwordLabel="VM password" confirmationLabel="Confirm VM password"/>
                    ) : (
                      <label>
                        SSH public key
                        <textarea
                          name="ssh_key"
                          placeholder="ssh-ed25519 AAAA…"
                          required
                          maxLength={8192}
                        />
                      </label>
                    )}

                    <label><span>เหตุผลที่ขอสร้าง VM <span className="required-note">(จำเป็น)</span></span><textarea name="request_reason" required minLength={3} maxLength={1000} placeholder="เช่น ใช้พัฒนาและทดสอบระบบงานของหน่วยงาน"/></label>
                    {dashboard&&quotaShortfall(dashboard,draft).some(row=>row.over)&&<p className="quota-inline" role="alert">เกินโควตา ส่งคำขอไม่ได้ ดูการ์ดสีแดงด้านบน แล้วลดค่าที่ขอ หรือขอผู้ดูแลเพิ่มโควตา</p>}
                    {requestError&&<p className="alert error" role="alert">{requestError}</p>}
                    <button
                      className="primary"
                      disabled={busy||!offered?.length||(!!dashboard&&quotaShortfall(dashboard,draft).some(row=>row.over))}
                    >
                      ส่งคำขออนุมัติ
                    </button>
                  </form>
                </section>
                <div className="request-aside">
                <section className="panel request-side">
                  <h2>หลังส่งคำขอ</h2>
                  <ol className="request-steps"><li>Admin ตรวจและอนุมัติคำขอ</li><li>ระบบสร้าง ตั้งค่า และเปิดเครื่องให้</li><li>ติดตามผลได้ที่หน้า <strong>สถานะคำขอ</strong> ระบบจะแจ้งเตือนเมื่อมีอัปเดต</li></ol>
                  <button type="button" onClick={()=>{setStatusSection("create");setTab("status");}}>ดูสถานะคำขอ{updateCount>0&&<span className="nav-count">{updateCount}</span>}</button>
                </section>
                </div>
              </div>
            )}
            {tab === "activity" && (
              <section className="panel">
                <div className="section-head"><h2>งานของระบบ</h2><HistoryPopup title="ประวัติงานที่เสร็จแล้ว" label="ประวัติ" count={jobs.filter(j=>!showJob(j)).length}>{jobs.filter(j=>!showJob(j)).map(renderJob)}</HistoryPopup></div>
                {jobs.filter(showJob).map(renderJob)}
                {!jobs.some(showJob) && <div className="empty">ไม่มีงานที่ต้องดำเนินการ</div>}

              </section>
            )}
            {tab === "status" && dashboard && <RequestStatus me={dashboard.user} admin={admin} users={users} requests={requests} deletions={deletions} resets={passwordResets} vms={vms} jobs={jobs} section={statusSection} setSection={setStatusSection} unseen={updates.unseen} markSeen={updates.markSeen} recentlySeen={updates.recentlySeen} busy={busy} onNewRequest={()=>setTab("requests")} onCancelReset={id=>void act(async()=>{await api(`/vm-password-resets/${id}/cancel`,{});setNotice("ยกเลิกคำขอรีเซ็ตแล้ว");await refresh();})}/>}
            {tab === "accounts" && admin && (
              <section className="panel accounts-panel">
                <div className="section-head accounts-heading"><div><h2>จัดการผู้ใช้</h2><p className="muted">{primaryAdmin?"กำหนดสิทธิ์ใช้ทรัพยากร ยกระดับสิทธิ์ และจัดการบัญชี":"กำหนดสิทธิ์ใช้ทรัพยากรและออกโค้ดกู้คืนให้ผู้ใช้ · การเปลี่ยนสิทธิ์และลบผู้ใช้สงวนไว้สำหรับผู้ดูแลหลัก"}</p></div><div className="accounts-heading-actions"><button type="button" aria-pressed={selectingUsers} onClick={()=>{setSelectingUsers(v=>!v);setSelectedQuotaUsers([]);}}>{selectingUsers?"ยกเลิกการเลือก":"เลือกหลายคน"}</button><button type="button" aria-label="สิทธิ์ใช้ทรัพยากรเริ่มต้น" onClick={()=>setShowQuotaDefaults(v=>!v)}>ค่าเริ่มต้น</button><HistoryPopup title="ประวัติผู้ใช้ที่ลบแล้ว" count={users.filter(u=>u.status==="deleted").length}>{users.filter(u=>u.status==="deleted").map(u=><article className="request" key={u.id}><div className="section-head"><strong>{u.username}</strong><span className="badge deleted">ลบแล้ว</span></div><p>{u.first_name} {u.last_name}</p><p className="muted">{u.role==="admin"?"ผู้ดูแล":"ผู้ใช้"} · สิทธิ์ใช้ทรัพยากร {u.quota_vms} VM</p></article>)}</HistoryPopup></div></div>
                {selectingUsers&&<div className="resource-toolbar">
                  <label className="checkbox-label"><input type="checkbox" checked={users.some(u=>!["deleted","deleting"].includes(u.status))&&users.filter(u=>!["deleted","deleting"].includes(u.status)).every(u=>selectedQuotaUsers.includes(u.id))} onChange={e=>setSelectedQuotaUsers(e.target.checked?users.filter(u=>!["deleted","deleting"].includes(u.status)).map(u=>u.id):[])}/>เลือกทั้งหมด</label>
                  <span>เลือก {users.filter(u=>selectedQuotaUsers.includes(u.id)&&!["deleted","deleting"].includes(u.status)).length} คน</span>
                  <button className="primary" aria-label="กำหนดสิทธิ์ใช้ทรัพยากรให้ผู้ใช้ที่เลือก" disabled={busy||!users.some(u=>selectedQuotaUsers.includes(u.id)&&!["deleted","deleting"].includes(u.status))} onClick={()=>{setRecoveryTarget(null);setQuotaTarget(users.filter(u=>selectedQuotaUsers.includes(u.id)&&!["deleted","deleting"].includes(u.status)));}}>กำหนดทรัพยากร</button>
                </div>}
                {showQuotaDefaults&&<QuotaDefaultsForm api={api} onClose={()=>setShowQuotaDefaults(false)} changed={refresh} canAdmin={primaryAdmin}/>}
                {quotaTarget && <QuotaForm key={quotaTarget.map(u=>u.id).join(",")} api={api} users={quotaTarget} onClose={()=>setQuotaTarget(null)} onDone={()=>{setQuotaTarget(null);setSelectedQuotaUsers([]);setNotice("บันทึกสิทธิ์ใช้ทรัพยากรแล้ว");void refresh();}}/>}
                {roleTarget && <AdminRoleForm key={roleTarget.id} api={api} user={roleTarget} onClose={()=>setRoleTarget(null)} onDone={changed=>{setRoleTarget(null);setNotice(changed.role==="admin"?`ยกระดับ ${changed.username} เป็น Admin แล้ว`:`ลดสิทธิ์ ${changed.username} เป็นผู้ใช้แล้ว`);void refresh();}}/>}
                {primaryTarget && <PrimaryAdminForm key={primaryTarget.id} api={api} user={primaryTarget} onClose={()=>setPrimaryTarget(null)} onDone={changed=>{setPrimaryTarget(null);setNotice(changed.primary_admin?`มอบสิทธิ์ผู้ดูแลหลักให้ ${changed.username} แล้ว`:`ถอนสิทธิ์ผู้ดูแลหลักของ ${changed.username} แล้ว`);void refresh();}}/>}
                {recoveryTarget && <IssueRecoveryForm key={recoveryTarget.id} api={api} user={recoveryTarget} onClose={() => setRecoveryTarget(null)} />}
                {deleteTarget&&<DeleteUserDialog user={deleteTarget} api={api} onClose={()=>setDeleteTarget(null)} onDone={()=>{setDeleteTarget(null);setNotice("รับคำขอลบผู้ใช้แล้ว ตรวจผลการลบ VM ได้ที่กิจกรรม");void refresh();}}/>}
                {users.filter(u=>u.status!=="deleted").map((u) => (
                  <article className={`request section-head account-row${selectedQuotaUsers.includes(u.id)?" is-selected":""}`} key={u.id}>
                    {selectingUsers&&!["deleted","deleting"].includes(u.status)&&below(u)&&<label className="checkbox-label account-select"><input type="checkbox" aria-label={`เลือก ${u.username}`} checked={selectedQuotaUsers.includes(u.id)} onChange={e=>setSelectedQuotaUsers(ids=>e.target.checked?[...ids,u.id]:ids.filter(id=>id!==u.id))}/></label>}
                    <div className="account-info">
                      <strong>{u.username}</strong>
                      {(u.first_name||u.last_name)&&<p>{u.first_name} {u.last_name}</p>}
                      <p className="muted">
                        {u.role==="admin"?<span className={`badge role-badge${u.primary_admin?" primary":""}`}>{u.top_admin?"ผู้ดูแลสูงสุด":u.primary_admin?"ผู้ดูแลหลัก":"Admin"}</span>:"ผู้ใช้"} · {statusLabel(u.status)} · สิทธิ์ใช้ทรัพยากร {u.quota_vms} VM {u.quota_customized&&<span className="badge">กำหนดเอง</span>}
                      </p>
                    </div>
                    <div className="account-actions">
                    {u.status === "deleting"&&<span className="badge pending">กำลังลบ VM — ตรวจหน้ากิจกรรม</span>}
                    {(()=>{
                      const live=!["deleted","deleting"].includes(u.status),self=u.id===dashboard?.user.id;
                      const items=[
                        live&&below(u)&&<button key="quota" className="resource-edit" aria-label="แก้ไขสิทธิ์ใช้ทรัพยากร" disabled={busy} onClick={()=>{setRecoveryTarget(null);setQuotaTarget([u]);}}>ปรับทรัพยากร</button>,
                        u.status==="approved"&&below(u)&&<button key="recovery" aria-label="ออกโค้ดกู้คืน Portal" disabled={busy} onClick={()=>{setQuotaTarget(null);setRecoveryTarget(u);}}>โค้ดกู้คืน</button>,
                        primaryAdmin&&u.status==="approved"&&below(u)&&<button key="role" disabled={busy} onClick={()=>{setQuotaTarget(null);setRecoveryTarget(null);setRoleTarget(u);}}>{u.role==="admin"?"ลดเป็นผู้ใช้":"ยกระดับเป็น Admin"}</button>,
                        topAdmin&&u.status==="approved"&&u.role==="admin"&&!u.top_admin&&!self&&<button key="primary" disabled={busy} onClick={()=>{setQuotaTarget(null);setRecoveryTarget(null);setPrimaryTarget(u);}}>{u.primary_admin?"ถอนสิทธิ์ผู้ดูแลหลัก":"มอบสิทธิ์ผู้ดูแลหลัก"}</button>,
                        primaryAdmin&&below(u)&&live&&<button key="delete" className="danger menu-danger" disabled={busy} onClick={()=>setDeleteTarget(u)}>ลบผู้ใช้</button>,
                      ].filter(Boolean);
                      return items.length>0&&<ActionMenu className="account-action-menu" label="จัดการ" ariaLabel={`จัดการ ${u.username}`}>{items}</ActionMenu>;
                    })()}
                    </div>
                  </article>
                ))}

              </section>
            )}
            {tab === "audit" && admin && (
              <section className="panel">
                <h2>Audit trail</h2>
                <div className="table-wrap">
                  <table className="audit-table">
                    <thead>
                      <tr>
                        <th>เวลา (ไทย)</th>
                        <th>Actor</th>
                        <th>Action</th>
                        <th>Target / Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((l) => (
                        <tr key={l.id}>
                          <td data-label="เวลา (ไทย)">{thaiTime(l.created_at)}</td>
                          <td data-label="Actor">{l.actor_id===null?"Worker":users.find(u=>u.id===l.actor_id)?.username??`#${l.actor_id}`}</td>
                          <td data-label="Action">{l.action}</td>
                          <td data-label="Target / Details">
                            {l.target}
                            <details className="technical-details"><summary>รายละเอียด</summary><small>{JSON.stringify(l.details)}</small></details>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}

      </main>
    </div>
  );
}
const consoleVM = new URLSearchParams(window.location.search).get("console");
createRoot(document.getElementById("root")!).render(consoleVM!==null?<ConsolePage vmId={consoleVM}/>:<App />);
