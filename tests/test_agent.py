import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.services.agent import AgentService
from app.services.company_api import IntegrationUnavailable
from app.services.complaints import ComplaintRepository


class FakeKnowledgeBase:
    def search(self, _: str):
        raise AssertionError("RAG must not be queried for an off-topic message")


class FakeQwen:
    async def answer(self, *_):
        return "unexpected"


class FakeCorporateApi:
    async def find_outages_by_address(self, _: str):
        raise IntegrationUnavailable("Subscriber lookup is disabled")

    async def check_capacity(self, *_):
        raise IntegrationUnavailable("Capacity endpoint is disabled")

    async def create_technical_condition(self, _: dict):
        return {"data": {"number": "TC-42"}}


class AgentServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        settings = Settings(data_dir=Path(self.temp_dir.name))
        complaints = ComplaintRepository(settings.database_path)
        complaints.initialize()
        self.agent = AgentService(settings, FakeKnowledgeBase(), FakeQwen(), FakeCorporateApi(), complaints)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_model_is_configurable_independently_of_provider(self):
        local = Settings(llm_provider="ollama", llm_model="gemma3:12b")
        pod = Settings(
            llm_provider="runpod_pod",
            llm_model="Qwen/Qwen3-VL-8B-Instruct",
            runpod_pod_id="pod123",
            runpod_pod_port=19123,
            llm_api_key="model-api-key",
        )
        external = Settings(
            llm_provider="openai_compatible",
            llm_model="company-llm",
            llm_base_url="https://llm.example.com/v1",
            llm_api_key="example-key",
        )

        self.assertEqual(local.resolved_llm_model, "gemma3:12b")
        self.assertEqual(local.resolved_llm_api_key, "ollama")
        self.assertEqual(pod.resolved_llm_base_url, "https://pod123-19123.proxy.runpod.net/v1")
        self.assertEqual(pod.resolved_llm_api_key, "model-api-key")
        self.assertEqual(external.resolved_llm_model, "company-llm")
        self.assertEqual(external.resolved_llm_api_key, "example-key")

    async def test_off_topic_question_is_refused_without_rag(self):
        response = await self.agent.chat("Кто выиграет футбольный матч?", None)

        self.assertEqual(response.workflow, "general")
        self.assertIn("только с вопросами ТАТЭК", response.message)

    async def test_greeting_receives_a_warm_company_focused_response(self):
        response = await self.agent.chat("Здравствуйте", None)

        self.assertEqual(response.workflow, "general")
        self.assertIn("Я на связи", response.message)
        self.assertIn("ТАТЭК", response.message)

    async def test_outage_flow_reassures_and_explains_why_it_needs_an_address(self):
        response = await self.agent.chat("У меня нет света", None)

        self.assertEqual(response.workflow, "outage")
        self.assertIn("Понимаю", response.message)
        self.assertIn("По полному адресу", response.message)
        self.assertIn("активные отключения", response.message)

    async def test_unavailable_outage_lookup_does_not_dismiss_the_customer_problem(self):
        initial = await self.agent.chat("У меня нет света", None)
        response = await self.agent.chat("Алматы, ул. Абая, 10", initial.conversation_id)

        self.assertIn("не означает, что отключения нет", response.message)
        self.assertIn("оставить обращение", response.message)

    async def test_technical_conditions_require_document_and_confirmation(self):
        initial = await self.agent.chat("Хочу подключить объект", None)
        conversation_id = initial.conversation_id

        await self.agent.chat("Алматы, ул. Абая, 10", conversation_id)
        await self.agent.chat("15 кВт", conversation_id)
        await self.agent.chat("ТОО Энергия", conversation_id)
        summary = await self.agent.chat("+7 777 000 00 00", conversation_id)
        blocked = await self.agent.chat("подтверждаю", conversation_id)

        self.assertTrue(summary.requires_confirmation)
        self.assertIn("Прикрепите", blocked.message)

        self.agent.add_application_document(conversation_id, "паспорт.pdf", "accepted", "Файл прочитан")
        created = await self.agent.chat("подтверждаю", conversation_id)

        self.assertIn("TC-42", created.message)
