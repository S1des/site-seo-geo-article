from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


H1_RE = re.compile(r"<h1\b", re.IGNORECASE)
P_RE = re.compile(r"<p>(.*?)</p>", re.IGNORECASE | re.DOTALL)
FAQ_RE = re.compile(r"<h[23]>\s*FAQ\s*</h[23]>", re.IGNORECASE)
REFERENCES_RE = re.compile(r"<h[23]>\s*References?(?:\s+and\s+Evidence\s+to\s+Verify)?\s*</h[23]>", re.IGNORECASE)


class ArticleValidator:
    def apply(
        self,
        article: dict[str, Any],
        *,
        category: str,
        keyword: str,
        rule_context: dict[str, Any],
    ) -> dict[str, Any]:
        working = deepcopy(article)
        html = str(working.get("raw_html") or working.get("html") or "")
        fixes: list[str] = []
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []

        html, replacement_hits = self._replace_banned_terms(html, rule_context.get("banned_terms", {}))
        if replacement_hits:
            fixes.extend(replacement_hits)

        working["title"], title_trimmed = self._trim_text(
            str(working.get("title") or keyword),
            int(rule_context.get("meta_title_limit", 60)),
        )
        if title_trimmed:
            fixes.append("trimmed article title to the configured title limit")

        working["meta_title"], meta_title_trimmed = self._trim_text(
            str(working.get("meta_title") or working["title"]),
            int(rule_context.get("meta_title_limit", 60)),
        )
        if meta_title_trimmed:
            fixes.append("trimmed meta title to the configured title limit")

        working["meta_description"], meta_description_trimmed = self._trim_text(
            str(working.get("meta_description") or ""),
            int(rule_context.get("meta_description_limit", 160)),
        )
        if meta_description_trimmed:
            fixes.append("trimmed meta description to the configured description limit")

        html, quick_answer_added = self._ensure_quick_answer(
            html,
            keyword=keyword,
            summary=str((working.get("strategy") or {}).get("answer_first_summary") or ""),
            enabled=category == "geo",
        )
        if quick_answer_added:
            fixes.append("added a quick-answer block for GEO extraction")

        html, link_added = self._ensure_early_link(
            html,
            shopify_url=str(rule_context.get("shopify_url") or ""),
            requires_shopify_link=bool(rule_context.get("requires_shopify_link", False)),
        )
        if link_added:
            fixes.append("added an early internal product link")

        html, disclaimer_added = self._ensure_disclaimer(
            html,
            disclaimer=str(rule_context.get("required_disclaimer") or ""),
        )
        if disclaimer_added:
            fixes.append("added the required disclaimer block")

        html, references_added = self._ensure_references(
            html,
            enabled=category == "geo",
            links=rule_context.get("resolved_internal_links") or [],
            notes=rule_context.get("required_notes") or [],
        )
        if references_added:
            fixes.append("added a references and verification section")

        h1_count = len(H1_RE.findall(html))
        if h1_count != 1:
            warnings.append(f"expected exactly one H1, found {h1_count}")
        checks.append({"name": "single_h1", "passed": h1_count == 1, "detail": f"H1 count: {h1_count}"})

        disclaimer_required = bool(rule_context.get("required_disclaimer"))
        disclaimer_present = not disclaimer_required or "Disclaimer" in html
        checks.append(
            {
                "name": "required_disclaimer",
                "passed": disclaimer_present,
                "detail": "present" if disclaimer_present else "missing",
            }
        )
        if disclaimer_required and not disclaimer_present:
            warnings.append("required disclaimer is still missing after remediation")

        if category == "geo":
            quick_answer_present = "Quick Answer" in html
            references_present = bool(REFERENCES_RE.search(html))
            checks.append(
                {
                    "name": "geo_structure",
                    "passed": quick_answer_present and references_present,
                    "detail": f"quick_answer={quick_answer_present}, references={references_present}",
                }
            )
            if not quick_answer_present or not references_present:
                warnings.append("GEO structure is missing either Quick Answer or References")

        early_link_required = bool(rule_context.get("requires_shopify_link") and rule_context.get("shopify_url"))
        early_link_present = not early_link_required or self._has_early_link(
            html,
            url=str(rule_context.get("shopify_url") or ""),
        )
        checks.append(
            {
                "name": "early_internal_link",
                "passed": early_link_present,
                "detail": "present" if early_link_present else "missing",
            }
        )
        if not early_link_present:
            warnings.append("required early internal link is missing")

        score = max(0, 100 - len(warnings) * 15)
        working["raw_html"] = html.strip()
        working["html"] = working["raw_html"]
        working["audit"] = {
            "score": score,
            "warnings": warnings,
            "applied_fixes": fixes,
            "checks": checks,
            "applied_rule_ids": rule_context.get("applied_rule_ids", []),
            "resolved_internal_links": rule_context.get("resolved_internal_links", []),
            "context": rule_context.get("context", {}),
        }
        return working

    def _replace_banned_terms(self, html: str, banned_terms: dict[str, str]) -> tuple[str, list[str]]:
        fixes: list[str] = []
        updated = html
        for source, replacement in banned_terms.items():
            pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
            if not pattern.search(updated):
                continue
            updated = pattern.sub(replacement, updated)
            fixes.append(f"replaced banned term '{source}'")
        return updated, fixes

    def _trim_text(self, value: str, limit: int) -> tuple[str, bool]:
        text = value.strip()
        if len(text) <= limit:
            return text, False
        return text[: limit - 3].rstrip() + "...", True

    def _ensure_quick_answer(self, html: str, *, keyword: str, summary: str, enabled: bool) -> tuple[str, bool]:
        if not enabled:
            return html, False
        if "Quick Answer" in html:
            return html, False
        first_paragraph = self._first_paragraph_text(html)
        if keyword.lower() in first_paragraph.lower():
            return f"{self._quick_answer_block(keyword, summary)}\n{html}", True
        return f"{self._quick_answer_block(keyword, summary)}\n{html}", True

    def _ensure_early_link(self, html: str, *, shopify_url: str, requires_shopify_link: bool) -> tuple[str, bool]:
        if not requires_shopify_link or not shopify_url:
            return html, False
        if self._has_early_link(html, shopify_url):
            return html, False
        paragraphs = list(P_RE.finditer(html))
        if not paragraphs:
            return html, False
        first = paragraphs[0]
        snippet = (
            f'{first.group(0)}<p>For product-specific details, see the official <a href="{shopify_url}">product page</a>.</p>'
        )
        return html[: first.start()] + snippet + html[first.end() :], True

    def _ensure_disclaimer(self, html: str, *, disclaimer: str) -> tuple[str, bool]:
        if not disclaimer:
            return html, False
        if disclaimer in html or "Disclaimer" in html:
            return html, False
        block = f"<h2>Disclaimer</h2><p>{disclaimer}</p>"
        faq_match = FAQ_RE.search(html)
        if faq_match:
            return html[: faq_match.start()] + block + html[faq_match.start() :], True
        return f"{html}\n{block}", True

    def _ensure_references(
        self,
        html: str,
        *,
        enabled: bool,
        links: list[dict[str, str]],
        notes: list[str],
    ) -> tuple[str, bool]:
        if not enabled:
            return html, False
        if REFERENCES_RE.search(html):
            return html, False
        items = [
            "<li>Verify all product claims against official specifications before publishing.</li>",
            "<li>Support policy or utility claims with official program or government sources.</li>",
        ]
        for link in links[:3]:
            items.append(f'<li>Internal reference: <a href="{link["url"]}">{link["label"]}</a>.</li>')
        for note in notes[:2]:
            items.append(f"<li>{note}</li>")
        block = "<h2>References and Evidence to Verify</h2><ul>" + "".join(items) + "</ul>"
        faq_match = FAQ_RE.search(html)
        if faq_match:
            return html[: faq_match.start()] + block + html[faq_match.start() :], True
        return f"{html}\n{block}", True

    def _has_early_link(self, html: str, url: str) -> bool:
        paragraphs = list(P_RE.finditer(html))[:2]
        return any(url in match.group(0) for match in paragraphs)

    def _quick_answer_block(self, keyword: str, summary: str) -> str:
        text = summary.strip() or (
            f"The short answer is that {keyword} content works best when it provides a direct recommendation first, "
            "then backs it up with verifiable product details, links, and source guidance."
        )
        return f"<h2>Quick Answer</h2><p>{text}</p>"

    def _first_paragraph_text(self, html: str) -> str:
        match = P_RE.search(html)
        return re.sub(r"<[^>]+>", " ", match.group(1)).strip() if match else ""
