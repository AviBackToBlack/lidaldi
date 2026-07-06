import { mount } from "svelte";
import "./tokens.css";
import "./app.css";
import App from "./App.svelte";
import { registerServiceWorker } from "./lib/push";

if (import.meta.env.PROD) {
  void registerServiceWorker();
}

const app = mount(App, {
  target: document.getElementById("app")!,
});

export default app;
