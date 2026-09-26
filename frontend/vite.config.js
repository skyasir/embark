import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import path from "path"

export default defineConfig({
	plugins: [
		// Owns the bench proxy, the asset base URL, the build output directory
		// and copying the built index.html to www/embark.html.
		frappeui({ frontendRoute: "/embark" }),
		vue(),
	],
	server: { port: 8082, allowedHosts: true },
	resolve: { alias: { "@": path.resolve(__dirname, "src") } },
	build: {
		rollupOptions: { output: { manualChunks: { "frappe-ui": ["frappe-ui"] } } },
	},
	optimizeDeps: {
		include: ["frappe-ui > feather-icons", "showdown", "tailwind.config.js"],
	},
})
