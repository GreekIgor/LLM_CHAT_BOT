import re
from typing import Literal

Language = Literal["ru", "kk", "en"]

_KAZAKH_LETTERS = set("әіңғүұқөһ")
_CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")

# функции для определения языка сообщения и работы с языковыми константами

def detect_language(message: str) -> Language:
    lowered = message.lower()
    if any(letter in lowered for letter in _KAZAKH_LETTERS):
        return "kk"
    cyrillic_count = len(_CYRILLIC_RE.findall(message))
    latin_count = len(_LATIN_RE.findall(message))
    if latin_count > cyrillic_count:
        return "en"
    return "ru"


LANGUAGE_NAMES: dict[Language, str] = {
    "ru": "русском",
    "kk": "казахском",
    "en": "английском",
}


PHRASES: dict[str, dict[Language, str]] = {
    "greeting": {
        "ru": "Здравствуйте! Я на связи и помогу разобраться с вопросом по ТАТЭК. Что случилось или что хотите оформить?",
        "kk": "Сәлеметсіз бе! Мен ТАТЭК бойынша сұрағыңызға көмектесе аламын. Не болды немесе нені рәсімдегіңіз келеді?",
        "en": "Hello! I'm here to help with any TATEK-related question. What happened, or what would you like to arrange?",
    },
    "thanks": {
        "ru": "Пожалуйста. Если появится вопрос по ТАТЭК, напишите сюда.",
        "kk": "Өтінемін. ТАТЭК бойынша сұрақ туындаса, осында жазыңыз.",
        "en": "You're welcome. If you have another TATEK-related question, feel free to write here.",
    },
    "outage_start": {
        "ru": "Понимаю, когда нет света, это очень неудобно. Давайте разберёмся. По полному адресу я сопоставлю ваш дом с линией электроснабжения и проверю активные отключения. Напишите населённый пункт, улицу, дом и квартиру или офис, если есть.",
        "kk": "Жарық болмаса, бұл өте ыңғайсыз екенін түсінемін. Келіңіз анықтайық. Толық мекенжай бойынша үйіңізді электр желісімен салыстырып, белсенді ажыратуларды тексеремін. Елді мекен, көше, үй және пәтер немесе кеңсені жазыңыз.",
        "en": "I understand a power outage is very inconvenient. Let's figure it out. With your full address I can match your building to the power line and check active outages. Please write the town, street, house number, and apartment or office if any.",
    },
    "technical_conditions_start": {
        "ru": "Хорошо, помогу оформить заявку на технические условия. Начнём с адреса объекта: он нужен, чтобы проверить возможность подключения и подготовить заявку.",
        "kk": "Жақсы, техникалық шарттарға өтінім рәсімдеуге көмектесемін. Нысанның мекенжайынан бастайық: ол қосылу мүмкіндігін тексеру және өтінімді дайындау үшін қажет.",
        "en": "Sure, I'll help you file a technical conditions request. Let's start with the site address — it's needed to check connection availability and prepare the application.",
    },
    "complaint_start": {
        "ru": "Понимаю, такую ситуацию важно не оставить без внимания. Я зафиксирую обращение и передам его специалистам. Напишите адрес, к которому оно относится, чтобы его направили в нужный участок.",
        "kk": "Мұндай жағдайды назарсыз қалдырмау маңызды екенін түсінемін. Өтінішіңізді тіркеп, мамандарға жіберемін. Тиесілі мекенжайды жазыңыз, сол бойынша тиісті учаскеге бағытталады.",
        "en": "I understand this situation deserves attention. I'll log your request and forward it to specialists. Please write the address it relates to, so it can be routed to the right team.",
    },
    "cancelled": {
        "ru": "Хорошо, отменил. Что ещё подсказать по ТАТЭК?",
        "kk": "Жарайды, бас тарттым. ТАТЭК бойынша тағы не айтып берейін?",
        "en": "Alright, cancelled. What else can I help with regarding TATEK?",
    },
    "outage_integration_unavailable": {
        "ru": "Пока не могу проверить адрес автоматически: адресная сверка с системой ТАТЭК ещё не подключена. Это не означает, что отключения нет. Можно оставить обращение, и специалисты проверят ситуацию по вашему адресу.",
        "kk": "Мекенжайды автоматты түрде тексере алмай тұрмын: ТАТЭК жүйесімен мекенжай салыстыру әлі қосылмаған. Бұл ажырату жоқ дегенді білдірмейді. Өтінім қалдыруға болады, мамандар мекенжайыңызды тексереді.",
        "en": "I can't verify the address automatically yet: address lookup with the TATEK system isn't connected. This doesn't mean there's no outage. You can leave a request, and specialists will check your address.",
    },
    "outage_api_error": {
        "ru": "Система отключений сейчас не ответила. Это не подтверждает, что аварии или работ нет. Попробуйте ещё раз чуть позже или оставьте обращение, чтобы специалисты проверили ваш адрес.",
        "kk": "Ажыратулар жүйесі қазір жауап бермеді. Бұл авария немесе жұмыс жоқ дегенді білдірмейді. Сәл кейінірек қайталап көріңіз немесе мамандар тексеруі үшін өтінім қалдырыңыз.",
        "en": "The outage system didn't respond just now. That doesn't confirm there's no fault or maintenance. Please try again shortly or leave a request so specialists can check your address.",
    },
    "outage_none_found": {
        "ru": "По этому адресу не вижу активного планового отключения. Это не исключает локальную неисправность в доме или на линии. Если света всё ещё нет, оставьте обращение, и специалисты проведут диагностику.",
        "kk": "Бұл мекенжай бойынша белсенді жоспарлы ажыратуды көрмеймін. Бұл үйде немесе желіде жергілікті ақаудың болмауын білдірмейді. Егер жарық әлі жоқ болса, өтінім қалдырыңыз, мамандар диагностика жасайды.",
        "en": "I don't see an active planned outage at this address. That doesn't rule out a local fault in the building or the line. If the power is still out, please leave a request so specialists can run diagnostics.",
    },
    "outage_found": {
        "ru": "По вашему адресу есть активное отключение:\n{details}\n\nПонимаю, это неудобно. Информация выше получена из системы ТАТЭК; восстановление ожидается в указанный срок, если его передала диспетчерская служба.",
        "kk": "Мекенжайыңыз бойынша белсенді ажырату бар:\n{details}\n\nБұл ыңғайсыз екенін түсінемін. Жоғарыдағы ақпарат ТАТЭК жүйесінен алынды; диспетчерлік қызмет мерзімді хабарласа, сол мерзімде қалпына келтіріледі.",
        "en": "There is an active outage at your address:\n{details}\n\nI understand this is inconvenient. The information above comes from the TATEK system; restoration is expected by the given time if the dispatch service provided one.",
    },
    "technical_conditions_ask_power": {
        "ru": "Спасибо. Какая мощность нужна для объекта? Она нужна для технического расчёта. Напишите число в кВт, например: 15 кВт. Если точной цифры пока нет, укажите ориентировочную.",
        "kk": "Рахмет. Нысанға қандай қуат қажет? Ол техникалық есептеу үшін керек. кВт-пен санды жазыңыз, мысалы: 15 кВт. Дәл сан болмаса, болжамды мәнін көрсетіңіз.",
        "en": "Thank you. What power capacity does the site need? It's required for the technical calculation. Please write a number in kW, e.g. 15 kW. If you don't have an exact figure yet, give an estimate.",
    },
    "technical_conditions_power_not_understood": {
        "ru": "Не смог понять мощность. Напишите число в кВт, например: 15 кВт.",
        "kk": "Қуатты түсінбедім. кВт-пен санды жазыңыз, мысалы: 15 кВт.",
        "en": "I couldn't understand the power value. Please write a number in kW, e.g. 15 kW.",
    },
    "technical_conditions_capacity_error": {
        "ru": "Не получилось проверить свободную мощность автоматически. Это не означает, что подключение невозможно: специалист ТАТЭК проверит возможность вручную при рассмотрении заявки.",
        "kk": "Бос қуатты автоматты түрде тексеру мүмкін болмады. Бұл қосылу мүмкін емес дегенді білдірмейді: ТАТЭК маманы өтінімді қарау кезінде мүмкіндікті қолмен тексереді.",
        "en": "I couldn't automatically check the available capacity. This doesn't mean the connection is impossible: a TATEK specialist will verify it manually when reviewing the application.",
    },
    "technical_conditions_ask_declarer": {
        "ru": "Теперь укажите заявителя: ваше ФИО или название организации.",
        "kk": "Енді өтініш берушіні көрсетіңіз: аты-жөніңіз немесе ұйымның атауы.",
        "en": "Now please provide the applicant: your full name or organization name.",
    },
    "technical_conditions_ask_contact": {
        "ru": "Остался контакт для связи: телефон или email. Он нужен, чтобы специалист мог уточнить детали заявки и сообщить результат.",
        "kk": "Байланысу үшін контакт қалды: телефон немесе email. Ол маманға өтінім бойынша нақтылау және нәтижені хабарлау үшін қажет.",
        "en": "One thing left: a contact — phone or email. It's needed so a specialist can clarify details and share the outcome.",
    },
    "technical_conditions_need_document": {
        "ru": "Для заявки нужен хотя бы один документ. Прикрепите его кнопкой «+». Я проверю, что файл открывается, а содержание затем проверит специалист ТАТЭК. После этого напишите «подтверждаю».",
        "kk": "Өтінім үшін кемінде бір құжат керек. Оны «+» түймесімен тіркеңіз. Файлдың ашылатынын тексеремін, ал мазмұнын кейін ТАТЭК маманы тексереді. Одан кейін «растаймын» деп жазыңыз.",
        "en": "The application needs at least one document. Attach it with the \"+\" button. I'll check the file opens; a TATEK specialist will review its content afterward. Then write \"confirm\".",
    },
    "technical_conditions_create_error": {
        "ru": "Заявку пока не удалось создать: {error} Можно исправить данные или попробовать немного позже.",
        "kk": "Өтінімді әзірге жасау мүмкін болмады: {error} Деректерді түзетуге немесе сәл кейінірек қайталап көруге болады.",
        "en": "The application couldn't be created yet: {error} You can correct the data or try again a bit later.",
    },
    "technical_conditions_created": {
        "ru": "Готово, заявка на технические условия создана{reference}. Мы свяжемся с вами по указанному контакту.",
        "kk": "Дайын, техникалық шарттарға өтінім жасалды{reference}. Сізбен көрсетілген байланыс арқылы хабарласамыз.",
        "en": "Done, the technical conditions application has been created{reference}. We'll contact you using the details you provided.",
    },
    "technical_conditions_summary": {
        "ru": "Проверьте, всё ли верно:\nАдрес: {address}\nМощность: {power} кВт\nЗаявитель: {declarer}\nКонтакт: {contact}\n{capacity_note}\n{documents_note}\n\nЕсли всё верно, напишите «подтверждаю». Если хотите остановиться, напишите «отмена».",
        "kk": "Барлығы дұрыс па, тексеріңіз:\nМекенжай: {address}\nҚуат: {power} кВт\nӨтініш беруші: {declarer}\nКонтакт: {contact}\n{capacity_note}\n{documents_note}\n\nБарлығы дұрыс болса, «растаймын» деп жазыңыз. Тоқтатқыңыз келсе, «бас тартамын» деп жазыңыз.",
        "en": "Please check everything is correct:\nAddress: {address}\nPower: {power} kW\nApplicant: {declarer}\nContact: {contact}\n{capacity_note}\n{documents_note}\n\nIf everything is correct, write \"confirm\". If you'd like to stop, write \"cancel\".",
    },
    "capacity_checked": {
        "ru": "Свободная мощность проверена автоматически.",
        "kk": "Бос қуат автоматты түрде тексерілді.",
        "en": "Available capacity has been checked automatically.",
    },
    "capacity_not_checked": {
        "ru": "Свободную мощность пока не удалось проверить автоматически. Это не отказ в подключении: специалист ТАТЭК уточнит её при рассмотрении заявки.",
        "kk": "Бос қуатты әзірге автоматты түрде тексеру мүмкін болмады. Бұл қосылудан бас тарту емес: ТАТЭК маманы өтінімді қарау кезінде нақтылайды.",
        "en": "Available capacity couldn't be checked automatically yet. This isn't a refusal to connect: a TATEK specialist will confirm it when reviewing the application.",
    },
    "documents_listed": {
        "ru": "Документы: {names}",
        "kk": "Құжаттар: {names}",
        "en": "Documents: {names}",
    },
    "documents_missing": {
        "ru": "Осталось приложить документы через кнопку «+».",
        "kk": "«+» түймесі арқылы құжаттарды тіркеу қалды.",
        "en": "You still need to attach documents using the \"+\" button.",
    },
    "complaint_ask_description": {
        "ru": "Спасибо. Опишите, пожалуйста, что произошло и когда это началось. Чем подробнее детали, тем быстрее специалисту будет понятна ситуация.",
        "kk": "Рахмет. Не болғанын және қашан басталғанын сипаттап беріңізші. Мәліметтер неғұрлым толық болса, маманға жағдай соғұрлым тез түсінікті болады.",
        "en": "Thank you. Please describe what happened and when it started. The more detail you give, the faster a specialist will understand the situation.",
    },
    "complaint_ask_contact": {
        "ru": "Укажите, пожалуйста, телефон или email, чтобы мы могли связаться с вами и сообщить результат.",
        "kk": "Телефон немесе email көрсетіңізші, сізбен хабарласып, нәтижені айту үшін.",
        "en": "Please provide a phone number or email so we can contact you and share the outcome.",
    },
    "complaint_ready_to_confirm": {
        "ru": "Данные записал. Проверьте их и напишите «подтверждаю», когда будете готовы зарегистрировать обращение. После регистрации оно получит номер. Если хотите остановиться, напишите «отмена».",
        "kk": "Деректерді жаздым. Оларды тексеріп, өтінішті тіркеуге дайын болғанда «растаймын» деп жазыңыз. Тіркелгеннен кейін нөмір беріледі. Тоқтатқыңыз келсе, «бас тартамын» деп жазыңыз.",
        "en": "I've recorded the details. Please review them and write \"confirm\" when you're ready to register the request. It will get a reference number after registration. If you'd like to stop, write \"cancel\".",
    },
    "complaint_confirm_prompt": {
        "ru": "Чтобы зарегистрировать обращение, напишите «подтверждаю». Если передумали, напишите «отмена».",
        "kk": "Өтінішті тіркеу үшін «растаймын» деп жазыңыз. Ойыңыз өзгерсе, «бас тартамын» деп жазыңыз.",
        "en": "To register the request, write \"confirm\". If you've changed your mind, write \"cancel\".",
    },
    "complaint_registered": {
        "ru": "Готово, обращение зарегистрировано под номером {id}. Я передал его специалистам ТАТЭК. Сохраните номер: он поможет уточнить статус обращения.",
        "kk": "Дайын, өтініш {id} нөмірімен тіркелді. Оны ТАТЭК мамандарына жеткіздім. Нөмірді сақтаңыз: ол өтініштің мәртебесін нақтылауға көмектеседі.",
        "en": "Done, the request has been registered under number {id}. I've forwarded it to TATEK specialists. Please keep this number — it will help you check the request status.",
    },
    "knowledge_base_error": {
        "ru": "Сейчас не получается открыть материалы ТАТЭК. Это не значит, что по вашему вопросу нет информации. Попробуйте немного позже или уточните её у службы поддержки ТАТЭК.",
        "kk": "Қазір ТАТЭК материалдарын ашу мүмкін болмай тұр. Бұл сұрағыңыз бойынша ақпарат жоқ дегенді білдірмейді. Сәл кейінірек көріңіз немесе ТАТЭК қолдау қызметінен нақтылаңыз.",
        "en": "I can't open TATEK's materials right now. This doesn't mean there's no information on your question. Please try again shortly or check with TATEK support.",
    },
    "no_relevant_materials": {
        "ru": "Пока не вижу ответа на этот вопрос в доступных материалах ТАТЭК. Чтобы не дать вам неточную информацию, лучше уточнить его у службы поддержки. Могу помочь сформулировать обращение.",
        "kk": "Бұл сұраққа жауапты қолжетімді ТАТЭК материалдарынан таба алмай тұрмын. Дәл емес ақпарат бермеу үшін оны қолдау қызметінен нақтылаған дұрыс. Өтініш құрастыруға көмектесе аламын.",
        "en": "I don't see an answer to this in TATEK's available materials. To avoid giving you inaccurate information, it's best to check with support. I can help you draft a request.",
    },
}


def phrase(key: str, language: Language, **kwargs: object) -> str:
    template = PHRASES[key][language]
    return template.format(**kwargs) if kwargs else template
