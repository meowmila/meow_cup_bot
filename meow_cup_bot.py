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
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 60)
    w, h = image.size
    text_w, text_h = draw.textsize(text, font=font)
    draw.text(((w - text_w) / 2, h - text_h - 20), text, font=font, fill="white")
    result_path = f"{PHOTOS_DIR}/txt_{photo.file_id}.jpg"
    image.save(result_path)
    return result_path

@dp.message(F.text == "/start")
async def start(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Турнир", callback_data="type_Турнир")
    kb.button(text="Ивент", callback_data="type_Ивент")
    kb.button(text="Праки", callback_data="type_Праки")
    if message.from_user.id == ADMIN_ID:
        kb.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    kb.adjust(2)
    await message.answer("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("type_"))
async def select_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(type=callback.data.split("_")[1])
    kb = InlineKeyboardBuilder()
    for date in get_upcoming_dates():
        kb.button(text=date, callback_data=f"date_{date}")
    kb.adjust(len(get_upcoming_dates()))
    kb.button(text="⬅ Назад", callback_data="back_start")
    await callback.message.edit_text("<b>Выберите дату:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("date_"))
async def select_date(callback: CallbackQuery, state: FSMContext):
    await state.update_data(date=callback.data.split("_")[1])
    kb = InlineKeyboardBuilder()
    kb.button(text="18:00", callback_data="time_18")
    kb.button(text="21:00", callback_data="time_21")
    kb.adjust(2)
    kb.button(text="⬅ Назад", callback_data="back_type")
    await callback.message.edit_text("<b>Выберите время:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("time_"))
async def select_time(callback: CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data.split("_")[1])
    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 Free", callback_data="access_Free")
    kb.button(text="💎 VIP", callback_data="access_VIP")
    kb.adjust(2)
    kb.button(text="⬅ Назад", callback_data="back_date")
    await callback.message.edit_text("<b>Выберите доступ:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("access_"))
async def select_access(callback: CallbackQuery, state: FSMContext):
    await state.update_data(access=callback.data.split("_")[1])
    data = await state.get_data()
    if data["type"] == "Праки":
        await show_tournaments(callback, state)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="1/2", callback_data="stage_1/2")
    kb.button(text="1/4", callback_data="stage_1/4")
    kb.button(text="1/8", callback_data="stage_1/8")
    kb.adjust(3)
    kb.button(text="⬅ Назад", callback_data="back_time")
    await callback.message.edit_text("<b>Выберите стадию:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("stage_"))
async def select_stage(callback: CallbackQuery, state: FSMContext):
    await state.update_data(stage=callback.data.split("_")[1])
    await show_tournaments(callback, state)
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
    if data.get("type") != "Праки":
        kb.button(text="⬅ Назад", callback_data="back_stage")
    else:
        kb.button(text="⬅ Назад", callback_data="back_access")

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

# КНОПКИ НАЗАД
@dp.callback_query(F.data == "back_stage")
async def back_stage(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="1/2", callback_data="stage_1/2")
    kb.button(text="1/4", callback_data="stage_1/4")
    kb.button(text="1/8", callback_data="stage_1/8")
    kb.adjust(3)
    kb.button(text="⬅ Назад", callback_data="back_time")
    await callback.message.edit_text("<b>Выберите стадию:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_access")
async def back_access(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="🆓 Free", callback_data="access_Free")
    kb.button(text="💎 VIP", callback_data="access_VIP")
    kb.adjust(2)
    kb.button(text="⬅ Назад", callback_data="back_date")
    await callback.message.edit_text("<b>Выберите доступ:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_time")
async def back_time(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="18:00", callback_data="time_18")
    kb.button(text="21:00", callback_data="time_21")
    kb.adjust(2)
    kb.button(text="⬅ Назад", callback_data="back_date")
    await callback.message.edit_text("<b>Выберите время:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_date")
async def back_date(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for date in get_upcoming_dates():
        kb.button(text=date, callback_data=f"date_{date}")
    kb.adjust(len(get_upcoming_dates()))
    kb.button(text="⬅ Назад", callback_data="back_type")
    await callback.message.edit_text("<b>Выберите дату:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_type")
async def back_type(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="Турнир", callback_data="type_Турнир")
    kb.button(text="Ивент", callback_data="type_Ивент")
    kb.button(text="Праки", callback_data="type_Праки")
    if callback.from_user.id == ADMIN_ID:
        kb.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())

# АДМИН-ПАНЕЛЬ
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Добавить турнир", callback_data="admin_add")
    kb.button(text="📸 Фото с текстом", callback_data="admin_photo")
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="⬅ Назад", callback_data="back_type")
    kb.adjust(1)
    await callback.message.edit_text("<b>Панель администратора:</b>", reply_markup=kb.as_markup())

# ФОТО С ТЕКСТОМ
@dp.callback_query(F.data == "admin_photo")
async def ask_photo(callback: CallbackQuery, state: FSMContext):
    await state.set_state("waiting_photo_text")
    await callback.message.answer("📸 Отправь фото с текстом — я наложу текст на изображение.")

@dp.message(F.photo, F.caption, F.from_user.id == ADMIN_ID)
async def overlay_and_send_photo(message: Message, state: FSMContext):
    text = message.caption.strip()
    new_path = await overlay_text_on_photo(message.photo[-1], text)
    await message.answer_photo(InputFile(new_path), caption=f"✅ Фото с текстом «{text}» готово.")
    await state.clear()

# ДОБАВЛЕНИЕ ТУРНИРА
@dp.callback_query(F.data == "admin_add")
async def admin_add_instruction(callback: CallbackQuery):
    await callback.message.answer(
        "Отправь фото турнира с подписью:\n"
        "Title: ...\nType: Турнир/Ивент/Праки\nDate: ...\nTime: ...\nPrize: ...\nLink: ...\nAccess: Free/VIP\nStage: ..."
    )

@dp.message(F.photo, F.caption, F.from_user.id == ADMIN_ID)
async def save_tournament_from_photo(message: Message, state: FSMContext):
    lines = message.caption.split("\n")
    try:
        data = {line.split(":")[0].strip().lower(): line.split(":")[1].strip() for line in lines if ":" in line}
        file_path = f"{PHOTOS_DIR}/{message.photo[-1].file_id}.jpg"
        await bot.download(message.photo[-1], destination=file_path)
        tournament = {
            "title": data["title"],
            "type": data["type"],
            "date": data["date"],
            "time": data["time"],
            "prize": data["prize"],
            "link": data["link"],
            "stage": data.get("stage", "-"),
            "access": data.get("access", "Free"),
            "photo": file_path
        }
        tournaments = load_tournaments()
        tournaments.append(tournament)
        save_tournaments(tournaments)
        await message.answer("✅ Турнир сохранён!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {e}")

# РАССЫЛКА
@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcasting(callback: CallbackQuery, state: FSMContext):
    await state.set_state("broadcast")
    await callback.message.answer("📢 Отправь сообщение (текст или фото с подписью) для рассылки.")

@dp.message()
async def broadcast_handler(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or await state.get_state() != "broadcast":
        return
    await state.clear()
    tournaments = load_tournaments()
    recipients = {ADMIN_ID}
    for t in tournaments:
        if "telegram_id" in t:
            recipients.add(t["telegram_id"])
    for uid in recipients:
        try:
            if message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            elif message.text:
                await bot.send_message(uid, message.text)
        except:
            continue
    await message.answer("✅ Рассылка завершена!")

# АВТОЧИСТКА + ЗАПУСК
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
