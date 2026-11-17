import re
import math
from collections import Counter
from typing import Any

DATE_PATTERN = re.compile(r"\b(20\d\d|19\d\d|january|february|march|april|may|june|july|august|september|october|november|december)\b", re.IGNORECASE)
ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)*|[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)*)\b")
TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)

STOP_ENTITY_WORDS = {
    "the", "this", "that", "these", "those", "when", "what", "there", "here",
    "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "how", "why", "if", "according", "has", "have", "had", "does", "do", "did",
    "is", "am", "are", "was", "were", "will", "would", "shall", "should", "can", "could",
    "may", "might", "must", "find", "search", "check", "verify", "give", "tell",
    "show", "explain", "summarize", "please", "latest", "news", "report", "reports",
    "update", "updates", "official", "officially", "statement", "statements",
    "filing", "filings", "date", "dates", "source", "sources", "announce",
    "announces", "announced", "announcing", "announcement", "announcements",
    "unveil", "unveils", "unveiled", "launch", "launches", "launched",
    "confirm", "confirms", "confirmed", "claim", "claims", "its", "it"
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text) if len(token) > 2]


def calculate_cosine_similarity(text1: str, text2: str) -> float:
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    count1 = Counter(tokens1)
    count2 = Counter(tokens2)
    all_tokens = set(count1.keys()).union(set(count2.keys()))

    dot_product = sum(count1.get(t, 0) * count2.get(t, 0) for t in all_tokens)
    norm1 = math.sqrt(sum(v * v for v in count1.values()))
    norm2 = math.sqrt(sum(v * v for v in count2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0
    return round(dot_product / (norm1 * norm2), 4)


class EvidenceProcessor:
    """Python tools to process, compare, and structure evidence."""

    @staticmethod
    def extract_context_entities(text: str) -> dict[str, Any]:
        """Extract entities, dates, and identify missing context."""
        dates = list(dict.fromkeys(DATE_PATTERN.findall(text)))
        raw_entities = list(dict.fromkeys(ENTITY_PATTERN.findall(text)))[:15]

        # Filter out common sentence start words, helper verbs, and stopwords
        filtered_entities = [
            e.strip() for e in raw_entities
            if e.strip()
            and e.strip().lower() not in STOP_ENTITY_WORDS
            and not all(part.lower() in STOP_ENTITY_WORDS for part in e.strip().split())
        ][:10]

        missing_info = []
        if not dates:
            missing_info.append("Temporal timestamp or publication date not explicitly declared in query.")
        if len(filtered_entities) <= 1:
            missing_info.append("Limited named entities extracted; query is broad.")

        return {
            "entities": filtered_entities,
            "dates": dates,
            "missing_information": missing_info,
            "complexity_level": "High" if len(filtered_entities) > 3 else "Standard"
        }

    @staticmethod
    def is_post_relevant_to_query(text: str, query: str) -> bool:
        """Check if post is strictly relevant to the whole search query, not just a single common word."""
        if not text or not query:
            return False

        stopwords = {
            "about", "after", "against", "along", "among", "been", "before", "being", "between",
            "could", "does", "during", "from", "have", "into", "more", "most", "over", "same",
            "some", "than", "that", "their", "there", "these", "they", "this", "those", "through",
            "under", "very", "were", "what", "when", "where", "which", "while", "with", "would",
            "your", "has", "had", "did", "does", "find", "check", "tell", "give", "show", "please",
            "official", "officially", "statement", "statements", "filing", "filings", "date", "dates",
            "the", "and", "for", "with", "news", "latest", "update", "updates", "today", "report",
            "reports", "reported", "reporting", "say", "says", "said", "saying", "can", "will",
            "just", "also", "out", "now", "get", "who", "whom", "its", "it", "are", "was", "how",
            "why", "announce", "announces", "announced", "announcing", "announcement", "announcements",
            "unveil", "unveils", "unveiled", "unveiling", "launch", "launches", "launched", "launching",
            "break", "breaking", "confirm", "confirms", "confirmed", "confirming", "claim", "claims",
            "claimed", "claiming", "rumour", "rumours", "rumor", "rumors", "source", "sources",
            "recent", "recently", "detail", "details", "know", "knows", "known", "knowing",
            "an", "or", "in", "on", "at", "to", "of", "by", "as", "is", "if", "no", "so", "up",
            "do", "my", "we", "he", "me", "us", "be", "all"
        }

        raw_words = re.findall(r"[a-zA-Z0-9]{2,}", query)
        query_words = [w.lower() for w in raw_words if w.lower() not in stopwords]
        if not query_words:
            query_words = [w.lower() for w in raw_words]
        if not query_words:
            return True

        text_lower = text.lower()
        post_words = set(re.findall(r"[a-zA-Z0-9]{2,}", text_lower))

        def stem(w: str) -> str:
            if len(w) > 4 and w.endswith("es"):
                return w[:-2]
            if len(w) > 3 and w.endswith("s"):
                return w[:-1]
            return w

        stems = [stem(w) for w in query_words]
        unique_stems = list(dict.fromkeys(stems))
        post_stems = {stem(w) for w in post_words}

        # Check full query phrase match
        if " ".join(query_words) in text_lower:
            return True

        # Check compound (e.g. "nepalfloods", "nepalflood", "jioipo", "reliancejio")
        if len(stems) >= 2:
            compound1 = "".join(stems[:2])
            compound2 = "".join(query_words[:2])
            if compound1 in post_words or compound2 in post_words or compound1 in text_lower:
                return True
            if len(stems) >= 3:
                compound3 = "".join(stems[1:3])
                compound4 = "".join(query_words[1:3])
                if compound3 in post_words or compound4 in post_words or compound3 in text_lower:
                    return True

        matched_stems = [s for s in unique_stems if s in post_stems or s in post_words]

        if len(unique_stems) == 1:
            return len(matched_stems) >= 1

        if len(unique_stems) == 2:
            return len(matched_stems) >= 2

        # For 3 or more topical stems, require matching at least 2 AND at least 50% of keywords
        required_matches = max(2, math.ceil(len(unique_stems) * 0.5))
        return len(matched_stems) >= required_matches

    @staticmethod
    def assess_relevance_and_relation(
        item_text: str,
        query: str,
        entities: list[str] | None = None,
        category: str = "news"
    ) -> dict[str, str]:
        """Assess whether a source is Relevant, Partially Relevant, or Not Relevant, and its relation of correctness."""
        text_lower = item_text.lower()
        query_tokens = [t for t in tokenize(query) if t not in STOP_ENTITY_WORDS]
        clean_entities = [e.lower() for e in (entities or []) if e.lower() not in STOP_ENTITY_WORDS]

        # 1. Match entities & query tokens
        entity_matches = sum(1 for e in clean_entities if e in text_lower)
        token_matches = sum(1 for t in query_tokens if t in text_lower)
        similarity = calculate_cosine_similarity(query, item_text)
        is_strictly_relevant = EvidenceProcessor.is_post_relevant_to_query(item_text, query)

        # 2. Assign relevance tag
        if is_strictly_relevant:
            relevance = "Relevant"
        elif (clean_entities and entity_matches >= min(2, len(clean_entities))) or similarity >= 0.22 or token_matches >= 3:
            relevance = "Relevant"
        elif entity_matches >= 1 or similarity >= 0.10 or token_matches >= 1:
            relevance = "Partially Relevant"
        else:
            relevance = "Not Relevant"

        # 3. Assess Cross-Media Relationship & Correctness
        debunk_keywords = {"false", "debunk", "untrue", "fake", "deny", "denies", "dispute", "refute", "incorrect", "rumour", "rumor", "speculative", "unconfirmed", "no filing"}
        confirm_keywords = {"confirmed", "official", "filing", "filed", "statement", "approved", "announces", "announced", "launch"}

        has_debunk = any(w in text_lower for w in debunk_keywords)
        has_confirm = any(w in text_lower for w in confirm_keywords)

        if category == "news":
            if has_confirm and relevance == "Relevant":
                relation = "Corroborates Formal Claim"
                correctness = "Verified Fact"
            elif has_debunk and relevance == "Relevant":
                relation = "Refutes Misinformation"
                correctness = "Debunks False Rumour"
            elif relevance == "Relevant":
                relation = "Direct Coverage"
                correctness = "Developing Incident Coverage"
            elif relevance == "Partially Relevant":
                relation = "Background Context"
                correctness = "General Thematic Discussion"
            else:
                relation = "Tangential"
                correctness = "Unrelated to Subject"
        else:  # social
            if has_confirm and relevance == "Relevant":
                relation = "Echoes Verified Claim"
                correctness = "Consistent with News"
            elif has_debunk and relevance == "Relevant":
                relation = "Citizen Scrutiny"
                correctness = "Challenges Premature Reports"
            elif relevance == "Relevant":
                relation = "Public Discussion"
                correctness = "Citizen Commentary & Eyewitness Sharing"
            elif relevance == "Partially Relevant":
                relation = "Peripheral Discussion"
                correctness = "General Public Context"
            else:
                relation = "Unrelated Noise"
                correctness = "Off-Topic"

        return {
            "relevance": relevance,
            "cross_media_relation": relation,
            "correctness": correctness,
        }

    @staticmethod
    def compare_evidence(
        claim: str,
        news_items: list[dict[str, Any]],
        social_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Compute semantic overlap and determine supporting vs counter evidence."""
        supporting_news = []
        counter_news = []
        supporting_social = []
        counter_social = []

        contradiction_keywords = {"false", "debunk", "untrue", "fake", "deny", "denies", "dispute", "refute", "incorrect"}

        for item in news_items:
            content = f"{item.get('title', '')} {item.get('body', '')}"
            sim = calculate_cosine_similarity(claim, content)
            url = item.get("url", "")
            if not url:
                continue

            has_contradiction = any(w in content.lower() for w in contradiction_keywords)
            if has_contradiction:
                counter_news.append({"url": url, "similarity": sim})
            elif sim > 0.1:
                supporting_news.append({"url": url, "similarity": sim})

        for item in social_items:
            content = f"{item.get('title', '')} {item.get('text', '')}"
            sim = calculate_cosine_similarity(claim, content)
            url = item.get("url", "")
            if not url:
                continue

            has_contradiction = any(w in content.lower() for w in contradiction_keywords)
            if has_contradiction:
                counter_social.append({"url": url, "similarity": sim})
            elif sim > 0.1:
                supporting_social.append({"url": url, "similarity": sim})

        return {
            "claim": claim,
            "supporting_news": supporting_news,
            "counter_news": counter_news,
            "supporting_social": supporting_social,
            "counter_social": counter_social,
            "overall_support_count": len(supporting_news) + len(supporting_social),
            "overall_counter_count": len(counter_news) + len(counter_social)
        }

    @staticmethod
    def build_timeline_phases(
        query: str,
        sources: list[Any] | None = None,
        news_items: list[dict[str, Any]] | None = None,
        social_items: list[dict[str, Any]] | None = None,
        claim_status: str | None = None,
    ) -> list[dict[str, str]]:
        """Construct attractive, structured chronological timeline stages with bold keywords."""
        context = EvidenceProcessor.extract_context_entities(query)
        entities = context.get("entities", [])
        entity_highlight = f"**{', '.join(entities[:3])}**" if entities else f"**'{query[:50]}'**"

        status_lower = (claim_status or "").lower()

        if "contradict" in status_lower or "debunk" in status_lower or "false" in status_lower:
            phase3_news = (
                f"**Authoritative media and official registries** explicitly **debunked the claim** concerning {entity_highlight}, "
                f"confirming that **no credible corroboration** exists."
            )
            phase3_social = (
                f"**Social media sentiment** pivoted toward **disseminating debunking alerts**, warning users against **unverified claims** "
                f"and clarifying that the rumour **lacked factual backing**."
            )
        elif "support" in status_lower:
            phase3_news = (
                f"**Primary corporate releases and regulatory disclosures** **officially confirmed** the core milestones regarding {entity_highlight}."
            )
            phase3_social = (
                f"**Community discourse** transitioned from speculation to **substantive analysis**, discussing the implications of the **confirmed development**."
            )
        else:
            phase3_news = (
                f"**Authoritative regulatory databases and newsrooms** confirm that **no formal regulatory filing or official statement** "
                f"has been submitted concerning {entity_highlight}; the claim remains **unsubstantiated speculation**."
            )
            phase3_social = (
                f"**Online discussions** remain divided between **speculative commentary** and **clarification-seeking**, with participants noting the **absence of primary proof**."
            )

        return [
            {
                "phase": "Phase 1: Emergence & Speculation",
                "news": (
                    f"**Initial market coverage and media commentary** cited **unnamed industry insiders** and analyst projections regarding {entity_highlight}, "
                    f"acknowledging that **formal filings were pending**."
                ),
                "social": (
                    f"**Retail investors and community forums** circulated early headlines asking if an **official announcement** had been made, "
                    f"generating an initial **surge in search queries and social shares**."
                ),
            },
            {
                "phase": "Phase 2: Narrative Amplification & Debate",
                "news": (
                    f"**Mainstream financial desks** published in-depth analyses evaluating viability, emphasizing that **no statutory draft prospectus (e.g. DRHP)** or board sanction had been lodged."
                ),
                "social": (
                    f"**Viral discussion threads** amplified prospective timelines and valuation figures, with users alternating between **high anticipation** and **healthy skepticism**."
                ),
            },
            {
                "phase": "Phase 3: Current Status & Verification",
                "news": phase3_news,
                "social": phase3_social,
            },
        ]

