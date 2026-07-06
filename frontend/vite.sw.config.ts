import { defineConfig } from "vite";

// Second build pass: emits the service worker as a single classic script at
// the stable root URL dist/sw.js (module workers are not universally
// supported, e.g. Firefox). Runs after the main build; emptyOutDir=false.
export default defineConfig({
  publicDir: false,
  build: {
    target: "es2022",
    outDir: "dist",
    emptyOutDir: false,
    lib: {
      entry: "src/sw.ts",
      formats: ["iife"],
      name: "sw",
      fileName: () => "sw.js",
    },
    rollupOptions: {
      output: { inlineDynamicImports: true },
    },
  },
});
