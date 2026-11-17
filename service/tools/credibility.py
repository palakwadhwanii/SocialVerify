from urllib.parse import urlparse
from typing import Any

TIER_1_DOMAINS = {
    "europa.eu", "wto.org", "reuters.com", "apnews.com", "who.int",
    "nature.com", "science.org", "un.org", "bbc.com", "bbc.co.uk",
    "ember-climate.org", "artificialintelligenceact.eu"
}

TIER_2_DOMAINS = {
    "nytimes.com", "theguardian.com", "bloomberg.com", "wsj.com",
    "ft.com", "washingtonpost.com", "cnbc.com", "economist.com",
    "theverge.com", "arstechnica.com", "wired.com"
}

SOCIAL_DOMAINS = {
    "reddit.com", "bsky.app", "mastodon.social", "twitter.com", "x.com"
}


class SourceCredibilityEvaluator:
    """Evaluates source reliability, domain authority, and evidence weight."""

    @staticmethod
    def evaluate_url(url: str, source_type: str = "other") -> dict[str, Any]:
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            # Strip subdomains for matching
            domain_parts = netloc.split(".")
            root_domain = ".".join(domain_parts[-2:]) if len(domain_parts) >= 2 else netloc

            if netloc in TIER_1_DOMAINS or root_domain in TIER_1_DOMAINS:
                tier = "Tier 1: Institutional & Authoritative Journalism"
                score = 0.95
                authority = "High"
            elif netloc in TIER_2_DOMAINS or root_domain in TIER_2_DOMAINS:
                tier = "Tier 2: Major Accredited News Organization"
                score = 0.85
                authority = "Moderate-High"
            elif netloc in SOCIAL_DOMAINS or root_domain in SOCIAL_DOMAINS or source_type == "social":
                tier = "Tier 4: Public Social Commentary"
                score = 0.50
                authority = "Unverified - Requires Corroboration"
            else:
                tier = "Tier 3: Web Article / Secondary Source"
                score = 0.70
                authority = "Moderate"

            return {
                "url": url,
                "domain": netloc,
                "credibility_tier": tier,
                "credibility_score": score,
                "authority_level": authority
            }
        except Exception:
            return {
                "url": url,
                "domain": "unknown",
                "credibility_tier": "Unverified",
                "credibility_score": 0.40,
                "authority_level": "Low"
            }

    @classmethod
    def evaluate_sources(cls, sources: list[dict[str, Any]]) -> dict[str, Any]:
        evaluations = []
        scores = []
        for src in sources:
            url = src.get("url", "")
            eval_res = cls.evaluate_url(url, src.get("source_type", "other"))
            evaluations.append(eval_res)
            scores.append(eval_res["credibility_score"])

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.5
        return {
            "average_source_credibility": avg_score,
            "evaluations": evaluations
        }
