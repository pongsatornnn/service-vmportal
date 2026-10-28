const known: Record<string,string> = {
  "VM confirmed missing from Proxmox":"ไม่พบ VM ใน Proxmox จึงยกเลิกงานโดยไม่ได้ส่งคำสั่ง สิทธิ์ใช้ทรัพยากรยังจองอยู่ รอ Admin ยืนยัน",
  'Session changed; retry after signing in':'บัญชีที่เข้าสู่ระบบเปลี่ยนแล้ว กรุณาลองใหม่',
  'VM must be stopped before approved deletion; no force stop performed':'กรุณาปิด VM ให้เรียบร้อยก่อนลบ ระบบไม่ได้บังคับปิดเครื่อง',
  'Operation failed or outcome uncertain; inspect worker and Proxmox logs.':'งานไม่สำเร็จหรือยังยืนยันผลไม่ได้ กรุณาให้ผู้ดูแลตรวจงานก่อนสั่งซ้ำ',
};
export function readableError(data: unknown, status: number, reference?: string|null): string {
  const value = data as {detail?: unknown; message?: unknown};
  let message: string;
  if(Array.isArray(value?.detail)) {
    const lines=value.detail.map(e=>typeof e?.msg==='string'?e.msg:'ข้อมูลที่กรอกไม่ถูกต้อง');
    message=[...new Set(lines)].join('\n');
  } else if(typeof value?.message==='string') message=value.message;
  else if(typeof value?.detail==='string'&&known[value.detail]) message=known[value.detail];
  else message=status===401?'กรุณาตรวจชื่อผู้ใช้และรหัสผ่าน หรือเข้าสู่ระบบใหม่':status===403?'คุณไม่มีสิทธิ์ทำรายการนี้ หรือบัญชียังไม่ได้รับอนุมัติ':status===404?'ไม่พบรายการหรือคุณไม่มีสิทธิ์เข้าถึง':status===429?'ทำรายการถี่เกินไป กรุณารอ 1 นาทีแล้วลองใหม่':status>=500?'ระบบหรือการเชื่อมต่อขัดข้อง กรุณาลองใหม่ภายหลัง':'ทำรายการไม่สำเร็จ กรุณาตรวจข้อมูลและสถานะล่าสุด';
  return message+(reference&&status>=500?`\nเลขอ้างอิง: ${reference}`:'');
}
export function jobError(text:string,operation?:string){return known[text]??(text.startsWith('Proxmox HTTP 403')?'สิทธิ์ Proxmox ไม่เพียงพอ ให้ผู้ดูแลตรวจ ACL ของ Token':text.startsWith('Proxmox connection interrupted')?operation==='provision'?'การเชื่อมต่อ Proxmox ขัดข้อง งานถูกพักไว้ ให้ Admin ตรวจที่หน้ากิจกรรมและทำต่อจากเครื่องเดิม ไม่ต้องส่งคำขอสร้างใหม่':'การเชื่อมต่อ Proxmox ขัดข้อง ให้ผู้ดูแลตรวจสถานะเครื่องและผล Task ในหน้ากิจกรรมก่อนดำเนินการต่อ':'งานไม่สำเร็จหรือผลไม่แน่นอน กรุณาให้ผู้ดูแลตรวจรายละเอียดงานก่อนดำเนินการต่อ');}
export function explainError(error:unknown){
 const message=error instanceof Error?error.message:'';
 if(known[message])return known[message];
 return /[\u0e00-\u0e7f]/.test(message)?message:'ทำรายการไม่สำเร็จ กรุณาโหลดข้อมูลล่าสุดแล้วลองใหม่ หากยังพบปัญหาให้ติดต่อผู้ดูแลระบบ';
}
