import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/chat": "http://localhost:50505",
            "/config": "http://localhost:50505",
            "/norms": "http://localhost:50505",
            "/evaluate": "http://localhost:50505",
            "/health": "http://localhost:50505",
        },
    },
    build: {
        outDir: "dist",
        sourcemap: true,
    },
});
