from rekanvault.contracts.documents import NormalizedDocument


class ReconciliationEngine:
    def reconcile(self, expected: list[NormalizedDocument], actual: list[NormalizedDocument]) -> dict[str, list[str]]:
        expected_ids: set[str] = {doc.document_id for doc in expected}
        actual_ids: set[str] = {doc.document_id for doc in actual}

        missing_ids = list(expected_ids - actual_ids)
        new_ids = list(actual_ids - expected_ids)
        reconciled_ids = list(expected_ids & actual_ids)

        return {
            "reconciled": reconciled_ids,
            "missing": missing_ids,
            "new": new_ids,
        }
