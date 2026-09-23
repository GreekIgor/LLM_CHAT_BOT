import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import Settings
from app.models import ChatResponse, Source
from app.services.company_api import CorporateApiClient, CorporateApiError, IntegrationUnavailable
from app.services.complaints import ComplaintRepository
from app.services.language import Language, detect_language, phrase
from app.services.qwen import QwenClient
from app.services.rag import KnowledgeBase, SearchHit


Workflow = Literal["general", "outage", "technical_conditions", "complaint"]


# Класс документа загруженный пользователем
# Может иметь два статуса подвержден и требует проверки
@dataclass
class ApplicationDocument:
    name: str
    status: Literal["accepted", "review_required"]
    message: str


# Класс для хранения состояния разговора с пользователем
# Содержит текущий рабочий процесс, язык, ожидающий вопрос, дополнительные данные и загруженные документы
@dataclass
class Conversation:
    workflow: Workflow = "general"
    language: Language = "ru"
    pending_question: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    documents: list[ApplicationDocument] = field(default_factory=list)

# Сервис агента, который обрабатывает сообщения от пользователя, управляет состоянием разговоров и взаимодействует с внешними системами
# Обеспечивает методы для общения с пользователем, обработки намерений и управления рабочими процессами
# Использует базу знаний RAG, корпоративный API и репозиторий жалоб для обработки запросов пользователя
# Управляет состоянием разговоров и координирует работу различных компонентов системы
# Отвечает за интеграцию всех компонентов и предоставление единого интерфейса для взаимодействия с пользователем
class AgentService:
    def __init__(
        self,
        settings: Settings,
        knowledge_base: KnowledgeBase,
        qwen: QwenClient,
        corporate_api: CorporateApiClient,
        complaints: ComplaintRepository,
    ) -> None:
        self.settings = settings
        self.knowledge_base = knowledge_base
        self.qwen = qwen
        self.corporate_api = corporate_api
        self.complaints = complaints
        self.conversations: dict[str, Conversation] = {}

# Функция для взаимодействия с пользователем через чат
    async def chat(self, message: str, conversation_id: str | None) -> ChatResponse:
        # Очистка сообщения пользователя
        clean_message = message.strip()
        # id Диалога
        conversation_id = conversation_id or str(uuid.uuid4())
        conversation = self.conversations.setdefault(conversation_id, Conversation())

        if clean_message:
            # определение языка сообщения пользователя
            conversation.language = detect_language(clean_message)
        language = conversation.language
    # Проверка сценария рабочего процесса
    # Если текущий рабочий процесс не "general", продолжаем его выполнение
        if conversation.workflow != "general":
            return await self._continue_workflow(conversation_id, conversation, clean_message)
# чтобы не грузить модель, сразу отвечаем на приветствия и благодарности
        if self._is_greeting(clean_message):
            return self._response(conversation_id, "general", phrase("greeting", language))
# тот же принцип для благодарностей
        if self._is_thanks(clean_message):
            return self._response(conversation_id, "general", phrase("thanks", language))
# определение ветви процесса на основе намерения пользователя
        intent = self._detect_intent(clean_message)
        
        if intent == "outage":
            conversation.workflow = "outage"
            return self._ask(conversation, conversation_id, "outage", phrase("outage_start", language))
        if intent == "technical_conditions":
            conversation.workflow = "technical_conditions"
            return self._ask(
                conversation, conversation_id, "technical_conditions", phrase("technical_conditions_start", language)
            )
        if intent == "complaint":
            conversation.workflow = "complaint"
            return self._ask(conversation, conversation_id, "complaint", phrase("complaint_start", language))

        try:
            hits = self.knowledge_base.search(clean_message)
        except Exception:
            return self._response(conversation_id, "general", phrase("knowledge_base_error", language))
        if not hits:
            return self._response(conversation_id, "general", phrase("no_relevant_materials", language))
        answer = await self.qwen.answer(clean_message, hits, language)
        return self._response(conversation_id, "general", answer, sources=self._sources(hits))

