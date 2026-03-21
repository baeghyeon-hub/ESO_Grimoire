/**
 * localStorage 래퍼 — 세션 지속성.
 */
const PREFIX = "grimoire_";

export function load(key, fallback = null) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function save(key, value) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // storage full — 무시
  }
}

export function remove(key) {
  localStorage.removeItem(PREFIX + key);
}
