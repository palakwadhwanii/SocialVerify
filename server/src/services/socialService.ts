import {
  REDDIT_CLIENT_ID,
  REDDIT_CLIENT_SECRET,
  REDDIT_USER_AGENT,
  MASTODON_INSTANCES,
  MASTODON_ACCESS_TOKEN,
  MASTODON_REQUEST_TIMEOUT,
} from "../lib/config";

export const SOCIAL_PLATFORMS = ["reddit", "mastodon", "bluesky"] as const;
export type SocialPlatform = typeof SOCIAL_PLATFORMS[number];

export type SocialPost = {
  id: string;
  platform: SocialPlatform;
  topic: string;
  author: string | null;
  title: string | null;
  content: string | null;
  url: string;
  externalUrl: string | null;
  community: string | null;
  instanceDomain?: string;
  publishedAt: string | null;
  retrievedAt: string;
  engagement: {
    score?: number;
    comments?: number;
    likes?: number;
    reposts?: number;
  };
  relationshipToClaim?: string;
  sourceQualityRationale?: string;
};

type RedditToken = { value: string; expiresAt: number };
let redditToken: RedditToken | undefined;

function isValidInstanceHost(host: string): boolean {
  const clean = host.trim().toLowerCase();
  if (!clean) return false;
  // Disallow direct IP addresses
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(clean) || clean.includes(":")) return false;
  // Disallow localhost and internal domains
  if (clean === "localhost" || clean.endsWith(".local") || clean.endsWith(".internal")) return false;
  // Disallow non-DNS names
  if (!/^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$/.test(clean)) return false;
  // Check approved allowlist
  return MASTODON_INSTANCES.includes(clean);
}

