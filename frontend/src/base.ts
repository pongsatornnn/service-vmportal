/// <reference types="vite/client" />
// The portal may be served under a URL path such as /vmportal; the build sets it.
export const BASE = import.meta.env.BASE_URL;
export const at = (path: string) => BASE + path.replace(/^\//, "");
