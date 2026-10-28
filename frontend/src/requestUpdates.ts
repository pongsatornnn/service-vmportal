import { useEffect, useMemo, useState } from "react";
import type { Deletion, Job, PasswordReset, VM, VMRequest } from "./types";

export type StatusSection="create"|"delete"|"reset";
export type TrackedSection=StatusSection|"job";
// quiet: a change the owner already learns about elsewhere (a create request closed
// because its VM was deleted shows up under "ลบ VM"), so it raises no alert.
export type TrackedRequest={key:string;section:TrackedSection;sig:string;pending:boolean;quiet?:boolean};
// Present once job states are tracked; without it existing jobs count as seen long ago.
const JOBS_MARKER="job-0";

// Stored as "<sig>@<unix seconds when that state was first viewed>".
type Seen=Record<string,string>;
const SEEN_KEEP_SECONDS=60*60;
const parse=(value:string|undefined)=>{
  if(value===undefined)return undefined;
  const at=value.lastIndexOf("@");
  return at<0?{sig:value,at:0}:{sig:value.slice(0,at),at:Number(value.slice(at+1))||0};
};
const nowSeconds=()=>Math.floor(Date.now()/1000);

export const latestJob=(jobs:Job[],vmId:number|undefined,operation:string)=>jobs.filter(j=>j.vm_id===vmId&&j.operation===operation).sort((a,b)=>b.id-a.id)[0];
export const requestKey=(section:StatusSection,id:number)=>`${section}-${id}`;

// A request's visible state: its own status plus the job carrying it out.
export function trackRequests(ownerId:number,requests:VMRequest[],deletions:Deletion[],resets:PasswordReset[],vms:VM[],jobs:Job[]):TrackedRequest[]{
  const own=<T extends {owner_id:number}>(rows:T[])=>rows.filter(r=>r.owner_id===ownerId);
  return [
    ...own(requests).map(r=>({key:requestKey("create",r.id),section:"create" as const,sig:`${r.status}|${latestJob(jobs,vms.find(v=>v.request_id===r.id)?.id,"provision")?.state??""}`,pending:r.status==="pending",quiet:r.status==="deleted"})),
    ...own(deletions).map(d=>({key:requestKey("delete",d.id),section:"delete" as const,sig:`${d.status}|${latestJob(jobs,d.vm_id,"delete")?.state??""}`,pending:d.status==="pending"})),
    ...own(resets).map(r=>({key:requestKey("reset",r.id),section:"reset" as const,sig:`${r.status}|${jobs.find(j=>j.id===r.job_id)?.state??""}`,pending:r.status==="pending"})),
  ];
}

export const jobDone=(job:Job)=>["succeeded","cancelled","failed"].includes(job.state);
export const trackJobs=(jobs:Job[]):TrackedRequest[]=>jobs.map(j=>({key:`job-${j.id}`,section:"job",sig:j.state,pending:!jobDone(j)}));

// Kept on the server per account (no browser storage), so a change seen on one
// device is not announced again on another. The first visit records everything
// as seen long ago instead of flooding alerts.
export function useRequestUpdates(userId:number|undefined,items:TrackedRequest[],ready:boolean,stored:Seen|null|undefined,persist:(seen:Seen)=>Promise<unknown>){
  const [seen,setSeen]=useState<Seen|null>(null);
  const save=(next:Seen)=>{setSeen(next);void persist(next).catch(()=>{/* Retried on the next view. */});};
  useEffect(()=>{
    if(!userId||!ready){setSeen(null);return;}
    const initial=(list:TrackedRequest[])=>Object.fromEntries(list.map(item=>[item.key,`${item.sig}@0`]));
    if(!stored){save({...initial(items),[JOBS_MARKER]:"seeded@0"});return;}
    if(!(JOBS_MARKER in stored)){save({...stored,...initial(items.filter(item=>item.section==="job")),[JOBS_MARKER]:"seeded@0"});return;}
    setSeen(stored);
  },[userId,ready]);
  const unseen=useMemo(()=>new Set(seen?items.filter(item=>{const entry=parse(seen[item.key]);if(item.quiet)return false;return entry===undefined?!item.pending:entry.sig!==item.sig;}).map(item=>item.key):[]),[seen,items]);
  // A finished request stays on the page for an hour after its result was first viewed.
  const recentlySeen=(key:string)=>{const entry=parse(seen?.[key]);return !!entry&&entry.at>0&&nowSeconds()-entry.at<SEEN_KEEP_SECONDS;};
  function markSeen(section:TrackedSection){
    if(!userId||!seen)return;
    const current=new Set(items.map(item=>item.key));
    const next=Object.fromEntries(Object.entries(seen).filter(([key])=>current.has(key)||key===JOBS_MARKER));
    let changed=Object.keys(next).length!==Object.keys(seen).length;
    // Only a new state gets a new timestamp, so revisiting never extends the hour.
    for(const item of items){
      const entry=parse(next[item.key]);
      if(item.section!==section||entry?.sig===item.sig)continue;
      // A quiet change keeps its old timestamp so it does not reappear for an hour.
      next[item.key]=`${item.sig}@${item.quiet?entry?.at??0:nowSeconds()}`;changed=true;
    }
    if(changed)save(next);
  }
  return {unseen,markSeen,recentlySeen};
}
