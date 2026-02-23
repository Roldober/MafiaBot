
import telebot
from telebot import types
import random
import threading
import time
import logging
import hashlib

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '8221831967:AAGaVkn259zFu1f-MUjJU-hfcRPZBpGIk94'
bot = telebot.TeleBot(TOKEN)

rooms = {}
user_states = {}

BOT_IDS = []
BOT_NAMES_PREFIX = "Бот"

def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_create = types.KeyboardButton("➕ Создать комнату")
    btn_find = types.KeyboardButton("🔍 Найти комнату")
    btn_available = types.KeyboardButton("📋 Доступные комнаты")
    btn_rules = types.KeyboardButton("📜 Правила")
    keyboard.add(btn_create, btn_find, btn_available, btn_rules)
    return keyboard

def cancel_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_cancel = types.KeyboardButton("❌ Отмена")
    keyboard.add(btn_cancel)
    return keyboard

def room_waiting_keyboard(room_id, creator_id, current_user_id):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    room = rooms.get(room_id)
    if not room:
        logger.debug(f"Attempted to create room_waiting_keyboard for non-existent room {room_id}. User {current_user_id}.")
        return main_menu_keyboard()

    if current_user_id == room['creator']:
        btn_start = types.KeyboardButton("▶️ Старт")
        btn_add_bots = types.KeyboardButton("🤖 Играть с ботами")
        keyboard.add(btn_start, btn_add_bots)
    
    players_count_btn = types.KeyboardButton(f"👥 Игроки в комнате {len(room['players'])}/{room['max_players']}")
    btn_leave = types.KeyboardButton("🚪 Выйти")
    keyboard.add(players_count_btn, btn_leave)
    
    if current_user_id == room['creator']:
        btn_delete = types.KeyboardButton("🗑️ Удалить комнату")
        keyboard.add(btn_delete)
    return keyboard

def get_player_game_keyboard(room_id, player_id):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    room = rooms.get(room_id)
    if not room:
        logger.debug(f"Attempted to create get_player_game_keyboard for non-existent room {room_id}. User {player_id}.")
        return main_menu_keyboard()
    
    player_role = room['players_roles'].get(player_id)
    
    if room['status'] == 'night':
        if player_id not in room['night_actions_made']:
            if player_role == 'Мафия':
                mafia_choices = [p_id for p_id in room['alive_players'] if p_id != player_id and room['players_roles'].get(p_id) != 'Мафия']
                for target_id in mafia_choices:
                    keyboard.add(types.KeyboardButton(f"🔪Убить {room['players'][target_id]}"))
            elif player_role == 'Доктор':
                doctor_choices = [p_id for p_id in room['alive_players']]
                for target_id in doctor_choices:
                    keyboard.add(types.KeyboardButton(f"💉Лечить {room['players'][target_id]}"))
            elif player_role == 'Шериф':
                sheriff_choices = [p_id for p_id in room['alive_players'] if p_id != player_id]
                for target_id in sheriff_choices:
                    keyboard.add(types.KeyboardButton(f"🔍Проверить {room['players'][target_id]}"))
            else:
                keyboard.add(types.KeyboardButton("💤Ждать утра"))
            
    elif room['status'] == 'voting':
        if player_id not in room['day_votes']:
            alive_players_for_vote = [p_id for p_id in room['alive_players'] if p_id != player_id]
            if alive_players_for_vote:
                for target_id in alive_players_for_vote:
                    keyboard.add(types.KeyboardButton(f"🗳️Голосовать за {room['players'][target_id]}"))
                keyboard.add(types.KeyboardButton("🔇Пропустить голосование"))
            else:
                keyboard.add(types.KeyboardButton("🤷‍♂️Нет кого голосовать"))

    players_count_btn = types.KeyboardButton(f"👥 Игроки в комнате ({len(room['alive_players'])}/{room['max_players']})")
    keyboard.add(players_count_btn)

    btn_leave_game = types.KeyboardButton("↪️ Выйти из игры")
    keyboard.add(btn_leave_game)

    return keyboard

MESSAGES = {
    'start_welcome': "Привет! Я бот для игры в Мафию. Выберите действие в меню.",
    'ask_players_count': "Напишите желаемое количество игроков (от 4 до 10).",
    'invalid_max_players': "Неверное количество игроков. Введите число от 4 до 10.",
    'room_created': "Комната создана.",
    'player_joined_room': "В комнату присоединился игрок.",
    'creator_deleted_room': "Создатель удалил комнату. Вы вернулись в главное меню.",
    'ask_room_id': "Введите ID комнаты чтобы присоединиться.",
    'room_not_found': "Такая комната не найдена.",
    'already_in_room': "Вы уже в этой комнате.",
    'room_full': "Комната полна.",
    'successfully_joined': "Вы успешно присоединились к комнате.",
    'left_room': "Вы вышли из комнаты.",
    'room_deleted_by_creator': "Вы удалили комнату.",
    'no_active_rooms': "Активных комнат нет.",
    'creator_left_room_transfer': "Создатель вышел из комнаты. Права создателя переданы другому игроку.",
    'list_available_rooms_title': "Список доступных комнат:",
    'unknown_command': "Неизвестная команда или действие. Пожалуйста, используйте кнопки меню.",
    'game_started': "Игра началась! Роли распределены.",
    'not_creator_to_start': "Вы не создатель активной комнаты, чтобы начать игру.",
    'not_enough_players_to_start': "Недостаточно игроков для старта. Минимум {min_players} игроков необходимо.",
    'not_in_room_for_leave': "Вы не находитесь ни в одной комнате.",
    'not_creator_to_delete': "Вы не создатель активной комнаты или такой комнаты нет.",
    'player_leave_room_notify': "Игрок {player_name} вышел из комнаты.",
    'creator_leave_room_new_creator_notify': "Игрок {old_creator_name} вышел из комнаты. Новый создатель: {new_creator_name}.",
    'chat_message_in_waiting': "💬 {sender_name}: {text}",
    'chat_message_in_game': "🗣️ {sender_name}: {text}",
    'cannot_chat_night': "🤫 Ночью мирным жителям запрещено говорить.",
    'your_role_is': "Ваша роль: *{role}*.",
    'mafia_partners': "Ваши напарники по мафии: {partners}.",
    'night_falls': "Город засыпает. Все жители закрывают глаза. ⏳ 1 минута.",
    'mafia_night_action': "Просыпается Мафия. Выберите, кого убить этой ночью.",
    'doctor_night_action': "Просыпается Доктор. Выберите, кого вылечить этой ночью.",
    'sheriff_night_action': "Просыпается Шериф. Выберите игрока, которого хотите проверить этой ночью.",
    'peaceful_night_wait': "Вы мирный житель. Спите спокойно.",
    'day_begins': "Город просыпается. Открывайте глаза.",
    'killed_player_day': "Этой ночью был убит *{player_name}* ({role_name}).",
    'no_one_killed_day': "Этой ночью никто не погиб.",
    'start_voting_day': "Начинается дневное голосование. Обсудите и выберите, кого вы хотите посадить. ⏳ 1 минута.",
    'sheriff_check_result': "Результат проверки Шерифа: *{player_name}* - это *{role_name}*.",
    'mafia_win': "Игра окончена. Мафия победила! Осталось {citizen_count} мирных жителей.",
    'citizens_win': "Игра окончена. Мирные жители победили! Вся мафия разоблачена.",
    'vote_tie_day': "Ничья в голосовании. Никто не был казнён.",
    'executed_player_day': "По итогам голосования был казнён *{player_name}* ({role_name}).",
    'no_execution_day': "Никто не был казнён по итогам голосования.",
    'you_already_acted': "Вы уже сделали свой ход.",
    'you_already_voted': "Вы уже проголосовали.",
    'message_to_players': "Сообщение от {sender_name}: {text}",
    'afk_message': "Вы были удалены из игры из-за бездействия.",
    'game_over_leave': "Вы покинули игру. Возвращаемся в главное меню.",
    'player_executed': "Игрок *{player_name}* был казнён по итогам голосования.",
    'player_killed_night': "Игрок *{player_name}* был убит ночью.",
    'doctor_saved_player': "Доктор спас игрока *{player_name}* этой ночью.",
    'action_confirmed': "Ваш выбор принят. Ожидаем действия других игроков.",
    'vote_confirmed': "Ваш голос принят. Ожидаем голосования других игроков.",
    'invalid_target_chosen': "Неверная цель. Выберите живого игрока из предложенных кнопок.",
    'you_are_out': "Вы выбыли из игры ({reason}). Возвращаемся в главное меню.",
    'rules_text': """
*Добро пожаловать в игру "Мафия"!*

**Цель игры:**
*   **Мирные жители:** Вычислить и "посадить" всех мафиози.
*   **Мафия:** Убить всех мирных жителей.

**Роли:**
*   **Мирный житель:** Просыпается днём, голосует за того, кого подозревает. Ночью спит.
*   **Мафия:** Знает друг друга. Ночью "убивает" одного мирного жителя. Днём притворяется мирным жителем и голосует.
*   **Шериф:** Просыпается ночью и "проверяет" одного игрока. Узнает его роль. Днём притворяется мирным жителем и голосует.
*   **Доктор:** Просыпается ночью и "лечит" одного игрока. Леченый игрок не может быть убит мафией этой ночью. Может лечить себя. Днём притворяется мирным жителем и голосует.

**Фазы игры:**
1.  **Ночь:** Все игроки "засыпают". Бот по очереди "будит" активные роли (Мафия, Доктор, Шериф) для выполнения их действий. Мирные жители "спят".
2.  **День:** Все игроки "просыпаются". Бот объявляет, кто погиб ночью (если погиб). Начинается обсуждение, во время которого игроки общаются в общем чате. Затем происходит голосование, во время которого игроки выбирают, кого они подозревают в принадлежности к мафии. Игрок с наибольшим количеством голосов "казнится" (выбывает из игры).

**Условия победы:**
*   **Мафия побеждает,** если количество мафиози становится равным или больше, чем количество мирных жителей. (Например, 1 мафия против 1 мирного, 2 мафии против 2 мирных).
*   **Мирные жители побеждают,** если все мафиози вычислены и устранены.

**Начало игры:**
Создатель комнаты нажимает "Старт", когда наберется достаточное количество игроков (минимум 4, максимум 10).
"""
}

