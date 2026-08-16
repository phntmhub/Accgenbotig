# language: Python, file: bot.py
# TELEGRAM BOT — Directly imports gen.py

import os
import sys
import json
import threading
import time
import logging
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== SETUP LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== BOT TOKEN ==========
BOT_TOKEN = "8666894951:AAGpPy7mOl4ghn3XjGGd1hat7dZ4E6-eUNA"

# ========== IMPORT GEN.PY ==========
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gen import (
        create_account,
        check_rarity,
        check_couple,
        save_normal_account,
        save_rare_account,
        save_couple_account,
        save_jwt_token,
        ACCOUNTS_FOLDER,
        RARE_ACCOUNTS_FOLDER,
        COUPLES_ACCOUNTS_FOLDER,
        GHOST_ACCOUNTS_FOLDER,
        GHOST_RARE_FOLDER,
        GHOST_COUPLES_FOLDER,
        BASE_FOLDER,
        EXIT_FLAG
    )
    logger.info("✅ gen.py imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import gen.py: {e}")
    logger.error("Make sure gen.py is in the same directory as bot.py")
    sys.exit(1)

# ========== TELEGRAM BOT ==========
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== GLOBALS ==========
user_sessions = {}
gen_threads = {}
stop_flags = {}
result_buffers = {}

# ========== KEYBOARDS ==========
def region_keyboard():
    kb = InlineKeyboardMarkup(row_width=4)
    regions = ["ME", "IND", "ID", "VN", "TH", "BD", "PK", "TW", "CIS", "SAC", "BR"]
    buttons = [InlineKeyboardButton(r, callback_data=f"region_{r}") for r in regions]
    kb.add(*buttons)
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return kb

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Generate", callback_data="gen_start"),
        InlineKeyboardButton("📊 Stats", callback_data="stats"),
        InlineKeyboardButton("📁 View Accounts", callback_data="view"),
        InlineKeyboardButton("⏹ Stop", callback_data="stop")
    )
    return kb

# ========== BOT COMMANDS ==========
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    user_id = msg.from_user.id
    bot.send_message(
        user_id,
        f"<b>🔥 DOPPY Guest Generator Bot</b>\n\n"
        f"Generate Free Fire guest accounts via Telegram.\n"
        f"Region, GHOST mode, rarity scanning, couples matching.\n\n"
        f"<i>Send /gen to start</i>",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=['gen'])
def gen_cmd(msg):
    user_id = msg.from_user.id
    if user_id in gen_threads and gen_threads[user_id].is_alive():
        bot.send_message(user_id, "⚠️ Generation already running. Use /stop to halt.")
        return
    bot.send_message(user_id, "🌍 Select region:", reply_markup=region_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("region_"))
def region_cb(call):
    user_id = call.from_user.id
    region = call.data.replace("region_", "")
    is_ghost = region == "BR"
    
    user_sessions[user_id] = {
        "region": region,
        "is_ghost": is_ghost,
        "name_prefix": None,
        "pass_prefix": None,
        "count": None,
        "threshold": 4,
        "threads": 5
    }
    
    bot.edit_message_text(
        f"📝 Region set: <b>{region}</b> {'(GHOST)' if is_ghost else ''}\n"
        f"Send /setname to choose account name prefix.",
        chat_id=user_id,
        message_id=call.message.message_id
    )

@bot.message_handler(commands=['setname'])
def setname_cmd(msg):
    user_id = msg.from_user.id
    if user_id not in user_sessions:
        bot.send_message(user_id, "Start /gen first.")
        return
    bot.send_message(user_id, "✏️ Send your account name prefix (e.g., <code>Doppy</code>):")
    bot.register_next_step_handler(msg, process_name_prefix)

def process_name_prefix(msg):
    user_id = msg.from_user.id
    user_sessions[user_id]["name_prefix"] = msg.text.strip() or "Dop"
    bot.send_message(user_id, "🔑 Send your password prefix:")
    bot.register_next_step_handler(msg, process_pass_prefix)

def process_pass_prefix(msg):
    user_id = msg.from_user.id
    user_sessions[user_id]["pass_prefix"] = msg.text.strip() or "Pass"
    bot.send_message(user_id, "🔢 Send number of accounts to generate (1-50):")
    bot.register_next_step_handler(msg, process_count)

def process_count(msg):
    user_id = msg.from_user.id
    try:
        count = int(msg.text.strip())
        if count <= 0 or count > 50:
            raise ValueError
        user_sessions[user_id]["count"] = count
    except:
        bot.send_message(user_id, "❌ Enter a number between 1 and 50.")
        bot.register_next_step_handler(msg, process_count)
        return
    
    bot.send_message(user_id, "🎯 Rarity threshold (1-15, default 4):")
    bot.register_next_step_handler(msg, process_threshold)

def process_threshold(msg):
    user_id = msg.from_user.id
    try:
        threshold = int(msg.text.strip())
        if 1 <= threshold <= 15:
            user_sessions[user_id]["threshold"] = threshold
        else:
            user_sessions[user_id]["threshold"] = 4
    except:
        user_sessions[user_id]["threshold"] = 4
    
    bot.send_message(user_id, "⚡ Thread pool count (default 5, max 10):")
    bot.register_next_step_handler(msg, process_threads)

