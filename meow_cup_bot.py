# MEOW.CUP Bot — Финальный код с рассылкой и улучшенным выводом турнира

import os
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import asyncio

API_TOKEN = "7507739946:AAE0p-9CEJWjUM0oXYamsakLvCEvz5KnLJA"
ADMIN_ID = 947800235

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

users = set()
import json

tournaments_file = "tournaments.json"
if os.path.exists(tournaments_file):
    with open(tournaments_file, "r", encoding="utf-8") as f:
        tournaments = json.load(f)
else:
    tournaments = []
photos = {}
ctx = {}

class AddTournament(StatesGroup):
    waiting_photo = State()

class BroadcastState(StatesGroup):
    waiting_content = State()

# Утилиты

def get_upcoming_dates():
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(3)]

def build_keyboard(buttons, row=2):
    builder = InlineKeyboardBuilder()
    for b in buttons:
        builder.button(text=b, callback_data=b)
    builder.adjust(row)
    return builder.as_markup()

def overlay_text_on_image(image_bytes, text):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    width, _ = image.size
    text_width = draw.textlength(text, font=font)
    draw.rectangle([(0, 0), (width, 60)], fill=(0, 0, 0, 180))
    draw.text(((width - text_width) / 2, 10), text, fill="white", font=font)
    output = io.BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    return output

def cleanup_old():
    today = datetime.now().strftime("%d.%m.%Y")
    global tournaments
    tournaments = [t for t in tournaments if t['date'] >= today]
    with open(tournaments_file, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, ensure_ascii=False, indent=2)

# Команды
@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    ctx[message.from_user.id] = {"step": "start"}
    users.add(message.from_user.id)
    kb = build_keyboard(["турнир", "ивент", "праки"], row=3)
    pid = photos.get("меню")
    if pid:
        await message.answer_photo(pid, caption="Выберите тип:", reply_markup=kb)
    else:
        await message.answer("Выберите тип:", reply_markup=kb)

@dp.message(F.text == "🔧 Панель администратора")
async def admin_panel(message: Message):
    ctx[message.from_user.id] = {"step": "admin"}
    if message.from_user.id != ADMIN_ID:
        return
    kb = build_keyboard(["Добавить турнир", "Загрузить фото кнопки", "Пользователи", "📢 Рассылка"])
    await message.answer("Панель администратора:", reply_markup=kb)

@dp.callback_query(F.data == "Пользователи")
async def list_users(call: CallbackQuery):
    await call.message.answer("Пользователей: " + str(len(users)))

@dp.callback_query(F.data == "Загрузить фото кнопки")
async def ask_photo_upload(call: CallbackQuery):
    await call.message.answer("Отправьте фото с подписью = код кнопки (например: 18:00 или 'турнир')")

@dp.callback_query(F.data == "📢 Рассылка")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastState.waiting_content)
    await call.message.answer("Отправьте сообщение для рассылки (можно с фото)")

@dp.message(BroadcastState.waiting_content)
async def handle_broadcast(message: Message, state: FSMContext):
    success = 0
    fail = 0
    all_targets = users.union({message.chat.id})  # для чатов тоже

    for uid in all_targets:
        try:
            if message.photo:
                await bot.send_photo(uid, photo=message.photo[-1].file_id, caption=message.caption or "")
            else:
                await bot.send_message(uid, message.text or "")
            success += 1
        except:
            fail += 1

    await message.answer(f"📢 Рассылка завершена! ✅ {success}, ❌ {fail}")
    await state.clear()
    with open(tournaments_file, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, ensure_ascii=False, indent=2)

@dp.message(F.from_user.id == ADMIN_ID, F.photo, F.caption)
async def photo_button_upload(message: Message):
    photos[message.caption.lower()] = message.photo[-1].file_id
    await message.answer("Фото сохранено под ключом: " + message.caption)

class AddTournament(StatesGroup):
    waiting_photo = State()

@dp.callback_query(F.data == "Добавить турнир")
async def ask_tournament_data(call: CallbackQuery, state: FSMContext):
    ctx[call.from_user.id]["step"] = "add_tournament"
    await call.message.answer("Отправь фото с подписью в формате:\n<дата> | <время> | <тип> | <стадия> | <название> | <описание> | <ссылка>")
    await state.set_state(AddTournament.waiting_photo)

