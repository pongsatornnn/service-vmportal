import { SearchField } from "./SearchField";
import { explainError } from "./errors";
import { ReactNode, useEffect, useState } from "react";

type API = <T>(path: string, body?: unknown) => Promise<T>;
type Infrastructure = {node: string; pool: string; storage: string; bridge: string; template: number; token_id: string; url: string};
function Command({where, text}: {where: string; text: string}) {
  return <div className="guide-command"><div><span>{where}</span></div><pre><code>{text}</code></pre></div>;
}
function Steps({children}: {children: ReactNode}) {return <ol className="guide-steps">{children}</ol>;}
export function AdminGuide({api}: {api: API}) {
  const [current,setCurrent] = useState<Infrastructure>({node:"Node3",pool:"Portal-Service",storage:"local-lvm",bridge:"VLAN48",template:9200,token_id:"vmportal@pve!portal-api",url:"https://Node3.localhot.com:8006"});
  const [selected,setSelected] = useState("start"), [search,setSearch] = useState(""), [error,setError] = useState("");
  useEffect(() => {let active=true;api<{values: Partial<Infrastructure>}>("/admin/settings").then(r => {if(active)setCurrent(v => ({...v,...r.values}));}).catch(e => {if(active)setError(explainError(e));});return () => {active=false;};}, []);
  const serviceUser = current.token_id.split("!")[0];
  const topics: {id: string; title: string; summary: string; keywords: string; body: ReactNode}[] = [
    {id:"start",title:"1. เตรียมระบบและลำดับติดตั้ง",summary:"เริ่มที่ไหน อะไรทำบน Proxmox และอะไรทำใน Ubuntu",keywords:"เริ่มต้น setup infrastructure node pool storage bridge",body:<>
      <p>Portal ทำงานบน Ubuntu Server แยกจาก Proxmox ผ่าน HTTPS ภายใน LAN ผู้ใช้เลือกทรัพยากรและบัญชี Guest ได้ ส่วน Node, Pool, Storage, Bridge และ Template กำหนดโดย Admin</p>
      <Steps><li>เตรียม Pool, Storage และ Bridge บน Proxmox แล้วสร้าง Service User / API Token ตามหัวข้อสิทธิ์</li><li>เตรียม Ubuntu Golden Template ให้มี Cloud-Init, SSH และ QEMU Guest Agent</li><li>หน้า ตั้งค่า → Proxmox: กรอก Endpoint, Token และอัปโหลด CA ครั้งแรก → เลือก Node/Storage และติ๊กเครือข่าย → บันทึกและตรวจสอบ → เปิดใช้งาน แล้วไปแท็บ Template: เพิ่ม Template ตั้งชื่อที่ผู้ใช้เห็น (เช่น Ubuntu 24.04) → ตรวจสอบ → เปิดให้ขอ</li><li>อนุมัติบัญชีและคำขอ VM ในเมนู รออนุมัติ ตรวจผลที่ กิจกรรม แล้วทดสอบ SSH/IP ของ VM เครื่องแรก</li></Steps>
      <div className="table-wrap"><table><thead><tr><th>ทำที่ไหน</th><th>งาน</th></tr></thead><tbody><tr><td>Proxmox UI / Shell ของ Node</td><td>สิทธิ์, Hardware, Cloud-Init drive, Clone และ Convert Template</td></tr><tr><td>ภายใน Ubuntu Guest</td><td>apt, SSH policy, Guest Agent และ cloud-init clean</td></tr><tr><td>Portal</td><td>Setup, Session, อนุมัติ, คำสั่ง VM และ Audit</td></tr></tbody></table></div>
      <p className="guide-note">คำสั่งในคู่มือนี้มีไว้คัดลอกเพื่อให้ Admin รันเอง หน้าเว็บไม่รันคำสั่งหรือสร้าง VM ให้โดยอัตโนมัติ ตัวอย่าง VMID 9300 ต้องตรวจว่าเลขว่างก่อนใช้</p>
    </>},
    {id:"permissions",title:"2. กำหนดสิทธิ์ User และ API Token",summary:"Role ที่ต้องใช้และ Path ที่จำกัดขอบเขต",keywords:"permission token user role acl clone allocate audit unrestricted console privilege separation SDN",body:<>
      <p>ใน Proxmox ใช้ Datacenter → Permissions → Roles สร้าง Custom Role แล้ว Add → User Permission และ API Token Permission ตาม Path ด้านล่าง เปิด Propagate สำหรับการสืบทอดใน Pool หากเปิด Privilege Separation สิทธิ์ที่ใช้ได้ต้องมีทั้ง Service User และ Token</p>
      <p><strong>Service User:</strong> {serviceUser} · <strong>Token ID:</strong> {current.token_id} · Secret เก็บใน Setup เท่านั้น ไม่แสดงในคู่มือ</p>
      <div className="table-wrap"><table><thead><tr><th>Path</th><th>Privileges</th></tr></thead><tbody>
        <tr><td>/vms/{current.template}</td><td>VM.Clone, VM.Audit</td></tr>
        <tr><td>/pool/{current.pool}</td><td>VM.Allocate, VM.Audit, VM.PowerMgmt, VM.Config.CPU, VM.Config.Memory, VM.Config.Disk, VM.Config.Network, VM.Config.Cloudinit, VM.Config.Options</td></tr>
        <tr><td>/storage/{current.storage}</td><td>Datastore.AllocateSpace</td></tr>
        <tr><td>/nodes/{current.node}</td><td>Sys.Audit</td></tr>
        <tr><td>/ (ทางเลือกสำหรับตรวจ VM หายอัตโนมัติ)</td><td>Sys.Audit สำหรับอ่านสถานะ Cluster; ไม่จำเป็นหาก Admin ตรวจใน Proxmox แล้วพิมพ์ชื่อ VM เพื่อยืนยันการลบจากภายนอก ระบบบันทึกว่า Admin เป็นผู้ยืนยัน</td></tr>
        <tr><td>/sdn/zones/localnetwork/{current.bridge}</td><td>SDN.Use สำหรับ Bridge ใน localnetwork ให้ยืนยัน Path จริงจาก Proxmox</td></tr>
        <tr><td>/pool/{current.pool}</td><td>VM.Console สำหรับ Console และ VM.GuestAgent.Audit สำหรับ IP/ข้อมูล Agent</td></tr>
        <tr><td>/pool/{current.pool} หรือ /vms/VMID ที่อนุญาต</td><td>VM.GuestAgent.Unrestricted เฉพาะเมื่อใช้รีเซ็ตรหัส Guest ผ่าน Portal</td></tr>
      </tbody></table></div>
      <p className="guide-note">Unrestricted เป็นสิทธิ์กว้างภายใน Guest รวมคำสั่งและไฟล์ ให้จำกัด VM/Pool ไม่ให้ที่ / และไม่ต้องเพิ่ม Administrator การเปลี่ยน Template ต้องเพิ่ม VM.Clone/VM.Audit ให้ Path ของ Template ใหม่ด้วย อย่าลบ Role เดิมตอนเพิ่มสิทธิ์เสริม</p>
    </>},
    {id:"golden",title:"3. สร้าง Golden Template",summary:"Ubuntu 24.04 Cloud Image พร้อม SSH และ Guest Agent แบบ Template ที่ใช้อยู่",keywords:"golden template ubuntu cloud image import disk clone agent SSH nano net-tools",body:<>
      <p>Template ที่ Portal ใช้อยู่คือ <strong>VMID {current.template}</strong> บน {current.node} คู่มือนี้รวมขั้นตอน Ubuntu 24.04 Cloud Image → SSH → Guest Agent → Clean → Convert ไว้ในหัวข้อเดียว สำหรับเตรียม Template แบบที่ใช้งานอยู่</p>
      <p>ทำตามลำดับนี้สำหรับเครื่องใหม่ ใช้ VMID 9300 เป็นตัวอย่าง ห้ามใช้เลขของ VM/Template ที่มีอยู่ แยกให้ออกระหว่าง Shell ของ Proxmox กับ Terminal ภายใน Ubuntu Guest</p>
      <h4>ขั้นที่ 1: เตรียม Network และพื้นที่เก็บ</h4>
      <Steps><li>เข้า Proxmox → {current.node} → Shell ด้วยบัญชี Admin ตรวจ Datacenter → Storage ว่า {current.storage} รองรับ Disk image และมีพื้นที่พอ</li><li>ตรวจ {current.node} → System → Network ว่ามี Bridge {current.bridge} เชื่อมต่อเครือข่ายที่มี DHCP จริง ชื่อ Bridge ไม่ได้หมายความว่า Portal สร้าง VLAN ให้</li><li>Datacenter → Permissions → Pools สร้าง {current.pool} หากยังไม่มี แล้วตรวจ VMID ในทั้ง Cluster ก่อนเลือก 9300</li></Steps>
      <Command where="Shell ของ Proxmox — ตรวจเลขและทรัพยากรก่อนสร้าง" text={`pvesh get /cluster/resources --type vm
pvesm status
ip link show ${current.bridge}`} />
      <h4>ขั้นที่ 2: ดาวน์โหลด Ubuntu Cloud Image</h4>
      <p>ใช้ไฟล์ .img ของ Ubuntu Server 24.04 LTS amd64 จาก <a href="https://cloud-images.ubuntu.com/noble/current/" target="_blank" rel="noreferrer">Ubuntu Cloud Images</a> ไม่ใช่ ISO ติดตั้งปกติ ดาวน์โหลด <a href="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img" target="_blank" rel="noreferrer">noble-server-cloudimg-amd64.img</a> และ <a href="https://cloud-images.ubuntu.com/noble/current/SHA256SUMS" target="_blank" rel="noreferrer">SHA256SUMS</a> ให้ครบทั้งสองไฟล์ หาก Node ออกอินเทอร์เน็ตไม่ได้ ให้ดาวน์โหลด image และ SHA256SUMS บนคอมพิวเตอร์ที่เข้าถึงได้ แล้วส่งสองไฟล์ไป Node ผ่าน SCP/SFTP ที่ /var/lib/vz/template/iso/ubuntu-noble/ (สร้างโฟลเดอร์ก่อน) ไม่ใช้ปุ่ม Upload ISO กับไฟล์ .img จากนั้นข้ามคำสั่ง wget แล้วตรวจ checksum ในโฟลเดอร์นี้</p>
      <Command where="Shell ของ Proxmox — ดาวน์โหลดและตรวจ checksum" text={`mkdir -p /var/lib/vz/template/iso/ubuntu-noble
cd /var/lib/vz/template/iso/ubuntu-noble
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
wget https://cloud-images.ubuntu.com/noble/current/SHA256SUMS
grep 'noble-server-cloudimg-amd64.img$' SHA256SUMS | sha256sum --check --status && echo 'Checksum OK'`} />
      <p>ต้องเห็น Checksum OK ก่อนใช้ ถ้าไม่ผ่านให้ดาวน์โหลดทั้งสองไฟล์ใหม่จากชุดเดียวกัน อย่าข้ามตรวจ</p>
      <h4>ขั้นที่ 3: สร้าง VM สำหรับเตรียม Template</h4>
      <p>คำสั่งถัดไปสร้าง VM จริง Admin ต้องเลือกเลขว่างแล้วจึงรันเอง ไม่ใช้ VMID ของ Template ปัจจุบัน {current.template}</p>
      <p className="muted">หากต้องการ VM หลายขา ให้ติ๊ก Bridge ในช่องเครือข่ายของ VM จำนวนขาจะนับให้อัตโนมัติ หากต้องใช้ Bridge เดิมหลายใบ ให้เปิดกำหนดแต่ละขาเอง ระบบเพิ่มการ์ดให้ตอน Clone และตั้ง DHCP ทุกขา ไม่ต้องเพิ่มการ์ดใน Template ล่วงหน้า</p>
      <Command where="Shell ของ Proxmox — สร้างเครื่องเตรียม ไม่ใช่คำสั่งใน Guest" text={`qm create 9300 --name ubuntu2404-template-portal --memory 2048 --cores 2 --scsihw virtio-scsi-pci --net0 virtio,bridge=${current.bridge} --pool ${current.pool}
qm set 9300 --scsi0 ${current.storage}:0,import-from=/var/lib/vz/template/iso/ubuntu-noble/noble-server-cloudimg-amd64.img
qm set 9300 --ide2 ${current.storage}:cloudinit --boot order=scsi0 --agent enabled=1 --ciuser ubuntu --ipconfig0 ip=dhcp
qm disk resize 9300 scsi0 20G
qm set 9300 --serial0 socket --vga serial0
qm config 9300`} />
      <p>20 GiB เป็นขนาดตัวอย่างของเครื่องเตรียมใหม่ ส่วน Template ปัจจุบัน 9200 มีดิสก์ 3584 MiB ไม่ต้องขยายเครื่องเดิมตามตัวอย่าง ต้องเห็น scsi0 ขนาด20G บนเครื่องเตรียม, ide2 เป็น Cloud-Init, agent เปิด และ Bridge ถูกต้อง serial0 ใช้แสดง Console ของ Cloud Image เลือก xterm.js ใน Proxmox เมื่อต้องเข้า serial console</p>
      <h4>ขั้นที่ 4: ตั้งรหัสแล้วเข้า Ubuntu ก่อนลง packages</h4>
      <Steps><li>เลือก VM9300 → Cloud-Init → User เป็น ubuntu → Password ตั้งรหัสชั่วคราวที่จำได้ → IP Config เป็น DHCP → Regenerate Image อย่าใส่รหัสใน shell history</li><li>Start VM แล้วเปิด Console (serial/xterm.js) รอ Boot และ Login ด้วย ubuntu กับรหัสที่ตั้ง หากเข้าไม่ได้ ตรวจ Cloud-Init disk และ user/password ก่อนสร้างใหม่</li><li>ใน Guest ใช้ ip -br address เพื่อดู IP แล้วลอง SSH จากเครื่องของคุณด้วย ssh ubuntu@IP ถ้า Password login ยังไม่ได้ ให้ใช้ Console ตั้งนโยบาย SSH ในหัวข้อถัดไปก่อน ซึ่งไม่ต้อง apt install หากมี sshd แล้ว</li><li>ทดสอบ DNS และ HTTPS ด้วย getent hosts archive.ubuntu.com และ curl -I https://archive.ubuntu.com หากยังไม่มี curl ให้ตรวจการเชื่อมต่อผ่าน Console ก่อน apt update</li></Steps>
      <h4>ขั้นที่ 5: ติดตั้งเครื่องมือภายใน Ubuntu Guest</h4>
      <Command where="ภายใน Ubuntu VM เตรียม Template ไม่ใช่ Node" text={"sudo cloud-init status --wait\nsudo apt update\nsudo apt install -y nano net-tools curl wget htop unzip zip jq dnsutils iputils-ping ca-certificates openssh-server cloud-init qemu-guest-agent\nsudo systemctl start qemu-guest-agent\nsudo systemctl status qemu-guest-agent --no-pager"} />
      <h4>ขั้นที่ 6: ตั้ง SSH Password และตรวจ Guest Agent</h4>

      <p>ตั้ง policy ภายใน Ubuntu ของ VM เตรียม Template ครั้งเดียว Portal จะใส่ Username/Password ของแต่ละเครื่องผ่าน Cloud-Init ไม่ต้องใช้ vendor snippet</p>
      <Command where="ภายใน Ubuntu Guest" text={"sudo tee /etc/cloud/cloud.cfg.d/99-portal-ssh.cfg >/dev/null <<'EOF'\nssh_pwauth: true\ndisable_root: true\nssh_deletekeys: true\nEOF\nsudo tee /etc/ssh/sshd_config.d/00-portal-ssh.conf >/dev/null <<'EOF'\nPasswordAuthentication yes\nPubkeyAuthentication yes\nPermitRootLogin no\nEOF\nsudo /usr/sbin/sshd -t\nsudo systemctl enable --now ssh\nsudo systemctl reload ssh\nsudo /usr/sbin/sshd -T | grep -E 'passwordauthentication|permitrootlogin'"} />
      <p>ควรได้ passwordauthentication yes และ permitrootlogin no ทดสอบ SSH ด้วย user ubuntu และรหัสชั่วคราวก่อนล้างเครื่อง Ubuntu ใช้ค่าตัวแรกที่พบใน SSH configuration ให้ตรวจ sshd -T ไม่ดูจากไฟล์เพียงอย่างเดียว</p>
      <h4>Guest Agent ขึ้น dependency failed</h4><Steps><li>Guest: ตรวจ ls -l /dev/virtio-ports/org.qemu.guest_agent.0</li><li>ถ้าไม่มีอุปกรณ์ ให้ sudo poweroff จาก Guest → Proxmox Options เปิด QEMU Guest Agent → Start ใหม่ให้ครบวงจร</li><li>กลับเข้า Guest แล้ว start qemu-guest-agent อีกครั้ง การติดตั้ง package อย่างเดียวไม่ทำให้อุปกรณ์ปรากฏ</li></Steps>
      <Command where="Shell ของ Node — อ่านอย่างเดียว ตัวอย่าง VMID 9300" text={"qm agent 9300 ping\nqm guest cmd 9300 network-get-interfaces"} />
      <p>IP ใน Portal ต้องมี VM.GuestAgent.Audit ส่วนรีเซ็ตรหัสต้องมี Unrestricted เพิ่ม การรีเซ็ตเปลี่ยนรหัสผ่าน Guest Agent ขณะ VM เปิดอยู่ ไม่รีบูตเครื่อง จากนั้นลบรหัสเดิมออกจาก Cloud-Init (cipassword) เพื่อไม่ให้ Regenerate ภายหลังคืนรหัสเก่า หากลบไม่ได้ รีเซ็ตยังถือว่าสำเร็จและบันทึก proxmox.cloudinit_password.clear_failed ไว้ใน Audit การแก้ Template ไม่ย้อนมาเปลี่ยน VM ที่สร้างไปแล้ว</p>
      <h4>ขั้นที่ 7: ทำความสะอาดและ Convert เป็น Template</h4>

      <p>ทำหลังตรวจ packages, SSH และ Agent ผ่านแล้ว ตัวอย่างใช้บัญชี ubuntu และ VMID 9300 ต้องเปลี่ยนให้ตรงกับเครื่องเตรียมจริง</p>
      <Command where="ภายใน Ubuntu Guest — หลังคำสั่งนี้เครื่องจะปิด" text={"sudo -i\npasswd -l ubuntu\nif [ -f /home/ubuntu/.ssh/authorized_keys ]; then truncate -s 0 /home/ubuntu/.ssh/authorized_keys; fi\napt-get clean\ncloud-init clean --logs --machine-id\npoweroff"} />
      <p>หลัง clean อย่า Start ก่อน Convert ตรวจจาก Node ว่า stopped แล้ว</p><Command where="Shell ของ Node — ตรวจอย่างเดียว" text={"qm status 9300\nqm config 9300"} />
      <p>ลบเฉพาะรายการที่มีใน config: cipassword, sshkeys และ cicustom เก่าที่ไม่ใช้ในแนวทาง SSH policy ภายใน Template ถ้าไม่มีก็ข้าม ไม่ลบ ciuser หรือ agent</p>
      <Command where="Shell ของ Node — ลบเฉพาะฟิลด์ที่มีจริง" text={"qm set 9300 --delete cipassword\n# ถ้ามี sshkeys หรือ cicustom ที่ไม่ใช้ ค่อยลบแยกทีละฟิลด์\nqm cloudinit update 9300\nqm template 9300\nqm config 9300"} />
      <Steps><li>ยืนยัน template: 1 และ agent: 1 แล้วเพิ่ม Clone/Audit บน /vms/9300 ให้ User/Token</li><li>Portal ตั้งค่า → Template → + เพิ่ม Template ตั้งชื่อที่ผู้ใช้เห็น เลือก VMID 9300 ระบบดึง Boot disk และขนาด Disk ให้ (ปัดขึ้นเป็น GiB เช่น 3584M เป็น 4 GiB) ตั้ง Disk ขั้นต่ำมากกว่านั้นได้ เช่น 20 GiB</li><li>กด ตรวจสอบ ให้ผ่าน แล้ว เปิดให้ขอ Template เดิมยังใช้ต่อได้ ปิดทีหลังเมื่อไม่ต้องการ คำขอที่อนุมัติแล้วใช้ Template ตอนอนุมัติเสมอ</li><li>Admin อนุญาตทดสอบสร้างจริงหนึ่งเครื่อง แล้วตรวจ SSH, IP, user/password และ packages ก่อนพิจารณาลบ Template เก่า</li></Steps>
    </>},
    {id:"templates",title:"4. เพิ่ม Template อื่น (Ubuntu เวอร์ชันอื่น, Debian, Windows Server)",summary:"สิ่งที่ Template ทุกตัวต้องมี และขั้นตอนสำหรับ Linux อื่นและ Windows Server",keywords:"template ubuntu 22.04 jammy debian bookworm windows server 2019 2022 2025 cloudbase-init virtio sysprep เพิ่ม template หลาย template",body:<>
      <p>Portal ให้ผู้ใช้เลือก Template ตามชื่อ แต่ละ Template คือ VM ที่ Convert เป็น Template บน Proxmox แล้วนำมาเพิ่มที่ ตั้งค่า → Template ขั้นตอนเตรียมเหมือนหัวข้อ 3 เป็นหลัก ต่างกันที่ไฟล์ต้นทางและเครื่องมือภายใน Guest</p>
      <h4>สิ่งที่ Template ทุกตัวต้องมี (ปุ่ม "ตรวจสอบ" จะเช็กให้)</h4>
      <Steps><li>อยู่บน Node เดียวกับที่ตั้งในแท็บ Proxmox ({current.node}) และ Convert เป็น Template แล้ว (template: 1)</li><li>มี Cloud-Init drive เช่น ide2: {current.storage}:cloudinit เพราะ Portal ส่งบัญชีผู้ใช้ รหัสผ่านหรือ SSH Key และ IP แบบ DHCP ผ่าน Cloud-Init</li><li>การ์ดเครือข่ายมีได้ไม่เกินจำนวนขาที่ตั้งในแท็บ Proxmox (ไม่ใส่เลยก็ได้) Portal จะใส่ net0, net1… ให้เองตอนสร้าง</li><li>Boot disk เป็น scsi/sata/virtio ที่อ่านขนาดได้ Disk ขั้นต่ำใน Portal ต้องไม่น้อยกว่าขนาดนี้ (ฟอร์มดึงให้อัตโนมัติ)</li><li>ไม่มี cicustom ที่มี user= เพราะจะทับรหัสผ่านที่ผู้ใช้ตั้ง</li><li>ติดตั้ง QEMU Guest Agent และเปิด agent: 1 เพื่อให้ Portal แสดง IP และรีเซ็ตรหัสได้</li><li>Token มี VM.Clone และ VM.Audit บน /vms/VMID ของ Template ใหม่ (หรือบน Pool ที่ Template อยู่)</li><li>ล้างข้อมูลเฉพาะเครื่องก่อน Convert เช่น machine-id, SSH host key, รหัสชั่วคราว และ authorized_keys</li></Steps>
      <h4>Ubuntu เวอร์ชันอื่น และ Debian</h4>
      <p>ทำตามหัวข้อ 3 ทุกขั้น เปลี่ยนแค่ไฟล์ Cloud Image, ชื่อ VM และ VMID ใหม่ที่ยังว่าง ใช้ไฟล์ Cloud Image (.img/.qcow2) เท่านั้น ไม่ใช้ ISO ติดตั้งปกติ</p>
      <div className="table-wrap"><table><thead><tr><th>ระบบ</th><th>ไฟล์ Cloud Image</th><th>หมายเหตุ</th></tr></thead><tbody>
        <tr><td>Ubuntu 22.04 LTS</td><td>cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img</td><td>ตรวจด้วย SHA256SUMS ในโฟลเดอร์เดียวกัน</td></tr>
        <tr><td>Ubuntu 24.04 LTS</td><td>cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img</td><td>แบบเดียวกับหัวข้อ 3</td></tr>
        <tr><td>Debian 12</td><td>cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2</td><td>ตรวจด้วย SHA512SUMS และต้องติดตั้ง qemu-guest-agent เอง</td></tr>
      </tbody></table></div>
      <Command where="Shell ของ Proxmox — ตัวอย่าง Ubuntu 22.04 ด้วย VMID 9310 (เปลี่ยนเลขให้ว่าง)" text={`mkdir -p /var/lib/vz/template/iso/ubuntu-jammy && cd /var/lib/vz/template/iso/ubuntu-jammy
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
wget https://cloud-images.ubuntu.com/jammy/current/SHA256SUMS
grep 'jammy-server-cloudimg-amd64.img$' SHA256SUMS | sha256sum --check --status && echo 'Checksum OK'
qm create 9310 --name ubuntu2204-template-portal --memory 2048 --cores 2 --scsihw virtio-scsi-pci --net0 virtio,bridge=${current.bridge}
qm set 9310 --scsi0 ${current.storage}:0,import-from=/var/lib/vz/template/iso/ubuntu-jammy/jammy-server-cloudimg-amd64.img
qm set 9310 --ide2 ${current.storage}:cloudinit --boot order=scsi0 --agent enabled=1 --ciuser ubuntu --ipconfig0 ip=dhcp
qm disk resize 9310 scsi0 20G
qm set 9310 --serial0 socket --vga serial0`} />
      <Command where="ภายใน Debian 12 Guest — ก่อนทำขั้นที่ 6 ของหัวข้อ 3" text={"sudo apt update\nsudo apt install -y qemu-guest-agent\nsudo systemctl enable --now qemu-guest-agent"} />
      <p>จากนั้นทำขั้นที่ 4–7 ของหัวข้อ 3 (ตั้ง SSH policy, ตรวจ Guest Agent, ล้างเครื่อง, qm template) แล้วเพิ่มใน Portal ตามหัวข้อ "เพิ่มใน Portal" ด้านล่าง</p>
      <h4>Windows Server (2019 / 2022 / 2025)</h4>
      <p className="alert warning">Portal สร้างเครื่องผ่าน Cloud-Init ซึ่ง Windows ไม่มีมาให้ ต้องติดตั้ง Cloudbase-Init แทน ยังไม่ได้ทดสอบ Windows กับ Portal นี้จริง ให้สร้างทดสอบ 1 เครื่องและตรวจครบทุกข้อก่อนกด "เปิดให้ขอ" และต้องมีสิทธิ์ใช้งาน (License) Windows Server สำหรับทุกเครื่องที่ Clone ออกไป</p>
      <h4>W1: เตรียมไฟล์</h4>
      <Steps><li>ISO ติดตั้ง Windows Server ที่มีสิทธิ์ใช้งาน อัปโหลดไว้ที่ local → ISO Images</li><li>virtio-win.iso (ไดรเวอร์ Disk/Network และ Guest Agent) จาก fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/</li></Steps>
      <h4>W2: สร้าง VM เตรียม Template</h4>
      <Command where="Shell ของ Proxmox — ตัวอย่าง VMID 9400 (เปลี่ยนชื่อไฟล์ ISO ให้ตรง)" text={`qm create 9400 --name winsrv2022-template-portal --ostype win11 --machine q35 --bios ovmf --cpu host --cores 2 --memory 4096 --scsihw virtio-scsi-single --net0 virtio,bridge=${current.bridge}
qm set 9400 --efidisk0 ${current.storage}:1,efitype=4m,pre-enrolled-keys=1
qm set 9400 --scsi0 ${current.storage}:60,discard=on,iothread=1
qm set 9400 --ide2 local:iso/WindowsServer2022.iso,media=cdrom --ide0 local:iso/virtio-win.iso,media=cdrom
qm set 9400 --boot order='ide2;scsi0' --agent enabled=1`} />
      <p className="muted">Windows Server 2019 ใช้ --ostype win10 ขนาด Disk 60 GiB เป็นตัวอย่าง ขนาดนี้จะเป็น Disk ขั้นต่ำของ Template</p>
      <h4>W3: ติดตั้ง Windows และไดรเวอร์</h4>
      <Steps><li>Start VM เปิด Console ตอนเลือก Disk กด Load driver → เลือกไดรฟ์ virtio-win → vioscsi\2k22\amd64 (2019 ใช้ 2k19) จึงจะเห็น Disk</li><li>ติดตั้งแบบ Desktop Experience หรือ Core ตามต้องการ ตั้งรหัส Administrator ชั่วคราว</li><li>ใน Windows เปิดไดรฟ์ virtio-win รัน virtio-win-guest-tools.exe ติดตั้งไดรเวอร์ทั้งหมดและ QEMU Guest Agent</li><li>ตรวจจาก Node ด้วย qm agent 9400 ping ต้องไม่ error</li><li>อัปเดต Windows ให้ครบ ตั้งเวลา Asia/Bangkok และเปิด Remote Desktop ถ้าจะให้ผู้ใช้เข้าทาง RDP</li></Steps>
      <Command where="PowerShell (Administrator) ภายใน Windows — ไม่บังคับ: เปิด RDP และ OpenSSH สำหรับผู้ใช้ที่เลือก SSH Key" text={"Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections -Value 0\nEnable-NetFirewallRule -DisplayGroup 'Remote Desktop'\nAdd-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0\nSet-Service sshd -StartupType Automatic"} />
      <h4>W4: ติดตั้ง Cloudbase-Init</h4>
      <Steps><li>ดาวน์โหลด CloudbaseInitSetup x64 (.msi) จาก cloudbase.it/cloudbase-init แล้วติดตั้ง</li><li>หน้าตั้งค่าของตัวติดตั้ง: Username ใส่ชื่อชั่วคราวได้ (Portal จะส่งชื่อจริงมาเอง) ติ๊ก Use metadata password ห้ามติ๊ก Run as LocalSystem ถ้าไม่จำเป็น</li><li>ยังไม่กด Finish ให้แก้ไฟล์ตั้งค่าตามด้านล่างก่อน</li></Steps>
      <p>แก้ทั้ง cloudbase-init.conf และ cloudbase-init-unattend.conf ในโฟลเดอร์ C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf ให้มีค่าเหล่านี้ (ใช้ Config Drive ที่ Proxmox สร้าง, ตั้งชื่อเครื่อง, สร้างผู้ใช้, ตั้งรหัส, ใส่ SSH Key และขยายพาร์ทิชันตาม Disk ที่ผู้ใช้ขอ):</p>
      <Command where="เพิ่มใต้ [DEFAULT] ในไฟล์ conf ทั้งสองไฟล์" text={"metadata_services=cloudbaseinit.metadata.services.configdrive.ConfigDriveService\nplugins=cloudbaseinit.plugins.common.sethostname.SetHostNamePlugin,cloudbaseinit.plugins.windows.createuser.CreateUserPlugin,cloudbaseinit.plugins.common.setuserpassword.SetUserPasswordPlugin,cloudbaseinit.plugins.common.sshpublickeys.SetUserSSHPublicKeysPlugin,cloudbaseinit.plugins.common.networkconfig.NetworkConfigPlugin,cloudbaseinit.plugins.windows.extendvolumes.ExtendVolumesPlugin,cloudbaseinit.plugins.common.userdata.UserDataPlugin\ngroups=Administrators\ninject_user_password=true\nfirst_logon_behaviour=no\nallow_reboot=true"} />
      <p className="muted">ถ้ามี Recovery Partition อยู่หลังไดรฟ์ C: ระบบจะขยาย C: ไม่ได้ ตรวจใน Disk Management และย้ายหรือลบ Recovery Partition ก่อน Sysprep</p>
      <h4>W5: Sysprep แล้ว Convert เป็น Template</h4>
      <Steps><li>กลับไปหน้าตัวติดตั้ง Cloudbase-Init ติ๊ก Run Sysprep to create a generalized image และ Shutdown when Sysprep terminates แล้วกด Finish เครื่องจะปิดเอง ห้าม Start อีก</li><li>ถอด ISO ทั้งสองแผ่นและใส่ Cloud-Init drive ตามคำสั่งด้านล่าง</li></Steps>
      <Command where="Shell ของ Proxmox — หลัง Windows ปิดเครื่องแล้ว" text={`qm status 9400
qm set 9400 --delete ide0
qm set 9400 --ide2 ${current.storage}:cloudinit --citype configdrive2 --boot order=scsi0
qm config 9400
qm template 9400`} />
      <h4>เพิ่มใน Portal และทดสอบ</h4>
      <Steps><li>ให้สิทธิ์ Token บน /vms/VMID ใหม่ (VM.Clone, VM.Audit และสิทธิ์ Guest Agent ตามหัวข้อ 2)</li><li>ตั้งค่า → Template → + เพิ่ม Template ตั้งชื่อที่ผู้ใช้เห็น เช่น "Ubuntu 22.04" หรือ "Windows Server 2022" เลือก VMID ระบบจะดึง Boot disk และขนาด Disk ให้ ปรับ Disk ขั้นต่ำได้ (Windows แนะนำ 60 GiB ขึ้นไป)</li><li>กด ตรวจสอบ ให้ผ่าน แต่ยังไม่ต้องเปิดให้ขอ</li><li>ทดสอบ: เปิดให้ขอชั่วคราว ขอสร้าง VM 1 เครื่องด้วยบัญชี Admin อนุมัติ แล้วตรวจว่าได้ IP, เข้าด้วยชื่อผู้ใช้/รหัสที่ขอได้, Disk ขยายตามที่ขอ และรีเซ็ตรหัสผ่าน Portal ได้ ถ้าไม่ผ่านให้กด ปิดไม่ให้ขอ แล้วแก้ Template</li><li>Windows: แจ้งผู้ใช้ให้เลือกวิธีเข้าเครื่องแบบ Password (SSH Key ใช้ได้เฉพาะเมื่อติดตั้ง OpenSSH ใน Template) และเข้าใช้งานผ่าน Console หรือ RDP</li></Steps>
    </>},
    {id:"setup",title:"5. เชื่อม Proxmox และ TLS",summary:"Endpoint, CA และความหมายของทรัพยากรใน Setup",keywords:"TLS CA certificate PEM endpoint node storage pool bridge allowlist setup verified enable",body:<>
      <p>Endpoint ปัจจุบัน: <strong>{current.url}</strong> ชื่อ/IP ใน URL ต้องตรง SAN ของ Certificate และ Portal Server ต้อง resolve ไป Proxmox ได้</p>
      <Command where="Shell ของ Node — อ่าน Public CA ไม่ใช่ Private Key" text="cat /etc/pve/pve-root-ca.pem" />
      <p>คัดลอก PEM นี้หรืออัปโหลดไฟล์ใน Setup ห้ามใช้ pve-ssl.key และไม่มีตัวเลือกปิด TLS verification ถ้าใช้ชื่อ Node3.localhot.com ให้ Portal Server resolve ชื่อนี้ไป IP ของ Proxmox ภายใน LAN</p>
      <ul><li>Node: โฮสต์ที่จะสร้าง VM ({current.node})</li><li>Pool: ขอบเขตทรัพยากร/สิทธิ์ ({current.pool})</li><li>Storage: ที่เก็บ Disk ({current.storage})</li><li>Bridge/allowlist: เครือข่ายที่ Backend อนุญาต ({current.bridge})</li><li>Template (แท็บ Template): ตั้งได้หลายตัว แต่ละตัวมีชื่อที่ผู้ใช้เห็น, VMID ใน Proxmox (เช่น {current.template}), Boot disk ที่จะขยาย (เช่น scsi0) และ Disk ขั้นต่ำ ต้องกดตรวจสอบให้ผ่านก่อนจึงเปิดให้ขอได้ ถ้าแก้ VMID/Boot disk/Disk ขั้นต่ำ หรือเปลี่ยนการเชื่อมต่อในแท็บ Proxmox ต้องตรวจสอบใหม่ คำขอที่อนุมัติแล้วใช้ค่าตอนอนุมัติเสมอ Template ที่มีคำขอใช้อยู่ลบไม่ได้ ให้ปิดแทน</li></ul>
      <p>เว้นช่อง Token Secret ว่างเพื่อเก็บค่าเดิมเมื่อแก้การตั้งค่า ปุ่มบันทึกและตรวจสอบจะบันทึกค่าและตรวจการเชื่อมต่อให้ต่อเนื่อง จากนั้นให้ Admin กดเปิดใช้งานแยกต่างหาก การตรวจ Read-only ไม่สร้าง VM การเปิดระบบจะอนุญาตงานที่ Admin อนุมัติให้ Worker ทำต่อ</p>
    </>},
    {id:"operate",title:"6. ใช้งานและแก้ปัญหาประจำวัน",summary:"อนุมัติ VM, Session, รหัสผ่าน, งานค้าง และการลบ",keywords:"session approval quota password reset recovery delete needs_review clone accepted running jobs audit resume resize close failed",body:<>
      <Steps><li>ผู้ใช้สมัคร → Admin อนุมัติบัญชีใน รออนุมัติ → ผู้ใช้ขอ VM → Admin อนุมัติเมื่อ Quota เพียงพอ</li><li>Worker ทำ Full Clone พร้อม Pool → CPU/RAM/Cloud-Init → Resize → Start ผู้ใช้จัดการได้เฉพาะเครื่องของตน Admin จัดการ VM ใน Portal ได้ทุกเจ้าของ</li><li>หน้า VM แสดง Power/IP แยกจากสถานะงาน ปุ่ม จัดการ รวม Restart, Console, รีเซ็ตรหัส และขอลบ</li><li>ตั้งค่า → Session ปรับ 5–1440 นาที มีผลกับ Login ถัดไป ไม่ใช่ idle timeout และไม่เปลี่ยนเวลาของ Session ที่เปิดอยู่ Console ไม่เกิน 15 นาทีหรือก่อน Portal Session หมดอายุ</li><li>เปลี่ยนรหัส Portal ที่เมนูบัญชี หากลืมให้ Admin ออกโค้ด 15 นาทีใน ผู้ใช้ ผู้ใช้ตั้งรหัสเองที่หน้า Login รหัส VM แยกจากรหัส Portal</li><li>รีเซ็ตรหัส VM ต้อง Guest Agent ทำงาน, Unrestricted และ Admin อนุมัติ เปลี่ยนเฉพาะ Guest username เดิม รหัสไม่ถูกแสดงย้อนหลัง</li><li>ขอลบ → Shutdown ให้ stopped → Admin พิมพ์ชื่อ VM ยืนยันลบ ไม่มี force stop อัตโนมัติ และคืน Quota หลัง Task สำเร็จ</li></Steps>
      <h4>งาน needs_review</h4><p>ระบบเก็บ VM ไว้ให้ตรวจ ไม่ลบเมื่อสร้างล้มเหลว ถ้า clone_accepted ให้ Admin ใช้ กิจกรรม → ตรวจและทำต่อจาก Clone เดิม ระบบตรวจ UPID เป็น OK ก่อน Configure/Resize/Start โดยไม่ Clone ซ้ำ หากงานลบถูกปฏิเสธเพราะยัง running ให้หยุดเครื่องแล้วใช้ปุ่มลองลบใหม่พร้อมพิมพ์ชื่อ กรณีผลคำสั่งไม่แน่นอนต้องตรวจ Task ก่อน ไม่กดส่งคำขอสร้างใหม่ซ้ำ</p>
      <p>ถ้าค้างหลังตั้งค่าเครื่องแล้ว (เช่น ขยาย Disk หรือเปิดเครื่องหมดเวลา) ให้ใช้ ตรวจและทำต่อจากขั้นที่ค้าง ระบบอ่านขนาด Disk และสถานะเครื่องจาก Proxmox ก่อน แล้วทำเฉพาะขั้นที่ยังไม่เสร็จ ถ้าทำต่อไม่ได้จริง ให้ใช้ ปิดงานและแจ้งผู้ใช้ พร้อมเขียนสาเหตุและสิ่งที่ผู้ใช้ควรทำ ข้อความนี้แสดงในหน้าคำขอของผู้ใช้ งานสร้าง VM ที่ปิดจะลบเครื่องที่ค้าง (ต้องปิดเครื่องอยู่) และคืนโควตา งานลบที่ปิดจะคืน VM ให้ใช้ต่อ งานรีเซ็ตรหัสที่ปิดจะให้ผู้ใช้ส่งคำขอใหม่</p>
      <p>Audit เก็บย้อนหลัง 7 วัน ประวัติงานสำเร็จและรายการที่ลบแล้วเก็บ 7 วันนับจากเสร็จสิ้น เปิดดูได้จากปุ่มประวัติด้านล่างของรายการ ซึ่งเปิดเป็น popup งานค้างหรือ needs_review ยังเก็บไว้จนจัดการเสร็จ</p>
    </>},
    {id:"monitor",title:"7. Dashboard, Session, ระดับผู้ดูแล และลบผู้ใช้",summary:"ภาพรวมทรัพยากร Node และสถานะ VM รายเครื่อง",keywords:"dashboard health monitoring CPU RAM session refresh console tab delete user ลบผู้ใช้",body:<>
      <Steps><li>หน้าเครื่องเสมือนของ Admin แสดงสุขภาพ Node จาก Proxmox: CPU, RAM, พื้นที่ Storage ของ VM และ Uptime อัปเดตทุก20วินาที ตัวเลข Node รวมการใช้งานบนโฮสต์ ไม่ใช่เฉพาะ VM ใน Portal; พื้นที่ VM อ่านจาก Storage ที่ตั้งค่าไว้ เช่น local-lvm ไม่ใช่พาร์ทิชันระบบ Node</li><li>แต่ละ VM มี CPU/RAM พร้อม Power/IP ตามข้อมูลจาก Proxmox ผู้ใช้เห็นเฉพาะ VM ของตน หาก Guest Agent ใช้ไม่ได้ยังดูตัวเลขทรัพยากรได้ แต่ IP อาจไม่แสดง</li><li>Node ต้องมี Sys.Audit บน /nodes/ชื่อNode; พื้นที่ Storage ต้องมี Datastore.Audit บน /storage/ชื่อStorage เมื่อ API ต้องการ; VM ต้องมี VM.Audit บน VM/Pool ของระบบ ข้อมูล IP ต้อง Guest Agent และ VM.GuestAgent.Audit ระบบไม่เพิ่มสิทธิ์ให้อัตโนมัติ</li><li>Console / Shell เปิดแท็บใหม่ หากถูกบล็อกให้อนุญาต popup สำหรับ Portal Console ยังผ่าน Backend และตรวจสิทธิ์ตามปกติ</li><li>Login คงอยู่เมื่อรีเฟรชแท็บเดิม จน Token หมดอายุหรือถูกเพิกถอน Logout/เปลี่ยนรหัส/ลบผู้ใช้จะยกเลิกสิทธิ์เดิม Backend ตรวจทุกครั้งที่เรียก API</li><li>ผู้ใช้ → ลบผู้ใช้ → ตรวจรายการ VM ทั้งหมด → Shutdown VM และรอให้งานเดิมเสร็จ → พิมพ์ชื่อบัญชี เหตุผล และรหัสผ่าน Admin แล้วยืนยัน ระบบไม่อนุญาตลบ Admin หรือตนเอง</li><li>เมื่อรับงาน บัญชีเปลี่ยนเป็นกำลังลบและ Login ถูกยกเลิก Worker ลบเฉพาะ VM ของบัญชีที่ Backend บันทึกไว้ เมื่อสำเร็จทั้งหมดจึงแสดงว่าลบแล้ว ประวัติและบัญชีที่ลบแล้วเก็บ 7 วันก่อนล้างเมื่อไม่มีงานอ้างอิง เมื่อลบสำเร็จชื่อเดิมสมัครใหม่ได้ทันที บัญชีใหม่ใช้ ID ใหม่และไม่รับประวัติของบัญชีเดิม</li><li>ถ้างานลบล้มเหลว บัญชีคงระงับและ VM แสดงต้องตรวจสอบ ให้ตรวจหน้ากิจกรรม ไม่ส่งลบซ้ำในกรณีที่ผลไม่แน่นอน กดปุ่มประวัติผู้ใช้ที่ลบแล้วเพื่อเปิด popup ได้</li></Steps>
      <h4>ระดับผู้ดูแลและการแจ้งผู้ใช้</h4><p>ผู้ดูแลหลัก (Admin คนแรกหรือที่สร้างจาก CLI) ยกระดับผู้ใช้ที่อนุมัติแล้วเป็น Admin ได้จากหน้าผู้ใช้ โดยพิมพ์ชื่อผู้ใช้และรหัส Portal ของตนเพื่อยืนยัน Admin ที่ยกระดับอนุมัติคำขอ จัดการ VM งานค้าง และตั้งค่าได้ แต่ลบผู้ใช้ เปลี่ยนสิทธิ์ผู้อื่น และออกโค้ดกู้คืนให้ Admin คนอื่นไม่ได้ ทุกการอนุมัติ ปฏิเสธ ทำต่อ หรือปิดงานจะแสดงชื่อ Admin ผู้ทำให้เจ้าของคำขอเห็นในหน้าสถานะคำขอ ซึ่งแยกตามประเภทและแจ้งเตือนเมื่อสถานะเปลี่ยน</p>
    </>},

  ];
  const visible=topics.filter(t => `${t.title} ${t.summary} ${t.keywords}`.toLowerCase().includes(search.toLowerCase()));
  const active=visible.find(t => t.id===selected) ?? visible[0];
  return <section className="panel admin-guide"><div className="section-head"><div><h2>คู่มือผู้ดูแลระบบ</h2></div><span className="badge">{topics.length} หัวข้อ</span></div>
    {error && <p className="alert error">อ่านค่าปัจจุบันไม่ได้: {error} ข้อมูลตัวอย่างยังอ่านได้ แต่ต้องตรวจค่าใน Setup ก่อนใช้</p>}
    <SearchField label="ค้นหาในคู่มือ" placeholder="ค้นหาในคู่มือ เช่น Template, สิทธิ์, SSH" value={search} onChange={setSearch}/>
    <div className="guide-mobile-select"><label>เลือกหัวข้อคู่มือ<select value={active?.id??""} onChange={e=>setSelected(e.target.value)}>{visible.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label></div>
    <div className="guide-layout"><div className="guide-index">{visible.map(t => <button key={t.id} className={active?.id===t.id?"selected":""} onClick={() => setSelected(t.id)}><strong>{t.title}</strong></button>)}</div>
      {active ? <article key={active.id} className="guide-content"><h3>{active.title}</h3>{active.body}<p className="muted">อ้างอิง: <a href="https://github.com/proxmox/pve-docs/blob/master/qm-cloud-init.adoc" target="_blank" rel="noreferrer">Proxmox Cloud-Init</a> · <a href="https://ubuntu.com/server/docs/how-to/security/openssh-server/" target="_blank" rel="noreferrer">Ubuntu OpenSSH</a></p></article> : <p className="empty">ไม่พบหัวข้อ ลองค้นหาคำอื่น</p>}
    </div>
  </section>;
}
