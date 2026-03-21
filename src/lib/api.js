/**
 * FastAPI backend communication wrapper.
 */
const BASE = "http://127.0.0.1:8111";

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function health() {
  return request("GET", "/health");
}

export async function getConfig() {
  return request("GET", "/config");
}

export async function putConfig(data) {
  return request("PUT", "/config", data);
}

export async function getProviders() {
  return request("GET", "/providers");
}


export async function sendChat(message) {
  return request("POST", "/chat", { message });
}

export async function clearHistory() {
  return request("DELETE", "/history");
}

export async function getDbStatus() {
  return request("GET", "/db-status");
}