def process_threads(msg):
    user_id = msg.from_user.id
    try:
        threads = int(msg.text.strip())
        if threads > 0:
            user_sessions[user_id]["threads"] = min(threads, 10)
        else:
            user_sessions[user_id]["threads"] = 5
    except:
        user_sessions[user_id]["threads"] = 5
    
    session = user_sessions[user_id]
    
    bot.send_message(
        user_id,
        f"✅ <b>Configuration confirmed</b>\n"
        f"Region: {session['region']} {'(GHOST)' if session['is_ghost'] else ''}\n"
        f"Name: {session['name_prefix']}\n"
        f"Count: {session['count']}\n"
        f"Threshold: {session['threshold']}\n"
        f"Threads: {session['threads']}\n\n"
        f"🚀 Starting generation...",
        reply_markup=main_menu()
    )
    
    stop_flags[user_id] = False
    result_buffers[user_id] = []
    t = threading.Thread(target=generator_worker, args=(user_id, session))
    t.daemon = True
    gen_threads[user_id] = t
    t.start()

# ========== GENERATOR WORKER ==========
def generator_worker(user_id, session):
    total = session["count"]
    success = 0
    rare = 0
    couples = 0
    start_time = time.time()
    status_msg = None
    
    region = session["region"]
    is_ghost = session["is_ghost"]
    name_prefix = session["name_prefix"]
    pass_prefix = session["pass_prefix"]
    threads = session["threads"]
    
    accounts = []
    
    global EXIT_FLAG
    EXIT_FLAG = False
    
    logger.info(f"🔄 Worker started: {total} accounts, {threads} threads")
    
    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for i in range(total):
                if stop_flags.get(user_id, False):
                    break
                futures.append(
                    executor.submit(
                        create_account,
                        region,
                        name_prefix,
                        pass_prefix,
                        is_ghost
                    )
                )
                time.sleep(0.5)
            
            for future in as_completed(futures):
                if stop_flags.get(user_id, False):
                    break
                
                try:
                    result = future.result(timeout=30)
                except Exception as e:
                    logger.error(f"❌ Future error: {e}")
                    continue
                
                if not result or result.get("account_id", "N/A") == "N/A":
                    continue
                
                success += 1
                accounts.append(result)
                result_buffers[user_id].append(result)
                
                save_normal_account(result, "GHOST" if is_ghost else region, is_ghost)
                
                is_rare, rtype, reason, rscore = check_rarity(result)
                if is_rare:
                    rare += 1
                    save_rare_account(result, rtype, reason, rscore, is_ghost)
                
                is_couple, creason, partner = check_couple(result, 0)
                if is_couple and partner:
                    couples += 1
                    save_couple_account(result, partner, creason, is_ghost)
                
                if result.get('jwt_token'):
                    save_jwt_token(result, result['jwt_token'], "GHOST" if is_ghost else region, is_ghost)
                
                logger.info(f"✅ Account {success}/{total}: {result.get('account_id')}")
                
                if success % 5 == 0:
                    try:
                        elapsed = time.time() - start_time
                        status_text = (
                            f"⏳ Generating... {success}/{total}\n"
                            f"Rare: {rare} | Couples: {couples}\n"
                            f"Elapsed: {elapsed:.1f}s"
                        )
                        if status_msg:
                            bot.edit_message_text(status_text, user_id, status_msg.message_id)
                        else:
                            status_msg = bot.send_message(user_id, status_text)
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"❌ Worker error: {e}")
        bot.send_message(user_id, f"❌ Error: {str(e)[:200]}")
    
    elapsed = time.time() - start_time
    logger.info(f"🏁 Generation complete: {success} accounts in {elapsed:.1f}s")
    
    if accounts:
        account_file = f"account_{region}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(account_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, indent=2, ensure_ascii=False)
            
            with open(account_file, 'rb') as f:
                bot.send_document(
                    user_id,
                    f,
                    caption=f"✅ <b>Generation Complete</b>\n\n"
                           f"Region: {region} {'(GHOST)' if is_ghost else ''}\n"
                           f"Generated: {success}\n"
                           f"Rare: {rare}\n"
                           f"Couples: {couples}\n"
                           f"Time: {elapsed:.1f}s",
                    reply_markup=main_menu()
                )
            os.remove(account_file)
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            bot.send_message(
                user_id,
                f"✅ Generated: {success}\nRare: {rare}\nCouples: {couples}\nTime: {elapsed:.1f}s",
                reply_markup=main_menu()
            )
    else:
        bot.send_message(
            user_id,
            f"❌ No accounts generated. Check logs.",
            reply_markup=main_menu()
        )
    
    gen_threads.pop(user_id, None)
    stop_flags.pop(user_id, None)
    result_buffers.pop(user_id, None)

