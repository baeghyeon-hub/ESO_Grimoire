export default {
  async fetch(request) {
    const url = new URL(request.url);
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders,
      });
    }
    try {
      const action = (url.searchParams.get("action") || "search").toLowerCase();
      const rawQuery =
        url.searchParams.get("q") ||
        url.searchParams.get("srsearch") ||
        url.searchParams.get("title") ||
        "";
      const query = rawQuery.trim();
      if (!query && action !== "health") {
        return jsonResponse(
          { ok: false, error: "No query provided" },
          400,
          corsHeaders
        );
      }
      if (action === "health") {
        return jsonResponse(
          { ok: true, service: "ESO UESP Worker", version: "3.1.0" },
          200,
          corsHeaders
        );
      }
      if (action === "search") {
        return await handleSearch(url, query, corsHeaders);
      }
      if (action === "resolve") {
        return await handleResolve(url, query, corsHeaders);
      }
      if (action === "page") {
        return await handlePage(query, corsHeaders);
      }
      if (action === "full") {
        return await handleFull(query, corsHeaders);
      }
      if (action === "sections") {
        return await handleSections(query, corsHeaders);
      }
      if (action === "section") {
        return await handleSection(url, query, corsHeaders);
      }
      return jsonResponse(
        { ok: false, error: `Unsupported action: ${action}` },
        400,
        corsHeaders
      );
    } catch (error) {
      return jsonResponse(
        {
          ok: false,
          error: "Internal worker error",
          message: error instanceof Error ? error.message : String(error),
        },
        500,
        corsHeaders
      );
    }
  },
};

// ── Cache TTL 설정 (초 단위) ─────────────────────────────
const TTL = {
  STATIC: 86400,    // 24h — 세트 정보, NPC, 스킬, 위키 페이지 등
  SEARCH: 1800,     // 30m — 검색 결과
  RESOLVE: 3600,    // 1h  — resolve (검색 + 페이지)
};

// ── 캐싱 fetch ───────────────────────────────────────────
async function fetchWithCache(apiUrl, ttl = TTL.STATIC) {
  const cache = caches.default;
  const cacheKey = new Request(apiUrl.toString(), { method: "GET" });

  // 캐시 히트
  const cached = await cache.match(cacheKey);
  if (cached) {
    return await cached.json();
  }

  // 캐시 미스 → UESP 호출
  const response = await fetch(apiUrl.toString(), {
    headers: {
      "User-Agent": "Grimoire/3.1 (Cloudflare Worker; cached)",
      Accept: "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(
      `UESP API request failed: ${response.status} ${response.statusText}`
    );
  }
  const data = await response.json();

  // 캐시 저장 (clone 불필요 — 새 Response 생성)
  const toCache = new Response(JSON.stringify(data), {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": `public, max-age=${ttl}`,
    },
  });
  // put은 fire-and-forget — await 해도 무방
  await cache.put(cacheKey, toCache);

  return data;
}

// ── 핸들러 ───────────────────────────────────────────────
async function handleSearch(url, query, corsHeaders) {
  const limit = clampInt(url.searchParams.get("limit"), 1, 10, 8);
  const mode = (url.searchParams.get("mode") || "smart").toLowerCase();
  const type = (url.searchParams.get("type") || "").toLowerCase();

  const apiUrl = new URL("https://en.uesp.net/w/api.php");
  applyCommonParams(apiUrl);
  apiUrl.searchParams.set("action", "query");
  apiUrl.searchParams.set("list", "search");
  apiUrl.searchParams.set("srnamespace", "144");
  apiUrl.searchParams.set("srlimit", String(limit));
  apiUrl.searchParams.set(
    "srprop",
    "snippet|titlesnippet|size|wordcount|timestamp"
  );
  apiUrl.searchParams.set("srinfo", "suggestion");
  apiUrl.searchParams.set("srwhat", "text");
  apiUrl.searchParams.set("srsearch", buildSearchQuery(query, mode, type));

  const data = await fetchWithCache(apiUrl, TTL.SEARCH);
  const results = (data?.query?.search || []).map((item) => ({
    title: item.title,
    pageid: item.pageid,
    snippet: stripHtml(item.snippet || ""),
    titlesnippet: stripHtml(item.titlesnippet || ""),
    timestamp: item.timestamp,
    wordcount: item.wordcount,
    size: item.size,
  }));

  return jsonResponse(
    {
      ok: true,
      action: "search",
      query,
      mode,
      type: type || null,
      count: results.length,
      results,
      suggestion: data?.query?.searchinfo?.suggestion || null,
    },
    200,
    corsHeaders
  );
}

