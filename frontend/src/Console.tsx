import { BASE } from "./base";
import { useEffect, useRef, useState } from "react";
import RFB from "@novnc/novnc";

export function VMConsole({ ticket, password, onClose }: {
  ticket: string; password: string; onClose: () => void;
}) {
  const target = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("กำลังเชื่อมต่อ Console…");
  useEffect(() => {
    if (!target.current) return;
    const rfb = new RFB(target.current,
      `wss://${window.location.host}${BASE}api/console/socket`,
      { credentials: { password }, wsProtocols: ["portal", ticket] });
    rfb.scaleViewport = true;
    rfb.resizeSession = false;
    rfb.addEventListener("connect", () => setStatus("เชื่อมต่อแล้ว — Login ด้วยบัญชีภายใน VM"));
    rfb.addEventListener("disconnect", () => setStatus("Console ตัดการเชื่อมต่อ กรุณาปิดแล้วเปิดใหม่"));
    rfb.addEventListener("securityfailure", () => setStatus("เชื่อมต่อไม่สำเร็จ กรุณาตรวจสิทธิ์ VM.Console"));
    return () => rfb.disconnect();
  }, [ticket, password]);
  return <section className="panel">
    <div className="section-head"><h2>VM Console</h2><button onClick={onClose}>ปิด Console</button></div>
    <p>{status}</p>
    <div ref={target} className="vm-console" />
  </section>;
}
