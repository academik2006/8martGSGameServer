from telebot import types
import telebot
import asyncio
import aiofiles
import time
from datetime import datetime, timezone
import threading
import logging
import sqlite3
from api_key import API_TOKEN
from datetime import datetime, timedelta


bot = telebot.TeleBot(API_TOKEN)
bot.delete_webhook()

gameName = "Spring Quiz Galeria Sushi"
#gameUrl = "https://academik2006.github.io/8martGSGameFront/"
gameUrl = "https://www.advent-sm.ru/"
bronzeMap = None
silverMap = None
goldMap = None
filenamebronze = 'bronze.txt'
filenamesilver = 'silver.txt'
filenamegold = 'gold.txt'
MAX_REMAINING_ATTEMPTS = 3
blocked_users = set()

logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)


def set_global_bronzeMap(value):
    global bronzeMap
    bronzeMap = value

def set_global_silverMap(value):
    global silverMap
    silverMap = value

def set_global_goldMap(value):
    global goldMap
    goldMap = value

def create_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        chat_id INTEGER,          
        last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        attempts_left INTEGER DEFAULT 3
    );
''')
    conn.commit()
    conn.close()


async def main():

    create_db()    

    try:
        set_global_bronzeMap (await readFileToMap(filenamebronze))        
        set_global_silverMap (await readFileToMap(filenamesilver))
        set_global_goldMap (await readFileToMap(filenamegold))        
    except Exception as e:
        print(f"Ошибка: {e}")

def create_webapp_keyboard(webapp_enabled=False):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        ('Правила игры', None),
        ('Условия акции', None),
    ]
    
    if webapp_enabled:
        webAppUrl = types.WebAppInfo(gameUrl)
        buttons.append(('Начать игру', webAppUrl))
    else:
        buttons.append(('Можно поиграть?', None))
    
    for text, web_app in buttons:
        btn = types.KeyboardButton(text=text, web_app=web_app)
        keyboard.add(btn)
    
    return keyboard   

rules_text = """
Тебя ждут вопросы, посвященные Международному женскому дню, 
и еще парочка о… прекрасной половине человечества (конечно же) 😉

За каждый правильный ответ ты получишь бонусные баллы ✨.
Складывай их, как комплименты в праздничный день. 

После <b>4</b> и <b>8</b> вопросов тебя ждет «несгораемая сумма» 🔥.

Можно забрать приз и выйти из игры красиво (прям как в песне Меладзе) 🎤, а можно рискнуть и продолжить путь к победе.

Тот, кто правильно ответит на <b>10-й вопрос</b>, заберет главный приз – 300 бонусных рублей от Мира Суши 🍣🥢. 
"""

conditions_text = """
<b> *Чтобы активировать призовые баллы, не забудь использовать индивидуальный промокод в момент оформления заказа до 30.04.2026 г. 
Открой для себя Мир Суши! </b> <a href="https://mirsushi.com/?utm_source=tg&utm_medium=game-mart">Мир суши</a> 
"""

@bot.message_handler(commands=['start']) #обрабатываем команду старт
def start_fun(message):        
    username = message.from_user.first_name 
    add_user_on_start(message.from_user.id, message.chat.id)      
    welcome_text = f"""
Добро пожаловать в интеллектуальное путешествие! 🚀✨

Весенний квиз от Мира Суши – это игра в формате «Кто хочет стать миллионером?» 🎬, но с праздничным настроением и женской логикой (она существует, мы проверяли 😉)!
""" 
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_webapp_keyboard(False), parse_mode="HTML")        
   

@bot.message_handler(func=lambda message: message.text == 'Можно поиграть?')
def handle_test_game_start(message):        
    user_id = message.from_user.id
    remaining_attempts = get_remaining_attempts(user_id)

    if remaining_attempts == 0:
        bot.send_message(message.chat.id, time_remaining_for_play(user_id))
        logger.info(f"Пользователь {message.chat.id} нажал кнопку можно поиграть и ему пришло нельзя и время ожидания {time_remaining_for_play(user_id)}")            
    else:
        remaining_attempts_text = 'шанс' if remaining_attempts == 1 else 'шанса'
        remaining_attempts_before_text = 'остался' if remaining_attempts == 1 else 'осталось'
        bot.send_message(message.chat.id, f'Ура! Сегодня у тебя {remaining_attempts_before_text} еще {remaining_attempts} {remaining_attempts_text}. Для запуска игры жми кнопку "Начать игру". Удачи', reply_markup=create_webapp_keyboard(True), parse_mode="HTML")                          
        logger.info(f"Пользователь {message.chat.id} нажал кнопку можно поиграть и ему пришло можно")            

@bot.message_handler(commands=['iaposhka']) #обрабатываем команду iaposhka
def start_fun(message):
   bot.send_message( message.chat.id, f"Всего осталось промокодов уровня золото {len(goldMap)}")
   bot.send_message( message.chat.id, f"Всего осталось промокодов уровня серебро {len(silverMap)}")
   bot.send_message( message.chat.id, f"Всего осталось промокодов уровня бронза {len(bronzeMap)}") 
       
     
@bot.message_handler(func=lambda message: message.text == 'Правила игры')
def handle_game_rules(message):        
    bot.send_message(message.chat.id, rules_text, parse_mode="HTML")
    logger.info(f"Пользователь {message.chat.id} нажал кнопку правила игры")            

@bot.message_handler(func=lambda message: message.text == 'Условия акции')
def handle_promotion_conditions(message):
    bot.send_message(message.chat.id, conditions_text, parse_mode="HTML")
    logger.info(f"Пользователь {message.chat.id} нажал кнопку условия акции")            

def get_remaining_attempts(user_id):
    try:
        conn = sqlite3.connect('users.db')  # Подключаемся к базе данных
        cursor = conn.cursor()

        # Запрашиваем запись о количестве оставшихся попыток для пользователя
        cursor.execute("SELECT attempts_left FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result is not None:
            remaining_attempts = result[0]
            return remaining_attempts
        else:
            return MAX_REMAINING_ATTEMPTS

    except Exception as e:
        return f'Ошибка при получении данных: {str(e)}'

    finally:
        conn.close()  # Закрываем соединение с базой данных

def add_user_on_start(user_id, chat_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Проверяем наличие пользователя в базе данных
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Новый пользователь, добавляем его с 3 попытками        
        cursor.execute(
            "INSERT INTO users (user_id, chat_id, attempts_left, last_played) VALUES (?, ?,?, CURRENT_TIMESTAMP)",
            (user_id, chat_id, 3)
            )        

        cursor.execute(
        "UPDATE users SET last_played = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user_id,)
            )  
        
        conn.commit()
        logger.info(f"Добавлен новый пользователь в базу данных {user_id}")
    else:
        logger.info(f"Пользователь {user_id} уже есть в базе")
        return
    
    conn.close()
        
def time_remaining_for_play(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()  
    cursor.execute('SELECT last_played FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result is None:
        return 'Пользователь не найден.'

    # Приводим last_played к объекту datetime и устанавливаем UTC-временную зону
    last_played_naive = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
    last_played_aware = last_played_naive.replace(tzinfo=timezone.utc)

    # Получаем текущее время в UTC
    current_time_utc = datetime.now(timezone.utc)

    # Рассчитываем разницу
    next_available_time = last_played_aware + timedelta(days=1)
    time_left = next_available_time - current_time_utc
        
    # Проверяем длительность оставшегося времени
    if time_left.total_seconds() <= 60:
        cursor.execute("UPDATE users SET attempts_left = 3 WHERE user_id = ?", (user_id,))
        conn.commit()
        message_text = f'У тебя снова есть 3 попытки. Жми кнопку "Можно играть" снова'
    else:
        # Преобразуем в часы и минуты
        hours_left = int(time_left.total_seconds() // 3600)
        minutes_left = int((time_left.total_seconds() % 3600) // 60)
        # Формируем текст уведомления
        message_text = f"""
✨ На сегодня достаточно подвигов. 
🌟 Отдохни, закажи роллы 🍣 и возвращайся завтра – мы будем ждать. 
Следующий запуск игры будет доступен через {hours_left} 🕑 часов и {minutes_left} 🕐 минут. 
Акулёнок пришлет напоминание. 🦈"""        
    conn.close()    
    return message_text
    

def reset_attempts_and_get_ready_users():    
    # Подключаемся к базе данных
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Получаем текущее время в UTC
    now_utc = datetime.now(timezone.utc)
    ready_users = []  # Список пользователей, готовых к игре

    try:
        cursor.execute("SELECT user_id, chat_id, last_played, attempts_left FROM users")
        rows = cursor.fetchall()                

        for row in rows:
            user_id = row[0]
            chat_id = row[1]
            last_played_str = row[2]
            attempts_left = row[3]

            # Приводим last_played к объекту datetime и задаём UTC-временную зону
            last_played = datetime.strptime(last_played_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

            # Определяем состояние игрока
            if now_utc >= last_played + timedelta(days=1) and attempts_left == 0:
                cursor.execute("UPDATE users SET attempts_left = 3 WHERE user_id = ?", (user_id,))                
                ready_users.append(chat_id)
                conn.commit()            
        
    except Exception as e:
        logger.error(f'Ошибка при выполнении запроса получения списка готовых к игре пользователей: {e}')
        raise        
    finally:
        conn.close()
    
    logger.info(f"В списке пользователей, готовых к игре {len(ready_users)} пользователей.")
    return ready_users    

  
@bot.message_handler(content_types="web_app_data") #получаем отправленные данные 
def answer(webAppMes):
   
   record_game_loss(webAppMes.from_user.id)   
   remaining_attempts = get_remaining_attempts(webAppMes.from_user.id)  
           
   if webAppMes.web_app_data.data == "GOLD":
        sendKeyboard(remaining_attempts,webAppMes)
        getPromo(webAppMes,goldMap,filenamegold, "золото")        
   elif webAppMes.web_app_data.data == "SILVER":        
        sendKeyboard(remaining_attempts,webAppMes)
        getPromo(webAppMes,silverMap,filenamesilver, "серебро")        
   elif webAppMes.web_app_data.data == "BRONZE":
        sendKeyboard(remaining_attempts,webAppMes)
        getPromo(webAppMes,bronzeMap,filenamebronze, "бронза")        
   elif webAppMes.web_app_data.data == "0":
        sendKeyboard(remaining_attempts,webAppMes)
   else:        
        bot.send_message(webAppMes.chat.id, "Недопустимое значение") 

def sendKeyboard (remaining_attempts, webAppMes):
    
    if remaining_attempts == 0:
        fail_text = """ 
✨ Сегодня ты уже блистал(а)! 
🌟Новая попытка – завтра. 
Немного интриги еще никому не вредило!  

<b>Акулёнок</b> 🦈 напомнит тебе, когда игра снова будет доступна."""  
               
        bot.send_message(webAppMes.chat.id, fail_text, reply_markup=create_webapp_keyboard(False), parse_mode="HTML")        
    else:
        attempts_left_text = f""" 
У тебя еще остался шанс улучшить результат сегодня. Жми кнопку "Можно играть" снова. 
"""  
        bot.send_message(webAppMes.chat.id, attempts_left_text, reply_markup=create_webapp_keyboard(False), parse_mode="HTML")        

def record_game_loss(user_id):
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Уменьшаем число попыток на единицу
    cursor.execute(
        "UPDATE users SET attempts_left = attempts_left - 1 WHERE user_id = ? AND attempts_left > 0",
        (user_id,)
    )

    # Обновляем время последней игры    
    cursor.execute(
        "UPDATE users SET last_played = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user_id,)
    )  

    conn.commit()
    conn.close()
    

def getPromo(webAppMes, my_map, filename,level):
    
    if level == "золото":
        conditions_text_short = "300 бонусных балов при заказе от 300 р!"
    elif level == "серебро":        
        conditions_text_short = "200 бонусных балов при заказе от 300 р!"
    elif level == "бронза":
        conditions_text_short = "100 бонусных баллов при заказе от 300 р!"    

    sizeMap = len(my_map)
    element = my_map[sizeMap-1]    
    image_path = 'logo_main.png'      
    
    with open(image_path, 'rb') as photo_file:
        bot.send_photo(webAppMes.chat.id, photo=photo_file, parse_mode="HTML")         
    
    bot.send_message(webAppMes.chat.id, f"Твой промокод {element} на {conditions_text_short}", parse_mode="HTML")       
    bot.send_message(webAppMes.chat.id, conditions_text, parse_mode="HTML")   
    my_map.pop(sizeMap-1)
    write_map_to_file(filename, my_map)  
    logger.info(f"Отправлен промокод уровня {level} пользователю {webAppMes.chat.id}")    

# Функция для отправки сообщения всем пользователям
def send_daily_reminder():
    logger.info("Функция send_daily_reminder запущена")
    
    # Получаем список пользователей, готовых к игре
    ready_users = reset_attempts_and_get_ready_users()

    dailyReminderText = """
🎉 Акулёнок напоминает:
Новый день – новые шансы в весеннем квизе от Мира Суши! 

На твоем балансе снова 3 попытки, чтобы продолжить наше интеллектуальное путешествие. 

Пристегни ремни, включай эрудицию (и немного женской логики ) и погнали к финишу!🎲 """

    # Отправляем уведомление каждому пользователю
    for chat_id in ready_users:
        if chat_id in blocked_users:
            logger.info(f"Пропущен заблокированный пользователь {chat_id}")
            continue
        
        try:
            # Отправляем сообщение пользователю
            bot.send_message(chat_id, dailyReminderText, parse_mode="HTML")
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Напоминание отправлено в {current_time}, пользователю {chat_id}")
        except Exception as e:
            error_message = str(e)
            if 'User has blocked this bot' in error_message:
                blocked_users.add(chat_id)
                logger.warning(f"Пользователь {chat_id} добавил бот в черный список и теперь считается заблокированным")
            else:
                logger.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {error_message}")
    
# Функция для запуска таймера
def run_timer():
    while True:
        try:
            send_daily_reminder()            
        except Exception as e:
            logger.error(f'Ошибка при попытке закуска функции send_daily_reminder в основном цикле: {e}')

        time.sleep(600)  # Проверять каждые 10 минут    

# Запускаем таймер в отдельном потоке
timer_thread = threading.Thread(target=run_timer)
timer_thread.start()

async def readFileToMap(file_path):
    map_result = {}
    line_number = 0

    async with aiofiles.open(file_path, mode='r') as file:
        async for line in file:
            map_result[line_number] = line.strip()
            line_number += 1

    print(len(map_result))
    return map_result

def write_map_to_file(filename, my_map):
    with open(filename, 'w') as file:
        for key, value in my_map.items():
            file.write(f'{value}\n')   
    print(len(my_map))       



if __name__ == "__main__":
    asyncio.run(main())
    bot.infinity_polling()