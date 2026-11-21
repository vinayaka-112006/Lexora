const TAVILY_SEARCH_URL = "https://api.tavily.com/search";
const MAX_RESULTS = 6;

function searchMode(query) {
  return /\b(news|latest|recent|announcement|announcements|policy|policies|regulation|regulatory|developments?|today|this week|this month)\b/i.test(
    query,
  )
    ? "news"
    : "general";
}

function sourceDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./i, "");
  } catch {
    return "";
  }
}

function normalizeResult(item) {
  if (!item || typeof item !== "object") return null;
  let url;
  try {
    url = new URL(item.url);
    if (!["http:", "https:"].includes(url.protocol)) return null;
  } catch {
    return null;
  }
  const title =
    typeof item.title === "string" ? item.title.trim().slice(0, 300) : "";
  const description =
    typeof item.content === "string" ? item.content.trim().slice(0, 1200) : "";
  if (!title && !description) return null;
  const publishedDate =
    typeof item.published_date === "string" && item.published_date.trim()
      ? item.published_date.trim()
      : null;
  return {
    title: title || sourceDomain(url.href),
    description,
    url: url.href,
    source: sourceDomain(url.href),
    publishedDate,
  };
}

async function searchTavily(
  query,
  {
    fetchImpl = global.fetch,
    apiKey = process.env.TAVILY_API_KEY,
    timeoutMs = 20000,
  } = {},
) {
  if (!apiKey || !apiKey.trim()) {
    const error = new Error("Tavily is not configured");
    error.code = "TAVILY_NOT_CONFIGURED";
    throw error;
  }
  const mode = searchMode(query);
  const response = await fetchImpl(TAVILY_SEARCH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      api_key: apiKey,
      query,
      topic: mode === "news" ? "news" : "general",
      search_depth: "basic",
      max_results: MAX_RESULTS,
      include_answer: "basic",
    }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    const error = new Error("Tavily search failed");
    error.code = "TAVILY_UPSTREAM_ERROR";
    throw error;
  }
  const payload = await response.json();
  const seen = new Set();
  const results = (Array.isArray(payload.results) ? payload.results : [])
    .map(normalizeResult)
    .filter((item) => {
      if (!item || seen.has(item.url)) return false;
      seen.add(item.url);
      return true;
    })
    .slice(0, MAX_RESULTS);
  return {
    mode,
    answer:
      typeof payload.answer === "string"
        ? payload.answer.trim().slice(0, 4000)
        : "",
    results,
  };
}

module.exports = { searchTavily, searchMode, normalizeResult, MAX_RESULTS };

// Suppose the user enters:
// Latest Ayurveda patent regulations in India

// 1. news.js receives the query

//    Validates authentication and the input.
// 2. searchTavily() is called

//    Receives the cleaned query.
// 3. searchMode()

//    Detects Latest and selects news.
// 4. Tavily API request

//    Sends the API key, query, news topic and search configuration.
// 5. Tavily returns results

//    The response is parsed into a JavaScript object.
// 6. Normalization and filtering

//    Invalid URLs and duplicate results are removed. Results are limited to six.
// 7. Final response

//    mode, answer and results are returned to React.

// 9. Important design observation
// There is one limitation worth understanding in this implementation.

// The searchMode() function uses keyword matching.

// For example:
// - "Latest Ayurveda news" → news.
// - "What are the latest patent developments?" → news.
// - "Tell me about Ayurveda regulations" → news, because it contains regulations? Actually, the regex contains regulation as a word-boundary match, so regulations does not match that exact alternative.
// That last example is important: regex-based classification has limitations. A user can ask for recent information without using one of the recognized keywords.

// Also, the service does not independently verify whether a returned article is legally authoritative or whether its publication date is accurate. It normalizes the search results; it does not perform legal validation.

// What we have covered in the Express backend
// Area	Files studied
// Server setup	server.js
// Database connection	config/db.js
// Authentication	middleware/auth.js, utils/auth.js, routes/auth.js
// Legal query proxy	routes/query.js
// Chat history	routes/chats.js, models/ChatLog.js
// News search	routes/news.js, services/tavilyService.js
// User schema	models/User.js