def generate_bot_id(room_id, bot_number):
    return -(int(hashlib.sha1(f"{room_id}_bot_{bot_number}".encode()).hexdigest(), 16) % (10**9)) 

def add_bots_to_room(room_id, num_bots_to_add):
    room = rooms[room_id]
    added_bots = []
    for i in range(num_bots_to_add):
        bot_number = len(BOT_IDS) + 1 
        bot_id = generate_bot_id(room_id, bot_number)
        bot_name = f"{BOT_NAMES_PREFIX} {bot_number}"
        
        room['players'][bot_id] = bot_name
        BOT_IDS.append(bot_id)

        user_states[bot_id] = 'in_room'
        
        added_bots.append({'id': bot_id, 'name': bot_name})
    
    logger.info(f"Added {num_bots_to_add} bots to room {room_id}. Bots: {added_bots}")
    return added_bots

def assign_roles(player_ids):
    roles = []
    num_players = len(player_ids)

    num_mafia = 0
    num_sheriff = 1
    num_doctor = 1

    if 4 <= num_players <= 5:
        num_mafia = 1
    elif 6 <= num_players <= 9:
        num_mafia = 2
    elif num_players == 10:
        num_mafia = 3
    else:
        logger.error(f"Invalid number of players for role assignment: {num_players}")
        return {}
    
    num_peaceful = num_players - num_mafia - num_sheriff - num_doctor

    roles.extend(['Мафия'] * num_mafia)
    roles.extend(['Шериф'] * num_sheriff)
    roles.extend(['Доктор'] * num_doctor)
    roles.extend(['Мирный житель'] * num_peaceful)
    
    random.shuffle(roles)
    
    player_roles = dict(zip(player_ids, roles))
    logger.info(f"Roles assigned: {player_roles}")
    return player_roles

def get_remaining_timer_seconds(room_id):
    room = rooms.get(room_id)
    if not room or 'timer_start_time' not in room or 'timer_duration' not in room or room['timer_start_time'] is None:
        return None
    
    elapsed_time = time.time() - room['timer_start_time']
    remaining = max(0, int(room['timer_duration'] - elapsed_time))
    return remaining

def send_message_to_alive_players(room_id, text, keyboard_func=None, parse_mode=None, exclude_player_id=None):
    room = rooms.get(room_id)
    if not room: 
        logger.debug(f"Attempted to send message to alive players in non-existent room {room_id}.")
        return
    
    for p_id in list(room['alive_players']):
        if p_id in BOT_IDS: continue
        if p_id == exclude_player_id: continue
        try:
            keyboard = keyboard_func(room_id, p_id) if keyboard_func else None
            bot.send_message(p_id, text, reply_markup=keyboard, parse_mode=parse_mode)
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"ApiTelegramException при отправке сообщения игроку {p_id} в комнате {room_id}: {e}")
            if p_id in room['alive_players']:
                room['alive_players'].discard(p_id)
                if p_id in room['players']:
                    del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за ошибки отправки сообщения.")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке сообщения игроку {p_id} в комнате {room_id}: {e}")
            if p_id in room['alive_players']:
                room['alive_players'].discard(p_id)
                if p_id in room['players']:
                    del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за неизвестной ошибки отправки сообщения.")


def send_message_to_all_players(room_id, text, keyboard_func=None, parse_mode=None):
    room = rooms.get(room_id)
    if not room: 
        logger.debug(f"Attempted to send message to all players in non-existent room {room_id}.")
        return

    for p_id in list(room['players'].keys()):
        if p_id in BOT_IDS: continue
        try:
            keyboard = keyboard_func(room_id, room.get('creator'), p_id) if keyboard_func else None 
            bot.send_message(p_id, text, reply_markup=keyboard, parse_mode=parse_mode)
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"ApiTelegramException при отправке сообщения всем игрокам {p_id} в комнате {room_id}: {e}")
            if p_id in room['players']:
                room['alive_players'].discard(p_id)
                del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за ошибки отправки сообщения (для всех).")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке сообщения всем игрокам {p_id} в комнате {room_id}: {e}")
            if p_id in room['players']:
                room['alive_players'].discard(p_id)
                del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за неизвестной ошибки отправки сообщения (для всех).")

def update_timer_and_check_afk(room_id):
    room = rooms.get(room_id)
    if not room or room['timer_thread'] is None:
        logger.warning(f"Timer update called for non-existent or inactive room {room_id}. Or timer_thread is None.")
        return

    actual_current_time_left = get_remaining_timer_seconds(room_id)
    if actual_current_time_left is None:
        logger.error(f"Failed to get remaining timer seconds for room {room_id}. Stopping timer updates.")
        stop_room_timer(room_id)
        return

    if actual_current_time_left > 0 and room_id in rooms:
        room['timer_thread'] = threading.Timer(1, update_timer_and_check_afk, args=[room_id])
        room['timer_thread'].start()
    elif room_id in rooms:
        logger.info(f"Timer finished for room {room_id}. Processing AFK/actions.")
        if process_afk_players(room_id):
            return
        if room_id in rooms:
            if room['status'] == 'night':
                process_night_actions(room_id)
            elif room['status'] == 'voting':
                process_day_voting(room_id)

def process_afk_players(room_id):
    room = rooms.get(room_id)
    if not room: 
        logger.warning(f"process_afk_players called for non-existent room {room_id}.")
        return False

    players_to_remove = []
    
    if room['status'] == 'night':
        for p_id in room['alive_players']:
            if p_id not in room['night_actions_made'] and p_id not in BOT_IDS:
                players_to_remove.append(p_id)
    elif room['status'] == 'voting':
        for p_id in room['alive_players']:
            if p_id not in room['day_votes'] and p_id not in BOT_IDS:
                players_to_remove.append(p_id)
    
    for p_id in players_to_remove:
        if p_id in room['alive_players']:
            player_name = room['players'].get(p_id, "Неизвестный")
            room['alive_players'].discard(p_id)
            if p_id in room['players']:
                del room['players'][p_id]
            if p_id in room['last_sent_message']:
                del room['last_sent_message'][p_id]
            try:
                bot.send_message(p_id, MESSAGES['afk_message'], reply_markup=main_menu_keyboard())
                user_states[p_id] = None
            except telebot.apihelper.ApiTelegramException as e:
                logger.error(f"ApiTelegramException при отправке AFK сообщения игроку {p_id} в комнате {room_id}: {e}")
            except Exception as e:
                logger.error(f"Неизвестная ошибка при отправке AFK сообщения игроку {p_id} в комнате {room_id}: {e}")
            
            if room_id in rooms:
                send_message_to_alive_players(room_id, f"Игрок *{player_name}* был удален из игры за бездействие.",
                                              keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid), parse_mode='Markdown', exclude_player_id=p_id)
            logger.info(f"Игрок {player_name} ({p_id}) удален за бездействие в комнате {room_id}.")
    
    if room_id in rooms:
        game_over, winner = check_win_condition(room_id)
        if game_over:
            end_game(room_id, winner)
            return True
    elif not room_id in rooms:
        return True
    return False