# добавление документа заявки пользователем
# conversation_id: идентификатор текущего разговора
# name: имя документа
# status: статус документа ("accepted" или "review_required")
# message: сообщение пользователя, связанное с документом
# возвращает объект ApplicationDocument, представляющий добавленный документ
    def add_application_document(
        self, conversation_id: str, name: str, status: Literal["accepted", "review_required"], message: str
    ) -> ApplicationDocument:
        conversation = self.conversations.setdefault(conversation_id, Conversation())
        document = ApplicationDocument(name=name, status=status, message=message)
        conversation.documents.append(document)
        return document

    async def _continue_workflow(
        self, conversation_id: str, conversation: Conversation, message: str
    ) -> ChatResponse:
        language = conversation.language
        if self._is_cancel(message):
            self.conversations[conversation_id] = Conversation(language=language)
            return self._response(conversation_id, "general", phrase("cancelled", language))

# Обработка приветствий и благодарностей пользователя
# Если сообщение является приветствием или благодарностью, перезапускаем разговор и отвечаем на него сразу
# conversation_id: идентификатор текущего разговора
# message: сообщение пользователя
# возвращает объект ChatResponse с ответом на приветствие или благодарность
        if self._is_greeting(message) or self._is_thanks(message):
            self.conversations[conversation_id] = Conversation(language=language)
            return await self.chat(message, conversation_id)
        if conversation.pending_question and not await self.qwen.is_answer_to_question(
            conversation.pending_question, message
        ):
            self.conversations[conversation_id] = Conversation(language=language)
            return await self.chat(message, conversation_id)
        # обработка сценария "отключение"
        if conversation.workflow == "outage":
            return await self._handle_outage(conversation_id, conversation, message)
        # Обработка сценария "технические условия"
        if conversation.workflow == "technical_conditions":
            return await self._handle_technical_conditions(conversation_id, conversation, message)
        return await self._handle_complaint(conversation_id, conversation, message)

