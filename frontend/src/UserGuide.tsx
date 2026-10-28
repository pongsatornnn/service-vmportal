import { ReactNode, useState } from "react";
import { SearchField } from "./SearchField";

function Steps({children}: {children: ReactNode}) {return <ol className="guide-steps">{children}</ol>;}
function Command({where, text}: {where: string; text: string}) {
  return <div className="guide-command"><div><span>{where}</span></div><pre><code>{text}</code></pre></div>;
}
// The everyday guide for people who request and use VMs; it names the buttons as they appear.
export function UserGuide() {
  const [selected,setSelected] = useState("start"), [search,setSearch] = useState("");
  const topics: {id: string; title: string; keywords: string; body: ReactNode}[] = [
    {id:"start",title:"1. สมัครและเข้าสู่ระบบ",keywords:"สมัคร login เข้าสู่ระบบ อนุมัติบัญชี session หมดอายุ",body:<>
      <Steps><li>หน้าเข้าสู่ระบบกด <strong>สร้างบัญชีใหม่</strong> กรอกชื่อ นามสกุล ชื่อผู้ใช้ และรหัสผ่าน (อย่างน้อย 12 ตัว มีตัวพิมพ์ใหญ่ ตัวพิมพ์เล็ก ตัวเลข และอักขระพิเศษ)</li><li>รอ Admin อนุมัติบัญชี ระหว่างนี้ยังเข้าสู่ระบบไม่ได้</li><li>เมื่ออนุมัติแล้ว เข้าสู่ระบบด้วยชื่อผู้ใช้และรหัสผ่าน ไม่ต้องใช้อีเมล</li></Steps>
      <p>ถ้าไม่ได้ใช้งานจนหมดเวลา ระบบจะให้เข้าสู่ระบบใหม่ ข้อมูลที่ส่งไปแล้วไม่หาย</p>
    </>},
    {id:"request",title:"2. ขอสร้าง VM",keywords:"ขอสร้าง template cpu ram disk quota โควตา hostname username password ssh key",body:<>
      <Steps>
        <li>เมนู <strong>ขอสร้าง VM</strong> เลือก <strong>ระบบปฏิบัติการ (Template)</strong> เช่น Ubuntu 24.04</li>
        <li>ตั้ง <strong>Hostname</strong> (ชื่อเครื่อง) ใช้ a–z, 0–9 และขีดกลาง เช่น <code>web01</code></li>
        <li>เลือก vCPU, RAM และ Disk ขนาด Disk ต้องไม่น้อยกว่าที่ Template กำหนด</li>
        <li>ตั้ง <strong>VM username</strong> (ค่าเริ่มต้น <code>ubuntu</code>) และเลือก <strong>วิธีเข้า VM</strong>: Password หรือ SSH public key</li>
        <li>ใส่เหตุผลที่ขอ แล้วกด <strong>ส่งคำขออนุมัติ</strong></li>
      </Steps>
      <h4>โควตา</h4>
      <p>การ์ดด้านบน (VM, vCPU, RAM, Disk) บอกว่าใช้และจองไปเท่าไร รวมคำขอที่รออนุมัติ ระหว่างกรอก หลอดจะแสดงส่วนของคำขอนี้ ถ้าการ์ดเป็นสีแดงแปลว่าเกินโควตา ปุ่มส่งจะกดไม่ได้ ให้ลดค่าที่ขอ หรือติดต่อผู้ดูแลเพื่อขอเพิ่มโควตา</p>
      <p className="guide-note">รหัส VM เป็นคนละรหัสกับรหัส Portal Admin ไม่เห็นรหัสนี้ และระบบลบสำเนาทิ้งหลังตั้งค่าเครื่องเสร็จ จดไว้ให้ดี</p>
    </>},
    {id:"status",title:"3. ติดตามคำขอ",keywords:"สถานะคำขอ แจ้งเตือน อนุมัติ ปฏิเสธ กิจกรรม สี รายละเอียด",body:<>
      <p>เมนู <strong>สถานะคำขอ</strong> แยกเป็นคำขอสร้าง ลบ และรีเซ็ตรหัส ตัวเลขบนเมนูคือรายการที่มีความคืบหน้าใหม่</p>
      <div className="table-wrap"><table><thead><tr><th>สี / สถานะ</th><th>ความหมาย</th></tr></thead><tbody>
        <tr><td>รออนุมัติ</td><td>ส่งคำขอแล้ว รอ Admin ตัดสินใจ</td></tr>
        <tr><td>กำลังดำเนินการ</td><td>อนุมัติแล้ว ระบบกำลังสร้างหรือตั้งค่าเครื่อง ใช้เวลาไม่กี่นาที</td></tr>
        <tr><td>สำเร็จ / พร้อมใช้งาน (เขียว)</td><td>เครื่องพร้อมใช้ที่เมนู เครื่องเสมือน</td></tr>
        <tr><td>ไม่อนุมัติ / ไม่สำเร็จ (แดง)</td><td>กด <strong>ดูรายละเอียด</strong> เพื่ออ่านเหตุผลจาก Admin</td></tr>
        <tr><td>ต้องตรวจสอบ</td><td>ระบบหยุดรอผู้ดูแลตรวจ ไม่ต้องส่งคำขอใหม่</td></tr>
      </tbody></table></div>
      <p>ทุกขั้นแสดงเวลาตามเวลาประเทศไทย และชื่อ Admin ที่ตัดสินใจ เมนู <strong>กิจกรรม</strong> แสดงงานที่ระบบทำกับเครื่อง เช่น เปิด ปิด Restart</p>
    </>},
    {id:"use",title:"4. ใช้งาน VM",keywords:"เครื่องเสมือน ip เปิด ปิด restart บังคับปิด console shell จัดการ",body:<>
      <p>เมนู <strong>เครื่องเสมือน</strong> แสดง VM ของคุณ สถานะ IP และการใช้ CPU / RAM กดปุ่ม <strong>จัดการ</strong> ของแต่ละเครื่อง:</p>
      <div className="table-wrap"><table><thead><tr><th>ปุ่ม</th><th>ใช้เมื่อ</th></tr></thead><tbody>
        <tr><td>อัปเดต IP</td><td>IP ยังไม่ขึ้นหรือเพิ่งเปลี่ยน (เครื่องต้องเปิดอยู่)</td></tr>
        <tr><td>เปิดเครื่อง / ปิดเครื่อง</td><td>ปิดเครื่องแบบปกติ ให้ระบบปฏิบัติการปิดตัวเอง</td></tr>
        <tr><td>Restart</td><td>เริ่มเครื่องใหม่</td></tr>
        <tr><td>บังคับปิดเครื่อง</td><td>เครื่องค้างจนปิดแบบปกติไม่ได้ งานที่ยังไม่บันทึกอาจหาย</td></tr>
        <tr><td>Console / Shell ↗</td><td>เปิดหน้าจอเครื่องในแท็บใหม่ ใช้ได้แม้ไม่มี IP ถ้าเบราว์เซอร์บล็อก popup ให้อนุญาตก่อน</td></tr>
      </tbody></table></div>
    </>},
    {id:"connect",title:"5. เข้าเครื่องผ่าน SSH",keywords:"ssh เข้าเครื่อง terminal putty key password ip",body:<>
      <p>ใช้ IP จากหน้า เครื่องเสมือน และ VM username ที่ตั้งตอนขอ (ดูได้ที่ <strong>จัดการ</strong> ของ VM บรรทัดบนสุด แสดงให้เจ้าของเห็นเท่านั้น ผู้ดูแลก็ดูไม่ได้):</p>
      <Command where="เครื่องของคุณ (Terminal / PowerShell)" text="ssh ubuntu@192.168.1.50"/>
      <p>ถ้าเลือก SSH public key ให้ใช้ private key คู่กัน เช่น <code>ssh -i ~/.ssh/id_ed25519 ubuntu@192.168.1.50</code> ถ้าเลือก Password การเข้า SSH ด้วยรหัสขึ้นกับ Template ที่ผู้ดูแลเตรียมไว้ ถ้าเข้าไม่ได้ให้ใช้ Console แทน</p>
    </>},
    {id:"reset",title:"6. ลืมรหัส VM",keywords:"ลืมรหัส vm รีเซ็ต reset password guest",body:<>
      <Steps><li>เปิดเครื่องไว้ก่อน</li><li>เครื่องเสมือน → <strong>จัดการ</strong> → <strong>ขอรีเซ็ตรหัส VM</strong> ตั้งรหัสใหม่และใส่เหตุผล</li><li>รอ Admin อนุมัติ ระบบจะเปลี่ยนรหัสของ VM username เดิมให้ ไม่ต้องรีสตาร์ทเครื่อง</li></Steps>
      <p>ยกเลิกคำขอที่ยังรออนุมัติได้ในหน้า สถานะคำขอ</p>
    </>},
    {id:"delete",title:"7. ลบ VM",keywords:"ลบ delete vm คืนโควตา",body:<>
      <Steps><li>ปิดเครื่องก่อน (ระบบไม่ลบเครื่องที่ยังเปิดอยู่)</li><li>เครื่องเสมือน → <strong>จัดการ</strong> → <strong>ขอลบ VM</strong> ใส่เหตุผล</li><li>รอผู้ดูแลอนุมัติ เมื่อลบสำเร็จ โควตาจะคืนให้ขอเครื่องใหม่ได้</li></Steps>
      <p className="guide-note">การลบเป็นการลบถาวร ข้อมูลในเครื่องกู้คืนไม่ได้ สำรองข้อมูลก่อนขอลบ</p>
    </>},
    {id:"account",title:"8. รหัส Portal และบัญชี",keywords:"เปลี่ยนรหัส portal ลืมรหัส โค้ดกู้คืน ออกจากระบบ",body:<>
      <p><strong>เปลี่ยนรหัส:</strong> กดชื่อบัญชีมุมขวาบน → <strong>เปลี่ยนรหัสผ่าน Portal</strong> แล้วเข้าสู่ระบบใหม่ทุกอุปกรณ์</p>
      <p><strong>ลืมรหัส:</strong> ติดต่อผู้ดูแลเพื่อขอโค้ดกู้คืน (ใช้ได้ 15 นาที ครั้งเดียว) แล้วกด <strong>ลืมรหัสผ่าน</strong> ที่หน้าเข้าสู่ระบบ กรอกโค้ดและตั้งรหัสใหม่</p>
      <p><strong>ออกจากระบบ</strong> ในเมนูบัญชี จะออกจากทุกอุปกรณ์พร้อมกัน</p>
    </>},
    {id:"trouble",title:"9. ปัญหาที่พบบ่อย",keywords:"ปัญหา ระบบยังไม่พร้อม ip ไม่ขึ้น console เปิดไม่ได้ เกินโควตา",body:<>
      <div className="table-wrap"><table><thead><tr><th>อาการ</th><th>ทำอย่างไร</th></tr></thead><tbody>
        <tr><td>มุมขวาบนขึ้น ระบบยังไม่พร้อม</td><td>ผู้ดูแลกำลังตั้งค่าหรือพักระบบ ส่งคำขอและสั่งงานไม่ได้ชั่วคราว รอแล้วลองใหม่</td></tr>
        <tr><td>IP ขึ้น —</td><td>รอเครื่องบูตสักครู่ แล้วกด อัปเดต IP</td></tr>
        <tr><td>Console เปิดไม่ได้</td><td>เครื่องต้องเปิดอยู่ อนุญาต popup และเปิดได้ครั้งละหนึ่งหน้าต่าง ปิดหน้าต่างเก่าก่อน</td></tr>
        <tr><td>ส่งคำขอไม่ได้ การ์ดเป็นสีแดง</td><td>เกินโควตา ลดค่าที่ขอ ลบเครื่องที่ไม่ใช้ หรือขอผู้ดูแลเพิ่มโควตา</td></tr>
        <tr><td>ปุ่มกดไม่ได้</td><td>เครื่องมีงานอื่นกำลังทำอยู่ หรือมีคำขอที่รออนุมัติ ดูที่ กิจกรรม / สถานะคำขอ</td></tr>
      </tbody></table></div>
    </>},
  ];
  const visible=topics.filter(t => `${t.title} ${t.keywords}`.toLowerCase().includes(search.toLowerCase()));
  const active=visible.find(t => t.id===selected) ?? visible[0];
  return <section className="panel admin-guide"><div className="section-head"><div><h2>คู่มือการใช้งาน</h2></div><span className="badge">{topics.length} หัวข้อ</span></div>
    <SearchField label="ค้นหาในคู่มือ" placeholder="ค้นหาในคู่มือ เช่น SSH, ลบ VM, โควตา" value={search} onChange={setSearch}/>
    <div className="guide-mobile-select"><label>เลือกหัวข้อคู่มือ<select value={active?.id??""} onChange={e=>setSelected(e.target.value)}>{visible.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label></div>
    <div className="guide-layout"><div className="guide-index">{visible.map(t => <button key={t.id} className={active?.id===t.id?"selected":""} onClick={() => setSelected(t.id)}><strong>{t.title}</strong></button>)}</div>
      {active ? <article key={active.id} className="guide-content"><h3>{active.title}</h3>{active.body}</article> : <p className="empty">ไม่พบหัวข้อ ลองค้นหาคำอื่น</p>}
    </div>
  </section>;
}
