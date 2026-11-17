import axios from "axios";
import { FALLBACK_NEWS_SOURCES, NEWS_API_BASE_URL, NEWS_API_KEY, NEWS_CACHE_TTL } from "../lib/config";
import CacheService, { cacheService } from "./cacheService";
import { parseSimpleRss } from "../utils/news";

export type NewsArticle = {
  title: string; url: string; publishedAt: string | null; retrievedAt: string; source: string;
  description?: string | null; content?: string | null; image?: string | null;
};
export type NewsQuery = {
  q: string;
  page: number;
  pageSize: number;
  language: string;
  sortBy: string;
  from?: string;
  to?: string;
};
type ProviderArticle = Omit<NewsArticle, "source" | "retrievedAt"> & { source: { name?: string }; urlToImage?: string };

async function fetchInshortsArticles(query: string, limit: number, retrievedAt: string): Promise<NewsArticle[]> {
  const articles: NewsArticle[] = [];
  const words = (query.match(/[a-zA-Z0-9]{3,}/g) || []).slice(0, 2);
  const headers = {
    authority: "inshorts.com",
    accept: "*/*",
    "accept-language": "en-GB,en;q=0.5",
    "content-type": "application/json",
    referer: "https://inshorts.com/en/read",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  };

  for (const term of words) {
    try {
      const { data } = await axios.get<any>(
        `https://inshorts.com/api/en/search/trending_topics/${encodeURIComponent(term.toLowerCase())}`,
        {
          headers,
          params: { category: "top_stories", max_limit: String(limit), include_card_data: "true" },
          timeout: 5000,
        }
      );
      const newsList = data?.data?.news_list || [];
      for (const item of newsList) {
        const obj = item?.news_obj;
        if (obj?.title && (obj?.source_url || obj?.shortened_url)) {
          const publishedAt = obj.created_at ? new Date(obj.created_at).toISOString() : null;
          articles.push({
            title: obj.title,
            url: obj.source_url || obj.shortened_url,
            source: obj.source_name || "Inshorts",
            description: obj.content || null,
            content: obj.content || null,
            image: obj.image_url || null,
            publishedAt,
            retrievedAt,
          });
        }
      }
    } catch {}
  }

  // Also query general top_stories for breaking news
  try {
    const { data } = await axios.get<any>(
      `https://inshorts.com/api/en/news?category=top_stories&max_limit=${limit}&include_card_data=true`,
      { headers, timeout: 5000 }
    );
    const newsList = data?.data?.news_list || [];
    for (const item of newsList) {
      const obj = item?.news_obj;
      if (obj?.title && (obj?.source_url || obj?.shortened_url)) {
        const publishedAt = obj.created_at ? new Date(obj.created_at).toISOString() : null;
        articles.push({
          title: obj.title,
          url: obj.source_url || obj.shortened_url,
          source: obj.source_name || "Inshorts",
          description: obj.content || null,
          content: obj.content || null,
          image: obj.image_url || null,
          publishedAt,
          retrievedAt,
        });
      }
    }
  } catch {}

  const seen = new Set<string>();
  const deduped: NewsArticle[] = [];
  for (const a of articles) {
    if (!seen.has(a.url)) {
      seen.add(a.url);
      deduped.push(a);
    }
  }
  return deduped;
}

export async function searchNews(params: NewsQuery) {
  const key = CacheService.generateCacheKey("news_search_v2", params);
  const cached = cacheService.get<{ totalResults: number; articles: NewsArticle[]; provider: string }>(key);
  if (cached) return cached;
  let result;
  const retrievedAt = new Date().toISOString();
  let fallbackReason = "NewsAPI did not return usable results.";
  try {
    if (!NEWS_API_KEY) throw new Error("NewsAPI unavailable");
    const { data } = await axios.get<{ articles: ProviderArticle[]; totalResults: number }>(`${NEWS_API_BASE_URL}/everything`, {
      params: { ...params, from: params.from, to: params.to }, headers: { "X-Api-Key": NEWS_API_KEY }, timeout: 10000,
    });
    if (!data.articles?.length) throw new Error("No articles");
    result = {
      totalResults: data.totalResults,
      provider: "NewsAPI",
      errors: [],
      articles: data.articles.filter(a => a.title && a.url).map(a => ({
        title: a.title, url: a.url, publishedAt: a.publishedAt || null, retrievedAt,
        source: a.source?.name || "NewsAPI",
        description: a.description, content: a.content, image: a.urlToImage,
      })),
    };
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined;
    fallbackReason = status === 429
      ? "NewsAPI rate limited the request; using Google News RSS fallback."
      : status
        ? `NewsAPI returned HTTP ${status}; using Google News RSS fallback.`
        : "NewsAPI was unavailable or returned no usable results; using Google News RSS fallback.";
    const datedQuery = [
      params.q,
      params.from ? `after:${params.from}` : "",
      params.to ? `before:${params.to}` : "",
    ].filter(Boolean).join(" ");
    try {
      const { data } = await axios.get<string>(FALLBACK_NEWS_SOURCES.GOOGLE_NEWS.BASE_URL + "/search", {
        params: { q: datedQuery, hl: params.language }, timeout: 10000,
      });
      const parsed = parseSimpleRss(data, "Google News");
      result = {
        ...parsed,
        provider: "Google News RSS",
        errors: [{ provider: "NewsAPI", message: fallbackReason }],
        articles: parsed.articles
          .slice((params.page - 1) * params.pageSize, params.page * params.pageSize)
          .map((article) => ({ ...article, retrievedAt })) as NewsArticle[],
      };
    } catch {
      // Inshorts API (cyberboysumanjay/Inshorts-News-API) & Bing News scraper fallback
      try {
        const combinedArticles: NewsArticle[] = [];
        const seenUrls = new Set<string>();

        // 1. Fetch Inshorts verified news cards
        try {
          const inshorts = await fetchInshortsArticles(params.q, params.pageSize, retrievedAt);
          for (const item of inshorts) {
            if (!seenUrls.has(item.url)) {
              seenUrls.add(item.url);
              combinedArticles.push(item);
            }
          }
        } catch {}

        // 2. Fetch Bing News cards
        try {
          const { data: bingHtml } = await axios.get<string>("https://www.bing.com/news/search", {
            params: { q: params.q },
            headers: {
              "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
              "Accept-Language": "en-US,en;q=0.9",
            },
            timeout: 10000,
          });
          const cardRegex = /<div[^>]*class="[^"]*news-card[^"]*"[^>]*data-url="([^"]+)"[^>]*data-title="([^"]+)"[^>]*data-author="([^"]+)"/gi;
          let match;
          while ((match = cardRegex.exec(bingHtml)) !== null && combinedArticles.length < params.pageSize) {
            const url = match[1];
            const title = match[2].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
            const author = match[3].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
            if (!seenUrls.has(url)) {
              seenUrls.add(url);
              combinedArticles.push({
                title,
                url,
                source: author || "Bing News",
                publishedAt: null,
                retrievedAt,
              });
            }
          }
        } catch {}

        result = {
          totalResults: combinedArticles.length,
          provider: "Inshorts & Bing News",
          errors: [{ provider: "Google News RSS", message: "Google News RSS unavailable; fell back to Inshorts & Bing News." }],
          articles: combinedArticles.slice(0, params.pageSize),
        };
      } catch {
        result = {
          totalResults: 0,
          provider: "None",
          errors: [{ provider: "NewsAPI", message: fallbackReason }],
          articles: [],
        };
      }
    }
  }
  cacheService.set(key, result, NEWS_CACHE_TTL / 1000);
  return result;
}
