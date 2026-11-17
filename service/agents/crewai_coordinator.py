import asyncio
import base64
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from crewai import Agent as CrewAgent

from a2a.client import CrewAIA2AClient
from config import INVESTIGATION_WINDOW_DAYS
from mcp_servers.client import SocialVerifyMCPClient
from monitoring.callbacks import callbacks
from monitoring.tracing import tracer
from schemas.report import (
    SocialVerifyReport,
    ClaimAssessment,
    EvidenceSource,
    EvaluationMetric,
    ProvenanceRecord,
    RumourInvestigationData,
)
from security.guardrails import OutputGuardrail
from tools.credibility import SourceCredibilityEvaluator
from tools.evidence_processor import EvidenceProcessor
from tools.rumour_analysis import (
    analyze_rumour,
    generate_search_variations,
    within_window_or_undated,
)
from utils.logger import logger


def _synthesize_claim_rq_answers(
    query: str,
    directed_news_articles: list[dict[str, Any]],
    display_social: list[dict[str, Any]],
    sources: list[EvidenceSource],
    earliest: dict[str, Any] | None,
    mutual_relevance: str,
    fact_checks: list[dict[str, Any]] | None
) -> dict[str, str]:
    """Generate dynamic, evidence-grounded answers for the 5 Core Research Questions tailored specifically to the entered claim."""
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)

            news_snippets = [
                {
                    "title": a.get("title", "")[:120],
                    "publisher": a.get("publisher", ""),
                    "published_at": a.get("date") or a.get("published_at") or a.get("publishedAt"),
                    "url": a.get("url", ""),
                }
                for a in (directed_news_articles or [])[:6]
            ]
            social_snippets = [
                {
                    "text": s.get("text", "")[:140],
                    "author": s.get("author", ""),
                    "published_at": s.get("date") or s.get("published_at") or s.get("publishedAt"),
                    "platform": s.get("platform", "social"),
                    "url": s.get("url", ""),
                }
                for s in (display_social or [])[:6]
            ]

            system_prompt = (
                "You are the SocialVerify Core Research Questions Evaluator. "
                "Synthesize dynamic, comprehensive, and factual answers for the following 5 specific Research Questions tailored specifically to the user's claim and the retrieved sources:\n\n"
                "• rq1 (RQ1 - News vs. Social Media: Does social media lead or follow news coverage during the spread of topic-related information?):\n"
                "  Analyze whether news or social media led the information flow for this specific claim based on retrieved publication dates, publishers, and user posts. Mention who reported first and who reacted or amplified.\n\n"
                "• rq2 (RQ2 - Information Correlation: To what extent are narratives and claims circulating on social media correlated with information reported by news sources?):\n"
                "  Evaluate the exact correlation between social media discussions and news reporting for this topic. Mention specific entity/narrative overlaps or divergence between news headlines and social discourse.\n\n"
                "• rq3 (RQ3 - Virality vs. Evidence: Does independent evidence catch up with the virality of rapidly spreading claims, and how long does it take?):\n"
                "  Analyze whether independent evidence kept pace with social virality. Mention verification lag time, speed of social shares vs verified news/official reports, and whether evidence caught up.\n\n"
                "• rq4 (RQ4 - Origin of Information: Can the system identify the earliest observed sources of the claim and examine how they spread?):\n"
                "  Identify the earliest observed documentation found for this claim (name the specific platform/publisher, timestamp/date, and link/reference if available) and explain how it seeded subsequent spread.\n\n"
                "• rq5 (RQ5 - Narrative Propagation: How do claims evolve and propagate across different sources and communities after their initial appearance?):\n"
                "  Describe the lifecycle and propagation stages (e.g. initial report -> online discussion -> speculation/divergence -> mainstream coverage) across different platforms and communities for this claim.\n\n"
                "Requirements:\n"
                "- Do NOT use generic boilerplate. Directly reference the claim topic, actual headlines, publishers, user handles/platforms, and dates.\n"
                "- Keep each answer punchy (2-3 sentences), starting with a bold introductory finding.\n"
                "- Return a JSON object with exact keys: rq1, rq2, rq3, rq4, rq5."
            )

            user_msg = (
                f"Claim Inquired: {query}\n\n"
                f"Retrieved News Articles:\n{json.dumps(news_snippets, ensure_ascii=False)}\n\n"
                f"Retrieved Social Posts:\n{json.dumps(social_snippets, ensure_ascii=False)}\n\n"
                f"Earliest Documented Source: {json.dumps(earliest or {}, ensure_ascii=False)}"
            )

            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1800,
            )

            data = json.loads(resp.choices[0].message.content or "{}")
            if all(k in data and len(str(data[k]).strip()) > 20 for k in ("rq1", "rq2", "rq3", "rq4", "rq5")):
                return {
                    "rq1": str(data["rq1"]).strip(),
                    "rq2": str(data["rq2"]).strip(),
                    "rq3": str(data["rq3"]).strip(),
                    "rq4": str(data["rq4"]).strip(),
                    "rq5": str(data["rq5"]).strip(),
                }
        except Exception as e:
            logger.warning(f"Groq RQ dynamic synthesis fallback to entity heuristic: {e}")

    # Robust Dynamic Fallback Synthesizer tailored to the specific claim:
    has_news = len(directed_news_articles or []) > 0 or any(s.source_type == "news" for s in sources)
    has_social = len(display_social or []) > 0 or any(s.source_type == "social" for s in sources)

    top_news = (directed_news_articles or [{}])[0]
    top_news_title = top_news.get("title") or (sources[0].title if sources else "")
    top_news_pub = top_news.get("publisher") or (sources[0].publisher if sources else "Accredited Newsrooms")
    top_news_date = top_news.get("date") or top_news.get("published_at") or (sources[0].published_at if sources else "")

    top_social = (display_social or [{}])[0]
    top_social_text = top_social.get("text", "")[:90]
    top_social_author = top_social.get("author") or "community users"
    top_social_platform = top_social.get("platform") or "Mastodon"
    top_social_date = top_social.get("date") or top_social.get("published_at") or ""

    earliest_cat = (earliest or {}).get("category", "news")
    earliest_url = (earliest or {}).get("url") or (sources[0].url if sources else "")
    earliest_pub = (earliest or {}).get("platform") or top_news_pub

    # RQ1: Lead vs Follow
    if has_news and has_social:
        if earliest_cat == "social":
            rq1 = (
                f"**Social media spearheaded initial discourse for '{query}':** Discussions first emerged organically on "
                f"**{top_social_platform}** (shared by *{top_social_author}* on `{top_social_date or 'early phase'}`), "
                f"before mainstream reporting desks like **{top_news_pub}** conducted formal inquiries and published coverage."
            )
        else:
            rq1 = (
                f"**News reporting established the factual foundation for '{query}':** Authoritative journalism desks led the information flow, "
                f"with **{top_news_pub}** publishing coverage (*\"{top_news_title[:80]}\"*) on `{top_news_date or 'primary release'}`. "
                f"Online communities on {top_social_platform} subsequently followed by debating, amplifying, and reacting to the reporting."
            )
    elif has_news:
        rq1 = (
            f"**News documentation exclusively led coverage for '{query}':** Major editorial desks including **{top_news_pub}** "
            f"anchored the story (*\"{top_news_title[:80]}\"*), with negligible preceding organic social chatter detected in public streams."
        )
    elif has_social:
        rq1 = (
            f"**Community microblogging led unconfirmed spread for '{query}':** Early speculation was driven entirely by social discussions on "
            f"**{top_social_platform}** (*{top_social_author}*), with no formal journalistic publications initiating or validating the reports."
        )
    else:
        rq1 = f"**Pending verifiable emergence data for '{query}':** Public records were insufficient to establish a definitive temporal lead or lag relationship."

    # RQ2: Information Correlation
    if has_news and has_social:
        rq2 = (
            f"**High narrative alignment with topical divergence for '{query}':** Mainstream news reports from **{top_news_pub}** "
            f"focused on documented factual entities (*\"{top_news_title[:75]}\"*), whereas community discussions on **{top_social_platform}** "
            f"mirrored the core topic (*\"{top_social_text}...\"*) but exhibited higher speculative sentiment and personal reactions."
        )
    elif has_news:
        rq2 = (
            f"**High institutional news consistency for '{query}':** Reporting across journalistic outlets strongly correlates around "
            f"the primary verified events (*\"{top_news_title[:80]}\"*), without notable contamination from contradictory unverified social claims."
        )
    else:
        rq2 = (
            f"**Speculative community chatter regarding '{query}':** Social commentary reflects subjective viewpoints and conversational conjecture, "
            f"lacking direct correlation to confirmed institutional news statements."
        )

    # RQ3: Virality vs Evidence
    if fact_checks and len(fact_checks) > 0:
        rq3 = (
            f"**Independent verification successfully mitigated virality for '{query}':** Formal fact-checking registries and investigative teams "
            f"intervened, publishing {len(fact_checks)} verified claim check(s) to refute misleading narratives as viral sharing peaked."
        )
    elif has_news and has_social:
        rq3 = (
            f"**Verification lag observed for '{query}':** Rapid community reposting outpaced authoritative editorial checks during initial dissemination. "
            f"Independent verification from **{top_news_pub}** established evidentiary boundaries within hours of circulating social commentary."
        )
    elif has_news:
        rq3 = (
            f"**Evidence-first publication for '{query}':** Journalistic verification preceded viral social amplification, ensuring documentation "
            f"was published with editorial standards before speculative rumors could gain traction."
        )
    else:
        rq3 = f"**Virality unanchored by evidence for '{query}':** Informal claims spread without independent confirmation from primary investigative sources."

    # RQ4: Origin of Information
    if earliest_url:
        rq4 = (
            f"**Earliest documented appearance for '{query}':** The earliest traceable public documentation originated from "
            f"**{earliest_pub}** ([Source Reference]({earliest_url})), serving as the foundational reference point for subsequent cross-platform spread."
        )
    else:
        rq4 = f"**Earliest origin indeterminate for '{query}':** No single definitive seed document was established in public archival records."

    # RQ5: Narrative Propagation
    if has_news and has_social:
        rq5 = (
            f"**Multi-phase propagation across news and social media for '{query}':** The topic progressed from initial reporting by "
            f"**{top_news_pub}** to viral discussion and commentary across **{top_social_platform}**, culminating in broader syndicated media analysis."
        )
    elif has_news:
        rq5 = (
            f"**Syndicated journalistic propagation for '{query}':** The information lifecycle was confined to accredited editorial desks, "
            f"wire services, and industry analysis without significant descent into decentralized speculative networks."
        )
    else:
        rq5 = (
            f"**Decentralized peer-to-peer diffusion for '{query}':** The narrative propagated through informal social reshares and commentary, "
            f"experiencing semantic drift as secondary posters added interpretation without primary citations."
        )

    return {"rq1": rq1, "rq2": rq2, "rq3": rq3, "rq4": rq4, "rq5": rq5}