# функция для обработки сценария "отключение"
    async def _handle_outage(
        self, conversation_id: str, conversation: Conversation, message: str
    ) -> ChatResponse:
        language = conversation.language
        conversation.data["address"] = message
        try:
            result = await self.corporate_api.find_outages_by_address(message)
        except IntegrationUnavailable:
            self.conversations[conversation_id] = Conversation(language=language)
            return self._response(conversation_id, "outage", phrase("outage_integration_unavailable", language))
        except CorporateApiError:
            self.conversations[conversation_id] = Conversation(language=language)
            return self._response(conversation_id, "outage", phrase("outage_api_error", language))

        self.conversations[conversation_id] = Conversation(language=language)
        outages = result["outages"]
        if not outages:
            return self._response(conversation_id, "outage", phrase("outage_none_found", language))
        details = "\n".join(f"- {self.corporate_api.display_outage(outage)}" for outage in outages)
        return self._response(conversation_id, "outage", phrase("outage_found", language, details=details))

    # функция для обработки сценария "технические условия"
    async def _handle_technical_conditions(
        self, conversation_id: str, conversation: Conversation, message: str
    ) -> ChatResponse:
        language = conversation.language
        data = conversation.data
        if "address" not in data:
            data["address"] = message
            return self._ask(
                conversation, conversation_id, "technical_conditions", phrase("technical_conditions_ask_power", language)
            )
        if "power_kw" not in data:
            power_kw = self._extract_power(message)
            if power_kw is None:
                return self._ask(
                    conversation,
                    conversation_id,
                    "technical_conditions",
                    phrase("technical_conditions_power_not_understood", language),
                )
            data["power_kw"] = power_kw
            try:
                data["capacity"] = await self.corporate_api.check_capacity(data["address"], power_kw)
            except IntegrationUnavailable:
                data["capacity"] = None
            except CorporateApiError:
                return self._ask(
                    conversation,
                    conversation_id,
                    "technical_conditions",
                    phrase("technical_conditions_capacity_error", language),
                )
            return self._ask(
                conversation, conversation_id, "technical_conditions", phrase("technical_conditions_ask_declarer", language)
            )
        if "declarer" not in data:
            data["declarer"] = message
            return self._ask(
                conversation, conversation_id, "technical_conditions", phrase("technical_conditions_ask_contact", language)
            )
        if "contact" not in data:
            data["contact"] = message
            return self._technical_conditions_summary(conversation_id, conversation)
        if not conversation.documents:
            return self._ask(
                conversation,
                conversation_id,
                "technical_conditions",
                phrase("technical_conditions_need_document", language),
                requires_confirmation=True,
            )
        if self._is_confirmation(message):
            payload = self._technical_condition_payload(data)
            try:
                result = await self.corporate_api.create_technical_condition(payload)
            except (CorporateApiError, IntegrationUnavailable) as error:
                return self._ask(
                    conversation,
                    conversation_id,
                    "technical_conditions",
                    phrase("technical_conditions_create_error", language, error=error),
                    requires_confirmation=True,
                )
            self.conversations[conversation_id] = Conversation(language=language)
            reference = self._extract_reference(result)
            reference_note = f". Номер: {reference}" if reference else ""
            return self._response(
                conversation_id,
                "technical_conditions",
                phrase("technical_conditions_created", language, reference=reference_note),
            )
        return self._technical_conditions_summary(conversation_id, conversation)

    # Функция для формирования сводки по техническим условиям
    def _technical_conditions_summary(self, conversation_id: str, conversation: Conversation) -> ChatResponse:
        language = conversation.language
        data = conversation.data
        capacity_note = (
            phrase("capacity_checked", language) if data.get("capacity") else phrase("capacity_not_checked", language)
        )
        documents_note = (
            phrase("documents_listed", language, names=", ".join(document.name for document in conversation.documents))
            if conversation.documents
            else phrase("documents_missing", language)
        )
        return self._ask(
            conversation,
            conversation_id,
            "technical_conditions",
            phrase(
                "technical_conditions_summary",
                language,
                address=data["address"],
                power=data["power_kw"],
                declarer=data["declarer"],
                contact=data["contact"],
                capacity_note=capacity_note,
                documents_note=documents_note,
            ),
            requires_confirmation=True,
        )

    # Функция для обработки жалоб пользователей
    async def _handle_complaint(
        self, conversation_id: str, conversation: Conversation, message: str
    ) -> ChatResponse:
        language = conversation.language
        data = conversation.data
        if "address" not in data:
            data["address"] = message
            return self._ask(conversation, conversation_id, "complaint", phrase("complaint_ask_description", language))
        if "description" not in data:
            data["description"] = message
            return self._ask(conversation, conversation_id, "complaint", phrase("complaint_ask_contact", language))
        if "contact" not in data:
            data["contact"] = message
            return self._ask(
                conversation, conversation_id, "complaint", phrase("complaint_ready_to_confirm", language), requires_confirmation=True
            )
        if not self._is_confirmation(message):
            return self._ask(
                conversation, conversation_id, "complaint", phrase("complaint_confirm_prompt", language), requires_confirmation=True
            )
        try:
            external = await self.corporate_api.send_complaint(data)
        except CorporateApiError:
            external = None
        complaint_id = self.complaints.save(
            address=data["address"],
            contact=data["contact"],
            description=data["description"],
            external_reference=external,
        )
        self.conversations[conversation_id] = Conversation(language=language)
        return self._response(conversation_id, "complaint", phrase("complaint_registered", language, id=complaint_id))

    def _technical_condition_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "declarer": data["declarer"],
            "consumer": data["declarer"],
            "address": data["address"],
            "power": data["power_kw"],
            "contacts": {"phone": data["contact"]},
            "notifications": {"promotions": False, "news": False, "events": False},
        }
        if self.settings.technical_condition_status_id is not None:
            payload["status_id"] = self.settings.technical_condition_status_id
        if self.settings.technical_condition_object_id is not None:
            payload["object_id"] = self.settings.technical_condition_object_id
        return payload

    # Функция для определения намерения пользователя на основе его сообщения
    # message: сообщение пользователя
    # возвращает Workflow (например, "outage", "technical_conditions", "complaint") или None, если намерение не распознано
    @staticmethod
    def _detect_intent(message: str) -> Workflow | None:
        normalized = message.lower()
        if any(
            word in normalized
            for word in (
                "нет света", "отключен", "отключили", "электричеств", "света нет",
                "жарық жоқ", "жарық өшті", "ток жоқ", "электр жоқ",
                "no power", "no electricity", "power outage", "power is out", "power cut",
            )
        ):
            return "outage"
        if any(
            word in normalized
            for word in (
                "техуслов", "техническ", "подключ", "присоедин",
                "техникалық шарт", "қосылу", "жалғану",
                "technical condition", "connect to the grid", "grid connection",
            )
        ):
            return "technical_conditions"
        if any(
            word in normalized
            for word in (
                "жалоб", "претензи", "обращени", "пожаловать",
                "шағым", "арыз",
                "complaint", "complain",
            )
        ):
            return "complaint"
        return None

