import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from PIL import Image, ImageDraw, ImageFont

API_TOKEN = "7507739946:AAE0p-9CEJWjUM0oXYamsakLvCEvz5KnLJA"
ADMIN_ID = 947800235

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

USERS_FILE = "tournaments.json"
PHOTOS_DIR = "photos"
os.makedirs(PHOTOS_DIR, exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump([], f)

def get_upcoming_dates():
    today = datetime.now().date()
    return [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(3)]

def load_tournaments():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_tournaments(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def overlay_text_on_photo(photo: types.PhotoSize, text: str) -> str:
    file_path = f"{PHOTOS_DIR}/{photo.file_id}.jpg"
    await bot.download(photo, destination=file_path)
    image = Image.open(file_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    w, h = image.size
    text_w, text_h = draw.textsize(text, font=font)
    draw.text(((w - text_w) / 2, h - text_h - 20), text, font=font, fill="white")
    result_path = f"{PHOTOS_DIR}/txt_{photo.file_id}.jpg"
    image.save(result_path)
    return result_path

# Умный переход и запись истории
async def go_to_step(callback: CallbackQuery, state: FSMContext, step_name: str, buttons: list, title: str):
    data = await state.get_data()
    history = data.get("step_history", [])
    if history and history[-1] != step_name:
        history.append(step_name)
    elif not history:
        history = [step_name]
    await state.update_data(step_history=history)
    kb = InlineKeyboardBuilder()
    for b in buttons:
        kb.button(text=b["text"], callback_data=b["data"])
    kb.adjust(len(buttons))
    kb.row(types.InlineKeyboardButton(text="⬅ Назад", callback_data="go_back"))
    await callback.message.edit_text(f"<b>{title}</b>", reply_markup=kb.as_markup())

# /start
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    buttons = [
        {"text": "Турнир", "data": "type_Турнир"},
        {"text": "Ивент", "data": "type_Ивент"},
        {"text": "Праки", "data": "type_Праки"},
    ]
    if message.from_user.id == ADMIN_ID:
        buttons.append({"text": "⚙️ Админ-панель", "data": "admin_panel"})
    kb = InlineKeyboardBuilder()
    for b in buttons:
        kb.button(text=b["text"], callback_data=b["data"])
    kb.adjust(2)
    await message.answer("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("type_"))
async def type_chosen(callback: CallbackQuery, state: FSMContext):
    await state.update_data(type=callback.data.split("_")[1])
    buttons = [{"text": date, "data": f"date_{date}"} for date in get_upcoming_dates()]
    await go_to_step(callback, state, "type", buttons, "Выберите дату:")

@dp.callback_query(F.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    await state.update_data(date=callback.data.split("_")[1])
    buttons = [
        {"text": "18:00", "data": "time_18"},
        {"text": "21:00", "data": "time_21"}
    ]
    await go_to_step(callback, state, "date", buttons, "Выберите время:")

@dp.callback_query(F.data.startswith("time_"))
async def time_chosen(callback: CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data.split("_")[1])
    buttons = [
        {"text": "🆓 Free", "data": "access_Free"},
        {"text": "💎 VIP", "data": "access_VIP"}
    ]
    await go_to_step(callback, state, "time", buttons, "Выберите доступ:")

@dp.callback_query(F.data.startswith("access_"))
async def access_chosen(callback: CallbackQuery, state: FSMContext):
    await state.update_data(access=callback.data.split("_")[1])
    data = await state.get_data()
    if data["type"] == "Праки":
        await show_tournaments(callback, state)
        return
    buttons = [
        {"text": "1/2", "data": "stage_1/2"},
        {"text": "1/4", "data": "stage_1/4"},
        {"text": "1/8", "data": "stage_1/8"},
    ]
    await go_to_step(callback, state, "access", buttons, "Выберите стадию:")

@dp.callback_query(F.data.startswith("stage_"))
async def stage_chosen(callback: CallbackQuery, state: FSMContext):
    await state.update_data(stage=callback.data.split("_")[1])
    await show_tournaments(callback, state)

@dp.callback_query(F.data == "go_back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    history = data.get("step_history", [])
    if history:
        history.pop()
        await state.update_data(step_history=history)
    if not history:
        return await start(callback.message, state)
    prev = history[-1]
    if prev == "type":
        return await type_chosen(callback, state)
    elif prev == "date":
        return await date_chosen(callback, state)
    elif prev == "time":
        return await time_chosen(callback, state)
    elif prev == "access":
        return await access_chosen(callback, state)
    elif prev == "stage":
        return await stage_chosen(callback, state)

# Показывать турнир
async def show_tournaments(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tournaments = load_tournaments()
    filtered = [
        t for t in tournaments
        if t.get("type") == data.get("type")
        and t.get("date") == data.get("date")
        and t.get("time") == data.get("time")
        and t.get("access") == data.get("access")
        and (t.get("stage") == data.get("stage") if data.get("type") != "Праки" else True)
    ]
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="⬅ Назад", callback_data="go_back"))
    if not filtered:
        await callback.message.edit_text("<b>Нет доступных турниров.</b>", reply_markup=kb.as_markup())
        return
    for t in filtered:
        caption = (
            f"<b>{t['title']}</b>\n\n"
            f"🎯 Стадия: {t.get('stage', '-') if t['type'] != 'Праки' else '—'}\n"
            f"📅 Дата: {t['date']}\n"
            f"🕒 Время: {t['time']}\n"
            f"✨ Тип: {t['type']}\n"
            f"🔒 Доступ: {t['access']}\n"
            f"🎁 Приз: {t['prize']}\n"
            f"🔗 Ссылка: {t['link']}"
        )
        if os.path.exists(t["photo"]):
            await callback.message.answer_photo(InputFile(t["photo"]), caption=caption)
        else:
            await callback.message.answer(caption)
    await callback.message.answer("⬅ Назад", reply_markup=kb.as_markup())

# Очистка устаревших
@dp.startup()
async def on_start(bot: Bot):
    asyncio.create_task(clean_old())

async def clean_old():
    while True:
        now = datetime.now().date()
        tournaments = load_tournaments()
        updated = [t for t in tournaments if datetime.strptime(t["date"], "%d.%m.%Y").date() >= now]
        save_tournaments(updated)
        await asyncio.sleep(3600)

# Запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)
# --- Админ-панель ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Добавить турнир", callback_data="admin_add")
    kb.button(text="📸 Фото с текстом", callback_data="admin_photo")
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.adjust(1)
    kb.row(types.InlineKeyboardButton(text="⬅ Назад", callback_data="go_back"))
    await callback.message.edit_text("<b>Панель администратора:</b>", reply_markup=kb.as_markup())

# --- Инструкция по добавлению турнира ---
@dp.callback_query(F.data == "admin_add")
async def admin_add_instruct(callback: CallbackQuery):
    await callback.message.answer(
        "Отправь фото с подписью в формате:\n"
        "Title: ...\nType: Турнир/Ивент/Праки\nDate: 01.01.2025\nTime: 18:00\nAccess: Free/VIP\nStage: 1/4\nPrize: ...\nLink: ..."
    )

# --- Добавление турнира по фото ---
@dp.message(F.photo, F.caption, F.from_user.id == ADMIN_ID)
async def save_tournament(message: Message, state: FSMContext):
    if await state.get_state() == "waiting_photo_text":
        new_path = await overlay_text_on_photo(message.photo[-1], message.caption.strip())
        await message.answer_photo(InputFile(new_path), caption="✅ Фото с текстом готово.")
        await state.clear()
        return
    try:
        lines = message.caption.split("\n")
        data = {line.split(":")[0].strip().lower(): line.split(":")[1].strip() for line in lines if ":" in line}
        file_path = f"{PHOTOS_DIR}/{message.photo[-1].file_id}.jpg"
        await bot.download(message.photo[-1], destination=file_path)
        tournament = {
            "title": data["title"],
            "type": data["type"],
            "date": data["date"],
            "time": data["time"],
            "access": data.get("access", "Free"),
            "stage": data.get("stage", "-"),
            "prize": data["prize"],
            "link": data["link"],
            "photo": file_path
        }
        tournaments = load_tournaments()
        tournaments.append(tournament)
        save_tournaments(tournaments)
        await message.answer("✅ Турнир добавлен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении: {e}")

# --- Фото с текстом ---
@dp.callback_query(F.data == "admin_photo")
async def ask_photo_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state("waiting_photo_text")
    await callback.message.answer("📸 Отправь фото с подписью — текст будет наложен на фото.")

# --- Рассылка ---
@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state("broadcast")
    await callback.message.answer("📢 Отправь сообщение (текст или фото с подписью) для рассылки.")

@dp.message(F.from_user.id == ADMIN_ID)
async def broadcast_msg(message: Message, state: FSMContext):
    if await state.get_state() != "broadcast":
        return
    await state.clear()
    users = set()
    tournaments = load_tournaments()
    for t in tournaments:
        if "telegram_id" in t:
            users.add(t["telegram_id"])
    users.add(ADMIN_ID)
    for uid in users:
        try:
            if message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            elif message.text:
                await bot.send_message(uid, message.text)
        except:
            continue
    await message.answer("✅ Рассылка завершена!")