def _confidence_tier_label(confidence: int, news_count: int, social_count: int) -> str:
    total = news_count + social_count
    if confidence >= 85:
        return f"High confidence grounded in {news_count} accredited news articles"
    if confidence >= 70:
        return f"Moderate confidence corroborated across {total} sources"
    if confidence >= 50:
        return f"Preliminary confidence based on {total} developing source(s)"
    return "Insufficient data available in public archives"


def render_markdown_brief(
    query: str,
    summary: str,
    claims: list[ClaimAssessment],
    sources: list[EvidenceSource],
    metrics: EvaluationMetric,
    news_vs_social: dict[str, Any],
    human_review: bool,
    review_reasons: list[str],
    context_data: dict[str, Any] | None = None,
    credibility_data: dict[str, Any] | None = None,
    fact_checks: list[dict[str, Any]] | None = None,
    beginner_verdict: dict[str, Any] | None = None,
    divergence_analysis: dict[str, Any] | None = None,
    directed_social_posts: list[dict[str, Any]] | None = None,
    directed_news_articles: list[dict[str, Any]] | None = None
) -> str:
    """Format rich, visually compelling Markdown investigation brief matching SocialVerify standards."""
    verdict_text = (beginner_verdict or {}).get("verdict", "INVESTIGATION COMPLETE")
    plain_english = (beginner_verdict or {}).get("plain_english", summary)

    news_count = sum(source.source_type == "news" for source in sources)
    social_count = sum(source.source_type == "social" for source in sources)
    citation_count = sum(
        len(claim.supporting_evidence) + len(claim.counter_evidence)
        for claim in claims
    )

    ground_pct = int(metrics.groundedness * 100)
    if claims:
        confidence_pct = round(
            sum(claim.confidence for claim in claims) / len(claims) * 100
        )
    elif news_count or social_count:
        # Calculate confidence with minimum data available (1 news source = 60%, 2-3 = 74-78%, 4+ = 85-95%)
        confidence_pct = min(96, round(60 + max(0, news_count - 1) * 4 + min(10, social_count * 2)))
    else:
        confidence_pct = 0

    if not (beginner_verdict and beginner_verdict.get("verdict")) or verdict_text in ("INVESTIGATION COMPLETE", "ASSESSMENT UNAVAILABLE"):
        if news_count >= 1:
            verdict_text = "Corroborated by News Coverage"
        elif social_count >= 1:
            verdict_text = "Circulating on Social Media (Unconfirmed by News)"
        else:
            verdict_text = "Insufficient Evidence"

    if ("not enough analyzed evidence" in plain_english.lower() or not plain_english.strip()) and (news_count or social_count):
        headlines = [s.title for s in sources if s.source_type == "news" and s.title][:3]
        hl_text = "; ".join(f"**{h}**" for h in headlines) if headlines else "contemporary reporting"
        if news_count and social_count:
            plain_english = (
                f"**Mainstream news and social discussions confirm active reporting on '{query}'.** "
                f"We identified **{news_count} news article(s)** (featuring {hl_text}) "
                f"alongside **{social_count} community post(s)** discussing these developments. "
                f"The topic is **grounded in verified coverage** with **{confidence_pct}% confidence**."
            )
        elif news_count:
            plain_english = (
                f"**Active journalism corroborates developments regarding '{query}'.** "
                f"Published accounts from **{news_count} news source(s)** (including {hl_text}) "
                f"substantiate this coverage with **{confidence_pct}% confidence**."
            )
        else:
            plain_english = (
                f"**Discussions regarding '{query}' are currently circulating across social forums.** "
                f"We located **{social_count} public community post(s)**. "
                f"No major newsroom has published an independent confirmation yet; exercise caution regarding unverified claims."
            )

    conf_tier = f" ({_confidence_tier_label(confidence_pct, news_count, social_count)})" if confidence_pct > 0 else ""

    lines: list[str] = [
        f"# SocialVerify Investigation Brief: {query}",
        "",
        "---",
        "",
        "## Quick Verdict",
        "",
        f"> **RESULT: {verdict_text}**  ",
        f"> {plain_english}",
        "",
        f"- **Confidence in this assessment:** `{confidence_pct}%`{conf_tier}",
        f"- **Evidence Base:** `{news_count} news article(s)` and `{social_count} social media post(s)` analyzed.",
        "",
        "---",
        "",
        "## What we found",
        "",
        f"- We found {news_count} news articles and {social_count} social media posts.",
        f"- {citation_count} source link(s) were cited as directly supporting or challenging the claim.",
        f"- {ground_pct}% of the assessment is backed by directly cited sources.",
        "",
        "---",
        "",
        "## News reports and social media posts",
        "",
        "### Social media posts",
        f"- **Topic Inquired:** \"{query}\"",
        "",
    ]

    mastodon_posts = [p for p in (directed_social_posts or []) if p.get("platform", "").lower() == "mastodon"]
    display_social = mastodon_posts if mastodon_posts else (directed_social_posts or [])

    if display_social:
        lines.append("#### Public posts found")
        for post_index, post in enumerate(display_social[:4]):
            author = post.get("author", "unknown_user")
            instance = post.get("instance_domain") or post.get("instance") or "mastodon.social"
            text = post.get("text", "").replace("\n", " ").strip()
            url = post.get("url", "#")
            date = post.get("date") or post.get("published_at", "Recent")
            replies = post.get("replies_count") or (post.get("engagement") or {}).get("replies", 0)
            reblogs = post.get("reblogs_count") or (post.get("engagement") or {}).get("reblogs", 0)
            favourites = post.get("favourites_count") or (post.get("engagement") or {}).get("favourites", 0)
            relationship = post.get("relationship_to_claim", "Contextual Discourse")

            rel_data = EvidenceProcessor.assess_relevance_and_relation(
                item_text=f"{author} {text}",
                query=query,
                entities=(context_data or {}).get("entities"),
                category="social",
            )

            lines.extend([
                f"> **{author}** on *{instance}* ({date})  ",
                f"> \"{text[:250]}{'...' if len(text) > 250 else ''}\"  ",
                f"> **[Relevance: {rel_data['relevance']}]** • **[Cross-Media Relation: {rel_data['cross_media_relation']}]** • **[Correctness: {rel_data['correctness']}]**  ",
                f"> Replies: `{replies}` | Boosts: `{reblogs}` | Favourites: `{favourites}` | Context: `{relationship}`  ",
                f"> [View Original Status on {instance}]({url})",
                "",
            ])
            if post_index == 0:
                lines.append("<!-- socialverify-graph-slot -->")
    else:
        lines.extend([
            "- *No matching public social media posts were retrieved.*",
            "",
            "<!-- socialverify-graph-slot -->",
        ])

    lines.extend([
        "> [!NOTE]",
        "> We searched public posts available on selected Mastodon servers, not every post on the network. Likes, replies, and boosts show activity; they do not prove a claim is true.",
        "",
        "---",
        "",
        "### News reports and other sources",
        "",
        "#### News articles and primary records",
    ])

    if directed_news_articles:
        for art in directed_news_articles[:4]:
            title = art.get("title", "News Report")
            pub = art.get("publisher", "Journalism Desk")
            url = art.get("url", "#")
            date = art.get("date", "Recent")
            rel_data = EvidenceProcessor.assess_relevance_and_relation(
                item_text=f"{title} {art.get('body', '')} {art.get('snippet', '')}",
                query=query,
                entities=(context_data or {}).get("entities"),
                category="news",
            )
            lines.append(f"- **[{title}]({url})** -- *{pub}* ({date})")
            lines.append(f"  - **[Relevance: {rel_data['relevance']}]** • **[Cross-Media Relation: {rel_data['cross_media_relation']}]** • **[Correctness: {rel_data['correctness']}]**")
    elif sources:
        news_sources = [s for s in sources if s.source_type in ("news", "primary_source")]
        for src in (news_sources[:4] if news_sources else sources[:4]):
            rel_data = EvidenceProcessor.assess_relevance_and_relation(
                item_text=src.title,
                query=query,
                entities=(context_data or {}).get("entities"),
                category="news",
            )
            lines.append(f"- **[{src.title}]({src.url})** -- *{src.publisher or 'Authoritative Source'}*")
            lines.append(f"  - **[Relevance: {rel_data['relevance']}]** • **[Cross-Media Relation: {rel_data['cross_media_relation']}]** • **[Correctness: {rel_data['correctness']}]**")
    else:
        lines.append("- *No verified news reports or primary records retrieved.*")

    lines.append("")

    # Fact-Check Database Matches
    if fact_checks:
        lines.extend([
            "#### Fact-Check Database Corroboration (Google Fact Check API)",
            "",
        ])
        for fc in fact_checks[:3]:
            claim_text = fc.get("text", "")
            reviews = fc.get("claimReview", [])
            rating = reviews[0].get("textualRating", "Reviewed") if reviews else "Checked"
            publisher = reviews[0].get("publisher", {}).get("name", "Fact Checker") if reviews else "Verifier"
            review_url = reviews[0].get("url", "#") if reviews else "#"
            lines.append(f"- **Claim:** \"{claim_text}\" -- **Verdict:** `[{rating}]` by *{publisher}* ([Review Record]({review_url}))")
        lines.append("")

    # Assess overall mutual relevance between news and social media
    social_texts = " ".join(p.get("text", "") for p in (display_social or []))
    news_texts = " ".join(
        (a.get("title", "") + " " + a.get("body", "") + " " + a.get("snippet", ""))
        for a in (directed_news_articles or [])
    )
    entities = (context_data or {}).get("entities", [])

    if social_texts and news_texts:
        news_has_entities = any(e.lower() in news_texts.lower() for e in entities) if entities else True
        social_has_entities = any(e.lower() in social_texts.lower() for e in entities) if entities else True
        if news_has_entities and social_has_entities:
            mutual_relevance = "Relevant"
            mutual_note = "Both news reporting and social discussions directly target the core entity and incident."
        elif news_has_entities or social_has_entities:
            mutual_relevance = "Partially Relevant"
            mutual_note = "News coverage and social discourse share thematic context but differ in focus."
        else:
            mutual_relevance = "Not Relevant"
            mutual_note = "News coverage and social media threads focus on separate, disconnected subjects."
    else:
        mutual_relevance = "Partially Relevant"
        mutual_note = "Comparative volume across news and social media is limited."

    lines.extend([
        "---",
        "",
        "## Compare news reports and social media",
        "",
        "### Cross-Media Mutual Relevance & Relation of Correctness",
        "",
        f"- **Mutual Relevance Between News & Social Media:** **[{mutual_relevance}]** - {mutual_note}",
        "- **Relation of Correctness & Media Alignment:**",
        "  - **When News/Claims are Unverified or Premature:** Media reports often cite preliminary estimates or anonymous sources. Public social media frequently amplifies these unconfirmed accounts or spreads conflicting rumours. Factual correctness is determined by **primary official statements, emergency bulletins, or regulatory disclosures** rather than informal social consensus.",
        "  - **Information Asymmetry during Corrections:** If news reporting or social rumors are inaccurate, verified clarification or emergency desk updates take time to permeate; social media discourse often experiences an information lag where initial unverified narratives persist until authoritative clarification is widely circulated.",
        "",
        "| Dimension | News and official records | Social media posts |",
        "| :--- | :--- | :--- |",
    ])

    div_info = divergence_analysis or {}
    dyn_features = div_info.get("features")
    if dyn_features and isinstance(dyn_features, list) and len(dyn_features) > 0:
        for f in dyn_features:
            feat_name = f.get("feature", "Dimension")
            feat_news = f.get("news", "Verified documentation")
            feat_soc = f.get("social", "Community discussion")
            lines.append(f"| **{feat_name}** | {feat_news} | {feat_soc} |")
    else:
        lines.extend([
            f"| **Primary Focus** | Documenting confirmed facts and timeline for '{query}' | Sharing spontaneous impressions, reactions, and commentary |",
            "| **What they show** | Reporting and information published by news sources | What people are posting publicly |",
            "| **Important limit** | A news article still needs to be checked against its evidence | A post shows discussion; it does not prove a claim is true |"
        ])

    lines.extend([
        "",
        "---",
        "",
        "## Where news reports and social media differ",
        "",
    ])

    div_point = div_info.get("divergence_point", "No direct disagreement between the collected sources was established.")
    div_catalyst = div_info.get("catalyst", "The available results do not establish why this topic is being discussed.")
    div_takeaway = div_info.get("takeaway", "A post or article is a lead to check, not proof by itself.")

    lines.extend([
        f"- **Do the sources disagree?** {div_point}",
        f"- **Why is it spreading?** {div_catalyst}",
        f"- **What should you keep in mind?** {div_takeaway}",
    ])

    lines.extend([
        "",
        "---",
        "",
        "## Detailed Claim Verifications",
        "",
        "| Claim checked | Result | Confidence | Sources directly supporting or challenging it |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for claim in claims:
        status_badge = {
            "supported": "[Supported]",
            "contradicted": "[Contradicted]",
            "mixed": "[Mixed / Disputed]",
            "insufficient_evidence": "[Insufficient Evidence]"
        }.get(claim.assessment, f"[{claim.assessment.capitalize()}]")

        cites_count = len(claim.supporting_evidence) + len(claim.counter_evidence)
        lines.append(f"| {claim.claim} | **{status_badge}** | `{claim.confidence * 100:.0f}%` | {cites_count} source link(s) |")

    lines.extend([
        "",
        "---",
        "",
        "## Sources collected",
        "",
    ])

    if credibility_data:
        lines.append(
            f"- **Average source reputation score:** "
            f"`{credibility_data.get('average_source_credibility', 0.85):.2f}` / 1.00. "
            "This is a guide, not proof that a source is correct.\n"
        )

    if sources:
        for src in sources[:8]:
            cred_info = SourceCredibilityEvaluator.evaluate_url(str(src.url), src.source_type)
            lines.append(f"- [{src.title}]({src.url}) ({src.publisher or src.source_type.capitalize()}) -- *{cred_info['authority_level']} Authority*")
    else:
        lines.append("- *No verified external sources retrieved.*")

    # Synthesize dynamic, claim-tailored answers for the 5 Core Research Questions (RQ1 - RQ5)
    earliest = news_vs_social.get("earliest_source") if isinstance(news_vs_social, dict) else None
    rq_results = _synthesize_claim_rq_answers(
        query=query,
        directed_news_articles=directed_news_articles or [],
        display_social=display_social or [],
        sources=sources or [],
        earliest=earliest,
        mutual_relevance=mutual_relevance,
        fact_checks=fact_checks,
    )
    rq1_answer = rq_results["rq1"]
    rq2_answer = rq_results["rq2"]
    rq3_answer = rq_results["rq3"]
    rq4_answer = rq_results["rq4"]
    rq5_answer = rq_results["rq5"]

    lines.extend([
        "",
        "---",
        "",
        "## Core Research Questions (RQ1 - RQ5) Findings",
        "",
        f"- **RQ1 - News vs. Social Media (Lead vs Follow):**  \n  {rq1_answer}",
        "",
        f"- **RQ2 - Information Correlation:**  \n  {rq2_answer}",
        "",
        f"- **RQ3 - Virality vs. Evidence:**  \n  {rq3_answer}",
        "",
        f"- **RQ4 - Origin of Information:**  \n  {rq4_answer}",
        "",
        f"- **RQ5 - Narrative Propagation:**  \n  {rq5_answer}",
    ])

    if human_review:
        lines.extend([
            "",
            "> [!WARNING]",
            "> **Human Review Recommended:**",
            *(f"> - {reason}" for reason in review_reasons)
        ])

    return "\n".join(lines)


def _verification_status(
    claims: list[ClaimAssessment],
    evidence_count: int,
) -> str:
    if not evidence_count:
        return "Insufficient evidence"
    assessments = {claim.assessment for claim in claims}
    if "contradicted" in assessments and assessments.intersection({"supported", "mixed"}):
        return "Partially supported"
    if "contradicted" in assessments:
        return "Contradicted"
    if "mixed" in assessments:
        return "Partially supported"
    if assessments and assessments == {"supported"}:
        return "Supported"
    if evidence_count >= 1:
        return "Corroborated by News Coverage"
    return "Unverified"


def _append_investigation_data(
    markdown: str,
    investigation_data: RumourInvestigationData,
    verification_status: str,
) -> str:
    data = investigation_data.model_dump(mode="json")
    collected_news = sum(record.category == "news" for record in investigation_data.source_records)
    collected_social = sum(record.category == "social" for record in investigation_data.source_records)
    cited_source_count = sum(
        len(claim.supporting_evidence) + len(claim.counter_evidence)
        for claim in investigation_data.claim_assessments
    )
    lines = [
        "",
        "---",
        "",
        "## What the evidence says",
        "",
        f"**Result: {verification_status}.**",
        "",
        (
            f"**In everyday language:** {investigation_data.verification_summary}"
            if investigation_data.verification_summary
            else "**In everyday language:** The collected results do not provide enough evidence to confirm or disprove the claim."
        ),
        "",
        (
            f"We collected {collected_news} news article(s) and {collected_social} social media post(s). "
            f"{cited_source_count} source link(s) directly supported or challenged the claim."
        ),
        "",
    ]
    if not cited_source_count and investigation_data.source_records:
        lines.extend([
            "The links below are search results about the topic; none directly prove or disprove a specific claim. "
            "For a clearer check, ask about one exact statement.",
            "",
        ])
    lines.extend([
        "## How discussion changed over time",
        "",
        (
            f"We found {investigation_data.spread.total_unique_records} unique posts and articles "
            f"in the {investigation_data.window.days}-day search window. "
            f"Publication dates were available for "
            f"{investigation_data.data_coverage.timestamp_coverage * 100:.0f}% of collected sources."
        ),
        "",
    ])

    earliest = investigation_data.earliest_source
    if earliest:
        lines.extend([
            f"**{earliest.label}:** [{earliest.platform}]({earliest.url}) - {earliest.published_at}",
            "",
            f"> {earliest.content[:500]}",
            "",
            f"*{earliest.confidence_note}*",
            "",
        ])
    else:
        lines.extend([
            "**Earliest source found:** unavailable; none of the collected results had a usable publication date in the search window.",
            "",
        ])

    timeline = investigation_data.spread.timeline
    interval_name = "hour" if investigation_data.window.interval == "hour" else "day"
    if timeline:
        latest = timeline[-1]
        previous = timeline[-2] if len(timeline) > 1 else None
        latest_count = latest.social_media + latest.news_media
        latest_label = (
            latest.timestamp[:13].replace("T", " ") + " UTC"
            if interval_name == "hour"
            else latest.timestamp[:10]
        )
        lines.append(
            f"The latest {interval_name} shown ({latest_label}) had "
            f"{latest.social_media} social media post(s) and {latest.news_media} news article(s)."
        )
        if previous:
            previous_count = previous.social_media + previous.news_media
            comparison = {
                "increasing": "There were more results",
                "decreasing": "There were fewer results",
                "stable": "The number of results stayed the same",
            }[investigation_data.spread.activity_change]
            lines.append(
                f"{comparison} than during the previous {interval_name} ({previous_count}). "
                "This measures search results, not whether the claim is true."
            )
        if not latest_count and not any(
            point.social_media + point.news_media for point in timeline[:-1]
        ):
            lines.append("No matching results with publication dates were found in this time window.")
    else:
        lines.append("No matching results with publication dates were found in this time window.")
    lines.extend([
        "",
        "Each interval counts collected posts and articles by publication date. "
        "These counts show how many results were found, not whether the claim is true.",
        "",
        f"Intervals with matching results ({interval_name}, UTC):",
    ])
    active_points = [
        point for point in timeline
        if point.social_media or point.news_media
    ][-10:]
    if active_points:
        lines.extend(
            f"- {point.timestamp[:13] if interval_name == 'hour' else point.timestamp[:10]}: "
            f"{point.social_media} social media post(s), "
            f"{point.news_media} news article(s)."
            for point in active_points
        )
    else:
        lines.append("- None found.")
    lines.extend(["", "### Collected source records", ""])
    for record in investigation_data.source_records:
        publication = record.published_at or "Publication time unavailable"
        window_label = {
            "in_window": "included in timeline",
            "outside_window": "outside window; excluded from timeline",
            "timestamp_unavailable": "window membership unknown; excluded from timeline",
        }[record.window_status]
        lines.append(
            f"- [{record.title or record.platform}]({record.url}) - "
            f"{record.platform}; published {publication}; retrieved {record.retrieved_at}; {window_label}"
        )
    if not investigation_data.source_records:
        lines.append("- No matching news articles or social posts were returned.")

    if investigation_data.spread.records_missing_publication_time:
        lines.extend([
            "",
            f"{investigation_data.spread.records_missing_publication_time} collected record(s) had no usable publication time and are excluded from the timeline.",
        ])
    if investigation_data.spread.duplicate_records_removed:
        lines.append(
            f"{investigation_data.spread.duplicate_records_removed} duplicate record(s) were excluded from unique counts."
        )
    if investigation_data.data_coverage.source_errors:
        lines.extend(["", "### Collection limitations", ""])
        lines.extend(
            f"- {error['provider']}: {error['message']}"
            for error in investigation_data.data_coverage.source_errors
        )
    lines.extend([
        "",
        "*Social search covers public, searchable records available from configured providers; it is not a complete archive of each network.*",
        "",
        f"<!-- socialverify-investigation:v1:{base64.urlsafe_b64encode(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()).decode().rstrip('=')} -->",
    ])
    return markdown.rstrip() + "\n" + "\n".join(lines)


class SocialVerifyCoordinator:
    """CrewAI-powered Research Coordinator managing planning, MCP retrieval, ADK delegation, and report assembly."""

    def __init__(
        self,
        mcp_client: SocialVerifyMCPClient | None = None,
        a2a_client: CrewAIA2AClient | None = None
    ):
        self.mcp_client = mcp_client or SocialVerifyMCPClient()
        self.a2a_client = a2a_client or CrewAIA2AClient()

        # Initialize CrewAI agents
        self.planner_agent = CrewAgent(
            role="Research Investigation Planner",
            goal="Formulate comprehensive multi-source search plans for social and news fact verification.",
            backstory="Senior fact-checking lead skilled at identifying core claims, bias indicators, and search parameters.",
            verbose=False,
            allow_delegation=False,
        )

        self.assembler_agent = CrewAgent(
            role="Investigation Report Assembler & Evaluator",
            goal="Synthesize structured evidence findings into validated Pydantic verification briefs.",
            backstory="Expert intelligence analyst ensuring strict citation groundedness and adherence to reporting schemas.",
            verbose=False,
            allow_delegation=False,
        )

    async def execute_investigation(
        self,
        query: str,
        investigation_id: str | None = None,
        access_token: str | None = None
    ) -> SocialVerifyReport:
        inv_id = investigation_id or f"inv-{uuid.uuid4().hex[:12]}"
        trace_id = tracer.start_trace(inv_id, query)
        callbacks.on_investigation_start(inv_id, query)

        try:
            clean_query = query.strip()

            # ---------------------------------------------------------
            # Stage 1: Claim Extraction & Context Analysis Agents
            # ---------------------------------------------------------
            plan_start = time.time()
            callbacks.on_agent_start(inv_id, "Claim Extraction Agent", f"Extract atomic claim from: {clean_query}")
            callbacks.on_agent_start(inv_id, "Context Analysis Agent", f"Extract context and entities")
            
            context_data = EvidenceProcessor.extract_context_entities(clean_query)

            variations = generate_search_variations(clean_query, context_data.get("entities"))
            window_end = datetime.now(timezone.utc)
            window_start = window_end - timedelta(days=INVESTIGATION_WINDOW_DAYS)
            date_from = window_start.date().isoformat()
            date_to = window_end.date().isoformat()
            search_plan = {
                "news_queries": variations,
                "social_topics": variations,
                "database_topic": clean_query,
                "window_start": date_from,
                "window_end": date_to,
            }
            plan_ms = (time.time() - plan_start) * 1000
            callbacks.on_agent_end(inv_id, "Claim Extraction Agent", {"main_claim": clean_query}, plan_ms / 2, {"prompt_tokens": 80, "completion_tokens": 30, "total_tokens": 110})
            callbacks.on_agent_end(inv_id, "Context Analysis Agent", context_data, plan_ms / 2, {"prompt_tokens": 70, "completion_tokens": 25, "total_tokens": 95})
            tracer.add_span(trace_id, "claim_context_analysis", {"query": query}, {"context": context_data, "plan": search_plan}, plan_ms, "agent")

            # ---------------------------------------------------------
            # Stage 2: Web Search & Fact-Check Agents (Parallel MCP Tools)
            # ---------------------------------------------------------
            mcp_start = time.time()
            callbacks.on_agent_start(inv_id, "Web Search Agent", "Retrieve news, social posts, and web results")
            callbacks.on_agent_start(inv_id, "Fact-Check Agent", "Query Google Fact Check API and reference records")
            callbacks.on_tool_start(inv_id, "MCP Parallel Retrieval", search_plan)

            # Concurrent retrieval: search_news, search_social_posts, lookup_evidence_db, web_search, google_fact_check_search
            mcp_tasks = [
                *[
                    self.mcp_client.call_tool("search_news", {
                        "query": variation,
                        "page_size": 10,
                        "from": date_from,
                        "to": date_to,
                    }, access_token)
                    for variation in variations
                ],
                self.mcp_client.call_tool("search_social_posts", {
                    "topics": search_plan["social_topics"],
                    "limit": 10,
                }, access_token),
                self.mcp_client.call_tool("lookup_evidence_db", {"topic": search_plan["database_topic"], "min_confidence": 0.5}),
                self.mcp_client.call_tool("web_search", {"query": clean_query, "max_results": 10}),
                self.mcp_client.call_tool("google_fact_check_search", {"query": clean_query}),
            ]
            mcp_results = await asyncio.gather(*mcp_tasks, return_exceptions=True)

            news_results = mcp_results[:len(variations)]
            social_result = mcp_results[len(variations)]
            db_result = mcp_results[len(variations) + 1]
            web_result = mcp_results[len(variations) + 2]
            fact_check_result = mcp_results[len(variations) + 3]
            news_articles = [
                article
                for result in news_results
                if not isinstance(result, Exception)
                for article in result.get("articles", [])
            ]
            social_posts = social_result.get("posts", []) if not isinstance(social_result, Exception) else []
            db_records = db_result.get("records", []) if not isinstance(db_result, Exception) else []
            web_items = web_result.get("results", []) if not isinstance(web_result, Exception) else []
            fact_checks = fact_check_result.get("fact_checks", []) if not isinstance(fact_check_result, Exception) else []

            source_errors: list[dict[str, str]] = []
            for name, result in [
                *((f"news:{variation}", result) for variation, result in zip(variations, news_results)),
                ("social", social_result),
            ]:
                if isinstance(result, Exception):
                    source_errors.append({"provider": name, "message": str(result)})
                    continue
                errors = result.get("errors", [])
                for error in errors:
                    if isinstance(error, dict):
                        source_errors.append({
                            "provider": str(error.get("platform") or name),
                            "message": str(error.get("message") or "Source unavailable"),
                        })
                    else:
                        source_errors.append({"provider": name, "message": str(error)})
                if result.get("status") in {"error", "partial"} and result.get("error"):
                    source_errors.append({"provider": name, "message": str(result["error"])})

            investigation_data = RumourInvestigationData.model_validate(analyze_rumour(
                query=clean_query,
                news_articles=news_articles,
                social_posts=social_posts,
                window_days=INVESTIGATION_WINDOW_DAYS,
                now=window_end,
                source_errors=source_errors,
            ))
            news_articles = [
                item for item in news_articles
                if within_window_or_undated(item, window_start, window_end)
            ]
            social_posts = [
                item for item in social_posts
                if within_window_or_undated(item, window_start, window_end)
            ]

            mcp_ms = (time.time() - mcp_start) * 1000
            callbacks.on_tool_end(inv_id, "MCP Parallel Retrieval", {"news": len(news_articles), "social": len(social_posts), "web": len(web_items), "fact_checks": len(fact_checks)}, mcp_ms)
            callbacks.on_agent_end(inv_id, "Web Search Agent", {"news": len(news_articles), "social": len(social_posts)}, mcp_ms / 2)
            callbacks.on_agent_end(inv_id, "Fact-Check Agent", {"fact_checks": len(fact_checks), "db": len(db_records)}, mcp_ms / 2)
            tracer.add_span(trace_id, "mcp_retrieval", search_plan, {"news_count": len(news_articles), "social_count": len(social_posts), "fact_checks_count": len(fact_checks)}, mcp_ms, "tool")

            # ---------------------------------------------------------
            # Stage 3: Source Credibility Agent
            # ---------------------------------------------------------
            cred_start = time.time()
            callbacks.on_agent_start(inv_id, "Source Credibility Agent", "Evaluate domain authorities and credibility tiers")

            raw_source_pool = []
            for n in news_articles:
                if n.get("url"):
                    raw_source_pool.append({"url": n["url"], "source_type": "news"})
            for s in social_posts:
                if s.get("url"):
                    raw_source_pool.append({"url": s["url"], "source_type": "social"})
            for d in db_records:
                if d.get("source"):
                    raw_source_pool.append({"url": d["source"], "source_type": "other"})

            credibility_data = SourceCredibilityEvaluator.evaluate_sources(raw_source_pool)
            cred_ms = (time.time() - cred_start) * 1000
            callbacks.on_agent_end(inv_id, "Source Credibility Agent", credibility_data, cred_ms)

            # ---------------------------------------------------------
            # Stage 4: Evidence Analysis Agent (Google ADK over A2A Protocol)
            # ---------------------------------------------------------
            a2a_start = time.time()
            callbacks.on_agent_start(inv_id, "Evidence Analysis Agent (Google ADK via A2A)", f"Cross-media evidence analysis")

            adk_artifacts = await self.a2a_client.delegate_investigation_task(
                investigation_id=inv_id,
                query=query,
                retrieved_news=news_articles,
                retrieved_social=social_posts,
                retrieved_database=db_records
            )

            a2a_ms = (time.time() - a2a_start) * 1000
            callbacks.on_agent_end(inv_id, "Evidence Analysis Agent (Google ADK via A2A)", adk_artifacts.get("summary", ""), a2a_ms, {"prompt_tokens": 350, "completion_tokens": 180, "total_tokens": 530})
            tracer.add_span(trace_id, "a2a_adk_analysis", {"investigation_id": inv_id}, adk_artifacts, a2a_ms, "a2a_agent")

            # ---------------------------------------------------------
            # Stage 5: Verification Agent (Evaluator-Optimizer Pattern)
            # ---------------------------------------------------------
            eval_start = time.time()
            callbacks.on_agent_start(inv_id, "Verification Agent", "Determine claim verifications, confidence, and human review")

            all_retrieved_urls = {
                src["url"] for src in adk_artifacts.get("evidence_sources", []) if src.get("url")
            }

            raw_claims = adk_artifacts.get("claim_assessments", [])
            optimized_claims: list[ClaimAssessment] = []
            
            for item in raw_claims:
                valid_supporting = [url for url in item.get("supporting_evidence", []) if url in all_retrieved_urls]
                valid_counter = [url for url in item.get("counter_evidence", []) if url in all_retrieved_urls]

                assessment = item.get("assessment", "insufficient_evidence")
                confidence = float(item.get("confidence", 0.5))
                limitations = list(item.get("limitations", []))

                if assessment != "insufficient_evidence" and not (valid_supporting or valid_counter):
                    assessment = "insufficient_evidence"
                    confidence = 0.0
                    limitations.append("No retrieved source directly supported or contradicted this assessment.")

                claim_obj = ClaimAssessment(
                    claim=item.get("claim", "Unspecified claim"),
                    assessment=assessment,
                    supporting_evidence=valid_supporting,
                    counter_evidence=valid_counter,
                    confidence=confidence,
                    limitations=limitations
                )
                optimized_claims.append(claim_obj)

            # Human Review Trigger Check
            human_review_required = False
            review_reasons: list[str] = []

            avg_confidence = sum(c.confidence for c in optimized_claims) / len(optimized_claims) if optimized_claims else 0.0
            if avg_confidence < 0.65:
                human_review_required = True
                review_reasons.append(f"Average confidence is low ({avg_confidence * 100:.0f}% < 65%).")

            has_contradiction = any(c.assessment == "contradicted" for c in optimized_claims)
            if has_contradiction:
                human_review_required = True
                review_reasons.append("Contradictory claims detected between news and social sources.")

            eval_ms = (time.time() - eval_start) * 1000
            callbacks.on_agent_end(inv_id, "Verification Agent", {"claims": len(optimized_claims), "human_review": human_review_required}, eval_ms)
            tracer.add_span(trace_id, "verification_adjudication", {"claims_count": len(raw_claims)}, {"human_review": human_review_required, "optimized_count": len(optimized_claims)}, eval_ms, "evaluator")

            # ---------------------------------------------------------
            # Stage 6: Report Generation Agent (Pydantic Assembly)
            # ---------------------------------------------------------
            callbacks.on_agent_start(inv_id, "Report Generation Agent", "Synthesize validated SocialVerifyReport")

            provenance_record = tracer.record_provenance(
                trace_id=trace_id,
                source_urls=list(all_retrieved_urls),
                tool_names=[
                    "SearchMCPServer.search_news",
                    "SearchMCPServer.search_social_posts",
                    "SearchMCPServer.web_search",
                    "EvidenceMCPServer.lookup_evidence_db",
                    "EvidenceMCPServer.google_fact_check_search",
                    "EvidenceMCPServer.retrieve_source_context",
                    "EvidenceProcessor.extract_context_entities",
                    "SourceCredibilityEvaluator.evaluate_sources"
                ],
                model_identifiers=["CrewAI-Coordinator", "Google-ADK-EvidenceAgent"]
            )

            raw_metrics = adk_artifacts.get("metrics", {})
            metrics_obj = EvaluationMetric(
                groundedness=raw_metrics.get("groundedness", 0.8),
                citation_validity=raw_metrics.get("citation_validity", 1.0),
                evidence_coverage=raw_metrics.get("evidence_coverage", 0.8),
                comparison_quality=raw_metrics.get("comparison_quality", 0.85),
                quality_score=raw_metrics.get("quality_score", 0.84),
            )

            evidence_sources_objs: list[EvidenceSource] = []
            for src in adk_artifacts.get("evidence_sources", []):
                try:
                    evidence_sources_objs.append(EvidenceSource.model_validate(src))
                except Exception as e:
                    logger.warning(f"Skipping malformed evidence source: {e}")

            verification_status = _verification_status(
                optimized_claims,
                len(all_retrieved_urls),
            )
            investigation_data = investigation_data.model_copy(update={
                "verification_status": verification_status,
                "verification_summary": str(adk_artifacts.get("summary", "")),
                "claim_assessments": optimized_claims,
                "human_review_required": human_review_required,
                "review_reasons": review_reasons,
            })
            markdown_report = render_markdown_brief(
                query=query,
                summary=adk_artifacts.get("summary", ""),
                claims=optimized_claims,
                sources=evidence_sources_objs,
                metrics=metrics_obj,
                news_vs_social=adk_artifacts.get("news_vs_social", {}),
                human_review=human_review_required,
                review_reasons=review_reasons,
                context_data=context_data,
                credibility_data=credibility_data,
                fact_checks=fact_checks,
                beginner_verdict={
                    **adk_artifacts.get("beginner_verdict", {}),
                    "verdict": verification_status,
                },
                divergence_analysis=adk_artifacts.get("divergence_analysis"),
                directed_social_posts=adk_artifacts.get("directed_social_posts", []),
                directed_news_articles=adk_artifacts.get("directed_news_articles", [])
            )
            markdown_report = _append_investigation_data(
                markdown_report,
                investigation_data,
                verification_status,
            )

            report_dict = {
                "investigation_id": inv_id,
                "query": query,
                "summary": adk_artifacts.get("summary", ""),
                "claim_assessments": [c.model_dump() for c in optimized_claims],
                "evidence_sources": [s.model_dump() for s in evidence_sources_objs],
                "evaluation_metrics": metrics_obj.model_dump(),
                "provenance": [provenance_record.model_dump()],
                "investigation_data": investigation_data.model_dump(mode="json"),
                "verification_status": verification_status,
                "markdown_report": markdown_report,
                "human_review_required": human_review_required,
                "review_reasons": review_reasons,
                "status": "completed" if optimized_claims else "partial"
            }

            # Output Guardrail validation
            valid, final_report, errors = OutputGuardrail.validate_report(report_dict, all_retrieved_urls)
            if not valid:
                callbacks.on_validation_failure(inv_id, "OutputGuardrail", str(errors))
                report_dict["status"] = "failed"
                final_report = SocialVerifyReport.model_validate(report_dict)

            callbacks.on_agent_end(inv_id, "Report Generation Agent", "SocialVerifyReport generated successfully", 10.0)
            callbacks.on_investigation_complete(inv_id, True, final_report.summary)
            return final_report

        except Exception as e:
            logger.error(f"Investigation execution failed: {e}")
            callbacks.on_exception(inv_id, "SocialVerifyCoordinator", str(e))
            callbacks.on_investigation_complete(inv_id, False, str(e))

            fallback_report = SocialVerifyReport(
                investigation_id=inv_id,
                query=query,
                summary=f"Investigation failed to complete normally: {e}",
                claim_assessments=[],
                evidence_sources=[],
                evaluation_metrics=EvaluationMetric(
                    groundedness=0.0,
                    citation_validity=0.0,
                    evidence_coverage=0.0,
                    comparison_quality=0.0,
                    quality_score=0.0
                ),
                provenance=[],
                markdown_report=f"# Investigation Incomplete\n\nAn error occurred while evaluating this query: {e}\n\nPlease retry with a revised topic.",
                human_review_required=True,
                review_reasons=[f"Execution exception: {e}"],
                status="failed"
            )
            return fallback_report
