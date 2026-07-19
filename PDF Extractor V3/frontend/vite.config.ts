import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env     = loadEnv(mode, process.cwd(), '')
  const apiPort = env.VITE_API_PORT ?? '8765'

  return {
    // Electron loads the built index.html via file:// (loadFile), so asset
    // references must be RELATIVE. Without this Vite emits "/assets/..."
    // which resolves to the filesystem root under file:// → white screen.
    base: './',
    plugins: [react()],
    server: {
      proxy: {
        '/api':       { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true },
        '/socket.io': { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true, ws: true },
      },
    },
    build: {
      outDir: '../electron/renderer',
      emptyOutDir: true,
      // Minify the production renderer with Terser for smaller, obfuscated output.
      // Requires `terser` in devDependencies (esbuild is the Vite default).
      minify: 'terser',
      sourcemap: false,
      terserOptions: {
        compress: {
          // Strip console.* and debugger statements from the shipped build.
          drop_console: true,
          drop_debugger: true,
        },
        format: {
          comments: false,
        },
      },
    },

  }
})
