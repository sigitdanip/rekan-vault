from rekanvault.contracts.documents import NormalizedDocument
from rekanvault.contracts.events import EventType, LifecycleEvent
from rekanvault.contracts.identifiers import generate_id


class IngestionLifecycleManager:
    def __init__(self) -> None:
        self.processed_documents: dict[str, NormalizedDocument] = {}

    def process_document(self, doc: NormalizedDocument) -> list[LifecycleEvent]:
        events: list[LifecycleEvent] = []
        is_new = doc.document_id not in self.processed_documents
        self.processed_documents[doc.document_id] = doc

        event_type = EventType.DOCUMENT_CREATED if is_new else EventType.DOCUMENT_UPDATED
        events.append(
            LifecycleEvent(
                event_id=generate_id("evt"),
                event_type=event_type,
                workspace_id=doc.workspace_id,
                aggregate_id=doc.document_id,
                payload={"title": doc.title, "provider": doc.provider.value, "version_id": doc.active_version_id},
            )
        )
        return events
