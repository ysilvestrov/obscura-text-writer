from .models import EvaluationCase, EvidenceCheck, JudgeReport


def check_evidence(case: EvaluationCase, report: JudgeReport, min_quote_chars: int = 12) -> EvidenceCheck:
    documents = {doc.id: doc for doc in case.documents}
    result = EvidenceCheck()
    cross_reference = {"plan_fidelity", "continuity", "editorial_preservation"}
    for finding in report.findings:
        valid = True
        anchors = set()
        for citation in finding.citations:
            doc = documents.get(citation.document_id)
            if (doc is None or citation.document_version != doc.version
                    or citation.quote not in doc.text
                    or len("".join(citation.quote.split())) < min_quote_chars):
                valid = False
            if doc is not None and citation.quote in doc.text:
                start = doc.text.find(citation.quote)
                anchors.add((citation.document_id, start, start + len(citation.quote)))
        independent_pair = any(a[0] != b[0] or a[2] <= b[1] or b[2] <= a[1]
            for a in anchors for b in anchors if a != b)
        if finding.criterion_id in cross_reference and not independent_pair:
            valid = False
        if valid:
            result.confirmed.append(finding)
        else:
            result.unconfirmed.append(finding)
            result.reasons.append(f"unconfirmed_evidence:{finding.criterion_id}")
    return result
