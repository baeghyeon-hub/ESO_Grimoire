import { writable, get } from 'svelte/store';

/**
 * 이미지 뷰어 전용 상태 관리
 * - 현재 표시 이미지
 * - 이미지 히스토리 (이전/다음)
 * - UI 상태 (zoom, 로딩)
 */

// ──── 현재 표시 중인 이미지 ────
export const currentImage = writable({
  url: '',
  thumb: '',
  title: '',
  width: 0,
  height: 0,
  source: ''
});

// ──── 이미지 히스토리 (이전/다음 네비게이션) ────
export const imageHistory = writable([]);
export const historyIndex = writable(-1);

// ──── UI 상태 ────
export const zoomLevel = writable(1);
export const isLoading = writable(false);
export const error = writable(null);

// ──── 도우미 함수 ────

function normalize(imageData) {
  return {
    url: imageData.url || '',
    thumb: imageData.thumb || imageData.url || '',
    title: imageData.title || '',
    width: imageData.width || 0,
    height: imageData.height || 0,
    source: imageData.source || 'external'
  };
}

/**
 * 이미지 설정 + 히스토리 추가
 */
export function setImage(imageData) {
  const img = normalize(imageData);
  currentImage.set(img);
  addToHistory(img);
  resetZoom();
  error.set(null);
}

/**
 * 이미지 리스트로 히스토리 초기화 + 특정 인덱스의 이미지 표시
 */
export function setImageList(images, startIndex = 0) {
  const normalized = images.map(normalize);
  imageHistory.set(normalized);
  const idx = Math.max(0, Math.min(startIndex, normalized.length - 1));
  historyIndex.set(idx);
  currentImage.set(normalized[idx]);
  resetZoom();
  error.set(null);
}

/**
 * 히스토리에 이미지 추가
 */
function addToHistory(imageData) {
  const history = get(imageHistory);

  // 중복 제거 (마지막과 같은 URL이면 추가 안 함)
  if (history.length > 0 && history[history.length - 1].url === imageData.url) {
    historyIndex.set(history.length - 1);
    return;
  }

  // 최대 20개까지만 보관
  const updated = [...history.slice(Math.max(0, history.length - 19)), imageData];
  imageHistory.set(updated);
  historyIndex.set(updated.length - 1);
}

export function previousImage() {
  const idx = get(historyIndex);
  if (idx <= 0) return;

  const history = get(imageHistory);
  const prev = history[idx - 1];
  currentImage.set(prev);
  historyIndex.set(idx - 1);
  resetZoom();
}

export function nextImage() {
  const idx = get(historyIndex);
  const history = get(imageHistory);
  if (idx >= history.length - 1) return;

  const next = history[idx + 1];
  currentImage.set(next);
  historyIndex.set(idx + 1);
  resetZoom();
}

export function zoomIn() {
  zoomLevel.update(z => Math.min(z * 1.2, 5));
}

export function zoomOut() {
  zoomLevel.update(z => Math.max(z / 1.2, 0.1));
}

export function resetZoom() {
  zoomLevel.set(1);
}

export function fitToWindow(containerW, containerH) {
  const img = get(currentImage);
  if (img.width && img.height) {
    const scale = Math.min(containerW / img.width, containerH / img.height, 1);
    zoomLevel.set(scale);
  }
}

export function reset() {
  currentImage.set({ url: '', thumb: '', title: '', width: 0, height: 0, source: '' });
  imageHistory.set([]);
  historyIndex.set(-1);
  zoomLevel.set(1);
  error.set(null);
  isLoading.set(false);
}
