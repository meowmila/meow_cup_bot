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

API_TOKEN = os.getenv("BOT_TOKEN") or "7507739946:AAGwX2ulBwPCoxOWoopBFIbonaga2K79gNE"
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
    users.add(message.from_user.id)
    kb = build_keyboard(["турнир", "ивент", "праки"], row=1)
    pid = photos.get("меню")
    if pid:
        await message.answer_photo(pid, caption="Выберите тип:", reply_markup=kb)
    else:
        await message.answer("Выберите тип:", reply_markup=kb)

@dp.message(F.text == "🔧 Панель администратора")
async def admin_panel(message: Message):
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
    for uid in users:
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
    await call.message.answer("Отправь фото с подписью в формате:\n<дата> | <время> | <тип> | <стадия> | <название> | <описание> | <ссылка>")
    await state.set_state(AddTournament.waiting_photo)

@dp.message(AddTournament.waiting_photo & F.photo)
async def handle_add_tournament(message: Message, state: FSMContext):
    if not message.caption:
        await message.answer("Добавь подпись к фото!")
        return
    parts = [p.strip() for p in message.caption.split("|")]
    if len(parts) != 7:
        await message.answer("Неверный формат. Должно быть 7 параметров через |")
        return
    date, time, type_, stage, title, desc, link = parts
    file = await bot.download(message.photo[-1])
    img = overlay_text_on_image(file.read(), title)
    sent = await bot.send_photo(message.chat.id, photo=img)
    tournaments.append({
        "date": date, "time": time, "type": type_.lower(), "stage": stage,
        "title": title, "desc": desc, "link": link, "photo": sent.photo[-1].file_id
    })
    await message.answer("✅ Турнир добавлен!")
    await state.clear()
    cleanup_old()

@dp.message(F.text == "🟦 Меню")
async def open_main_menu(message: Message):
    kb = build_keyboard(["турнир", "ивент", "праки"], row=1)
    pid = photos.get("меню")
    await message.answer_photo(pid, caption="Выберите тип:", reply_markup=kb) if pid else await message.answer("Выберите тип:", reply_markup=kb)

@dp.callback_query()
async def universal_flow(call: CallbackQuery):
    uid = call.from_user.id
    data = call.data

    if data in ["турнир", "ивент", "праки"]:
        ctx[uid] = {"type": data}
        kb = build_keyboard(get_upcoming_dates(), row=1)
        pid = photos.get(data)
        await call.message.answer_photo(pid, caption="Выберите дату:", reply_markup=kb) if pid else await call.message.answer("Выберите дату:", reply_markup=kb)

    elif data in get_upcoming_dates():
        ctx[uid]["date"] = data
        kb = build_keyboard(["18:00", "21:00"])
        pid = photos.get(data)
        await call.message.answer_photo(pid, caption="Выберите время:", reply_markup=kb) if pid else await call.message.answer("Выберите время:", reply_markup=kb)

    elif data in ["18:00", "21:00"]:
        ctx[uid]["time"] = data
        if ctx[uid]['type'] == "праки":
            return await show_titles(call, uid)
        stages = sorted(set(t['stage'] for t in tournaments if t['date'] == ctx[uid]['date'] and t['time'] == data and t['type'] == ctx[uid]['type']))
        if not stages:
            return await show_titles(call, uid)
        kb = build_keyboard(stages)
        await call.message.answer("Выберите стадию:", reply_markup=kb)

    elif data in ["1/8", "1/4", "1/2", "финал"]:
        ctx[uid]['stage'] = data
        kb = build_keyboard(["duo", "squad"])
        await call.message.answer("Выберите формат:", reply_markup=kb)

    elif data in ["duo", "squad"]:
        ctx[uid]['format'] = data
        await show_titles(call, uid)

    elif any(t['title'] == data for t in tournaments):
        t = next(t for t in tournaments if t['title'] == data)
        text = f"""🏆 <b>{t['title']}</b>

🍬 │ Призовой фонд: 💸
🍬 │ Фри слотов: 14
🍬 │ Стадия: {t['stage']}
🍬 │ Проход: Топ 6"""
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти к турниру", url=t['link'])],
            [InlineKeyboardButton(text="Назад", callback_data="Назад")]
        ])
        await call.message.answer_photo(t['photo'], caption=text, reply_markup=kb)

    elif data == "Назад":
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
        await call.message.answer("Нет турниров по этим параметрам")
        return
    kb = build_keyboard([t['title'] for t in filtered], row=1)
    await call.message.answer("Выберите турнир:", reply_markup=kb)

# Запуск
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    async def start():
    async def ping():
        while True:
            try:
                await bot.get_me()
            except:
                pass
            await asyncio.sleep(300)  # каждые 5 минут

    asyncio.create_task(ping())
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    asyncio.run(start())
