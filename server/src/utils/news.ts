export function parseSimpleRss(xml: string, sourceName: string) {
    const items: any[] = [];
    const itemRegex = /<item>([\s\S]*?)<\/item>/g;
    const titleRegex = /<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/title>/;
    const linkRegex = /<link>(.*?)<\/link>/;
    const pubDateRegex = /<pubDate>(.*?)<\/pubDate>/;
    const descriptionRegex = /<description>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/description>/;

    let match;
    while ((match = itemRegex.exec(xml)) !== null) {
        const itemXml = match[1] || "";
        const titleMatch = titleRegex.exec(itemXml);
        const linkMatch = linkRegex.exec(itemXml);
        const pubDateMatch = pubDateRegex.exec(itemXml);
        const descriptionMatch = descriptionRegex.exec(itemXml);

        if (titleMatch || linkMatch) {
            const description = descriptionMatch?.[1]
                ? cleanRssText(descriptionMatch[1])
                : null;
            items.push({
                title: titleMatch ? cleanRssText(titleMatch[1]) : "No Title",
                url: linkMatch ? decodeXmlEntities(linkMatch[1]) : "",
                publishedAt: parsePublishedAt(pubDateMatch?.[1]),
                description,
                content: description,
                source: sourceName
            });
        }

        function cleanRssText(value: string): string {
            return value
                .replace(/<[^>]*>/g, " ")
                .replace(/&(amp|lt|gt|quot|#39);/g, (_, entity: string) => decodeXmlEntities(`&${entity};`))
                .replace(/\s+/g, " ")
                .trim();
        }

        function decodeXmlEntities(value: string): string {
            const entities: Record<string, string> = {
                amp: "&",
                lt: "<",
                gt: ">",
                quot: '"',
                "#39": "'",
            };
            return value.replace(/&(amp|lt|gt|quot|#39);/g, (_, entity: string) => entities[entity]);
        }

        function parsePublishedAt(value?: string): string | null {
            if (!value) return null;
            const timestamp = Date.parse(value);
            return Number.isNaN(timestamp) ? null : new Date(timestamp).toISOString();
        }
    }
    return {
        totalResults: items.length,
        articles: items
    };
}