async function getJson<T>(url: string, init?: RequestInit, timeoutMs: number = 10_000): Promise<T> {
  const response = await fetch(url, { ...init, signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

async function getRedditToken(): Promise<string> {
  if (redditToken && redditToken.expiresAt > Date.now()) return redditToken.value;
  if (!REDDIT_CLIENT_ID || !REDDIT_CLIENT_SECRET) {
    throw new Error("Reddit credentials are not configured");
  }

  const credentials = Buffer.from(`${REDDIT_CLIENT_ID}:${REDDIT_CLIENT_SECRET}`).toString("base64");
  const data = await getJson<{ access_token?: string; expires_in?: number }>(
    "https://www.reddit.com/api/v1/access_token",
    {
      method: "POST",
      headers: {
        Authorization: `Basic ${credentials}`,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": REDDIT_USER_AGENT,
      },
      body: "grant_type=client_credentials",
    },
  );
  if (!data.access_token) throw new Error("Reddit did not return an access token");

  redditToken = {
    value: data.access_token,
    expiresAt: Date.now() + Math.max((data.expires_in || 3600) - 60, 60) * 1000,
  };
  return redditToken.value;
}

export async function fetchReddit(topic: string, limit: number): Promise<SocialPost[]> {
  const token = await getRedditToken();
  const params = new URLSearchParams({ q: topic, sort: "new", limit: String(limit), raw_json: "1" });
  const data = await getJson<any>(`https://oauth.reddit.com/search?${params}`, {
    headers: { Authorization: `Bearer ${token}`, "User-Agent": REDDIT_USER_AGENT },
  });

  const retrievedAt = new Date().toISOString();
  return (data.data?.children || []).map(({ data: post }: any) => ({
    id: post.name || `t3_${post.id}`,
    platform: "reddit",
    topic,
    author: post.author ? `u/${post.author}` : null,
    title: post.title || null,
    content: post.selftext || null,
    url: `https://www.reddit.com${post.permalink}`,
    externalUrl: post.url_overridden_by_dest || null,
    community: post.subreddit_name_prefixed || null,
    publishedAt: Number.isFinite(post.created_utc)
      ? new Date(post.created_utc * 1000).toISOString()
      : null,
    retrievedAt,
    engagement: { score: post.score || 0, comments: post.num_comments || 0 },
  }));
}

export async function fetchMastodon(topic: string, limit: number): Promise<SocialPost[]> {
  const instances = MASTODON_INSTANCES.filter(isValidInstanceHost);
  if (instances.length === 0) {
    throw new Error("No valid Mastodon instances configured in MASTODON_INSTANCES");
  }

  const postsPerInstance = Math.max(1, Math.ceil(limit / instances.length));
  const results = await Promise.allSettled(
    instances.map((instance) => searchInstance(instance, topic, postsPerInstance))
  );

  const allPosts: SocialPost[] = [];
  let atLeastOneSuccess = false;

  for (const res of results) {
    if (res.status === "fulfilled") {
      allPosts.push(...res.value);
      atLeastOneSuccess = true;
    }
  }

  if (!atLeastOneSuccess && results.length > 0) {
    const firstErr = (results[0] as PromiseRejectedResult).reason;
    throw new Error(`Mastodon instances unavailable: ${firstErr?.message || String(firstErr)}`);
  }

  // Deduplicate by URL
  const seen = new Set<string>();
  const deduped: SocialPost[] = [];
  for (const post of allPosts) {
    if (!seen.has(post.url)) {
      seen.add(post.url);
      deduped.push(post);
    }
  }

  return deduped.slice(0, limit);
}

type BlueskyPost = {
  uri?: string;
  record?: { text?: string; createdAt?: string };
  indexedAt?: string;
  author?: { handle?: string };
  replyCount?: number;
  repostCount?: number;
  likeCount?: number;
};

export async function fetchBluesky(topic: string, limit: number): Promise<SocialPost[]> {
  const params = new URLSearchParams({ q: topic, limit: String(limit), sort: "latest" });
  const headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    Accept: "application/json",
  };

  let data: { posts?: BlueskyPost[] } = { posts: [] };
  try {
    data = await getJson<{ posts?: BlueskyPost[] }>(
      `https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?${params}`,
      { headers },
    );
  } catch {
    try {
      data = await getJson<{ posts?: BlueskyPost[] }>(
        `https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?${params}`,
        { headers },
      );
    } catch {
      data = { posts: [] };
    }
  }

  const retrievedAt = new Date().toISOString();

  return (data.posts || [])
    .filter((post) => post.uri)
    .map((post) => {
      const handle = post.author?.handle || null;
      const uriParts = post.uri!.split("/");
      const postId = uriParts.at(-1);
      const actor = handle || uriParts[2];
      return {
        id: post.uri!,
        platform: "bluesky" as const,
        topic,
        author: handle ? `@${handle}` : null,
        title: null,
        content: post.record?.text || null,
        url: actor && postId
          ? `https://bsky.app/profile/${encodeURIComponent(actor)}/post/${encodeURIComponent(postId)}`
          : "https://bsky.app",
        externalUrl: null,
        community: "Bluesky",
        publishedAt: post.record?.createdAt || null,
        retrievedAt,
        engagement: {
          comments: post.replyCount ?? 0,
          likes: post.likeCount ?? 0,
          reposts: post.repostCount ?? 0,
        },
      };
    });
}

async function searchInstance(instance: string, topic: string, limit: number): Promise<SocialPost[]> {
  const headers: Record<string, string> = {
    "User-Agent": "SocialVerify/1.0 (+https://socialverify.ai; multi-agent evidence engine)",
    Accept: "application/json",
  };
  if (MASTODON_ACCESS_TOKEN) {
    headers["Authorization"] = `Bearer ${MASTODON_ACCESS_TOKEN}`;
  }

  // 1. Try official /api/v2/search?type=statuses
  try {
    const searchParams = new URLSearchParams({
      q: topic,
      type: "statuses",
      limit: String(limit),
    });
    if (MASTODON_ACCESS_TOKEN) {
      searchParams.set("resolve", "true");
    }

    const data = await getJson<any>(
      `https://${instance}/api/v2/search?${searchParams}`,
      { headers },
      MASTODON_REQUEST_TIMEOUT
    );

    const statuses = data.statuses || [];
    if (statuses.length > 0) {
      return statuses.map((s: any) => mapMastodonStatus(s, instance, topic));
    }
  } catch (err: any) {
    // If rate limited or restricted, we will attempt fallback below
  }

  // 2. Fallback to hashtag search & timeline if full-text returns 0 or requires auth
  try {
    const tagParams = new URLSearchParams({ q: topic, type: "hashtags", limit: "3" });
    const tagData = await getJson<any>(
      `https://${instance}/api/v2/search?${tagParams}`,
      { headers },
      MASTODON_REQUEST_TIMEOUT
    );

    const stopWords = new Set([
      "about", "after", "against", "along", "among", "been", "before", "being", "between",
      "could", "does", "during", "from", "have", "into", "more", "most", "over", "same", "some",
      "than", "that", "their", "there", "these", "they", "this", "those", "through", "under", "very",
      "were", "what", "when", "where", "which", "while", "with", "would", "your", "has", "had", "did",
      "find", "check", "tell", "give", "show", "please", "official", "officially", "statement", "statements",
      "filing", "filings", "date", "dates", "the", "and", "for", "with", "news", "latest", "update", "updates",
      "today", "report", "reports", "reported", "reporting", "say", "says", "said", "saying", "can",
      "will", "just", "also", "out", "now", "get", "who", "whom", "its", "it", "are", "was", "how", "why",
      "announce", "announces", "announced", "announcing", "announcement", "announcements", "unveil",
      "unveils", "unveiled", "unveiling", "launch", "launches", "launched", "launching", "break",
      "breaking", "confirm", "confirms", "confirmed", "confirming", "claim", "claims", "claimed",
      "claiming", "rumour", "rumours", "rumor", "rumors", "source", "sources", "recent", "recently",
      "an", "or", "in", "on", "at", "to", "of", "by", "as", "is", "if", "no", "so", "up", "do",
      "my", "we", "he", "me", "us", "be", "all",
    ]);

    const words = (topic.match(/[a-zA-Z0-9]{2,}/g) || []).filter(
      (w) => !stopWords.has(w.toLowerCase())
    );
    const compoundTags: string[] = [];
    const [w0, w1, w2] = words;
    if (words.length >= 2 && w0 && w1) {
      compoundTags.push((w0 + w1).toLowerCase());
      if (words.length >= 3 && w2) {
        compoundTags.push((w1 + w2).toLowerCase());
      }
      if (w1.toLowerCase().endsWith("s") && w1.length > 3) {
        compoundTags.push(w0.toLowerCase() + w1.slice(0, -1).toLowerCase());
      }
    }
    const apiTags = (tagData.hashtags || []).map((t: any) => t.name).filter(Boolean);
    const tags = Array.from(
      new Set([w0, ...compoundTags, ...words.slice(1), ...apiTags].filter((t): t is string => Boolean(t)))
    ).slice(0, 5);

    if (!tags.length) return [];

    const timelineStatuses = (
      await Promise.all(
        tags.map((tag: string) =>
          getJson<any[]>(
            `https://${instance}/api/v1/timelines/tag/${encodeURIComponent(tag)}?limit=${limit * 2}`,
            { headers },
            MASTODON_REQUEST_TIMEOUT
          ).catch(() => [])
        )
      )
    ).flat();

    const uniqueMap = new Map<string, any>();
    for (const item of timelineStatuses) {
      const post = item.reblog || item;
      if (post && post.id && !uniqueMap.has(post.id)) {
        uniqueMap.set(post.id, item);
      }
    }

    const stems = words.map((w) =>
      w.length > 4 && w.endsWith("es") ? w.slice(0, -2) : w.length > 3 && w.endsWith("s") ? w.slice(0, -1) : w
    ).map((w) => w.toLowerCase());
    const uniqueStems = Array.from(new Set(stems));

    const filteredStatuses = Array.from(uniqueMap.values()).filter((item) => {
      const post = item.reblog || item;
      const text = (
        (post?.content || "") + " " +
        (post?.spoiler_text || "") + " " +
        (post?.card?.title || "") + " " +
        (post?.card?.description || "")
      ).toLowerCase();
      const postWords = new Set(text.match(/[a-zA-Z0-9]{2,}/g) || []);
      const postStems = new Set(
        Array.from(postWords).map((w) =>
          w.length > 4 && w.endsWith("es") ? w.slice(0, -2) : w.length > 3 && w.endsWith("s") ? w.slice(0, -1) : w
        )
      );
      if (!uniqueStems.length) return true;
      const s0 = uniqueStems[0];
      if (uniqueStems.length === 1 && s0) {
        return postStems.has(s0) || postWords.has(s0) || text.includes(s0);
      }
      if (uniqueStems.length >= 2) {
        const compound1 = uniqueStems.slice(0, 2).join("");
        if (postWords.has(compound1) || text.includes(compound1)) return true;
        if (uniqueStems.length >= 3) {
          const compound2 = uniqueStems.slice(1, 3).join("");
          if (postWords.has(compound2) || text.includes(compound2)) return true;
        }
        const matches = uniqueStems.filter((s) => postStems.has(s) || postWords.has(s) || text.includes(s));
        const required = Math.max(1, Math.min(2, Math.ceil(uniqueStems.length * 0.4)));
        return matches.length >= required;
      }
      return true;
    });

    return filteredStatuses
      .slice(0, limit)
      .map((s) => mapMastodonStatus(s, instance, topic));
  } catch {
    return [];
  }
}

function mapMastodonStatus(raw: any, instance: string, topic: string): SocialPost {
  const post = raw.reblog || raw;
  const account = post.account || {};
  const username = account.username || "anonymous";
  const acct = account.acct || username;
  const authorHandle = acct.includes("@") ? `@${acct}` : `@${acct}@${instance}`;
  const statusUrl = post.url || post.uri || `https://${instance}/@${username}/${post.id}`;

  return {
    id: String(post.id),
    platform: "mastodon",
    topic,
    author: authorHandle,
    title: post.spoiler_text || null,
    content: stripHtml(post.content || "") || null,
    url: statusUrl,
    externalUrl: post.card?.url || null,
    community: instance,
    instanceDomain: instance,
    publishedAt: post.created_at || null,
    retrievedAt: new Date().toISOString(),
    engagement: {
      comments: post.replies_count || 0,
      likes: post.favourites_count || 0,
      reposts: post.reblogs_count || 0,
    },
    relationshipToClaim: "unassessed",
    sourceQualityRationale: `Public federated post retrieved from Mastodon instance '${instance}'. Visibility reflects instance federation and public indexing.`,
  };
}

function stripHtml(value: string): string {
  const entities: Record<string, string> = {
    amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", nbsp: " ",
  };
  return value
    .replace(/<\/?(?:p|div|br)[^>]*>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (_, entity) => entities[entity] ?? "")
    .replace(/\s+/g, " ")
    .trim();
}

const fetchers: Record<SocialPlatform, (topic: string, limit: number) => Promise<SocialPost[]>> = {
  reddit: fetchReddit,
  mastodon: fetchMastodon,
  bluesky: fetchBluesky,
};

export async function fetchSocialPosts(
  topics: string[],
  platforms: SocialPlatform[],
  limit: number,
) {
  const requests = topics.flatMap((topic) =>
    platforms.map(async (platform) => ({
      topic,
      platform,
      posts: await fetchers[platform](topic, limit).catch((err) => {
        return { error: err instanceof Error ? err.message : String(err) };
      }),
    })),
  );

  const responses = await Promise.all(requests);
  const posts: SocialPost[] = [];
  const errors: { platform: string; message: string }[] = [];

  for (const response of responses) {
    if ("error" in response.posts) {
      errors.push({ platform: response.platform, message: response.posts.error });
    } else {
      posts.push(...response.posts);
    }
  }

  return { posts, errors };
}
