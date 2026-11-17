import time
import uuid
from typing import Any
from config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
from schemas.report import ProvenanceRecord
from utils.logger import logger

try:
    from langfuse import Langfuse
    _HAS_LANGFUSE = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
    if _HAS_LANGFUSE:
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_BASE_URL
        )
    else:
        _langfuse_client = None
except Exception as e:
    logger.info(f"Langfuse offline or not configured: {e}")
    _langfuse_client = None


class DistributedTracer:
    """Manages correlated distributed tracing and provenance across agents and tools."""

    def __init__(self):
        self._traces: dict[str, dict[str, Any]] = {}

    def start_trace(self, investigation_id: str, query: str) -> str:
        trace_id = investigation_id or str(uuid.uuid4())
        self._traces[trace_id] = {
            "trace_id": trace_id,
            "query": query,
            "start_time": time.time(),
            "spans": [],
            "provenance": []
        }
        if _langfuse_client:
            try:
                _langfuse_client.trace(id=trace_id, name="SocialVerify Investigation", input={"query": query})
            except Exception as e:
                logger.warning(f"Langfuse trace creation failed: {e}")
        return trace_id

    def add_span(
        self,
        trace_id: str,
        name: str,
        input_data: Any,
        output_data: Any,
        duration_ms: float,
        span_type: str = "agent"
    ) -> None:
        span_record = {
            "name": name,
            "type": span_type,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
            "input_preview": str(input_data)[:200],
            "output_preview": str(output_data)[:200]
        }
        if trace_id in self._traces:
            self._traces[trace_id]["spans"].append(span_record)

        if _langfuse_client:
            try:
                _langfuse_client.span(
                    trace_id=trace_id,
                    name=name,
                    input=input_data,
                    output=output_data,
                    metadata={"duration_ms": duration_ms, "type": span_type}
                )
            except Exception as e:
                logger.debug(f"Langfuse span record warning: {e}")

    def record_provenance(
        self,
        trace_id: str,
        source_urls: list[str],
        tool_names: list[str],
        model_identifiers: list[str]
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            source_urls=source_urls,
            tool_names=tool_names,
            model_identifiers=model_identifiers,
            trace_id=trace_id
        )
        if trace_id in self._traces:
            self._traces[trace_id]["provenance"].append(record.model_dump())
        return record

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        return self._traces.get(trace_id)


# Global tracer instance
tracer = DistributedTracer()
