import vinext from "vinext";
import { defineConfig } from "vite";

// Local Node server; Cloudflare bindings are not required by this dashboard.
export default defineConfig({ plugins: [vinext()] });
