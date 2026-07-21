import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base URL is read at runtime from VITE_API_BASE (see api.ts),
// defaulting to http://localhost:8000. The frontend NEVER talks to Neo4j.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
