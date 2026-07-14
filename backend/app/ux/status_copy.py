"""Human-facing Telegram status strings for presence UX."""

STATUS_LOOKING = "Смотрю…"
STATUS_WORKING = "Работаю над задачей…"
STATUS_RESEARCHING = "Ищу информацию…"
STATUS_INTERRUPTED = "⚠️ Задача прервана"

UNSUPPORTED_PHOTO = (
    "Сейчас фото документов ещё не разбираю.\n"
    "Пришли DOCX, PDF или текст — сделаю по аналогии в фирменном стиле."
)
UNSUPPORTED_VOICE = (
    "Локальную расшифровку звонков (Whisper) ещё не подключил.\n"
    "Пока пришли текст или файл с саммари."
)
UNSUPPORTED_MEDIA = (
    "Этот тип вложения пока не обрабатываю.\n"
    "Пришли текст, DOCX или PDF."
)