async function handleResolve(url, query, corsHeaders) {
  const type = (url.searchParams.get("type") || "").toLowerCase();

  const searchApiUrl = new URL("https://en.uesp.net/w/api.php");
  applyCommonParams(searchApiUrl);
  searchApiUrl.searchParams.set("action", "query");
  searchApiUrl.searchParams.set("list", "search");
  searchApiUrl.searchParams.set("srnamespace", "144");
  searchApiUrl.searchParams.set("srlimit", "5");
  searchApiUrl.searchParams.set(
    "srprop",
    "snippet|titlesnippet|size|wordcount|timestamp"
  );
  searchApiUrl.searchParams.set("srinfo", "suggestion");
  searchApiUrl.searchParams.set("srwhat", "text");
  searchApiUrl.searchParams.set(
    "srsearch",
    buildSearchQuery(query, "smart", type)
  );

  const searchData = await fetchWithCache(searchApiUrl, TTL.RESOLVE);
  const searchResults = searchData?.query?.search || [];
  const best = chooseBestMatch(query, searchResults);

  if (!best?.title) {
    return jsonResponse(
      {
        ok: true,
        action: "resolve",
        query,
        type: type || null,
        found: false,
        message: "No matching ESO page found.",
      },
      200,
      corsHeaders
    );
  }

  const pageData = await fetchWithCache(
    buildExtractUrl(best.title, true),
    TTL.STATIC
  );

  return jsonResponse(
    {
      ok: true,
      action: "resolve",
      query,
      type: type || null,
      found: true,
      resolvedTitle: best.title,
      searchHit: {
        title: best.title,
        pageid: best.pageid,
        snippet: stripHtml(best.snippet || ""),
        titlesnippet: stripHtml(best.titlesnippet || ""),
        timestamp: best.timestamp,
        wordcount: best.wordcount,
        size: best.size,
      },
      page: pageData,
    },
    200,
    corsHeaders
  );
}

async function handlePage(query, corsHeaders) {
  const title = normalizeEsoTitle(query);
  const data = await fetchWithCache(buildExtractUrl(title, true), TTL.STATIC);
  return jsonResponse(
    { ok: true, action: "page", title, page: simplifyPages(data) },
    200,
    corsHeaders
  );
}

async function handleFull(query, corsHeaders) {
  const title = normalizeEsoTitle(query);
  const data = await fetchWithCache(buildExtractUrl(title, false), TTL.STATIC);
  return jsonResponse(
    { ok: true, action: "full", title, page: simplifyPages(data) },
    200,
    corsHeaders
  );
}

async function handleSections(query, corsHeaders) {
  const title = normalizeEsoTitle(query);
  const apiUrl = new URL("https://en.uesp.net/w/api.php");
  applyCommonParams(apiUrl);
  apiUrl.searchParams.set("action", "parse");
  apiUrl.searchParams.set("page", title);
  apiUrl.searchParams.set("prop", "sections");

  const data = await fetchWithCache(apiUrl, TTL.STATIC);
  return jsonResponse(
    {
      ok: true,
      action: "sections",
      title,
      sections: data?.parse?.sections || [],
    },
    200,
    corsHeaders
  );
}

async function handleSection(url, query, corsHeaders) {
  const title = normalizeEsoTitle(query);
  const section = String(url.searchParams.get("section") || "0");

  const apiUrl = new URL("https://en.uesp.net/w/api.php");
  applyCommonParams(apiUrl);
  apiUrl.searchParams.set("action", "parse");
  apiUrl.searchParams.set("page", title);
  apiUrl.searchParams.set("prop", "wikitext");
  apiUrl.searchParams.set("section", section);

  const data = await fetchWithCache(apiUrl, TTL.STATIC);
  return jsonResponse(
    {
      ok: true,
      action: "section",
      title,
      section,
      wikitext: data?.parse?.wikitext || "",
    },
    200,
    corsHeaders
  );
}

