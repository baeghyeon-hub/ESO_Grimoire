/**
 * Minimal i18n — English + Korean.
 * Usage: import { t } from "../lib/i18n.svelte.js";  t("key")
 */

const strings = {
  // ── General ──
  "language":         { en: "Language",         ko: "언어" },
  "lang_en":          { en: "English",          ko: "English" },
  "lang_ko":          { en: "한국어",            ko: "한국어" },

  // ── Panel Header ──
  "opacity":          { en: "Opacity",          ko: "투명도" },
  "settings":         { en: "Settings",         ko: "설정" },
  "clear":            { en: "Clear",            ko: "초기화" },
  "minimize":         { en: "Minimize",         ko: "최소화" },
  "close":            { en: "Close",            ko: "닫기" },

  // ── Input Bar ──
  "input_placeholder": { en: "Search ESO info (e.g. Medusa set, vDSR)", ko: "ESO 정보 검색 (예: 메두사 세트, vDSR)" },
  "send":             { en: "Send",             ko: "전송" },

  // ── Welcome Screen ──
  "welcome_title":    { en: "Grimoire",         ko: "Grimoire" },
  "welcome_desc":     { en: "Ask me anything about ESO.", ko: "ESO에 대해 무엇이든 물어보세요." },

  // ── Message Bubble ──
  "user_label":       { en: "Vestige",          ko: "Vestige" },
  "bot_label":        { en: "Grimoire",         ko: "Grimoire" },
  "copy":             { en: "Copy",             ko: "복사" },
  "ask_grimoire":     { en: "Ask Grimoire",     ko: "Grimoire에 질문" },
  "uesp_wiki":        { en: "UESP Wiki",        ko: "UESP 위키" },

  // ── Settings Dialog ──
  "settings_title":   { en: "Settings",         ko: "설정" },
  "backend_offline":  { en: "Backend offline — showing defaults", ko: "백엔드 오프라인 — 기본값 표시" },
  "provider":         { en: "Provider",         ko: "프로바이더" },
  "model":            { en: "Model",            ko: "모델" },
  "response_length":  { en: "Response Length",  ko: "응답 길이" },
  "short":            { en: "Short",            ko: "짧게" },
  "standard":         { en: "Standard",         ko: "보통" },
  "detailed":         { en: "Detailed",         ko: "상세" },
  "very_detailed":    { en: "Very Detailed",    ko: "매우 상세" },
  "api_key":          { en: "API Key",          ko: "API 키" },
  "response_length":  { en: "Response Length",  ko: "응답 길이" },
  "cancel":           { en: "Cancel",           ko: "취소" },
  "save":             { en: "Save",             ko: "저장" },
  "ollama_warning":   {
    en: "Local models have limited tool-calling ability, which may result in less accurate answers. Recommended for personal experimentation or fine-tuned models only.",
    ko: "로컬 모델은 도구 호출 능력이 제한적이라 정확한 답변이 나오지 않을 수 있습니다. 개인 실험용 또는 파인튜닝된 모델 사용을 권장합니다."
  },

  // ── DB Missing Dialog ──
  "db_required":      { en: "Database Required", ko: "데이터베이스 필요" },
  "db_desc":          {
    en: "Grimoire needs the ESO database to work. Download grimoire-db.zip from the releases page and extract it into the app's db/ folder.",
    ko: "Grimoire를 사용하려면 ESO 데이터베이스가 필요합니다. 릴리즈 페이지에서 grimoire-db.zip을 다운로드하고 앱의 db/ 폴더에 압축을 풀어주세요."
  },
  "db_step1":         {
    en: "Download grimoire-db.zip from GitHub Releases",
    ko: "GitHub Releases에서 grimoire-db.zip 다운로드"
  },
  "db_step2":         {
    en: "Press Win+R, type %LOCALAPPDATA%\\Grimoire → create a db folder → extract the zip there",
    ko: "Win+R → %LOCALAPPDATA%\\Grimoire 입력 → db 폴더 생성 → zip 압축 해제"
  },
  "db_step3":         {
    en: "Click Re-check below",
    ko: "아래 재확인 버튼 클릭"
  },
  "download_db":      { en: "Download DB",      ko: "DB 다운로드" },
  "recheck":          { en: "Re-check",         ko: "재확인" },
  "checking":         { en: "Checking...",      ko: "확인 중..." },
  "db_not_found":     {
    en: "Database not found. Please extract the DB files and try again.",
    ko: "데이터베이스를 찾을 수 없습니다. DB 파일을 압축 해제한 후 다시 시도해주세요."
  },
  "backend_no_response": { en: "Backend not responding.", ko: "백엔드가 응답하지 않습니다." },

  // ── Image Viewer ──
  "image_viewer":     { en: "Image Viewer",     ko: "이미지 뷰어" },
  "close_esc":        { en: "Close (ESC)",      ko: "닫기 (ESC)" },
  "no_image":         { en: "No image loaded",  ko: "이미지 없음" },
  "prev_image":       { en: "Previous image",   ko: "이전 이미지" },
  "prev":             { en: "← Prev",           ko: "← 이전" },
  "next_image":       { en: "Next image",       ko: "다음 이미지" },
  "next":             { en: "Next →",           ko: "다음 →" },
  "zoom_out":         { en: "Zoom out",         ko: "축소" },
  "zoom_in":          { en: "Zoom in",          ko: "확대" },
  "reset":            { en: "Reset",            ko: "초기화" },
  "reset_zoom":       { en: "Reset zoom",       ko: "줌 초기화" },
  "fit_window":       { en: "Fit to window",    ko: "창에 맞춤" },
  "fit":              { en: "Fit",              ko: "맞춤" },
  "open_uesp":        { en: "Open on UESP Wiki", ko: "UESP 위키에서 열기" },
  "download_original": { en: "Download / Open original", ko: "다운로드 / 원본 열기" },
  "download":         { en: "Download",         ko: "다운로드" },
  "hide_info":        { en: "Hide info",        ko: "정보 숨기기" },
  "show_info":        { en: "Show info",        ko: "정보 보기" },
  "info":             { en: "Info",             ko: "정보" },
  "caption":          { en: "Caption:",         ko: "설명:" },
  "dimensions":       { en: "Dimensions:",      ko: "크기:" },
  "source":           { en: "Source:",          ko: "출처:" },
  "file":             { en: "File:",            ko: "파일:" },
  "url":              { en: "URL:",             ko: "URL:" },
  "external":         { en: "External",         ko: "외부" },

  // ── Bar ──
  "hide_panel":       { en: "Hide panel",       ko: "패널 숨기기" },
  "show_panel":       { en: "Show panel",       ko: "패널 보기" },
  "mini_bar":         { en: "Mini bar",         ko: "미니 바" },
  "exit":             { en: "Exit",             ko: "종료" },

  // ── Errors ──
  "error_prefix":     { en: "Error:",           ko: "오류:" },
};

let _lang = "en";

// Load language from localStorage immediately (before first render)
try {
  const stored = localStorage.getItem("grimoire_lang");
  if (stored === "ko" || stored === "en") _lang = stored;
} catch {}

/** Set current language and persist to localStorage */
export function setLang(lang) {
  _lang = (lang === "ko") ? "ko" : "en";
  try { localStorage.setItem("grimoire_lang", _lang); } catch {}
}

/** Get current language */
export function getLang() {
  return _lang;
}

/** Translate key */
export function t(key) {
  const entry = strings[key];
  if (!entry) return key;
  return entry[_lang] || entry.en || key;
}