@dp.message(AddTournament.waiting_photo & F.photo)
async def handle_add_tournament(message: Message, state: FSMContext):
    if not message.caption:
        return await message.answer("Добавь подпись к фото!")

    parts = [p.strip() for p in message.caption.split("|")]
    if len(parts) != 7:
        return await message.answer("Неверный формат. Должно быть 7 параметров через |")

    date, time, type_, stage, title, desc, link = parts
    file = await bot.download(message.photo[-1])
    img = overlay_text_on_image(file.read(), title)
    sent = await bot.send_photo(message.chat.id, photo=img)
    tournaments.append({
        "date": date, "time": time, "type": type_.lower(), "stage": stage,
        "title": title, "desc": desc, "link": link, "photo": sent.photo[-1].file_id
    })
    cleanup_old()
    await message.answer("✅ Турнир сразу добавлен!")
    cleanup_old()

@dp.message(F.text == "🟦 Меню")
async def open_main_menu(message: Message):
    kb = build_keyboard(["турнир", "ивент", "праки"], row=1)
    pid = photos.get("меню")
    await message.answer_photo(pid, caption="Выберите тип:", reply_markup=kb) if pid else await message.answer("Выберите тип:", reply_markup=kb)

@dp.callback_query()
async def universal_flow(call: CallbackQuery):
    uid = call.from_user.id
    if uid not in ctx:
        ctx[uid] = {}
    uid = call.from_user.id
    data = call.data

    if data in ["турнир", "ивент", "праки"]:
    ctx[uid] = {"type": data, "step": "type"}
    kb = build_keyboard(get_upcoming_dates(), row=1)
    pid = photos.get(data)

    if pid:
        await call.message.edit_media(InputMediaPhoto(media=pid, caption="Выберите дату:"), reply_markup=kb)
    else:
        if not hasattr(kb, 'inline_keyboard'):
            kb.inline_keyboard = []
        kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="Назад")])
        try:
            await call.message.edit_text("Выберите дату:", reply_markup=kb)
        except:
            await call.message.answer("Выберите дату:", reply_markup=kb)
            except:
                await call.message.edit_text("Выберите дату:", reply_markup=kb)

    elif data in get_upcoming_dates():
        ctx[uid]["date"] = data
        ctx[uid]["step"] = "date"
        kb = build_keyboard(["18:00", "21:00"])
        pid = photos.get(data)
        kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="Назад")])
        await call.message.edit_text("🕒 Выберите время мероприятия:", reply_markup=kb)
            kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="Назад")])
            await call.message.edit_text("📅 Выберите дату мероприятия:", reply_markup=kb)
        elif step == "date":
            ctx[uid]["step"] = "type"
            kb = build_keyboard(["турнир", "ивент", "праки"], row=3)
            await call.message.edit_text("🔘 Выберите тип мероприятия:", reply_markup=kb)
        else:
            await open_main_menu(call.message)

async def show_titles(call, uid):
    filters = ctx[uid]
    filtered = [t for t in tournaments if all([
        t['type'] == filters['type'],
        t['date'] == filters['date'],
        t['time'] == filters['time'],
        filters.get('stage') is None or t['stage'] == filters['stage'],
        filters.get('format') is None or t.get('format') == filters['format']
    ])]
    if not filtered:
        await call.message.edit_text("❌ Нет турниров по выбранным параметрам.", reply_markup=build_keyboard(["◀ Назад"]))
        return
    kb = build_keyboard([t['title'] for t in filtered], row=1)
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="Назад")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="Назад")])
    await call.message.edit_text(
        f"🏆 Выберите турнир из списка:

📌 Вы выбрали:
• Тип: {ctx[uid].get('type', '-')}
• Дата: {ctx[uid].get('date', '-')}
• Время: {ctx[uid].get('time', '-')}
• Стадия: {ctx[uid].get('stage', '-')}
• Формат: {ctx[uid].get('format', '-')}",
        reply_markup=kb
    )

@dp.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_messages(message: Message):
    await message.reply("Привет! Я готов работать, но используй /start в личке 💌")

@dp.message(F.chat.type.in_(["group", "supergroup"]) & F.text == "/турнир")
async def group_add_tournament_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("⛔ Только админ может добавлять турнир из группы.")
    await state.set_state(AddTournament.waiting_photo)
    await message.reply("Отправьте фото с подписью в формате:\n<дата> | <время> | <тип> | <стадия> | <название> | <описание> | <ссылка>")

# Запуск
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    async def main():
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    asyncio.run(main())
