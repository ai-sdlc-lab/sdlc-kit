import "./style.css";
import { statusText } from "./status";

const status = document.querySelector<HTMLElement>("#status")!;

fetch("/api/health")
  .then(async (res) => (status.textContent = statusText(res.ok, res.ok ? await res.json() : null)))
  .catch(() => (status.textContent = statusText(false, null)));
