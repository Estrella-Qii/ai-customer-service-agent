import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.__about__ import __version__
from app.core.config import settings
from app.main import app


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "version": __version__})

    @patch("app.main.get_qdrant_client")
    def test_readiness_reports_dependencies_without_secrets(self, mocked_qdrant_client):
        mocked_qdrant_client.return_value.get_collections.return_value = object()
        response = self.client.get("/health/ready")
        self.assertIn(response.status_code, {200, 503})
        payload = response.json()
        self.assertIn("checks", payload)
        self.assertNotIn("api_key", response.text.lower())
        if settings.llm_api_key:
            self.assertNotIn(settings.llm_api_key, response.text)

        status_response = self.client.get("/health/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["checks"]["qdrant"], True)

    def test_openapi_contains_core_routes(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("/chat", paths)
        self.assertIn("/documents", paths)
        self.assertIn("/documents/{filename}", paths)
        self.assertIn("/documents/upload", paths)
        self.assertIn("/documents/search", paths)
        self.assertIn("/rag/ask", paths)
        self.assertIn("/sessions/{session_id}/history", paths)
        self.assertIn("/governance/analyze", paths)
        self.assertIn("/governance/gaps", paths)
        self.assertIn("/governance/drafts", paths)
        self.assertIn("/governance/unanswered_questions", paths)
        self.assertIn("/governance/drafts/{draft_id}/approve", paths)

    def test_static_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("智能客服 Agent", response.text)

    @patch("routers.documents.document_exists", return_value=False)
    @patch("routers.documents.add_documents", return_value=1)
    def test_upload_txt_document(self, mocked_add_documents, mocked_document_exists):
        response = self.client.post(
            "/documents/upload",
            files={"file": ("demo.txt", b"hello customer service", "text/plain")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filename"], "demo.txt")
        self.assertEqual(payload["chunks_stored"], 1)
        self.assertFalse(payload["replaced"])
        mocked_document_exists.assert_called_once_with("demo.txt")
        mocked_add_documents.assert_called_once()

    @patch("routers.documents.list_documents")
    def test_list_documents(self, mocked_list_documents):
        mocked_list_documents.return_value = [
            {"filename": "demo.txt", "chunks": 1, "chunk_indexes": [0], "preview": "hello"}
        ]
        response = self.client.get("/documents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    @patch("routers.documents.delete_document", return_value=2)
    def test_delete_document(self, mocked_delete_document):
        response = self.client.delete("/documents/demo.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_chunks"], 2)
        mocked_delete_document.assert_called_once_with("demo.txt")

    def test_upload_rejects_unknown_file_type(self):
        response = self.client.post(
            "/documents/upload",
            files={"file": ("demo.exe", b"bad", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_file_over_size_limit(self):
        with patch.object(settings, "max_upload_bytes", 4):
            response = self.client.post(
                "/documents/upload",
                files={"file": ("demo.txt", b"12345", "text/plain")},
            )
        self.assertEqual(response.status_code, 413)

    @patch("routers.documents.document_exists", return_value=False)
    @patch("routers.documents.add_documents", return_value=1)
    def test_upload_strips_client_path_from_filename(self, mocked_add_documents, mocked_document_exists):
        response = self.client.post(
            "/documents/upload",
            files={"file": ("../policy.txt", b"safe content", "text/plain")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filename"], "policy.txt")
        mocked_document_exists.assert_called_once_with("policy.txt")

    def test_session_id_is_bounded_and_path_safe(self):
        response = self.client.get("/sessions/not%20safe/history")
        self.assertEqual(response.status_code, 422)

    def test_session_history_can_be_read_and_cleared(self):
        session_id = "unit-test-session"
        self.client.delete(f"/sessions/{session_id}")

        response = self.client.get(f"/sessions/{session_id}/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"], [])

        response = self.client.delete(f"/sessions/{session_id}")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
