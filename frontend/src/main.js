import { createApp } from "vue"
import { Button, FrappeUI } from "frappe-ui"

import App from "./App.vue"
import router from "./router"
import { rememberOnboarding } from "./data/store"
import "./main.css"

// A consultant opens the portal from the desk with ?id=ONB-...; a customer
// never needs it, because the server finds the onboarding from their login.
rememberOnboarding(new URLSearchParams(window.location.search).get("id"))

const app = createApp(App)
app.use(router)
app.use(FrappeUI)
app.component("Button", Button)
app.mount("#app")