def stop_room_timer(room_id):
    room = rooms.get(room_id)
    if room and 'timer_thread' in room and room['timer_thread']:
        room['timer_thread'].cancel()
        room['timer_thread'] = None
        room['timer_start_time'] = None
        room['timer_duration'] = None
        logger.info(f"Timer for room {room_id} stopped and reset.")

def start_game_logic(room_id):
    room = rooms[room_id]
    player_ids = list(room['players'].keys())
    
    if len(player_ids) < room['min_players']:
        try:
            bot.send_message(room['creator'], MESSAGES['not_enough_players_to_start'].format(min_players=room['min_players']),
                            reply_markup=room_waiting_keyboard(room_id, room['creator'], room['creator']))
        except Exception as e:
            logger.error(f"Error sending 'not_enough_players_to_start' to creator {room['creator']} in room {room_id}: {e}")
        logger.warning(f"Tried to start room {room_id} but not enough players ({len(player_ids)}). Game aborted.")
        return

    room['players_roles'] = assign_roles(player_ids)
    room['alive_players'] = set(player_ids)
    room['night_actions'] = {}
    room['night_actions_made'] = set()
    room['day_votes'] = {}
    room['status'] = 'night'
    room['game_round'] = 0
    room['timer_thread'] = None
    room['timer_start_time'] = None
    room['timer_duration'] = None
    room['last_sent_message'] = {}
    room['sheriff_check_results'] = {}

    mafia_players = [p_id for p_id, role in room['players_roles'].items() if role == 'Мафия']

    for p_id, role in room['players_roles'].items():
        if p_id in BOT_IDS: continue
        try:
            bot.send_message(p_id, MESSAGES['your_role_is'].format(role=role), parse_mode='Markdown')
            if role == 'Мафия':
                other_mafia_names = [room['players'][mp_id] for mp_id in mafia_players if mp_id != p_id]
                if other_mafia_names:
                    bot.send_message(p_id, MESSAGES['mafia_partners'].format(partners=", ".join(other_mafia_names)), parse_mode='Markdown')
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"ApiTelegramException при отправке роли игроку {p_id} в комнате {room_id}: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке роли игроку {p_id} в комнате {room_id}: {e}")
    
    send_night_message(room_id)
    logger.info(f"Game started in room {room_id} with players: {player_ids}.")

def send_night_message(room_id):
    room = rooms.get(room_id)
    if not room:
        logger.warning(f"Attempted to send night message to non-existent room {room_id}.")
        return

    room['game_round'] += 1
    room['night_actions'] = {}
    room['night_actions_made'] = set()
    room['sheriff_check_results'] = {}
    
    current_phase_duration = 60
    room['timer_start_time'] = time.time()
    room['timer_duration'] = current_phase_duration

    for p_id in list(room['alive_players']):
        if p_id in BOT_IDS: 
            handle_bot_night_action(room_id, p_id)
            continue

        player_role = room['players_roles'].get(p_id)
        message_text = MESSAGES['night_falls']
        
        if player_role == 'Мафия':
            message_text += f"\n{MESSAGES['mafia_night_action']}"
        elif player_role == 'Доктор':
            message_text += f"\n{MESSAGES['doctor_night_action']}"
        elif player_role == 'Шериф':
            message_text += f"\n{MESSAGES['sheriff_night_action']}"
        else:
            message_text += f"\n{MESSAGES['peaceful_night_wait']}"
        
        try:
            sent_message = bot.send_message(p_id, message_text, reply_markup=get_player_game_keyboard(room_id, p_id))
            room['last_sent_message'][p_id] = sent_message.message_id
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"ApiTelegramException при отправке ночного сообщения игроку {p_id} в комнате {room_id}: {e}")
            if p_id in room['alive_players']:
                room['alive_players'].discard(p_id)
                if p_id in room['players']:
                    del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за ошибки отправки ночного сообщения.")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке ночного сообщения игроку {p_id} в комнате {room_id}: {e}")
            if p_id in room['alive_players']:
                room['alive_players'].discard(p_id)
                if p_id in room['players']:
                    del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за неизвестной ошибки отправки ночного сообщения.")
            
    if room_id in rooms:
        room['timer_thread'] = threading.Timer(1, update_timer_and_check_afk, args=[room_id])
        room['timer_thread'].start()
        logger.info(f"Night phase started for room {room_id}, round {room['game_round']}.")
    else:
        logger.warning(f"Room {room_id} was removed before timer could be started for night phase.")


def check_all_night_actions_made(room_id):
    room = rooms.get(room_id)
    if not room: return False
    
    required_to_act_count = len(room['alive_players'])
    
    all_acted = len(room['night_actions_made']) >= required_to_act_count
    logger.debug(f"Room {room_id}: All night actions made: {all_acted}. Done: {len(room['night_actions_made'])}, Alive: {required_to_act_count}")
    return all_acted


def process_night_actions(room_id):
    room = rooms.get(room_id)
    if not room or room['status'] != 'night':
        logger.warning(f"process_night_actions called for non-existent or wrong status room {room_id}")
        return
    
    stop_room_timer(room_id)
    
    mafia_target_votes = {}
    doctor_heals = {}
    sheriff_checks = {}

    for p_id in list(room['alive_players']):
        if p_id in room['night_actions']:
            target_id = room['night_actions'][p_id]
            role = room['players_roles'].get(p_id)
            if role == 'Мафия':
                mafia_target_votes[target_id] = mafia_target_votes.get(target_id, 0) + 1
            elif role == 'Доктор':
                doctor_heals[target_id] = doctor_heals.get(target_id, 0) + 1
            elif role == 'Шериф':
                sheriff_checks[p_id] = target_id
    logger.info(f"Night actions for room {room_id}: Mafia votes: {mafia_target_votes}, Doctor heals: {doctor_heals}, Sheriff checks: {sheriff_checks}")

    killed_by_mafia = None
    if mafia_target_votes:
        max_mafia_votes = 0
        potential_mafia_targets = []
        for target, votes in mafia_target_votes.items():
            if votes > max_mafia_votes:
                max_mafia_votes = votes
                potential_mafia_targets = [target]
            elif votes == max_mafia_votes:
                potential_mafia_targets.append(target)
        
        killed_by_mafia = random.choice(potential_mafia_targets) if potential_mafia_targets else None
    
    healed_player = None
    if doctor_heals:
        max_doctor_heals = 0
        potential_heals = []
        for target, heals in doctor_heals.items():
            if heals > max_doctor_heals:
                max_doctor_heals = heals
                potential_heals = [target]
            elif heals == max_doctor_heals:
                potential_heals.append(target)
        
        healed_player = random.choice(potential_heals) if potential_heals else None

    killed_player_id = None
    night_summary_messages = [MESSAGES['day_begins']]
    
    if killed_by_mafia:
        if killed_by_mafia == healed_player:
            night_summary_messages.append(MESSAGES['doctor_saved_player'].format(player_name=room['players'].get(healed_player, "Неизвестный")))
            logger.info(f"Player {room['players'].get(healed_player, 'Unknown')} was healed by doctor in room {room_id}.")
        else:
            night_summary_messages.append(MESSAGES['player_killed_night'].format(player_name=room['players'].get(killed_by_mafia, "Неизвестный")))
            killed_player_id = killed_by_mafia
            logger.info(f"Player {room['players'].get(killed_by_mafia, 'Unknown')} was killed by mafia in room {room_id}.")
    else:
        night_summary_messages.append(MESSAGES['no_one_killed_day'])
        logger.info(f"No one was killed in room {room_id} this night.")
        
    send_message_to_alive_players(room_id, "\n".join(night_summary_messages), parse_mode='Markdown')

    for sheriff_id, target_id in sheriff_checks.items():
        if sheriff_id in room['alive_players'] and target_id in room['alive_players']:
            target_role = room['players_roles'].get(target_id)
            if sheriff_id in BOT_IDS:
                if sheriff_id not in room['sheriff_check_results']:
                    room['sheriff_check_results'][sheriff_id] = {}
                room['sheriff_check_results'][sheriff_id][target_id] = target_role
                logger.info(f"Бот-шериф {room['players'].get(sheriff_id, 'Unknown')} проверил {room['players'].get(target_id, 'Unknown')} как {target_role} в комнате {room_id}.")
            else:
                try:
                    bot.send_message(sheriff_id, MESSAGES['sheriff_check_result'].format(
                        player_name=room['players'].get(target_id, "Неизвестный"), role_name=target_role), parse_mode='Markdown')
                    logger.info(f"Шериф {room['players'].get(sheriff_id, 'Unknown')} проверил {room['players'].get(target_id, 'Unknown')} как {target_role} в комнате {room_id}.")
                except telebot.apihelper.ApiTelegramException as e:
                    logger.error(f"ApiTelegramException при отправке результата шерифу {sheriff_id} в комнате {room_id}: {e}")
                except Exception as e:
                    logger.error(f"Неизвестная ошибка при отправке результата шерифу {sheriff_id} в комнате {room_id}: {e}")

    if killed_player_id:
        if killed_player_id in room['alive_players']:
            killed_player_name = room['players'].get(killed_player_id, "Неизвестный")
            killed_player_role = room['players_roles'].get(killed_player_id, "Неизвестный")

            room['alive_players'].discard(killed_player_id)
            if killed_player_id in room['players']:
                del room['players'][killed_player_id]
            if killed_player_id in room['last_sent_message']:
                del room['last_sent_message'][killed_player_id]

            if killed_player_id not in BOT_IDS:
                try:
                    bot.send_message(killed_player_id, MESSAGES['you_are_out'].format(reason=f"был убит мафией (ваша роль: {killed_player_role})"), 
                                     reply_markup=main_menu_keyboard(), parse_mode='Markdown')
                    user_states[killed_player_id] = None
                except telebot.apihelper.ApiTelegramException as e:
                    logger.error(f"ApiTelegramException при отправке сообщения 'вы выбыли' игроку {killed_player_id} в комнате {room_id}: {e}")
                except Exception as e:
                    logger.error(f"Неизвестная ошибка при отправке сообщения 'вы выбыли' игроку {killed_player_id} в комнате {room_id}: {e}")

            logger.info(f"Player {killed_player_name} ({killed_player_id}) removed from alive players and main players list in room {room_id} (killed by mafia).")

    if process_afk_players(room_id):
        return

    if room_id in rooms:
        game_over, winner = check_win_condition(room_id)
        if game_over:
            end_game(room_id, winner, killed_player_id)
        else:
            room['status'] = 'day'
            send_day_message(room_id, killed_player_id)
    else:
        logger.info(f"Room {room_id} was removed after night actions due to no players left.")
    logger.info(f"Night phase ended for room {room_id}.")

