import asyncio
import subprocess
import os
import platform
import psutil
import configparser
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

config = configparser.ConfigParser()
config.read("config.ini")

bot = Bot(token=config['telegram']['token'])
dp = Dispatcher(bot)


running_scripts = {}

async def check_access(user_id):
    allowed_users = config['telegram']['allowed_users'].split(',')
    return str(user_id) in allowed_users

def get_script_list():
    scripts_path = config['telegram']['scripts_path']
    return [file for file in os.listdir(scripts_path) if file.endswith('.py')]

def get_python_processes():
    return [proc for proc in psutil.process_iter(attrs=['pid', 'cmdline']) if proc.info['cmdline'] and 'python' in proc.info['cmdline'][0]]

def get_system_info():
    info = platform.uname()
    uptime = int(time.time() - psutil.boot_time())
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    info_str = f"System Information:\n"
    info_str += f"System: {info.system}\n"
    info_str += f"Node Name: {info.node}\n"
    info_str += f"Release: {info.release}\n"
    info_str += f"Version: {info.version}\n"
    info_str += f"Machine: {info.machine}\n"
    info_str += f"Uptime: {uptime} seconds\n"
    info_str += f"CPU Count: {cpu_count}\n"
    info_str += f"CPU Usage: {cpu_percent}%\n"
    info_str += f"Memory Total: {memory.total / (1024 * 1024)} MB\n"
    info_str += f"Memory Used: {memory.used / (1024 * 1024)} MB\n"
    return info_str

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if await check_access(message.from_user.id):
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("Список", callback_data="list_scripts"),
                     InlineKeyboardButton("Запуск", callback_data="run_script"))
        keyboard.row(InlineKeyboardButton("Остановка", callback_data="stop_script"),
                     InlineKeyboardButton("System Info", callback_data="system_info"))
        await message.answer("Выбирай:", reply_markup=keyboard)
    else:
        await message.answer("Доступ запрещен.")

@dp.callback_query_handler(lambda query: True)
async def process_callback(callback_query: types.CallbackQuery):
    if not await check_access(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.")
        return

    data = callback_query.data

    if data == "list_scripts":
        script_list = get_script_list()
        response = "Available scripts:\n" + "\n".join(script_list)
        await callback_query.answer(response)

    elif data == "run_script":
        script_list = get_script_list()
        buttons = [InlineKeyboardButton(script, callback_data=f"run_{script}") for script in script_list]
        keyboard = InlineKeyboardMarkup().add(*buttons)
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)

    elif data.startswith("run_"):
        script_name = data[4:]
        script_path = os.path.join(config['telegram']['scripts_path'], script_name)
        process = subprocess.Popen(['python', script_path])
        running_scripts[script_name] = {"pid": process.pid, "process_obj": process}
        await callback_query.answer(f"Скрипт {script_name} был запущен с PID: {process.pid}")

    elif data == "stop_script":
        running_pids = [running_scripts[script]["pid"] for script in running_scripts]
        buttons = [InlineKeyboardButton(f"PID: {pid}", callback_data=f"stop_{pid}") for pid in running_pids]
        keyboard = InlineKeyboardMarkup().add(*buttons)
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)

    elif data.startswith("stop_"):
        pid = int(data[5:])
        for script, info in running_scripts.items():
            if info["pid"] == pid:
                info["process_obj"].terminate()
                del running_scripts[script]
                await callback_query.answer(f"Скрипт с PID {pid} был остановлен.")
                return
        await callback_query.answer(f"Скрипт с PID {pid} не запущен.")

    elif data == "system_info":
        info = get_system_info()
        await bot.send_message(callback_query.from_user.id, info)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
