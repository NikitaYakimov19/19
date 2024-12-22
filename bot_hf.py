import logging
import telebot
import multiprocessing
from telebot import types
from g4f.client import Client as G4FClient

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

API_KEY = '7691656738:AAFc5LSfp70mH7MektIwNFN3qaTCqM1aWeg'  # Замените на ваш API ключ Telegram
bot = telebot.TeleBot(API_KEY)

user_preferences = {}  # Словарь для сохранения предпочтений пользователей

def send_request(text: str, prompt: str, model: str, result_queue):
    try:
        client = G4FClient()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": f'{prompt}\n{text}'
                }
            ]
        )
        result_queue.put({'result': response.choices[0].message.content})
    except Exception as e:
        result_queue.put({'error': str(e)})

def answer(text: str, prompt: str, model: str = 'gpt-4o', limit: int = 60, timeout: int = 20) -> str | None:
    i = 1
    while i <= 15:  # Попробуем до 15 раз
        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=send_request, args=(text, prompt, model, result_queue))
        process.start()
        process.join(timeout=timeout)

        if process.is_alive():
            process.terminate()
            process.join()
        else:
            result = result_queue.get() if not result_queue.empty() else None

            if result is None:
                pass
            elif 'error' in result:
                logging.error(f"Ошибка при получении ответа: {result['error']}")
            else:
                return result['result'].strip()

        i += 1

    return None

# Создание клавиатуры для команд
def create_start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_button = types.KeyboardButton("/start")
    save_preferences_button = types.KeyboardButton("/get_preferences")
    add_preferences_button = types.KeyboardButton("/add_preferences")
    delete_preferences_button = types.KeyboardButton("/delete_preferences")
    ai_questions = types.KeyboardButton("/ai_questions")
    keyboard.add(start_button, ai_questions ,save_preferences_button, add_preferences_button,
                 delete_preferences_button)
    return keyboard


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Привет! Я могу помочь с вопросами о питании и здоровье. Выберите команду.',
                     reply_markup=create_start_keyboard())


@bot.message_handler(commands=['get_preferences'])
def get_preferences(message):
    user_id = message.from_user.id
    preferences = user_preferences.get(user_id, [])

    if preferences:
        preferences_message = "Ваши предпочтения в еде:\n" + "\n".join(
            f"{index + 1}. {pref}" for index, pref in enumerate(preferences)
        )
    else:
        preferences_message = "У вас нет предпочтений."

    bot.send_message(message.chat.id, preferences_message)


@bot.message_handler(commands=['add_preferences'])
def add_preferences(message):
    bot.send_message(message.chat.id, "Введите ваши предпочтения (например, 'Я не ем мясо'): ")
    bot.register_next_step_handler(message, process_add_preferences)


def process_preferences(message, user_id):
    # Получаем предпочтения от пользователя
    preferences = message.text.split(',')
    # Очищаем пробелы и формируем список
    cleaned_preferences = [pref.strip() for pref in preferences if pref.strip()]
    # Сохраняем предпочтения
    user_preferences[user_id] = cleaned_preferences
    bot.send_message(message.chat.id, "Ваши предпочтения сохранены.")

@bot.message_handler(commands=['get_preferences'])
def get_preferences(message):
    user_id = message.from_user.id
    preferences = user_preferences.get(user_id, [])
    preferences_message = "Ваши предпочтения в еде:\n" + "\n".join(preferences) if preferences else "У вас нет предпочтений."
    bot.send_message(message.chat.id, preferences_message)


def process_add_preferences(message):
    user_id = message.from_user.id
    preference = message.text

    if user_id not in user_preferences:
        user_preferences[user_id] = []

    user_preferences[user_id].append(preference)
    bot.send_message(message.chat.id, f"Предпочтение добавлено: {preference}")


@bot.message_handler(commands=['delete_preferences'])
def delete_preferences(message):
    user_id = message.from_user.id
    if user_id in user_preferences and user_preferences[user_id]:
        preferences_message = "Ваши предпочтения:\n" + "\n".join(
            f"{index + 1}. {pref}" for index, pref in enumerate(user_preferences[user_id])
        ) + "\nВведите номер предпочтения для удаления:"
        bot.send_message(message.chat.id, preferences_message)
        bot.register_next_step_handler(message, process_delete_preferences)
    else:
        bot.send_message(message.chat.id, "У вас нет предпочтений для удаления.")

        
def process_delete_preferences(message):
    user_id = message.from_user.id
    try:
        index = int(message.text) - 1
        if user_id in user_preferences and 0 <= index < len(user_preferences[user_id]):
            removed = user_preferences[user_id].pop(index)
            bot.send_message(message.chat.id, f"Предпочтение удалено: {removed}")
        else:
            raise ValueError("Неверный номер.")
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер предпочтения.")


@bot.message_handler(commands=['ai_questions'])
def handle_message(message):
    text = message.text
    user_id = message.from_user.id

    logging.info(f"Получено сообщение от пользователя: {text}")

    # Уведомляем пользователя о том, что ответ может занять некоторое время
    bot.send_message(message.chat.id, "Пожалуйста, подождите, я обрабатываю ваш запрос...")

    preferences = user_preferences.get(user_id, [])
    preferences_info = ", ".join(preferences) if preferences else "У вас нет предпочтений."

    prompt = f"Ты бот, который отвечает на вопросы о питании и диетах. У твоего пользователя есть предпочтения: {preferences_info}. Вот вопрос:"

    # Получаем ответ от ИИ
    ai_response = answer(text=text, prompt=prompt)

    if ai_response:
        bot.send_message(message.chat.id, ai_response)
    else:
        bot.send_message(message.chat.id, "Извините, я не смог обработать ваш запрос.")


if __name__ == '__main__':
    logging.info("Бот запущен и ожидает сообщений...")
    bot.polling(none_stop=True)