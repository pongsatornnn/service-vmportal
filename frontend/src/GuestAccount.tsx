import { useState } from "react";

// Hidden until the owner asks; the menu unmounts on close, so it hides again.
export function GuestAccount({ name }: { name: string }) {
  const [shown, setShown] = useState(false);
  return shown
    ? <p className="menu-info" role="status">บัญชีในเครื่อง VM <strong>{name}</strong></p>
    : <button type="button" onClick={e => { e.stopPropagation(); setShown(true); }}>แสดงบัญชีในเครื่อง VM</button>;
}
