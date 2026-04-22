from __future__ import annotations

from typing import Any

from app.services.llm_client import LLMClient
from app.utils.common import extract_json_object, split_keywords


class OutlineService:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        *,
        category: str,
        keyword: str,
        site_url: str,
        product_urls: list[str],
        provider: str = "openai",
        access_tier: str = "standard",
    ) -> dict[str, Any]:
        normalized_category = (category or "seo").strip().lower()
        normalized_keyword = keyword.strip()
        normalized_site_url = site_url.strip()
        normalized_product_urls = [item.strip() for item in product_urls if item.strip()]

        if not normalized_keyword:
            raise ValueError("keyword is required")
        if not normalized_site_url:
            raise ValueError("site_url is required")

        if self.llm_client.enabled(provider):
            prompt = self._build_prompt(
                category=normalized_category,
                keyword=normalized_keyword,
                site_url=normalized_site_url,
                product_urls=normalized_product_urls,
            )
            raw = self.llm_client.complete(
                prompt,
                expect_json=True,
                access_tier=access_tier,
                provider=provider,
            )
            payload = extract_json_object(raw)
            return self._normalize_payload(
                payload,
                category=normalized_category,
                keyword=normalized_keyword,
                site_url=normalized_site_url,
                product_urls=normalized_product_urls,
                generation_mode="llm",
            )

        return self._mock_payload(
            category=normalized_category,
            keyword=normalized_keyword,
            site_url=normalized_site_url,
            product_urls=normalized_product_urls,
        )

    def _build_prompt(
        self,
        *,
        category: str,
        keyword: str,
        site_url: str,
        product_urls: list[str],
    ) -> str:
        mode_name = "GEO" if category == "geo" else "SEO"
        language_hint = (
            "Write in the same language as the keyword unless the keyword language is unclear."
        )
        product_url_lines = "\n".join(f"- {item}" for item in product_urls) or "- None provided"
        mode_requirements = (
            "- Optimize for answer-first extraction, AI readability, clear entities, FAQ, citations, and trust signals.\n"
            "- Make the outline directly usable for a GEO article.\n"
            "- The opening should answer the query quickly.\n"
            "- Include sections for sources/verification and FAQ."
            if category == "geo"
            else
            "- Optimize for search intent alignment, H1/H2/H3 structure, natural keyword coverage, readability, and internal linking.\n"
            "- Make the outline directly usable for an SEO article.\n"
            "- Include a strong intro, clear section hierarchy, conclusion, and FAQ."
        )
        return f"""
You are a senior {mode_name} content strategist.
Create a clean article outline plan for the keyword below.

Keyword:
{keyword}

Official website:
{site_url}

Product URLs:
{product_url_lines}

Requirements:
{mode_requirements}
- {language_hint}
- Do not invent product URLs or internal links. Only recommend the provided site URL and provided product URLs.
- The output should be ready for a content writer to use immediately.
- Keep the outline practical, specific, and commercially relevant without sounding like an ad.

Return strict JSON only:
{{
  "title": "",
  "outline_markdown": "",
  "writing_suggestions": ["", "", ""],
  "recommended_internal_links": [
    {{
      "label": "",
      "url": "",
      "reason": ""
    }}
  ]
}}
""".strip()

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        *,
        category: str,
        keyword: str,
        site_url: str,
        product_urls: list[str],
        generation_mode: str,
    ) -> dict[str, Any]:
        writing_suggestions = [
            str(item).strip()
            for item in payload.get("writing_suggestions") or []
            if str(item).strip()
        ]
        if not writing_suggestions:
            writing_suggestions = self._default_writing_suggestions(category, keyword)

        recommended_internal_links = []
        for item in payload.get("recommended_internal_links") or []:
            url = str(item.get("url") or "").strip()
            label = str(item.get("label") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not url:
                continue
            if url != site_url and url not in product_urls:
                continue
            recommended_internal_links.append(
                {
                    "label": label or url,
                    "url": url,
                    "reason": reason or "Recommended because it matches the official site or supplied product page.",
                }
            )

        if not recommended_internal_links:
            recommended_internal_links = self._default_internal_links(site_url, product_urls)

        outline_markdown = str(payload.get("outline_markdown") or "").strip()
        if not outline_markdown:
            outline_markdown = self._default_outline(category, keyword, product_urls)

        return {
            "category": category,
            "keyword": keyword,
            "site_url": site_url,
            "product_urls": product_urls,
            "title": str(payload.get("title") or keyword).strip() or keyword,
            "outline_markdown": outline_markdown,
            "writing_suggestions": writing_suggestions,
            "recommended_internal_links": recommended_internal_links,
            "generation_mode": generation_mode,
        }

    def _mock_payload(
        self,
        *,
        category: str,
        keyword: str,
        site_url: str,
        product_urls: list[str],
    ) -> dict[str, Any]:
        return {
            "category": category,
            "keyword": keyword,
            "site_url": site_url,
            "product_urls": product_urls,
            "title": keyword,
            "outline_markdown": self._default_outline(category, keyword, product_urls),
            "writing_suggestions": self._default_writing_suggestions(category, keyword),
            "recommended_internal_links": self._default_internal_links(site_url, product_urls),
            "generation_mode": "mock",
        }

    def _default_outline(self, category: str, keyword: str, product_urls: list[str]) -> str:
        answer_label = "Quick Answer" if category == "geo" else "Intro"
        source_label = "Bronnen en verificatie" if category == "geo" else "Aanbevolen interne links"
        product_line = (
            f"- Link vroeg in het artikel naar: {product_urls[0]}"
            if product_urls
            else "- Voeg vroeg in het artikel een relevante productlink toe."
        )
        return f"""# {keyword}

## {answer_label}
- Beantwoord de hoofdvraag in 2-3 zinnen.
- Leg kort uit voor wie dit onderwerp relevant is.
{product_line}

## Wat betekent deze zoekvraag precies?
- Definieer de belangrijkste term of het besliskader.
- Leg uit welke factoren het antwoord beïnvloeden.

## Belangrijkste vergelijking of besliscriteria
- Benoem 3-5 hoofdcriteria.
- Houd deze sectie scanbaar en feitelijk.

## Welke oplossing past het best bij welke situatie?
- Verdeel dit in duidelijke subsecties per gebruikssituatie.
- Koppel waar relevant naar het officiële product.

## Aandachtspunten vóór je kiest
- Benoem grenzen, randvoorwaarden of compatibiliteit.
- Voeg nuance toe zodat de tekst geloofwaardig blijft.

## Conclusie
- Vat het antwoord kort samen.
- Sluit af met een natuurlijke CTA.

## FAQ
### Veelgestelde vraag 1
### Veelgestelde vraag 2
### Veelgestelde vraag 3

## {source_label}
- Gebruik alleen officiële website- en productlinks.
- Noem alleen verifieerbare claims en specificaties.
""".strip()

    def _default_writing_suggestions(self, category: str, keyword: str) -> list[str]:
        suggestions = [
            f"Open met een direct antwoord op '{keyword}' in de eerste 100-150 woorden.",
            "Gebruik korte, scanbare H2-secties en vermijd generieke tussenkoppen.",
            "Werk met concrete criteria, zodat de lezer en AI-systemen het antwoord makkelijk kunnen samenvatten.",
        ]
        if category == "geo":
            suggestions.extend(
                [
                    "Voeg een duidelijke bronnen- of verificatiesectie toe voor claims en productspecificaties.",
                    "Maak de FAQ anders dan de hoofdtekst en laat elk antwoord een echte vervolgquery afdekken.",
                ]
            )
        else:
            suggestions.extend(
                [
                    "Verwerk het hoofdkeyword natuurlijk in H1, intro, minstens één H2 en de conclusie.",
                    "Plaats het belangrijkste interne productlink vroeg in het artikel voor een sterkere SEO-structuur.",
                ]
            )
        return suggestions

    def _default_internal_links(self, site_url: str, product_urls: list[str]) -> list[dict[str, str]]:
        links = [{"label": "Officiële website", "url": site_url, "reason": "Gebruik als merk- of categorieverwijzing."}]
        for index, url in enumerate(split_keywords(product_urls), start=1):
            links.append(
                {
                    "label": f"Productpagina {index}",
                    "url": url,
                    "reason": "Gebruik als vroege productlink of ondersteunende interne verwijzing.",
                }
            )
        return links
