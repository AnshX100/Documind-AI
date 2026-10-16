"""Answer Generation Service for constructing deterministic prose answers from verified facts."""

from typing import Dict, Any


class AnswerGenerationService:
    """Service to convert structured financial facts into deterministic prose answers."""

    def generate_answer(self, evidence: Dict[str, Any]) -> str:
        """Generate human-readable answer string based on evidence facts and status.

        Args:
            evidence (Dict[str, Any]): Structured evidence dictionary.

        Returns:
            str: Deterministic prose answer string.
        """
        status = evidence.get("status", "error")
        intent = evidence.get("intent", "UNKNOWN")
        facts = evidence.get("facts", {})
        warnings = evidence.get("warnings", [])

        if status == "insufficient_data":
            if warnings:
                return f"I couldn't find enough analyzed financial data to calculate this. {warnings[0]}"
            return "I couldn't find enough analyzed financial data in your workspace to calculate this reliably."

        if status == "not_found":
            if warnings:
                return f"No matching document was found in your workspace. {warnings[0]}"
            return "No matching document was found in your workspace or access is unauthorized."

        if status == "error":
            return "An internal error occurred while retrieving verified financial evidence."

        if intent == "TOTAL_SPENDING":
            return (
                f"Your total spending is ₹{facts.get('total_spending', 0.0):,.2f} "
                f"across {facts.get('analyzed_documents', 0)} analyzed documents."
            )

        if intent == "CATEGORY_SPENDING":
            if "requested_category" in facts:
                return (
                    f"You spent ₹{facts.get('total_amount', 0.0):,.2f} on {facts.get('requested_category')} "
                    f"across {facts.get('document_count', 0)} analyzed documents "
                    f"({facts.get('percentage', 0.0)}% of your total spending)."
                )
            cats = facts.get("categories", [])
            if not cats:
                return "No category spending data is available."
            top_cats = ", ".join([f"{c['category_name']}: ₹{c['total_amount']:,.2f} ({c['percentage']}%)" for c in cats[:4]])
            return f"Category spending breakdown: {top_cats}."

        if intent == "TOP_VENDOR":
            return (
                f"Your top vendor by spending is {facts.get('vendor_name', 'Unknown')} "
                f"with a total expenditure of ₹{facts.get('total_spending', 0.0):,.2f} "
                f"across {facts.get('document_count', 0)} documents "
                f"({facts.get('spending_percentage', 0.0)}% of total spending)."
            )

        if intent == "TOP_VENDORS":
            vendors = facts.get("vendors", [])
            if not vendors:
                return "No vendor spending data is available."
            v_list = "; ".join([f"{v['vendor_name']}: ₹{v['total_spending']:,.2f} ({v['document_count']} docs)" for v in vendors[:5]])
            return f"Your top vendors by spending are: {v_list}."

        if intent == "SPENDING_TREND":
            trends = facts.get("trends", [])
            if not trends:
                return "No monthly spending trend data is available."
            last_few = ", ".join([f"{t['month_label']}: ₹{t['total_amount']:,.2f}" for t in trends[-4:]])
            return f"Recent monthly spending trend: {last_few}."

        if intent == "MONTH_COMPARISON":
            curr = facts.get("current_period", {})
            prev = facts.get("previous_period", {})
            diff = facts.get("difference", 0.0)
            pct = facts.get("percentage_change", 0.0)
            direction = "increased" if diff >= 0 else "decreased"
            return (
                f"Comparing {curr.get('label')} (₹{curr.get('amount', 0.0):,.2f}) with {prev.get('label')} (₹{prev.get('amount', 0.0):,.2f}): "
                f"spending {direction} by ₹{abs(diff):,.2f} ({pct:+.2f}%)."
            )

        if intent == "ANOMALIES":
            count = facts.get("anomalies_count", 0)
            if count == 0:
                return "No active financial anomalies or risk signals were detected in your workspace."
            anom_list = facts.get("anomalies", [])
            reasons = "; ".join([f"{a['title']}: {a['desc']}" for a in anom_list[:3]])
            return f"Detected {count} active financial anomaly/risk signal(s) in your workspace: {reasons}."

        if intent == "DUPLICATE_DOCUMENTS":
            count = facts.get("duplicate_count", 0)
            if count == 0:
                return "No duplicate documents or duplicate invoices were detected in your workspace."
            dups = facts.get("duplicates", [])
            reasons = "; ".join([f"{d['title']}: {d['desc']}" for d in dups[:3]])
            return f"Detected {count} duplicate invoice/transaction risk signal(s): {reasons}."

        if intent == "DOCUMENT_RISK":
            filename = facts.get("original_filename", "Document")
            count = facts.get("anomalies_count", 0)
            if count == 0:
                return f"No recorded risk signal was found for document '{filename}'."
            anom_titles = ", ".join([a['title'] for a in facts.get("anomalies", [])])
            return f"Document '{filename}' was flagged with {count} risk signal(s): {anom_titles}."

        if intent == "DOCUMENT_LOOKUP":
            filename = facts.get("original_filename", "Document")
            inv_num = facts.get("invoice_number") or facts.get("document_id")
            vendor = facts.get("vendor_name") or "Unknown"
            amt = facts.get("total_amount", 0.0)
            status_text = facts.get("status", "processed")
            return f"Document '{filename}' (Invoice #{inv_num}): Vendor: {vendor}, Total: ₹{amt:,.2f}, Status: {status_text}."

        if intent == "DUE_DILIGENCE":
            score = facts.get("overall_score", 100)
            profile = facts.get("risk_profile", "Low risk profile")
            comp = facts.get("completeness_score", 100)
            cons = facts.get("consistency_score", 100)
            conc = facts.get("concentration_rating", "Low")
            return (
                f"Your workspace financial audit health index score is {score}/100 ({profile}). "
                f"Document completeness is {comp}%, arithmetic consistency is {cons}%, and supplier concentration is {conc}."
            )

        if intent == "TAX_SUMMARY":
            tax = facts.get("total_tax", 0.0)
            subtotal = facts.get("total_subtotal", 0.0)
            rate = facts.get("effective_tax_rate", 0.0)
            docs = facts.get("analyzed_documents", 0)
            return f"Your recorded tax total is ₹{tax:,.2f} on a subtotal of ₹{subtotal:,.2f} across {docs} analyzed documents (Effective tax rate: {rate}%)."

        if intent == "PAYMENT_METHOD_SUMMARY":
            methods = facts.get("payment_methods", [])
            if not methods:
                return "No payment method distribution data is available."
            m_str = ", ".join([f"{m['method']}: ₹{m['total_amount']:,.2f} ({m['percentage']}%)" for m in methods])
            return f"Payment method distribution: {m_str}."

        if intent == "GENERAL_FINANCIAL_SUMMARY":
            ov = facts.get("overview", {})
            v = facts.get("top_vendor")
            top_v_str = f" Top vendor: {v['vendor_name']} (₹{v['total_spending']:,.2f})." if v else ""
            score = facts.get("audit_score", 100)
            profile = facts.get("risk_profile", "Low risk profile")
            return (
                f"Financial Summary: Total spending is ₹{ov.get('total_spending', 0.0):,.2f} "
                f"across {ov.get('analyzed_documents', 0)} analyzed documents.{top_v_str} "
                f"Audit health score is {score}/100 ({profile})."
            )

        return (
            "I couldn't understand that financial question. "
            "You can ask about total spending, category spending, top vendors, spending trends, "
            "month-over-month comparisons, financial anomalies, invoice risk explanations, due diligence scores, or tax totals."
        )
