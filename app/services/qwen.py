from openai import AsyncOpenAI

from app.config import Settings
from app.services.language import LANGUAGE_NAMES, Language
from app.services.rag import SearchHit

# Класс и функции для работы с клиентом Qwen LLM
class QwenClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: AsyncOpenAI | None = None

    @property
    def configured(self) -> bool:
        if self.settings.llm_provider == "ollama":
            return bool(self.settings.resolved_llm_base_url and self.settings.resolved_llm_model)
        return bool(self.settings.resolved_llm_base_url and self.settings.resolved_llm_api_key)

    async def answer(self, question: str, hits: list[SearchHit], language: Language = "ru") -> str:
        if not self.configured:
            return "Пока не могу подключиться к базе ответов. Попробуйте чуть позже или обратитесь в поддержку ТАТЭК."

        context = "\n\n".join(f"Источник: {hit.source}\n{hit.text}" for hit in hits)
        language_name = LANGUAGE_NAMES[language]
        # Системный промпт для Qwen LLM
        system = (
            "Ты Чат ассистент энергетической организации ТАТЭК, оператор консультант энергетической организации ТАТЭК. "
            f"Пользователь написал на {language_name} языке. Отвечай ТОЛЬКО на {language_name} языке, "
            "естественно, спокойно и по-человечески, как опытный сотрудник поддержки. "
            "Сначала коротко ответь на суть вопроса, затем при необходимости объясни причину и предложи следующий конкретный шаг. "
            "Пиши ясными короткими абзацами, без канцелярита, шаблонных фраз и избыточных списков. "
            "Если вопрос связан с отключением, оплатой, документами или другой неприятной ситуацией, сначала спокойно признай её. "
            "Объясняй, зачем просишь адрес, номер лицевого счёта или документ. "
            "Если данных или доступа к системе нет, прямо скажи, что это не подтверждает отсутствие проблемы, и подскажи, как её зарегистрировать. "
            "Не преувеличивай сочувствие и не обещай то, чего не можешь сделать. "
            "Отвечай только на вопросы о ТАТЭК, её услугах, документах и обслуживании. "
            "Используй только факты из контекста. Если ответа в нём нет, честно скажи об этом на языке ответа "
            "и предложи обратиться в службу поддержки. Не выдумывай тарифы, сроки, статусы, контакты или правила."
        )
        # Отправка запроса к Qwen LLM с системным и пользовательским сообщениями
        response = await self._get_client().chat.completions.create(
            model=self.settings.resolved_llm_model,
            temperature=0.1,
            max_tokens=500,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Контекст:\n{context or 'Нет подходящих документов.'}\n\nВопрос: {question}"},
            ],
        )
        return response.choices[0].message.content or "Не удалось сформировать ответ."

# определение, отвечает ли сообщение пользователя на заданный вопрос или сменил тему
    # pending_question: вопрос, заданный ботом
    # message: сообщение пользователя
    # возвращает True, если сообщение отвечает на вопрос, False, если смена темы    
    async def is_answer_to_question(self, pending_question: str, message: str) -> bool:
        """Classify whether `message` answers `pending_question` or the user switched topics."""
        if not self.configured:
            return True

        system = (
            "Ты классификатор реплик в чат-боте службы поддержки энергетической компании. "
            "Тебе дают вопрос, который задал бот, и следующее сообщение пользователя. "
            "Определи: пользователь отвечает на заданный вопрос (даже кратко, с опечатками или неполно), "
            "или он сменил тему / задал новый вопрос / попросил что-то другое. "
            "Ответь ровно одним словом: ДА — если это ответ на вопрос, НЕТ — если это смена темы."
        )
        user = f"Вопрос бота: {pending_question}\nСообщение пользователя: {message}\nЭто ответ на вопрос?"
        try:
            response = await self._get_client().chat.completions.create(
                model=self.settings.resolved_llm_model,
                temperature=0.0,
                max_tokens=5,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception:
            return True

        verdict = (response.choices[0].message.content or "").strip().lower()
        return not verdict.startswith(("нет", "no"))

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.resolved_llm_api_key,
                base_url=self.settings.resolved_llm_base_url,
            )
        return self._client