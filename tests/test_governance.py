import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.governance.store import governance_store
from app.main import app


class GovernanceApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        governance_store.path = Path(self.tmpdir.name) / "governance_store.json"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    @patch("app.agent.governance_workflow.retrieve", return_value=[])
    def test_analyze_creates_gaps_clusters_and_drafts(self, mocked_retrieve):
        response = self.client.post(
            "/governance/analyze",
            json={
                "questions": [
                    "优惠券过期了还能补发吗？",
                    "我的满减券昨天过期了还能恢复吗？",
                    "发票可以修改抬头吗？",
                ],
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["gaps"]), 3)
        self.assertGreaterEqual(len(payload["clusters"]), 2)
        self.assertGreaterEqual(len(payload["drafts"]), 2)
        self.assertTrue(governance_store.path.exists())
        mocked_retrieve.assert_called()

    @patch("app.governance.service.add_documents", return_value=2)
    @patch("app.agent.governance_workflow.retrieve", return_value=[])
    def test_approve_reject_and_edit_draft(self, mocked_retrieve, mocked_add_documents):
        analyze_response = self.client.post(
            "/governance/analyze",
            json={"questions": ["企业采购支持对公转账吗？"], "top_k": 3},
        )
        self.assertEqual(analyze_response.status_code, 200)
        draft_id = analyze_response.json()["drafts"][0]["id"]

        edit_response = self.client.post(
            f"/governance/drafts/{draft_id}/edit",
            json={
                "title": "企业采购与对公转账处理规则",
                "standard_answer": "企业采购问题需要先确认采购主体、金额、开票和合同需求。",
            },
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.json()["review_status"], "pending")

        approve_response = self.client.post(f"/governance/drafts/{draft_id}/approve")
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["review_status"], "approved")
        self.assertEqual(approve_response.json()["published_chunks"], 2)
        mocked_add_documents.assert_called_once()

        reject_response = self.client.post(
            f"/governance/drafts/{draft_id}/reject",
            json={"reason": "已发布草稿不应再拒绝"},
        )
        self.assertEqual(reject_response.status_code, 409)

        edit_published_response = self.client.post(
            f"/governance/drafts/{draft_id}/edit",
            json={"title": "不应直接修改已发布草稿"},
        )
        self.assertEqual(edit_published_response.status_code, 409)

    def test_governance_list_endpoints(self):
        response = self.client.get("/governance/gaps")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"gaps": []})

        response = self.client.get("/governance/drafts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"drafts": []})

        response = self.client.get("/governance/unanswered_questions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"questions": [], "total": 0})

    @patch("routers.rag.answer_with_rag")
    def test_rag_records_unanswered_question(self, mocked_answer):
        mocked_answer.return_value = {
            "session_id": "unit-session",
            "question": "优惠券过期了还能补发吗？",
            "answer": "知识库中暂未找到相关信息。",
            "sources": [],
            "contexts": [],
        }

        response = self.client.post(
            "/rag/ask",
            json={"question": "优惠券过期了还能补发吗？", "session_id": "unit-session"},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/governance/unanswered_questions")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["questions"][0]["status"], "pending")
        self.assertEqual(payload["questions"][0]["session_id"], "unit-session")


if __name__ == "__main__":
    unittest.main()
