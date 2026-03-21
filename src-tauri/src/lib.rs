use std::sync::{Arc, Mutex};
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Python FastAPI 사이드카 실행
            let sidecar_command = app
                .shell()
                .sidecar("grimoire-server")
                .expect("failed to create sidecar command");

            let (mut rx, child) = sidecar_command
                .spawn()
                .expect("failed to spawn grimoire-server sidecar");

            let child: Arc<Mutex<Option<CommandChild>>> = Arc::new(Mutex::new(Some(child)));

            // 사이드카 로그 출력
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("[server] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[server] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(status) => {
                            eprintln!("[server] terminated: {:?}", status);
                        }
                        _ => {}
                    }
                }
            });

            // Panel 닫으면 사이드카 종료 + 앱 종료
            let app_handle = app.handle().clone();
            let child_clone = child.clone();
            if let Some(panel) = app.get_webview_window("panel") {
                panel.on_window_event(move |event| {
                    if let tauri::WindowEvent::Destroyed = event {
                        if let Some(c) = child_clone.lock().unwrap().take() {
                            let _ = c.kill();
                        }
                        app_handle.exit(0);
                    }
                });
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
