import { WebviewWindow } from '@tauri-apps/api/webviewWindow';

/**
 * Tauri 윈도우 제어 모듈
 *
 * image-viewer는 동적 생성 전용 (tauri.conf.json에 미등록)
 * 이미지 데이터는 URL 쿼리 파라미터로 전달 → 타이밍/IPC 문제 없음
 */

/**
 * 이미지 뷰어 윈도우 열기
 * @param {Object} imageData - 클릭한 이미지
 * @param {Array} [allImages] - 같은 메시지의 전체 이미지 리스트
 */
export async function openImageViewer(imageData, allImages = null) {
  try {
    const existing = await WebviewWindow.getByLabel('image-viewer');
    if (existing) {
      await existing.close();
      await new Promise(r => setTimeout(r, 150));
    }

    const params = new URLSearchParams();

    if (allImages && allImages.length > 1) {
      // 이미지 리스트 전달 (JSON)
      params.set('images', JSON.stringify(allImages));
      const idx = allImages.findIndex(img => img.url === imageData.url);
      params.set('index', String(Math.max(0, idx)));
    } else {
      // 단일 이미지
      if (imageData.url) params.set('url', imageData.url);
      if (imageData.thumb) params.set('thumb', imageData.thumb);
      if (imageData.title) params.set('title', imageData.title);
      if (imageData.source) params.set('source', imageData.source);
    }

    new WebviewWindow('image-viewer', {
      url: `/image-viewer.html?${params.toString()}`,
      title: imageData.title || 'Grimoire - Image Viewer',
      width: 900,
      height: 720,
      decorations: false,
      transparent: false,
      resizable: true,
      visible: true,
      alwaysOnTop: false,
      minWidth: 600,
      minHeight: 400,
    });
  } catch (err) {
    console.error('[ImageViewer] Failed to open:', err);
  }
}

/**
 * 이미지 뷰어 윈도우 닫기
 */
export async function closeImageViewer() {
  try {
    const viewer = await WebviewWindow.getByLabel('image-viewer');
    if (viewer) await viewer.close();
  } catch (err) {
    console.error('[ImageViewer] Failed to close:', err);
  }
}