# ========== COMMAND: STOP ==========
@bot.message_handler(commands=['stop'])
@bot.callback_query_handler(func=lambda call: call.data == "stop")
def stop_cmd(call_or_msg):
    if hasattr(call_or_msg, 'from_user'):
        user_id = call_or_msg.from_user.id
    else:
        user_id = call_or_msg.from_user.id
    
    stop_flags[user_id] = True
    global EXIT_FLAG
    EXIT_FLAG = True
    
    if user_id in result_buffers and result_buffers[user_id]:
        results = result_buffers[user_id]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        partial_file = f"partial_{timestamp}.json"
        with open(partial_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        try:
            with open(partial_file, 'rb') as f:
                bot.send_document(
                    user_id,
                    f,
                    caption=f"⏹ Stopped\nAccounts: {len(results)}",
                    reply_markup=main_menu()
                )
        except:
            bot.send_message(user_id, f"⏹ Stopped. {len(results)} accounts.", reply_markup=main_menu())
        os.remove(partial_file)
    result_buffers.pop(user_id, None)
    bot.send_message(user_id, "⏹ Generation stopped.", reply_markup=main_menu())

# ========== COMMAND: STATS ==========
@bot.message_handler(commands=['stats'])
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats_cmd(call_or_msg):
    if hasattr(call_or_msg, 'from_user'):
        user_id = call_or_msg.from_user.id
    else:
        user_id = call_or_msg.from_user.id
    
    total_normal = 0
    total_rare = 0
    total_couples = 0
    
    for folder in [ACCOUNTS_FOLDER, GHOST_ACCOUNTS_FOLDER]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith('.json'):
                    try:
                        with open(os.path.join(folder, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                total_normal += len(data)
                    except:
                        pass
    
    for folder in [RARE_ACCOUNTS_FOLDER, GHOST_RARE_FOLDER]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith('.json'):
                    try:
                        with open(os.path.join(folder, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                total_rare += len(data)
                    except:
                        pass
    
    for folder in [COUPLES_ACCOUNTS_FOLDER, GHOST_COUPLES_FOLDER]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith('.json'):
                    try:
                        with open(os.path.join(folder, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                total_couples += len(data)
                    except:
                        pass
    
    bot.send_message(
        user_id,
        f"📊 <b>Stats</b>\n\nNormal: {total_normal}\nRare: {total_rare}\nCouples: {total_couples}",
        reply_markup=main_menu()
    )

# ========== COMMAND: VIEW ==========
@bot.message_handler(commands=['view'])
@bot.callback_query_handler(func=lambda call: call.data == "view")
def view_cmd(call_or_msg):
    if hasattr(call_or_msg, 'from_user'):
        user_id = call_or_msg.from_user.id
    else:
        user_id = call_or_msg.from_user.id
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📄 Normal", callback_data="view_normal"),
        InlineKeyboardButton("⭐ Rare", callback_data="view_rare"),
        InlineKeyboardButton("💑 Couples", callback_data="view_couples"),
        InlineKeyboardButton("🔙 Back", callback_data="cancel")
    )
    bot.send_message(user_id, "Select account type:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_"))
def view_type_cb(call):
    user_id = call.from_user.id
    view_type = call.data.replace("view_", "")
    
    if view_type == "normal":
        folders = [ACCOUNTS_FOLDER, GHOST_ACCOUNTS_FOLDER]
    elif view_type == "rare":
        folders = [RARE_ACCOUNTS_FOLDER, GHOST_RARE_FOLDER]
    elif view_type == "couples":
        folders = [COUPLES_ACCOUNTS_FOLDER, GHOST_COUPLES_FOLDER]
    else:
        return
    
    all_accounts = []
    for folder in folders:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith('.json'):
                    try:
                        with open(os.path.join(folder, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                all_accounts.extend(data)
                    except:
                        pass
    
    if not all_accounts:
        bot.send_message(user_id, "No accounts found.")
        return
    
    recent = all_accounts[-20:] if len(all_accounts) > 20 else all_accounts
    text = f"📄 <b>{view_type.upper()}</b> (last {len(recent)} of {len(all_accounts)})\n\n"
    
    for entry in recent:
        if view_type == "couples":
            text += f"💑 {entry.get('couple_id', entry.get('account1', {}).get('account_id', 'N/A'))}\n"
        else:
            text += f"🆔 {entry.get('account_id', 'N/A')} | {entry.get('name', 'N/A')}\n"
    
    bot.send_message(user_id, text[:4000], reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_cb(call):
    bot.edit_message_text("✅ Cancelled.", call.from_user.id, call.message.message_id)
    bot.send_message(call.from_user.id, "Back to menu.", reply_markup=main_menu())

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.send_message(
        msg.from_user.id,
        "<b>📖 Commands</b>\n\n"
        "/start - Main menu\n"
        "/gen - Start generation\n"
        "/stop - Stop generation\n"
        "/stats - View stats\n"
        "/view - View accounts\n"
        "/help - This message",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda msg: True)
def echo_all(msg):
    bot.reply_to(msg, "Unknown command. Send /help")

# ========== MAIN ==========
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 DOPPY Bot starting...")
    logger.info(f"✓ Token: {BOT_TOKEN[:10]}...")
    logger.info(f"✓ Using gen.py from: {os.path.dirname(os.path.abspath(__file__))}")
    logger.info("=" * 60)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