def send_day_message(room_id, killed_player_id):
    room = rooms.get(room_id)
    if not room:
        logger.warning(f"Attempted to send day message to non-existent room {room_id}.")
        return

    current_phase_duration = 60
    room['timer_start_time'] = time.time()
    room['timer_duration'] = current_phase_duration

    if room_id in rooms:
        start_day_voting(room_id)
        logger.info(f"Day phase started for room {room_id}.")
    else:
        logger.warning(f"Room {room_id} was removed before day voting could be started.")

def check_all_day_votes_made(room_id):
    room = rooms.get(room_id)
    if not room: return False
    
    all_voted = len(room['day_votes']) == len(room['alive_players'])
    logger.debug(f"Room {room_id}: All day votes made: {all_voted}. Done: {len(room['day_votes'])}, Alive: {len(room['alive_players'])}")
    return all_voted


def start_day_voting(room_id):
    room = rooms.get(room_id)
    if not room:
        logger.warning(f"Attempted to start day voting for non-existent room {room_id}.")
        return

    room['status'] = 'voting'
    room['day_votes'] = {}
    
    current_phase_duration = 60
    room['timer_start_time'] = time.time()
    room['timer_duration'] = current_phase_duration

    for p_id in list(room['alive_players']):
        if p_id in BOT_IDS:
            handle_bot_day_vote(room_id, p_id)
            continue

        try:
            sent_message = bot.send_message(p_id, MESSAGES['start_voting_day'], reply_markup=get_player_game_keyboard(room_id, p_id))
            room['last_sent_message'][p_id] = sent_message.message_id
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"ApiTelegramException при отправке сообщения о голосовании игроку {p_id} в комнате {room_id}: {e}")
            if p_id in room['alive_players']:
                room['alive_players'].discard(p_id)
                if p_id in room['players']:
                    del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за ошибки отправки сообщения о голосовании.")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке сообщения о голосованию игроку {p_id} в комнате {room_id}: {e}")
            if p_id in room['alive_players']:
                room['alive_players'].discard(p_id)
                if p_id in room['players']:
                    del room['players'][p_id]
                if p_id in room['last_sent_message']:
                    del room['last_sent_message'][p_id]
                logger.info(f"Игрок {p_id} удален из игры в комнате {room_id} из-за неизвестной ошибки отправки сообщения о голосовании.")
            
    if room_id in rooms:
        room['timer_thread'] = threading.Timer(1, update_timer_and_check_afk, args=[room_id])
        room['timer_thread'].start()
        logger.info(f"Voting phase started for room {room_id}.")
    else:
        logger.warning(f"Room {room_id} was removed before timer could be started for voting phase.")


def process_day_voting(room_id):
    room = rooms.get(room_id)
    if not room or room['status'] != 'voting':
        logger.warning(f"process_day_voting called for non-existent or wrong status room {room_id}")
        return
    
    stop_room_timer(room_id)
    
    vote_counts = {}
    for voter_id, target_id in room['day_votes'].items():
        if target_id is not None and target_id in room['alive_players']:
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
            
    executed_player_id = None
    if vote_counts:
        max_votes = 0
        potential_targets = []
        for target, votes in vote_counts.items():
            if votes > max_votes:
                max_votes = votes
                potential_targets = [target]
            elif votes == max_votes:
                potential_targets.append(target)
        
        if len(potential_targets) == 1:
            executed_player_id = potential_targets[0]
            logger.info(f"Player {room['players'].get(executed_player_id, 'Unknown')} selected for execution by vote in room {room_id}.")
        else:
            send_message_to_alive_players(room_id, MESSAGES['vote_tie_day'], keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid))
            logger.info(f"Vote tie in room {room_id}.")

    if executed_player_id:
        executed_player_name = room['players'].get(executed_player_id, "Неизвестный")
        executed_player_role = room['players_roles'].get(executed_player_id, "Неизвестный")
        
        if executed_player_id in room['alive_players']:
            room['alive_players'].discard(executed_player_id)
            if executed_player_id in room['players']:
                del room['players'][executed_player_id]
            if executed_player_id in room['last_sent_message']:
                del room['last_sent_message'][executed_player_id]
            
            if executed_player_id not in BOT_IDS:
                try:
                    bot.send_message(executed_player_id, MESSAGES['you_are_out'].format(reason=f"был казнён голосованием (ваша роль: {executed_player_role})"), 
                                     reply_markup=main_menu_keyboard(), parse_mode='Markdown')
                    user_states[executed_player_id] = None
                except telebot.apihelper.ApiTelegramException as e:
                    logger.error(f"ApiTelegramException при отправке сообщения 'вы выбыли' игроку {executed_player_id} в комнате {room_id}: {e}")
                except Exception as e:
                    logger.error(f"Неизвестная ошибка при отправке сообщения 'вы выбыли' игроку {executed_player_id} в комнате {room_id}: {e}")

            logger.info(f"Player {executed_player_name} ({executed_player_id}) ({executed_player_role}) was executed in room {room_id}.")
        
        send_message_to_alive_players(room_id, MESSAGES['executed_player_day'].format(
            player_name=executed_player_name, role_name=executed_player_role), parse_mode='Markdown', keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid))
        
    else:
        if not vote_counts or len(potential_targets) > 1:
             send_message_to_alive_players(room_id, MESSAGES['no_execution_day'], keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid))
             logger.info(f"No execution in room {room_id} (no votes or tie).")

    if process_afk_players(room_id):
        return
        
    if room_id in rooms:
        game_over, winner = check_win_condition(room_id)
        if game_over:
            end_game(room_id, winner, executed_player_id)
        else:
            room['status'] = 'night'
            send_night_message(room_id)
    else:
        logger.info(f"Room {room_id} was removed after day voting due to no players left.")
    logger.info(f"Day phase ended for room {room_id}.")

