/**
 * Tauri Events 기반 윈도우 간 통신.
 * BroadcastChannel은 별도 WebView2 간에 작동하지 않으므로
 * Tauri의 emit/listen API를 사용합니다.
 *
 * 메시지 타입:
 *   TOGGLE_PANEL  — bar→panel: 패널 표시/숨김 토글
 *   PANEL_VISIBLE — panel→bar: 패널 표시 상태 알림 { visible: boolean }
 *   SEND_CHAT     — bar→panel: 채팅 전송 { message: string }
 */
import { emit, listen as tauriListen } from "@tauri-apps/api/event";

const EVENT_NAME = "grimoire_ipc";

export function send(type, data = {}) {
  emit(EVENT_NAME, { type, ...data });
}

export function listen(handler) {
  tauriListen(EVENT_NAME, (event) => handler(event.payload));
}
