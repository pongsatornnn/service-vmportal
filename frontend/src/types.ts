export type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
  primary_admin?: boolean;
  top_admin?: boolean;
  status: string;
  quota_customized?: boolean;
  quota_vms: number;
  quota_cpu: number;
  quota_ram: number;
  quota_disk: number;
};
export type VM = {
  request_id?: number;
  presence_previous_status?: string | null;
  can_confirm_external_deletion?: boolean;
  id: number;
  vmid: number | null;
  owner_id: number;
  hostname: string;
  status: string;
};
export type Runtime = { power: string; ips: string[]; ip_error: string | null; cpu_percent?:number; cpu_count?:number; memory_used?:number; memory_total?:number; uptime_seconds?:number };
export type Deletion = { id: number; vm_id: number; owner_id: number; status: string; reason: string; decision_reason: string | null; decided_by_name?: string | null; decided_at?: string | null; created_at?: string };
export type VMRequest = {
  request_reason: string | null;
  id: number;
  owner_id: number;
  hostname: string;
  cpu: number;
  ram: number;
  disk: number;
  status: string;
  reason: string | null;
  decided_by_name?: string | null;
  decided_at?: string | null;
  template_id?: number | null;
  template_name?: string | null;
  created_at?: string;
  auth_method: "password" | "ssh_key";
  guest_username: string | null;
  ssh_password_login: boolean;
};
export type Job = {
  id: number;
  vm_id: number;
  operation: string;
  state: string;
  checkpoint: string;
  error: string | null;
  user_message?: string | null;
  reviewed_by_name?: string | null;
  created_at?: string;
  finished_at?: string | null;
};
// Users get id, name, description and min_disk_gb; admins also the clone details.
export type Template = {
  id: number;
  name: string;
  description: string;
  min_disk_gb: number;
  vmid: number;
  disk_device: string;
  enabled: boolean;
  verified: boolean;
  verified_at: string | null;
  // Pending requests that still need this template; deleting waits for them.
  in_use: number;
  requests: number;
};
export type Audit = {
  id: number;
  action: string;
  actor_id: number | null;
  target: string;
  created_at: string;
  details: unknown;
};
export type Dashboard = {
  user: User;
  request_seen?: Record<string, string> | null;
  usage: Record<string, number>;
  // Approved plus pending requests: what new requests are checked against.
  reserved?: Record<string, number>;
  setup?: {
    configured: boolean;
    enabled: boolean;
    connection_verified: boolean;
  };
  execution_mode: string;
  execution_enabled: boolean;
  ssh_password_login_available: boolean;
};
export type PasswordReset = {job_id?: number | null; id: number; vm_id: number; owner_id: number; status: string; reason: string; decision_reason: string | null; decided_by_name?: string | null; decided_at?: string | null; created_at?: string};
