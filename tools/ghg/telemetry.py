"""Optional OpenTelemetry helper for ghg.

Telemetry is off by default. It is enabled only when the env var
``GHG_OTEL_FILE`` names a JSONL output file AND the OpenTelemetry
SDK is importable. When disabled or when the SDK is absent, every
operation is a pure no-op: no file is created, no exception is
raised, and actor callables are never invoked.

Spans carry ONLY allowlisted attributes (see ``ALLOWED_ATTRIBUTES``):
never argv, never resolved env values, never tokens. Every
attribute -- initial, explicit, and finish-time -- passes through
``filter_attributes`` via the handle's ``set_attribute`` method,
which is the one and only attribute-setting path.

The SDK is imported lazily and every SDK interaction is guarded:
any SDK-side failure degrades silently to the no-op path, so
telemetry can never break the caller.
"""

import json
import os
import threading
import time
from pathlib import Path

ENV_VAR = "GHG_OTEL_FILE"

ALLOWED_ATTRIBUTES = frozenset(
    {"operation", "actor", "exit_code", "duration_ms", "gate_verdict"}
)

_SCALAR_TYPES = (str, int, float, bool)

__all__ = [
    "ENV_VAR",
    "ALLOWED_ATTRIBUTES",
    "filter_attributes",
    "sdk_available",
    "enabled",
    "operation",
]


def filter_attributes(attrs):
    """Return only allowlisted keys whose values are scalars.

    This function is the single attribute filter for the whole
    module. Non-dict input yields an empty dict.
    """
    if not isinstance(attrs, dict):
        return {}
    out = {}
    for key, value in attrs.items():
        if key not in ALLOWED_ATTRIBUTES:
            continue
        if not isinstance(value, _SCALAR_TYPES):
            continue
        out[key] = value
    return out


def sdk_available():
    """True iff opentelemetry.sdk is importable; never raises."""
    try:
        import importlib

        importlib.import_module("opentelemetry.sdk")
        # Also require the trace submodule used by the provider
        # setup; an api-only install must report unavailable.
        importlib.import_module("opentelemetry.sdk.trace")
        return True
    except Exception:
        return False


def enabled():
    """True iff the env var is set (non-empty) and the SDK is present."""
    try:
        value = os.environ.get(ENV_VAR)
        if not value:
            return False
        return bool(sdk_available())
    except Exception:
        return False


# ------------------------------------------------------- provider cache

_providers_lock = threading.Lock()
# Maps output-file path string -> tracer (provider kept alive by the
# tracer / processor / exporter references reachable from it, and
# also stored explicitly alongside).
_providers = {}


def _get_tracer(file_path):
    """Return a tracer for ``file_path``, or None on any failure.

    Provider setup is lazy and cached per process (keyed by the
    output file, so distinct files in one process do not collide).
    """
    key = str(file_path)
    with _providers_lock:
        cached = _providers.get(key)
        if cached is not None:
            return cached[1]
    try:
        import importlib

        trace_sdk = importlib.import_module("opentelemetry.sdk.trace")
        export_mod = importlib.import_module(
            "opentelemetry.sdk.trace.export")
        resources_mod = importlib.import_module(
            "opentelemetry.sdk.resources")

        TracerProvider = trace_sdk.TracerProvider
        SimpleSpanProcessor = export_mod.SimpleSpanProcessor
        SpanExporter = export_mod.SpanExporter
        SpanExportResult = export_mod.SpanExportResult
        Resource = resources_mod.Resource

        class _JsonlExporter(SpanExporter):
            """Append one JSON object per finished span; never raise."""

            def __init__(self, path):
                self._path = path

            def export(self, spans):
                try:
                    with open(self._path, "a", encoding="utf-8") as fh:
                        for span in spans:
                            try:
                                fh.write(
                                    json.dumps(self._record(span)) + "\n")
                            except Exception:
                                continue
                except Exception:
                    return SpanExportResult.FAILURE
                return SpanExportResult.SUCCESS

            def shutdown(self):
                return None

            def force_flush(self, timeout_millis=30000):
                return True

            @staticmethod
            def _record(span):
                # trace / span ids
                trace_id_hex = "0" * 32
                span_id_hex = "0" * 16
                try:
                    ctx = None
                    get_ctx = getattr(span, "get_span_context", None)
                    if callable(get_ctx):
                        ctx = get_ctx()
                    if ctx is None:
                        ctx = getattr(span, "context", None)
                        if callable(ctx):
                            ctx = ctx()
                    if ctx is not None:
                        if getattr(ctx, "trace_id", 0):
                            trace_id_hex = format(ctx.trace_id, "032x")
                        if getattr(ctx, "span_id", 0):
                            span_id_hex = format(ctx.span_id, "016x")
                except Exception:
                    pass
                parent_hex = None
                try:
                    parent = getattr(span, "parent", None)
                    if parent is not None:
                        pid = getattr(parent, "span_id", 0)
                        if pid:
                            parent_hex = format(pid, "016x")
                except Exception:
                    parent_hex = None
                status_str = "UNSET"
                try:
                    status = getattr(span, "status", None)
                    if status is not None:
                        code = getattr(status, "status_code", None)
                        if code is not None:
                            status_str = getattr(code, "name", None) or str(code)
                        else:
                            status_str = str(status)
                except Exception:
                    status_str = "UNSET"
                try:
                    attrs = dict(span.attributes) if getattr(
                        span, "attributes", None) else {}
                except Exception:
                    attrs = {}
                # Attributes reaching the exporter have already
                # passed through filter_attributes via the handle's
                # set_attribute (the single filtering path); the
                # exporter deliberately does not re-filter, so that
                # path is the sole guard against leaks.
                return {
                    "name": getattr(span, "name", ""),
                    "trace_id": trace_id_hex,
                    "span_id": span_id_hex,
                    "parent_span_id": parent_hex,
                    "start_time": int(getattr(span, "start_time", 0) or 0),
                    "end_time": int(getattr(span, "end_time", 0) or 0),
                    "status": status_str,
                    "attributes": attrs,
                }

        try:
            resource = Resource.create({"service.name": "ghg"})
        except Exception:
            try:
                resource = Resource(attributes={"service.name": "ghg"})
            except Exception:
                resource = None
        if resource is not None:
            provider = TracerProvider(resource=resource)
        else:
            provider = TracerProvider()
        exporter = _JsonlExporter(key)
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("ghg")
    except Exception:
        return None
    with _providers_lock:
        existing = _providers.get(key)
        if existing is not None:
            return existing[1]
        _providers[key] = (provider, tracer)
        return tracer


