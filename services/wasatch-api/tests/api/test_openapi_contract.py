"""OpenAPI contract alignment for the laboratory HTTP slice."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from wasatch_api.documents.application.decisions import EXTRACTION_REVIEW_DECISIONS
from wasatch_api.governance.application.decisions import CUSTOMER_MESSAGE_DECISIONS
from wasatch_api.workflows.domain.follow_up import FOLLOW_UP_DECISIONS

from .openapi_contract_catalog import (
    POST_BODY_DECISION_ENUMS,
    READ_PATHS,
    SLICE_PATH_METHODS,
    WRITE_PATHS,
)


def _openapi(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def _methods(path_item: dict[str, Any]) -> set[str]:
    return {method.lower() for method in path_item if method.lower() != "parameters"}


def _request_schema(spec: dict[str, Any], path: str, method: str) -> dict[str, Any]:
    operation = spec["paths"][path][method]
    content = operation.get("requestBody", {}).get("content", {})
    json_body = content.get("application/json", {})
    schema = json_body.get("schema", {})
    ref = schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        return spec["components"]["schemas"][name]
    return schema


def test_openapi_paths_match_the_slice_catalog(client: TestClient) -> None:
    spec = _openapi(client)
    published = {
        path: frozenset(_methods(path_item))
        for path, path_item in spec["paths"].items()
    }
    assert published == SLICE_PATH_METHODS


def test_write_routes_are_post_only_and_reads_stay_get(client: TestClient) -> None:
    spec = _openapi(client)
    paths = spec["paths"]
    assert WRITE_PATHS <= set(paths)
    post_only_writes = WRITE_PATHS - {
        "/api/v1/approval-requests/{approval_id}/follow-up-visits",
    }
    for path in post_only_writes:
        assert _methods(paths[path]) == {"post"}
    follow_up = paths["/api/v1/approval-requests/{approval_id}/follow-up-visits"]
    assert _methods(follow_up) == {"get", "post"}
    for path in READ_PATHS:
        assert _methods(paths[path]) <= {"get", "head"}


def test_decision_request_bodies_match_application_rules(client: TestClient) -> None:
    spec = _openapi(client)
    expected_by_domain = {
        "/api/v1/approval-requests/{approval_id}/decisions": CUSTOMER_MESSAGE_DECISIONS,
        "/api/v1/document-extractions/{extraction_id}/decisions": (
            EXTRACTION_REVIEW_DECISIONS
        ),
        "/api/v1/approval-requests/{approval_id}/follow-up-visits": FOLLOW_UP_DECISIONS,
    }
    for path, expected in POST_BODY_DECISION_ENUMS.items():
        schema = _request_schema(spec, path, "post")
        decision = schema["properties"]["decision"]
        if "$ref" in decision:
            ref_name = decision["$ref"].rsplit("/", 1)[-1]
            decision = spec["components"]["schemas"][ref_name]
        published = frozenset(decision["enum"])
        assert published == expected
        assert published == expected_by_domain[path]


def test_runtime_errors_use_the_shared_envelope(
    client: TestClient, anonymous_client: TestClient
) -> None:
    not_found = client.get("/api/v1/customers/cust_9999")
    assert not_found.status_code == 404
    body = not_found.json()
    json.dumps(body)
    assert body == {
        "error": {
            "code": "not_found",
            "message": "customer cust_9999 was not found",
        }
    }

    unauthenticated = anonymous_client.get("/api/v1/customers/cust_0001")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "unauthenticated"
