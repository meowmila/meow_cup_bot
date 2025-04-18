import os
import logging
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

API_TOKEN = "7507739946:AAE0p-9CEJWjUM0oXYamsakLvCEvz5KnLJA"
ADMIN_ID = 947800235

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
users = set()
tournaments_file = "tournaments.json"

if not os.path.exists(tournaments_file):
    with open(tournaments_file, "w") as f:
        json.dump([], f)

def load_tournaments():
    with open(tournaments_file, "r") as f:
        return json.load(f)

def save_tournaments(data):
    with open(tournaments_file, "w") as f:
        json.dump(data, f, indent=2)

def get_upcoming_dates():
    today = datetime.now().date()
    return [(today + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(3)]

@dp.message(F.text == "/start")
async def start(message: Message):
    users.add(message.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.button(text="Турнир", callback_data="type_Турнир")
    kb.button(text="Ивент", callback_data="type_Ивент")
    kb.button(text="Праки", callback_data="type_Праки")
    kb.adjust(2)
    await message.answer("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("type_"))
async def select_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(type=callback.data.split("_")[1])
    kb = InlineKeyboardBuilder()
    for date in get_upcoming_dates():
        kb.button(text=date, callback_data=f"date_{date}")
    kb.button(text="Назад", callback_data="back_start")
    kb.adjust(1)
    await callback.message.edit_text("<b>Выберите дату:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("date_"))
async def select_date(callback: CallbackQuery, state: FSMContext):
    await state.update_data(date=callback.data.split("_")[1])
    kb = InlineKeyboardBuilder()
    kb.button(text="18:00", callback_data="time_18")
    kb.button(text="21:00", callback_data="time_21")
    kb.button(text="Назад", callback_data="back_type")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите время:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("time_"))
async def select_time(callback: CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data.split("_")[1])
    kb = InlineKeyboardBuilder()
    kb.button(text="Free", callback_data="access_Free")
    kb.button(text="VIP", callback_data="access_VIP")
    kb.button(text="Назад", callback_data="back_date")
    kb.adjust(2)
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
    kb.button(text="Назад", callback_data="back_time")
    kb.adjust(2)
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
        kb.button(text="Назад", callback_data="back_stage")
    else:
        kb.button(text="Назад", callback_data="back_access")

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
            await callback.message.answer_photo(types.FSInputFile(t["photo"]), caption=caption)
        else:
            await callback.message.answer(caption)

    await callback.message.answer("<b>⬅ Назад к выбору</b>", reply_markup=kb.as_markup())

# Все кнопки Назад
@dp.callback_query(F.data == "back_stage")
async def back_to_stage(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="1/2", callback_data="stage_1/2")
    kb.button(text="1/4", callback_data="stage_1/4")
    kb.button(text="1/8", callback_data="stage_1/8")
    kb.button(text="Назад", callback_data="back_time")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите стадию:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_access")
async def back_to_access(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="Free", callback_data="access_Free")
    kb.button(text="VIP", callback_data="access_VIP")
    kb.button(text="Назад", callback_data="back_date")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите доступ:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_time")
async def back_to_time(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="18:00", callback_data="time_18")
    kb.button(text="21:00", callback_data="time_21")
    kb.button(text="Назад", callback_data="back_date")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите время:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_date")
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for date in get_upcoming_dates():
        kb.button(text=date, callback_data=f"date_{date}")
    kb.button(text="Назад", callback_data="back_type")
    kb.adjust(1)
    await callback.message.edit_text("<b>Выберите дату:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_type")
async def back_to_type(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="Турнир", callback_data="type_Турнир")
    kb.button(text="Ивент", callback_data="type_Ивент")
    kb.button(text="Праки", callback_data="type_Праки")
    kb.adjust(2)
    await callback.message.edit_text("<b>Выберите тип мероприятия:</b>", reply_markup=kb.as_markup())

@dp.message(F.photo)
async def add_tournament(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.caption:
        await message.answer("❗ Шаблон:\nTitle: ...\nType: Турнир/Ивент/Праки\nDate: ...\nTime: ...\nPrize: ...\nLink: ...\nAccess: Free/VIP\nStage: ...")
        return
    try:
        data = {line.split(":")[0].strip().lower(): line.split(":")[1].strip() for line in message.caption.split("\n") if ":" in line}
        file_path = f"photos/{message.photo[-1].file_id}.jpg"
        os.makedirs("photos", exist_ok=True)
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
        await message.answer("✅ Турнир добавлен!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(F.text == "/broadcast")
async def start_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state("broadcast")
    await message.answer("📢 Отправь текст или фото с подписью для рассылки:")

@dp.message()
async def broadcast_message(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if await state.get_state() != "broadcast":
        return
    await state.clear()
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
async def on_startup(bot: Bot):
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
