import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

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
