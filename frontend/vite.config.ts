import { defineConfig } from "vite";

// PORTAL_BASE_PATH (e.g. /vmportal) serves the portal under that URL path.
const base = (process.env.PORTAL_BASE_PATH ?? "").replace(/\/+$/, "") + "/";

export default defineConfig({ base, build: { target: "es2022" } });
