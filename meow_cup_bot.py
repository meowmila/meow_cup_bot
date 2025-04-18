import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from PIL import Image, ImageDraw, ImageFont

API_TOKEN = "7507739946:AAE0p-9CEJWjUM0oXYamsakLvCEvz5KnLJA"
ADMIN_ID = 947800235

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

TOURNAMENTS_FILE = "tournaments.json"
PHOTOS_DIR = "photos"
os.makedirs(PHOTOS_DIR, exist_ok=True)
if not os.path.exists(TOURNAMENTS_FILE):
    with open(TOURNAMENTS_FILE, "w") as f:
        json.dump([], f)

def get_upcoming_dates():
    today = datetime.now().date()
    return [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(3)]

def load_tournaments():
    with open(TOURNAMENTS_FILE, "r") as f:
        return json.load(f)

def save_tournaments(data):
    with open(TOURNAMENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def overlay_text_on_photo(photo: types.PhotoSize, text: str) -> str:
    path = f"{PHOTOS_DIR}/{photo.file_id}.jpg"
    await bot.download(photo, destination=path)
    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    w, h = img.size
    tw, th = draw.textsize(text, font=font)
    draw.text(((w - tw) / 2, h - th - 20), text, font=font, fill="white")
    result = f"{PHOTOS_DIR}/txt_{photo.file_id}.jpg"
    img.save(result)
    return result

async def go_to_step(callback: CallbackQuery, state: FSMContext, step: str, buttons: list, title: str):
    data = await state.get_data()
    history = data.get("step_history", [])
    if not history or history[-1] != step:
        history.append(step)
    await state.update_data(step_history=history)
    kb = InlineKeyboardBuilder()
    for btn in buttons:
        kb.button(text=btn["text"], callback_data=btn["data"])
    kb.adjust(len(buttons))
    kb.row(types.InlineKeyboardButton(text="⬅ Назад", callback_data="go_back"))
    await callback.message.edit_text(f"<b>{title}</b>", reply_markup=kb.as_markup())

@dp.message(F.text == "/start")
async def start_message(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.button(text="Турнир", callback_data="type_Турнир")
    kb.button(text="Ивент", callback_data="type_Ивент")
    kb.button(text="Праки", callback_data="type_Праки")
    if message.from_user.id == ADMIN_ID:
        kb.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    kb.adjust(2)
    await message.answer("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.button(text="Турнир", callback_data="type_Турнир")
    kb.button(text="Ивент", callback_data="type_Ивент")
    kb.button(text="Праки", callback_data="type_Праки")
    if callback.from_user.id == ADMIN_ID:
        kb.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())
@dp.callback_query(F.data.startswith("type_"))
async def choose_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(type=callback.data.split("_")[1])
    buttons = [{"text": d, "data": f"date_{d}"} for d in get_upcoming_dates()]
    await go_to_step(callback, state, "type", buttons, "Выберите дату:")

@dp.callback_query(F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    await state.update_data(date=callback.data.split("_")[1])
    buttons = [{"text": "18:00", "data": "time_18"}, {"text": "21:00", "data": "time_21"}]
    await go_to_step(callback, state, "date", buttons, "Выберите время:")

@dp.callback_query(F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data.split("_")[1])
    buttons = [{"text": "🆓 Free", "data": "access_Free"}, {"text": "💎 VIP", "data": "access_VIP"}]
    await go_to_step(callback, state, "time", buttons, "Выберите доступ:")

@dp.callback_query(F.data.startswith("access_"))
async def choose_access(callback: CallbackQuery, state: FSMContext):
    await state.update_data(access=callback.data.split("_")[1])
    data = await state.get_data()
    if data["type"] == "Праки":
        return await show_tournaments(callback, state)
    buttons = [
        {"text": "1/2", "data": "stage_1/2"},
        {"text": "1/4", "data": "stage_1/4"},
        {"text": "1/8", "data": "stage_1/8"},
    ]
    await go_to_step(callback, state, "access", buttons, "Выберите стадию:")

@dp.callback_query(F.data.startswith("stage_"))
async def choose_stage(callback: CallbackQuery, state: FSMContext):
    await state.update_data(stage=callback.data.split("_")[1])
    await show_tournaments(callback, state)

@dp.callback_query(F.data == "go_back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    history = data.get("step_history", [])
    if history:
        history.pop()
    if not history:
        return await back_to_start(callback, state)
    await state.update_data(step_history=history)
    prev = history[-1]

    if prev == "type":
        buttons = [{"text": d, "data": f"date_{d}"} for d in get_upcoming_dates()]
        await go_to_step(callback, state, "type", buttons, "Выберите дату:")
    elif prev == "date":
        buttons = [{"text": "18:00", "data": "time_18"}, {"text": "21:00", "data": "time_21"}]
        await go_to_step(callback, state, "date", buttons, "Выберите время:")
    elif prev == "time":
        buttons = [{"text": "🆓 Free", "data": "access_Free"}, {"text": "💎 VIP", "data": "access_VIP"}]
        await go_to_step(callback, state, "time", buttons, "Выберите доступ:")
    elif prev == "access":
        type_ = data.get("type")
        if type_ == "Праки":
            buttons = [{"text": "🆓 Free", "data": "access_Free"}, {"text": "💎 VIP", "data": "access_VIP"}]
            await go_to_step(callback, state, "access", buttons, "Выберите доступ:")
        else:
            buttons = [
                {"text": "1/2", "data": "stage_1/2"},
                {"text": "1/4", "data": "stage_1/4"},
                {"text": "1/8", "data": "stage_1/8"},
            ]
            await go_to_step(callback, state, "access", buttons, "Выберите стадию:")
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

    t = filtered[0]  # пока показываем только первый
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
        media = InputMediaPhoto(media=types.FSInputFile(t["photo"]), caption=caption, parse_mode="HTML")
        await callback.message.edit_media(media=media, reply_markup=kb.as_markup())
    else:
        await callback.message.edit_text(caption, reply_markup=kb.as_markup())

# ========== АДМИН ПАНЕЛЬ ==========

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Добавить турнир", callback_data="admin_add")
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.adjust(1)
    kb.row(types.InlineKeyboardButton(text="⬅ Назад", callback_data="go_back"))
    await callback.message.edit_text("<b>Панель администратора:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_add")
async def admin_add_instruct(callback: CallbackQuery):
    await callback.message.edit_text(
        "Отправь фото с подписью в формате:\n"
        "Title: ...\nType: Турнир/Ивент/Праки\nDate: 01.01.2025\nTime: 18:00\nAccess: Free/VIP\nStage: 1/4\nPrize: ...\nLink: ..."
    )

@dp.message(F.photo, F.caption, F.from_user.id == ADMIN_ID)
async def save_tournament(message: types.Message, state: FSMContext):
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
        await message.answer(f"❌ Ошибка: {e}")

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state("broadcast")
    await callback.message.edit_text("📢 Отправь сообщение (текст или фото с подписью) для рассылки.")

@dp.message(F.from_user.id == ADMIN_ID)
async def broadcast_msg(message: types.Message, state: FSMContext):
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)