def check_win_condition(room_id):
    room = rooms.get(room_id)
    if not room: 
        logger.warning(f"check_win_condition called for non-existent room {room_id}.")
        return False, None
    
    mafia_count = sum(1 for p_id in room['alive_players'] if room['players_roles'].get(p_id) == 'Мафия')
    citizen_count = sum(1 for p_id in room['alive_players'] if room['players_roles'].get(p_id) != 'Мафия')
    
    logger.debug(f"Win condition check for room {room_id}: Mafia alive: {mafia_count}, Citizens alive: {citizen_count}")

    if mafia_count >= citizen_count and mafia_count > 0:
        logger.info(f"Mafia wins in room {room_id}: Mafia count ({mafia_count}) >= Citizen count ({citizen_count}).")
        return True, 'Мафия'
    
    elif mafia_count == 0 and citizen_count > 0:
        logger.info(f"Citizens win in room {room_id}: No Mafia left, Citizens ({citizen_count}) remain.")
        return True, 'Мирные жители'
    
    if not room['alive_players'] and mafia_count == 0 and citizen_count == 0:
        logger.info(f"Game over in room {room_id}: No players left. No clear winner.")
        return True, 'No Winner'
        
    return False, None

def end_game(room_id, winner, last_removed_player_id=None):
    room = rooms.get(room_id)
    if not room:
        logger.warning(f"end_game called for non-existent room {room_id}")
        return

    stop_room_timer(room_id)

    mafia_count_at_end = sum(1 for p_id in room['alive_players'] if room['players_roles'].get(p_id) == 'Мафия')
    citizen_count_at_end = sum(1 for p_id in room['alive_players'] if room['players_roles'].get(p_id) != 'Мафия')
    
    winner_message = ""

    if winner == 'Мафия':
        winner_message = MESSAGES['mafia_win'].format(citizen_count=citizen_count_at_end)
    elif winner == 'Мирные жители':
        winner_message = MESSAGES['citizens_win']
    elif winner == 'No Winner':
        winner_message = "Игра завершилась, но победитель не определен (возможно, все вышли)."
    
    logger.info(f"Game ended in room {room_id}. Winner: {winner}. Mafia alive: {mafia_count_at_end}, Citizens alive: {citizen_count_at_end}.")
    
    players_to_notify = list(room['players'].keys()) 
    final_main_menu_keyboard = main_menu_keyboard()

    for p_id in players_to_notify:
        if p_id in BOT_IDS: continue
        try:
            bot.send_message(p_id, winner_message, reply_markup=final_main_menu_keyboard, parse_mode='Markdown')
            user_states[p_id] = None
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"ApiTelegramException при отправке сообщения о завершении игры игроку {p_id} в комнате {room_id}: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при отправке сообщения о завершении игры игроку {p_id} в комнате {room_id}: {e}")
            
    time.sleep(1) 
    if room_id in rooms:
        del rooms[room_id]
        logger.info(f"Room {room_id} deleted after game end.")
    else:
        logger.warning(f"Attempted to delete room {room_id} after game end, but it was already deleted.")

def handle_bot_night_action(room_id, bot_id):
    room = rooms.get(room_id)
    if not room or bot_id not in room['alive_players']: return
    
    bot_role = room['players_roles'].get(bot_id)
    alive_players_without_self = [p_id for p_id in room['alive_players'] if p_id != bot_id]
    
    if not alive_players_without_self:
        room['night_actions_made'].add(bot_id)
        return

    if bot_role == 'Мафия':
        targets = [p_id for p_id in alive_players_without_self if room['players_roles'].get(p_id) != 'Мафия']
        if targets:
            target_id = random.choice(targets)
            room['night_actions'][bot_id] = target_id
            logger.info(f"Бот {room['players'][bot_id]} (Мафия) выбрал убить {room['players'][target_id]} в комнате {room_id}.")
        else:
            logger.info(f"Бот {room['players'][bot_id]} (Мафия) не нашел цель для убийства в комнате {room_id}.")
    elif bot_role == 'Доктор':
        target_id = random.choice(alive_players_without_self + [bot_id])
        room['night_actions'][bot_id] = target_id
        logger.info(f"Бот {room['players'][bot_id]} (Доктор) выбрал лечить {room['players'][target_id]} в комнате {room_id}.")
    elif bot_role == 'Шериф':
        target_id = random.choice(alive_players_without_self)
        room['night_actions'][bot_id] = target_id
        logger.info(f"Бот {room['players'][bot_id]} (Шериф) выбрал проверить {room['players'][target_id]} в комнате {room_id}.")
    
    room['night_actions_made'].add(bot_id)
    
    if check_all_night_actions_made(room_id):
        logger.info(f"All night actions made in room {room_id}. Forcing next phase.")
        stop_room_timer(room_id)
        if room_id in rooms:
            process_night_actions(room_id)
        return

def handle_bot_day_vote(room_id, bot_id):
    room = rooms.get(room_id)
    if not room or bot_id not in room['alive_players']: return

    alive_players_for_vote = [p_id for p_id in room['alive_players'] if p_id != bot_id]
    
    if not alive_players_for_vote:
        room['day_votes'][bot_id] = None
        room['night_actions_made'].add(bot_id)
        return

    target_id = None
    bot_role = room['players_roles'].get(bot_id)
    
    if bot_role == 'Шериф' and room.get('sheriff_check_results', {}).get(bot_id):
        for checked_player_id, checked_role in room['sheriff_check_results'][bot_id].items():
            if checked_role == 'Мафия' and checked_player_id in alive_players_for_vote:
                target_id = checked_player_id
                logger.info(f"Бот {room['players'][bot_id]} (Шериф) голосует за обнаруженную мафию: {room['players'][target_id]} в комнате {room_id}.")
                bot_chat_message(room_id, bot_id, f"Я подозреваю, что {room['players'][target_id]} - мафия. Нужно голосовать за него!")
                break
    
    if not target_id:
        target_id = random.choice(alive_players_for_vote + [None])
        if target_id:
            bot_chat_message(room_id, bot_id, f"Думаю, мы должны проголосовать за {room['players'][target_id]}.")
        else:
            bot_chat_message(room_id, bot_id, "Я пока не уверен в своем выборе. Пропускаю голосование.")


    room['day_votes'][bot_id] = target_id
    
    if target_id:
        logger.info(f"Бот {room['players'][bot_id]} проголосовал за {room['players'][target_id]} в комнате {room_id}.")
    else:
        logger.info(f"Бот {room['players'][bot_id]} пропустил голосование в комнате {room_id}.")
        
    if check_all_day_votes_made(room_id):
        logger.info(f"All day votes made in room {room_id}. Forcing next phase.")
        stop_room_timer(room_id)
        if room_id in rooms:
            process_day_voting(room_id)

def bot_chat_message(room_id, bot_id, text):
    room = rooms.get(room_id)
    if not room: return
    
    bot_name = room['players'].get(bot_id, "Бот")
    
    send_message_to_alive_players(room_id, MESSAGES['chat_message_in_game'].format(sender_name=bot_name, text=text), 
                                  keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid), parse_mode='Markdown')
    logger.info(f"Бот {bot_name} ({bot_id}) отправил сообщение в комнате {room_id}: '{text}'")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.from_user.id] = None
    bot.send_message(message.chat.id, MESSAGES['start_welcome'], reply_markup=main_menu_keyboard())
    logger.info(f"User {message.from_user.id} started bot.")

@bot.message_handler(func=lambda message: message.text == "➕ Создать комнату")
def handle_create_room_button(message):
    user_states[message.from_user.id] = 'awaiting_max_players_count'
    bot.send_message(message.chat.id, MESSAGES['ask_players_count'], reply_markup=cancel_keyboard())
    logger.info(f"User {message.from_user.id} clicked 'Create room'.")