# ------------------------------------------------------------- handle

class _OperationHandle:
    """Handle yielded by ``operation``; also the context manager."""

    def __init__(self, op_name, actor=None):
        self._op_name = op_name
        self._actor_arg = actor
        self._start = time.monotonic()
        self._attrs = {}
        self._span = None
        self._active = False
        self._finished = False

    # -- the one and only attribute-setting path --------------------

    def set_attribute(self, key, value):
        """Record an attribute, filtered through filter_attributes."""
        try:
            if not isinstance(key, str):
                return
            filtered = filter_attributes({key: value})
            if key in filtered:
                self._attrs[key] = filtered[key]
        except Exception:
            pass

    def finish(self, exit_code):
        """Record exit_code, duration_ms and gate_verdict."""
        try:
            duration_ms = float(
                (time.monotonic() - self._start) * 1000.0)
            self.set_attribute("exit_code", exit_code)
            self.set_attribute("duration_ms", duration_ms)
            self.set_attribute(
                "gate_verdict",
                "denied" if exit_code == 75 else "allowed")
            self._finished = True
        except Exception:
            pass

    # -- context manager protocol -----------------------------------

    def __enter__(self):
        self._start = time.monotonic()
        try:
            if not enabled():
                return self
            file_path = os.environ.get(ENV_VAR)
            if not file_path:
                return self
            # Unusable path (e.g. parent dir missing) -> no-op.
            try:
                parent = Path(file_path).expanduser().parent
                if str(parent) and not parent.exists():
                    return self
            except Exception:
                return self
            tracer = _get_tracer(file_path)
            if tracer is None:
                return self
            try:
                span = tracer.start_span("ghg.%s" % (self._op_name,))
            except Exception:
                return self
            # Telemetry is actually enabled and a span exists: only
            # now may an actor callable be invoked.
            self._span = span
            self._active = True
            try:
                self.set_attribute("operation", self._op_name)
                if self._actor_arg is not None:
                    if callable(self._actor_arg):
                        resolved = self._actor_arg()
                    else:
                        resolved = self._actor_arg
                    if resolved is not None:
                        self.set_attribute("actor", resolved)
            except Exception:
                # A failing actor callable / attribute step must not
                # break the caller; keep the span with what we have.
                pass
            return self
        except Exception:
            # Any failure degrades to the no-op handle.
            self._span = None
            self._active = False
            return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._active or self._span is None:
            return False
        span = self._span
        try:
            if exc_type is not None:
                self._attrs.pop("exit_code", None)
                duration_ms = float(
                    (time.monotonic() - self._start) * 1000.0)
                self.set_attribute("duration_ms", duration_ms)
                self.set_attribute("gate_verdict", "error")
                try:
                    import importlib

                    trace_mod = importlib.import_module("opentelemetry.trace")
                    span.set_status(
                        trace_mod.Status(trace_mod.StatusCode.ERROR))
                except Exception:
                    pass
            elif "duration_ms" not in self._attrs:
                # No finish() call on the success path: still record
                # elapsed time so the span is well-formed.
                try:
                    self.set_attribute(
                        "duration_ms",
                        float((time.monotonic() - self._start) * 1000.0))
                except Exception:
                    pass
            # Buffered attributes were all recorded through
            # set_attribute -> filter_attributes (the single path);
            # apply them verbatim to the span.
            final = dict(self._attrs)
            for key, value in final.items():
                try:
                    span.set_attribute(key, value)
                except Exception:
                    pass
            try:
                span.end()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._active = False
            self._span = None
        return False


def operation(op_name, actor=None):
    """Context manager for one ghg operation span.

    ``actor`` may be a string or a zero-arg callable returning a
    string; the callable is invoked only when telemetry is actually
    enabled. Yields a handle with ``set_attribute`` and ``finish``.
    """
    return _OperationHandle(op_name, actor=actor)