# вспомогательные функции для обработки сообщений пользователя
    # Функция для извлечения мощности из сообщения пользователя
    @staticmethod
    def _extract_power(message: str) -> float | None:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:квт|kw)?", message.lower())
        if not match:
            return None
        value = float(match.group(1).replace(",", "."))
        return value if 0 < value <= 100_000 else None

    @staticmethod
    def _is_confirmation(message: str) -> bool:
        return message.lower().strip() in {
            "подтверждаю", "подтвердить", "да, подтверждаю", "да",
            "растаймын", "иә", "ия",
            "confirm", "yes", "i confirm",
        }

    @staticmethod
    def _is_cancel(message: str) -> bool:
        return message.lower().strip() in {
            "отмена", "отменить", "стоп",
            "бас тартамын", "тоқта",
            "cancel", "stop",
        }

    @staticmethod
    def _is_greeting(message: str) -> bool:
        return message.lower().strip() in {
            "привет", "здравствуйте", "добрый день", "доброе утро", "добрый вечер", "салам",
            "сәлем", "сәлеметсіз бе", "қайырлы күн", "қайырлы таң", "қайырлы кеш",
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        }

    @staticmethod
    def _is_thanks(message: str) -> bool:
        return message.lower().strip() in {
            "спасибо", "благодарю", "спс",
            "рахмет", "рақмет",
            "thanks", "thank you", "thx",
        }

    # Преобразует результаты поиска в список источников (Source)
    # hits: список результатов поиска (SearchHit)
    # возвращает список объектов Source, содержащих документ и фрагмент текста
    @staticmethod
    def _sources(hits: list[SearchHit]) -> list[Source]:
        return [Source(document=hit.source, excerpt=hit.text[:220]) for hit in hits]

    # Функция для извлечения ссылки на документ из ответа
    # response: ответ, содержащий данные о документе
    # возвращает строку с ссылкой на документ или None, если ссылка не найдена  
    @staticmethod
    def _extract_reference(response: Any) -> str | None:
        if not isinstance(response, dict):
            return None
        data = response.get("data", response)
        if isinstance(data, dict):
            for key in ("number", "id", "reference"):
                if data.get(key) is not None:
                    return str(data[key])
        return None

    # Функция для отправки сообщения от бота, ожидающего ответа пользователя
    # conversation: объект Conversation, представляющий текущий разговор
    # conversation_id: идентификатор текущего разговора
    # workflow: текущий рабочий процесс
    # message: сообщение бота
    # requires_confirmation: флаг, указывающий, требуется ли подтверждение от пользователя
    # возвращает объект ChatResponse с отправленным сообщением
    @staticmethod
    def _ask(
        conversation: Conversation,
        conversation_id: str,
        workflow: Workflow,
        message: str,
        *,
        requires_confirmation: bool = False,
    ) -> ChatResponse:
        """Send a bot message that expects a reply, recording it so a later message
        can be checked against it to detect a topic switch."""
        conversation.pending_question = message
        return AgentService._response(
            conversation_id, workflow, message, requires_confirmation=requires_confirmation
        )

    @staticmethod
    def _response(
        conversation_id: str,
        workflow: Workflow,
        message: str,
        *,
        requires_confirmation: bool = False,
        sources: list[Source] | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            conversation_id=conversation_id,
            workflow=workflow,
            message=message,
            requires_confirmation=requires_confirmation,
            sources=sources or [],
        )