@bot.message_handler(func=lambda message: message.text == "❌ Отмена" and user_states.get(message.from_user.id) == 'awaiting_max_players_count')
def handle_cancel_create_room(message):
    user_states[message.from_user.id] = None
    bot.send_message(message.chat.id, "Создание комнаты отменено.", reply_markup=main_menu_keyboard())
    logger.info(f"User {message.from_user.id} cancelled room creation.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'awaiting_max_players_count')
def process_max_players_count(message):
    try:
        max_players = int(message.text)

        if not (4 <= max_players <= 10):
            bot.send_message(message.chat.id, MESSAGES['invalid_max_players'], reply_markup=cancel_keyboard())
            logger.warning(f"User {message.from_user.id} entered invalid max_players: {message.text}")
            return

        room_id = ''.join(random.choices('0123456789ABCDEF', k=4))
        while room_id in rooms:
            room_id = ''.join(random.choices('0123456789ABCDEF', k=4))

        rooms[room_id] = {
            'creator': message.from_user.id,
            'min_players': 4,
            'max_players': max_players,
            'players': {message.from_user.id: message.from_user.first_name},
            'status': 'waiting',
            'chat_id': message.chat.id
        }
        user_states[message.from_user.id] = 'in_room'
        bot.send_message(message.chat.id, f"{MESSAGES['room_created']}\nID: `{room_id}`",
                        parse_mode='Markdown', reply_markup=room_waiting_keyboard(room_id, message.from_user.id, message.from_user.id))
        logger.info(f"Room {room_id} created by {message.from_user.first_name} ({message.from_user.id}) with {max_players} max players.")

    except (ValueError):
        bot.send_message(message.chat.id, MESSAGES['invalid_max_players'], reply_markup=cancel_keyboard())
        logger.warning(f"User {message.from_user.id} entered non-numeric max_players: {message.text}")

@bot.message_handler(func=lambda message: message.text == "🔍 Найти комнату")
def handle_find_room_button(message):
    user_states[message.from_user.id] = 'awaiting_room_id'
    bot.send_message(message.chat.id, MESSAGES['ask_room_id'], reply_markup=cancel_keyboard())
    logger.info(f"User {message.from_user.id} clicked 'Find room'.")

@bot.message_handler(func=lambda message: message.text == "❌ Отмена" and user_states.get(message.from_user.id) == 'awaiting_room_id')
def handle_cancel_find_room(message):
    user_states[message.from_user.id] = None
    bot.send_message(message.chat.id, "Поиск комнаты отменен.", reply_markup=main_menu_keyboard())
    logger.info(f"User {message.from_user.id} cancelled room search.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'awaiting_room_id')
def process_room_id_for_join(message):
    room_id = message.text.upper().strip()

    if room_id not in rooms or rooms[room_id]['status'] != 'waiting':
        bot.send_message(message.chat.id, MESSAGES['room_not_found'], reply_markup=main_menu_keyboard())
        user_states[message.from_user.id] = None
        logger.warning(f"User {message.from_user.id} tried to join non-existent or full room {room_id}.")
        return

    room = rooms[room_id]
    if message.from_user.id in room['players']:
        bot.send_message(message.chat.id, MESSAGES['already_in_room'], reply_markup=room_waiting_keyboard(room_id, room['creator'], message.from_user.id))
        user_states[message.from_user.id] = 'in_room'
        logger.info(f"User {message.from_user.id} already in room {room_id}.")
        return

    if len(room['players']) >= room['max_players']:
        bot.send_message(message.chat.id, MESSAGES['room_full'], reply_markup=main_menu_keyboard())
        user_states[message.from_user.id] = None
        logger.warning(f"User {message.from_user.id} tried to join full room {room_id}.")
        return

    room['players'][message.from_user.id] = message.from_user.first_name
    user_states[message.from_user.id] = 'in_room'
    bot.send_message(message.chat.id, MESSAGES['successfully_joined'], reply_markup=room_waiting_keyboard(room_id, room['creator'], message.from_user.id))

    for player_id in list(room['players']):
        if player_id in BOT_IDS: continue
        if player_id != message.from_user.id:
            if room_id in rooms:
                bot.send_message(player_id, f"{MESSAGES['player_joined_room']} {message.from_user.first_name}.",
                                reply_markup=room_waiting_keyboard(room_id, rooms[room_id]['creator'], player_id))
            else:
                logger.warning(f"Room {room_id} was removed while notifying players about new join. Player {player_id}.")
    logger.info(f"User {message.from_user.id} ({message.from_user.first_name}) joined room {room_id}.")

@bot.message_handler(func=lambda message: message.text == "📋 Доступные комнаты")
def handle_available_rooms_button(message):
    if not rooms:
        bot.send_message(message.chat.id, MESSAGES['no_active_rooms'], reply_markup=main_menu_keyboard())
        return

    room_list_text = MESSAGES['list_available_rooms_title'] + "\n"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    found_joinable_room = False

    for room_id, room_data in list(rooms.items()): 
        if room_data['status'] == 'waiting' and len(room_data['players']) < room_data['max_players']:
            found_joinable_room = True
            room_list_text += (f"ID: `{room_id}` (Игроков: {len(room_data['players'])}/{room_data['max_players']})\n"
                               f"Создатель: {rooms[room_id]['players'].get(rooms[room_id]['creator'], 'Неизвестный')}\n")
            keyboard.add(types.InlineKeyboardButton(f"ID: {room_id} ({len(room_data['players'])}/{room_data['max_players']})", callback_data=f"join_{room_id}"))

    if not found_joinable_room:
        bot.send_message(message.chat.id, MESSAGES['no_active_rooms'], reply_markup=main_menu_keyboard())
        logger.info(f"User {message.from_user.id} requested available rooms, none found.")
    else:
        bot.send_message(message.chat.id, room_list_text, parse_mode='Markdown', reply_markup=keyboard)
        logger.info(f"User {message.from_user.id} requested available rooms, {len(rooms)} found.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('join_'))
def callback_join_room(call):
    room_id = call.data.split('_')[1]
    message = call.message

    bot.answer_callback_query(call.id, "Обработка запроса...")
    logger.info(f"User {call.from_user.id} tried to join room {room_id} via inline button.")

    if room_id not in rooms or rooms[room_id]['status'] != 'waiting':
        bot.send_message(message.chat.id, MESSAGES['room_not_found'], reply_markup=main_menu_keyboard())
        return

    room = rooms[room_id]
    if call.from_user.id in room['players']:
        bot.send_message(message.chat.id, MESSAGES['already_in_room'], reply_markup=room_waiting_keyboard(room_id, room['creator'], call.from_user.id))
        return

    if len(room['players']) >= room['max_players']:
        bot.send_message(message.chat.id, MESSAGES['room_full'], reply_markup=main_menu_keyboard())
        return

    room['players'][call.from_user.id] = call.from_user.first_name
    user_states[call.from_user.id] = 'in_room'
    bot.send_message(message.chat.id, MESSAGES['successfully_joined'], reply_markup=room_waiting_keyboard(room_id, room['creator'], call.from_user.id))

    for player_id in list(room['players']):
        if player_id in BOT_IDS: continue
        if player_id != call.from_user.id:
            if room_id in rooms:
                bot.send_message(player_id, f"{MESSAGES['player_joined_room']} {call.from_user.first_name}.",
                                reply_markup=room_waiting_keyboard(room_id, rooms[room_id]['creator'], player_id))
            else:
                logger.warning(f"Room {room_id} was removed while notifying players about new join via inline. Player {player_id}.")

    bot.edit_message_reply_markup(message.chat.id, message.message_id, reply_markup=None)

@bot.message_handler(func=lambda message: message.text == "🚪 Выйти")
def handle_leave_room_button(message):
    user_id = message.from_user.id
    current_room_id = None
    for r_id, r_data in rooms.items():
        if user_id in r_data['players'] and r_data['status'] == 'waiting':
            current_room_id = r_id
            break

    if not current_room_id:
        bot.send_message(message.chat.id, MESSAGES['not_in_room_for_leave'], reply_markup=main_menu_keyboard())
        user_states[user_id] = None
        logger.warning(f"User {user_id} tried to leave room but not in one (waiting status).")
        return

    room = rooms[current_room_id]
    player_name = room['players'].get(user_id, "Неизвестный")
    
    if user_id in room['players']:
        del room['players'][user_id]
    user_states[user_id] = None

    bot.send_message(message.chat.id, MESSAGES['left_room'], reply_markup=main_menu_keyboard())

    if user_id == room['creator']:
        if room['players']:
            new_creator_id = random.choice(list(room['players'].keys()))
            room['creator'] = new_creator_id
            new_creator_name = room['players'].get(new_creator_id, "Неизвестный")
            logger.info(f"Creator {player_name} ({user_id}) left room {current_room_id}, new creator: {new_creator_name} ({new_creator_id}).")
            
            players_to_notify = list(room['players'].keys())
            for player_id in players_to_notify:
                if player_id in BOT_IDS: continue
                bot.send_message(player_id, MESSAGES['creator_leave_room_new_creator_notify'].format(
                                 old_creator_name=player_name, new_creator_name=new_creator_name),
                                 reply_markup=room_waiting_keyboard(current_room_id, room['creator'], player_id))
        else:
            del rooms[current_room_id]
            logger.info(f"Creator {player_name} ({user_id}) left room {current_room_id}, room deleted (empty).")
    else:
        logger.info(f"User {player_name} ({user_id}) left room {current_room_id}.")
        if current_room_id in rooms:
            players_to_notify = list(room['players'].keys())
            for player_id in players_to_notify:
                if player_id in BOT_IDS: continue
                bot.send_message(player_id, MESSAGES['player_leave_room_notify'].format(player_name=player_name),
                                 reply_markup=room_waiting_keyboard(current_room_id, room['creator'], player_id))
        else:
            logger.warning(f"Room {current_room_id} was already removed when player {player_name} ({user_id}) left.")

    if current_room_id in rooms and not room['players']:
        del rooms[current_room_id]
        logger.info(f"Room {current_room_id} automatically deleted because it became empty after player {player_name} ({user_id}) left.")


@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить комнату")
def handle_delete_room_button(message):
    user_id = message.from_user.id
    current_room_id = None
    for r_id, r_data in rooms.items():
        if user_id == r_data['creator'] and r_data['status'] == 'waiting':
            current_room_id = r_id
            break

    if not current_room_id:
        bot.send_message(message.chat.id, MESSAGES['not_creator_to_delete'], reply_markup=main_menu_keyboard())
        user_states[user_id] = None
        logger.warning(f"User {user_id} tried to delete room but not creator or room not in waiting status.")
        return

    room = rooms[current_room_id]
    players_to_notify = list(room['players'].keys())

    del rooms[current_room_id]

    bot.send_message(message.chat.id, MESSAGES['room_deleted_by_creator'], reply_markup=main_menu_keyboard())
    user_states[user_id] = None

    for player_id in players_to_notify:
        if player_id != user_id and player_id not in BOT_IDS:
            bot.send_message(player_id, MESSAGES['creator_deleted_room'], reply_markup=main_menu_keyboard())
            user_states[player_id] = None
    logger.info(f"Room {current_room_id} deleted by creator {user_id}.")

@bot.message_handler(func=lambda message: message.text == "▶️ Старт")
def handle_start_game_button(message):
    user_id = message.from_user.id
    current_room_id = None
    for r_id, r_data in rooms.items():
        if user_id == r_data['creator'] and r_data['status'] == 'waiting':
            current_room_id = r_id
            break

    if not current_room_id:
        bot.send_message(message.chat.id, MESSAGES['not_creator_to_start'], reply_markup=main_menu_keyboard())
        logger.warning(f"User {user_id} tried to start game but not creator or room not in waiting status.")
        return

    room = rooms[current_room_id]

    if len(room['players']) < room['min_players']:
        bot.send_message(message.chat.id, MESSAGES['not_enough_players_to_start'].format(min_players=room['min_players']),
                        reply_markup=room_waiting_keyboard(current_room_id, user_id, user_id))
        logger.warning(f"Creator {user_id} tried to start room {current_room_id} with not enough players.")
        return
    
    start_game_logic(current_room_id)

@bot.message_handler(func=lambda message: message.text == "🤖 Играть с ботами")
def handle_add_bots_button(message):
    user_id = message.from_user.id
    current_room_id = None
    for r_id, r_data in rooms.items():
        if user_id == r_data['creator'] and r_data['status'] == 'waiting':
            current_room_id = r_id
            break

    if not current_room_id:
        bot.send_message(message.chat.id, MESSAGES['not_creator_to_start'], reply_markup=main_menu_keyboard())
        logger.warning(f"User {user_id} tried to add bots but not creator or room not in waiting status.")
        return
    
    room = rooms[current_room_id]
    
    current_players_count = len(room['players'])
    max_players = room['max_players']
    
    if current_players_count >= max_players:
        bot.send_message(message.chat.id, "Комната уже полна. Нажмите 'Старт' для начала игры.", 
                         reply_markup=room_waiting_keyboard(current_room_id, user_id, user_id))
        return

    num_bots_to_add = max_players - current_players_count
    added_bots = add_bots_to_room(current_room_id, num_bots_to_add)

    bot.send_message(message.chat.id, f"Добавлено {len(added_bots)} ботов. Комната заполнена! Запускаю игру...",
                     reply_markup=room_waiting_keyboard(current_room_id, user_id, user_id))
    
    for player_id in list(room['players']):
        if player_id not in BOT_IDS and player_id != user_id:
            bot.send_message(player_id, f"Комната заполнена ботами ({len(added_bots)} шт.)! Игра начинается!",
                             reply_markup=room_waiting_keyboard(current_room_id, user_id, player_id))

    start_game_logic(current_room_id)


@bot.message_handler(func=lambda message: message.text.startswith("👥 Игроки в комнате (") and user_states.get(message.from_user.id) == 'in_room')
def handle_in_game_players_button(message):
    user_id = message.from_user.id
    room_id = None
    for r_id, r_data in rooms.items():
        if user_id in r_data['players'] and r_data['status'] != 'waiting':
            room_id = r_id
            break
    
    if room_id:
        room = rooms[room_id]
        alive_players_names = [room['players'].get(p_id, "Неизвестный") for p_id in room['alive_players']]
        
        keyboard = get_player_game_keyboard(room_id, user_id)
        
        bot.send_message(user_id, f"Сейчас живы ({len(alive_players_names)}/{room['max_players']}): {', '.join(alive_players_names)}", reply_markup=keyboard)
        logger.info(f"User {user_id} requested alive players list in room {room_id}.")
    else:
        bot.send_message(user_id, MESSAGES['not_in_room_for_leave'], reply_markup=main_menu_keyboard())
        user_states[user_id] = None
        logger.warning(f"User {user_id} tried to get in-game player list but not in a game.")

@bot.message_handler(func=lambda message: message.text == "↪️ Выйти из игры" )
def handle_leave_game_button(message):
    user_id = message.from_user.id
    current_room_id = None
    for r_id, r_data in rooms.items():
        if user_id in r_data['players'] and r_data['status'] != 'waiting':
            current_room_id = r_id
            break

    if not current_room_id:
        if user_states.get(user_id) == 'in_room':
            bot.send_message(message.chat.id, "Кажется, вы пытаетесь выйти из игры, которая уже неактивна. Возвращаемся в главное меню.", reply_markup=main_menu_keyboard())
            user_states[user_id] = None
            logger.warning(f"User {user_id} tried to leave game but was in a stale 'in_room' state.")
            return
        bot.send_message(message.chat.id, MESSAGES['not_in_room_for_leave'], reply_markup=main_menu_keyboard())
        user_states[user_id] = None
        logger.warning(f"User {user_id} tried to leave game but not in one.")
        return
    
    room = rooms[current_room_id]
    player_name = room['players'].get(user_id, "Неизвестный")
    
    if user_id in room['alive_players']:
        room['alive_players'].discard(user_id)
    if user_id in room['players']:
        del room['players'][user_id]
    if user_id in room['last_sent_message']:
        del room['last_sent_message'][user_id]
    user_states[user_id] = None

    bot.send_message(message.chat.id, MESSAGES['game_over_leave'], reply_markup=main_menu_keyboard())

    if current_room_id in rooms and room['alive_players']:
        send_message_to_alive_players(current_room_id, MESSAGES['player_leave_room_notify'].format(player_name=player_name), 
                                      keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid), parse_mode='Markdown')
    logger.info(f"User {player_name} ({user_id}) left game in room {current_room_id}.")

    if current_room_id in rooms:
        game_over, winner = check_win_condition(current_room_id)
        if game_over:
            end_game(current_room_id, winner, user_id)
            return
        
        if not room['alive_players']:
            stop_room_timer(current_room_id)
            del rooms[current_room_id]
            logger.info(f"Room {current_room_id} deleted because all players left the game.")
            return
    else:
        logger.warning(f"Room {current_room_id} was removed before leave_game_button handler finished processing.")


@bot.message_handler(func=lambda message: message.text.startswith("👥 Игроки в комнате") and user_states.get(message.from_user.id) == 'in_room')
def handle_waiting_room_players_button(message):
    user_id = message.from_user.id
    room_id = None
    for r_id, r_data in rooms.items():
        if user_id in r_data['players'] and r_data['status'] == 'waiting':
            room_id = r_id
            break
    
    if room_id:
        room = rooms[room_id]
        players_names = [room['players'].get(p_id, "Неизвестный") for p_id in room['players']]
        
        keyboard = room_waiting_keyboard(room_id, room['creator'], user_id)
        
        bot.send_message(user_id, f"Сейчас в комнате ({len(players_names)}/{room['max_players']}): {', '.join(players_names)}", reply_markup=keyboard)
        logger.info(f"User {user_id} requested waiting room player list in room {room_id}.")
    else:
        bot.send_message(user_id, MESSAGES['not_in_room_for_leave'], reply_markup=main_menu_keyboard())
        user_states[user_id] = None
        logger.warning(f"User {user_id} tried to get waiting room player list but not in one.")

@bot.message_handler(func=lambda message: message.text == "📜 Правила")
def handle_rules_button(message):
    bot.send_message(message.chat.id, MESSAGES['rules_text'], parse_mode='Markdown', reply_markup=main_menu_keyboard())
    logger.info(f"User {message.from_user.id} requested rules.")

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    
    current_state = user_states.get(user_id)
    if current_state in ['awaiting_max_players_count', 'awaiting_room_id'] and message.text != "❌ Отмена":
        return


    room_id = None
    for r_id, r_data in rooms.items():
        if user_id in r_data['players']:
            room_id = r_id
            break
            
    if room_id and room_id in rooms:
        room = rooms[room_id]
        player_name = room['players'].get(user_id, "Неизвестный")

        if room['status'] == 'night':
            action_made = False
            
            possible_actions = {
                "🔪Убить ": 'Мафия',
                "💉Лечить ": 'Доктор',
                "🔍Проверить ": 'Шериф'
            }
            
            action_prefix = None
            target_player_name_raw = None
            
            for prefix, role in possible_actions.items():
                if message.text.startswith(prefix) and room['players_roles'].get(user_id) == role:
                    action_prefix = prefix
                    target_player_name_raw = message.text[len(prefix):].strip()
                    break
            
            if message.text == "💤Ждать утра" and room['players_roles'].get(user_id) == 'Мирный житель':
                if user_id in room['night_actions_made']:
                    bot.send_message(user_id, MESSAGES['you_already_acted'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    return
                room['night_actions_made'].add(user_id)
                bot.send_message(user_id, MESSAGES['action_confirmed'], reply_markup=get_player_game_keyboard(room_id, user_id))
                action_made = True
                logger.info(f"User {room['players'].get(user_id, 'Unknown')} ({room['players_roles'].get(user_id)}) chose 'Ждать утра' in room {room_id}.")

            elif action_prefix:
                if user_id in room['night_actions_made']:
                    bot.send_message(user_id, MESSAGES['you_already_acted'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    return

                target_id = None
                
                for p_id_in_room, p_name in room['players'].items():
                    if p_name == target_player_name_raw and p_id_in_room in room['alive_players']:
                        if action_prefix == "🔪Убить " and room['players_roles'].get(p_id_in_room) == 'Мафия':
                            continue
                        if action_prefix == "🔍Проверить " and p_id_in_room == user_id:
                            continue
                        target_id = p_id_in_room
                        break
                
                if target_id:
                    room['night_actions'][user_id] = target_id
                    room['night_actions_made'].add(user_id)
                    bot.send_message(user_id, MESSAGES['action_confirmed'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    action_made = True
                    logger.info(f"User {room['players'].get(user_id, 'Unknown')} ({room['players_roles'].get(user_id)}) chose to {action_prefix.strip()} {room['players'].get(target_id, 'Unknown')} in room {room_id}.")
                else:
                    bot.send_message(user_id, MESSAGES['invalid_target_chosen'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    logger.warning(f"User {room['players'].get(user_id, 'Unknown')} ({room['players_roles'].get(user_id)}) chose invalid target '{target_player_name_raw}' in room {room_id}.")

                if action_made and check_all_night_actions_made(room_id):
                    logger.info(f"All night actions made in room {room_id}. Forcing next phase.")
                    stop_room_timer(room_id)
                    if room_id in rooms:
                        process_night_actions(room_id)
                    return

            if not action_made:
                if room['players_roles'].get(user_id) == 'Мафия':
                    mafia_partners_in_game = [p_id for p_id in room['alive_players'] if room['players_roles'].get(p_id) == 'Мафия' and p_id != user_id]
                    for p_id_mafia in mafia_partners_in_game:
                        if p_id_mafia in BOT_IDS: continue
                        bot.send_message(p_id_mafia, MESSAGES['chat_message_in_game'].format(sender_name=player_name, text=message.text),
                                        reply_markup=get_player_game_keyboard(room_id, p_id_ma), parse_mode='Markdown')
                    logger.info(f"Mafia user {player_name} sent chat message during night in room {room_id}: '{message.text}'")
                else:
                    bot.send_message(user_id, MESSAGES['cannot_chat_night'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    logger.info(f"Non-mafia user {player_name} tried to chat during night in room {room_id}: '{message.text}'")
                
        elif room['status'] == 'voting' or room['status'] == 'day':
            action_made = False
            vote_prefix = "🗳️Голосовать за "
            skip_vote_text = "🔇Пропустить голосование"

            if room['status'] == 'voting' and (message.text.startswith(vote_prefix) or message.text == skip_vote_text):
                if user_id in room['day_votes']:
                    bot.send_message(user_id, MESSAGES['you_already_voted'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    return

                target_id = None
                
                if message.text.startswith(vote_prefix):
                    target_player_name_raw = message.text[len(vote_prefix):].strip()
                    for p_id_in_room, p_name in room['players'].items():
                        if p_name == target_player_name_raw and p_id_in_room in room['alive_players']:
                            target_id = p_id_in_room
                            break
                    
                    if target_id:
                        room['day_votes'][user_id] = target_id
                        bot.send_message(user_id, MESSAGES['vote_confirmed'], reply_markup=get_player_game_keyboard(room_id, user_id))
                        action_made = True
                        logger.info(f"User {room['players'].get(user_id, 'Unknown')} voted for {room['players'].get(target_id, 'Unknown')} in room {room_id}.")
                    else:
                        bot.send_message(user_id, MESSAGES['invalid_target_chosen'], reply_markup=get_player_game_keyboard(room_id, user_id))
                        logger.warning(f"User {room['players'].get(user_id, 'Unknown')} chose invalid vote target '{target_player_name_raw}' in room {room_id}.")
                
                elif message.text == skip_vote_text:
                    room['day_votes'][user_id] = None
                    bot.send_message(user_id, MESSAGES['vote_confirmed'], reply_markup=get_player_game_keyboard(room_id, user_id))
                    action_made = True
                    logger.info(f"User {room['players'].get(user_id, 'Unknown')} skipped vote in room {room_id}.")
            
            if action_made and check_all_day_votes_made(room_id):
                logger.info(f"All day votes made in room {room_id}. Forcing next phase.")
                stop_room_timer(room_id)
                if room_id in rooms:
                    process_day_voting(room_id)
                return

            if not action_made:
                send_message_to_alive_players(room_id, MESSAGES['chat_message_in_game'].format(sender_name=player_name, text=message.text),
                                              exclude_player_id=user_id, keyboard_func=lambda rid, pid: get_player_game_keyboard(rid, pid), parse_mode='Markdown')
                logger.info(f"User {room['players'].get(user_id, 'Unknown')} sent chat message during day/voting in room {room_id}: '{message.text}'")
        
        elif room['status'] == 'waiting':
            for p_id in list(room['players'].keys()):
                if p_id != user_id and p_id not in BOT_IDS:
                    bot.send_message(p_id, MESSAGES['chat_message_in_waiting'].format(sender_name=player_name, text=message.text),
                                    reply_markup=room_waiting_keyboard(room_id, room['creator'], p_id))
            logger.info(f"User {player_name} sent chat message in waiting room {room_id}: '{message.text}'")

    else:
        if user_states.get(user_id) not in ['awaiting_max_players_count', 'awaiting_room_id', 'in_room']:
            bot.send_message(message.chat.id, MESSAGES['unknown_command'], reply_markup=main_menu_keyboard())
            logger.warning(f"User {message.from_user.id} sent unknown command '{message.text}'.")


if __name__ == '__main__':
    logger.info("Bot started polling.")
    bot.polling(none_stop=True)