// ── 헬퍼 ─────────────────────────────────────────────────
function buildExtractUrl(title, introOnly) {
  const apiUrl = new URL("https://en.uesp.net/w/api.php");
  applyCommonParams(apiUrl);
  apiUrl.searchParams.set("action", "query");
  apiUrl.searchParams.set("prop", "extracts|info");
  apiUrl.searchParams.set("explaintext", "1");
  apiUrl.searchParams.set("inprop", "url");
  apiUrl.searchParams.set("titles", title);
  if (introOnly) {
    apiUrl.searchParams.set("exintro", "1");
  }
  return apiUrl;
}

function applyCommonParams(apiUrl) {
  apiUrl.searchParams.set("format", "json");
  apiUrl.searchParams.set("formatversion", "2");
  apiUrl.searchParams.set("redirects", "1");
}

function jsonResponse(data, status = 200, corsHeaders = {}) {
  // 액션별 클라이언트 캐시 TTL
  const action = data?.action || "";
  let clientTtl = 0;
  if (action === "page" || action === "full" || action === "sections" || action === "section") {
    clientTtl = 3600;  // 1h 클라이언트 캐시
  } else if (action === "search") {
    clientTtl = 300;   // 5m
  } else if (action === "resolve") {
    clientTtl = 600;   // 10m
  }

  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": clientTtl > 0
        ? `public, max-age=${clientTtl}`
        : "no-store",
    },
  });
}

function clampInt(value, min, max, fallback) {
  const parsed = Number.parseInt(value ?? "", 10);
  if (Number.isNaN(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function normalizeEsoTitle(query) {
  const trimmed = String(query || "").trim();
  if (!trimmed) return trimmed;
  if (/^Online:/i.test(trimmed)) return trimmed;
  return `Online:${trimmed}`;
}

function buildSearchQuery(query, mode = "smart", type = "") {
  const q = String(query || "").trim();
  const lower = q.toLowerCase();

  if (mode === "exact") {
    return `"${q}"`;
  }

  if (type === "quest") return `${q} quest`;
  if (type === "set") return `${q} set`;
  if (type === "skill") return `${q} skill`;
  if (type === "npc") return `${q} npc`;
  if (type === "location") return `${q} location`;
  if (type === "dungeon") return `${q} dungeon`;
  if (type === "trial") return `${q} trial`;

  if (
    lower.includes("how to start") ||
    lower.includes("start quest") ||
    lower.includes("quest")
  ) {
    return `${q} quest`;
  }
  if (
    lower.includes("set") ||
    lower.includes("gear") ||
    lower.includes("5 piece") ||
    lower.includes("five piece")
  ) {
    return `${q} set`;
  }
  if (
    lower.includes("skill") ||
    lower.includes("passive") ||
    lower.includes("ultimate")
  ) {
    return `${q} skill`;
  }
  if (
    lower.includes("dungeon") ||
    lower.includes("boss") ||
    lower.includes("mechanic")
  ) {
    return `${q} dungeon`;
  }

  return q;
}

function chooseBestMatch(query, results) {
  if (!Array.isArray(results) || results.length === 0) return null;
  const normalizedQuery = normalizeString(query);
  const scored = results.map((item) => {
    const title = item.title || "";
    const normalizedTitle = normalizeString(title.replace(/^online:/i, ""));
    let score = 0;
    if (normalizedTitle === normalizedQuery) score += 100;
    if (title.toLowerCase() === `online:${query}`.toLowerCase()) score += 80;
    if (normalizedTitle.includes(normalizedQuery)) score += 40;
    if (normalizedQuery.includes(normalizedTitle)) score += 20;
    if (/^Online:/i.test(title)) score += 10;
    return { item, score };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored[0].item;
}

function normalizeString(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/^online:/, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function stripHtml(text) {
  return String(text || "")
    .replace(/<[^>]+>/g, "")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function simplifyPages(data) {
  const pages = data?.query?.pages || [];
  return pages.map((page) => ({
    pageid: page.pageid,
    title: page.title,
    extract: page.extract || "",
    fullurl: page.fullurl || null,
    canonicalurl: page.canonicalurl || null,
    touched: page.touched || null,
    length: page.length || null,
  }));
}
