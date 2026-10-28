// Every time in the portal is shown in Thai time, whatever the viewer's device says.
const formatter=new Intl.DateTimeFormat("th-TH",{timeZone:"Asia/Bangkok",day:"numeric",month:"short",year:"2-digit",hour:"2-digit",minute:"2-digit"});
export const thaiTime=(iso?:string|null)=>iso?`${formatter.format(new Date(iso))} น.`:"";
