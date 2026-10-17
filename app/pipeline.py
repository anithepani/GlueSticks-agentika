"""The Witness pipeline: intake, ground, decide by rule, verify, recommend.

The pipeline can reach VERIFIED or NEEDS_REVIEW. It can never reach a final denial:
'DENIED' is only reachable through an explicit human decision.
"""

from __future__ import annotations

from app.config import AdapterBundle
from app.models import (
    OUTCOME_ELIGIBLE,
    OUTCOME_NEEDS_REVIEW,
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED,
    Case,
    Recommendation,
)


def build_recommendation(verification, rules) -> Recommendation:
    if verification.status == "ABSTAIN":
        return Recommendation(OUTCOME_NEEDS_REVIEW, list(verification.reasons))
    failed = [rule for rule in rules if rule.status == "FAIL"]
    if failed:
        names = "; ".join(rule.title.lower() for rule in failed)
        return Recommendation(
            OUTCOME_NEEDS_REVIEW,
            [f"Not met: {names}. An officer makes the decision."],
        )
    return Recommendation(
        OUTCOME_ELIGIBLE,
        ["All seven clauses are met and every fact is supported by a quotation from the documents."],
    )


def run_pipeline(packet: dict, bundle: AdapterBundle, extractor=None) -> Case:
    active_extractor = extractor or bundle.extractor
    documents = bundle.reader.read(packet)
    case = Case(
        id=str(packet["id"]),
        applicant_name=str(packet.get("applicant_name", "Unknown")),
        applicant_cnic=str(packet.get("applicant_cnic", "")),
        province=str(packet.get("province", "")),
        documents=documents,
    )
    case.log("intake", f"{len(documents)} document(s) read via '{bundle.reader.name}' reader")

    case.facts = active_extractor.extract(documents, packet)
    grounded = sum(1 for fact in case.facts if fact.citation is not None)
    case.log("extract", f"{len(case.facts)} fact(s) via '{active_extractor.name}' extractor, {grounded} grounded")

    case.rules = bundle.rules.evaluate(case.facts)
    tally = {state: sum(1 for rule in case.rules if rule.status == state) for state in ("PASS", "FAIL", "UNKNOWN")}
    case.log("rules", f"PASS={tally['PASS']} FAIL={tally['FAIL']} UNKNOWN={tally['UNKNOWN']}")

    draft = Recommendation(OUTCOME_NEEDS_REVIEW, [])
    case.verification = bundle.verifier.verify(documents, case.facts, case.rules, draft)
    case.log(
        "verify",
        f"verifier '{bundle.verifier.name}' -> {case.verification.status}"
        + (f" ({len(case.verification.reasons)} reason(s))" if case.verification.reasons else ""),
    )

    case.recommendation = build_recommendation(case.verification, case.rules)
    case.status = STATUS_VERIFIED if case.recommendation.outcome == OUTCOME_ELIGIBLE else STATUS_NEEDS_REVIEW
    case.log("recommend", f"outcome={case.recommendation.outcome}, status={case.status}")
    case.touch()
    return case
