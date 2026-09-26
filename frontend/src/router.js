import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{ path: "/", name: "home", component: () => import("./pages/Home.vue") },
	{ path: "/business", name: "interview", component: () => import("./pages/Interview.vue") },
	{ path: "/company", name: "company", component: () => import("./pages/Company.vue") },
	{ path: "/data/:area", name: "area", component: () => import("./pages/Area.vue"), props: true },
	{ path: "/:pathMatch(.*)*", redirect: "/" },
]

export default createRouter({
	history: createWebHistory("/embark"),
	routes,
	scrollBehavior: () => ({ top: 0 }),
})
