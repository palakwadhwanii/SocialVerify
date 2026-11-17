import { afterEach, expect, test } from "bun:test";
import { fetchBluesky, fetchSocialPosts, fetchMastodon } from "./socialService";

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

test("normalizes Mastodon posts and handles errors gracefully", async () => {
  globalThis.fetch = (async (input: any) => {
    const url = new URL(String(input));
    if (url.pathname === "/api/v2/search" && url.searchParams.get("type") === "statuses") {
      return Response.json({
        statuses: [{
          id: "11234567890",
          account: { username: "investigator", acct: "investigator@mastodon.social" },
          content: "<p>Mastodon public verification finding with &amp; entity</p>",
          url: "https://mastodon.social/@investigator/11234567890",
          created_at: "2026-10-27T12:00:00.000Z",
          favourites_count: 14,
          replies_count: 5,
          reblogs_count: 8,
        }]
      });
    }
    return new Response("unavailable", { status: 503 });
  }) as unknown as typeof fetch;

  const result = await fetchSocialPosts(["test topic"], ["mastodon"], 5);

  expect(result.posts.length).toBe(1);
  const first = result.posts[0]!;
  expect(first).toMatchObject({
    platform: "mastodon",
    topic: "test topic",
    author: "@investigator@mastodon.social",
    content: "Mastodon public verification finding with & entity",
    url: "https://mastodon.social/@investigator/11234567890",
    instanceDomain: "mastodon.social",
  });
  expect(first.engagement).toEqual({
    comments: 5,
    likes: 14,
    reposts: 8,
  });
});

test("preserves genuine status URLs and instance domains from Mastodon", async () => {
  globalThis.fetch = (async () => {
    return Response.json({
      statuses: [{
        id: "998877",
        account: { username: "auditor", acct: "auditor" },
        content: "<p>Investigating claim divergence</p>",
        url: "https://mastodon.social/@auditor/998877",
        created_at: "2026-10-27T10:00:00.000Z",
        favourites_count: 3,
        replies_count: 1,
        reblogs_count: 2,
      }]
    });
  }) as unknown as typeof fetch;

  const posts = await fetchMastodon("claim", 3);
  expect(posts.length).toBeGreaterThan(0);
  const first = posts[0]!;
  expect(first.url).toBe("https://mastodon.social/@auditor/998877");
  expect(first.instanceDomain).toBe("mastodon.social");
});

test("collects Bluesky posts with original publication and retrieval timestamps", async () => {
  globalThis.fetch = (async (input: any) => {
    const url = new URL(String(input));
    expect(url.hostname).toBe("public.api.bsky.app");
    expect(url.searchParams.get("q")).toBe("public claim");
    return Response.json({
      posts: [{
        uri: "at://did:plc:abc/app.bsky.feed.post/record123",
        record: {
          text: "A matching public claim",
          createdAt: "2026-10-25T10:15:00.000Z",
        },
        indexedAt: "2026-10-25T10:16:00.000Z",
        author: { handle: "reporter.example" },
      }],
    });
  }) as unknown as typeof fetch;

  const [post] = await fetchBluesky("public claim", 5);
  expect(post).toBeDefined();
  expect(post!).toMatchObject({
    platform: "bluesky",
    author: "@reporter.example",
    content: "A matching public claim",
    url: "https://bsky.app/profile/reporter.example/post/record123",
    publishedAt: "2026-10-25T10:15:00.000Z",
  });
  expect(Number.isNaN(Date.parse(post!.retrievedAt))).toBe(false);
});

test("does not substitute Bluesky indexing time for a missing publication time", async () => {
  globalThis.fetch = (async () => Response.json({
    posts: [{
      uri: "at://did:plc:abc/app.bsky.feed.post/record123",
      indexedAt: "2026-10-25T10:16:00.000Z",
      author: { handle: "reporter.example" },
    }],
  })) as unknown as typeof fetch;

  const [post] = await fetchBluesky("public claim", 5);
  expect(post).toBeDefined();
  expect(post!.publishedAt).toBeNull();
});
