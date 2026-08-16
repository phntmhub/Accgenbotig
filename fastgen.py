# language: Python, file: bot.py, runtime: Python 3.8+
# COMPLETE RE-WRITE — Using app.py's working engine

import os
import sys
import json
import threading
import time
import random
import string
import base64
import hashlib
import hmac
import re
import codecs
import uuid
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
import urllib3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== BOT TOKEN ==========
BOT_TOKEN = "8666894951:AAGpPy7mOl4ghn3XjGGd1hat7dZ4E6-eUNA"

# ========== FOLDER STRUCTURE ==========
BASE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RAO_GUEST_GEN")
FOLDERS = [
    os.path.join(BASE_FOLDER, "TOKENS-JWT"),
    os.path.join(BASE_FOLDER, "ACCOUNTS"),
    os.path.join(BASE_FOLDER, "RARE ACCOUNTS"),
    os.path.join(BASE_FOLDER, "COUPLES ACCOUNTS"),
    os.path.join(BASE_FOLDER, "GHOST", "ACCOUNTS"),
    os.path.join(BASE_FOLDER, "GHOST", "RAREACCOUNT"),
    os.path.join(BASE_FOLDER, "GHOST", "COUPLESACCOUNT"),
    os.path.join(BASE_FOLDER, "GHOST", "TOKENS-JWT"),
]

for folder in FOLDERS:
    os.makedirs(folder, exist_ok=True)

# ========== TELEGRAM BOT INIT ==========
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== CONSTANTS (from app.py) ==========
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
REGION_LANG = {
    "IND":"hi", "BR":"pt", "US":"en", "ID":"id", "TH":"th",
    "VN":"vi", "ME":"ar", "SG":"ms", "PK":"ur", "BD":"bn"
}
RARITY_SCORE_THRESHOLD = 4
EXIT_FLAG = False

# ============================================================
#  PROTOBUF HELPERS (from app.py)
# ============================================================
def varint_encode(n):
    out = []
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)

def build_field(field_num, value):
    if isinstance(value, int):
        return varint_encode((field_num << 3) | 0) + varint_encode(value)
    elif isinstance(value, (str, bytes)):
        data = value.encode('utf-8') if isinstance(value, str) else value
        return varint_encode((field_num << 3) | 2) + varint_encode(len(data)) + data
    elif isinstance(value, dict):
        sub = assemble_proto(value)
        return varint_encode((field_num << 3) | 2) + varint_encode(len(sub)) + sub
    else:
        raise TypeError(f"Unsupported type: {type(value)}")

def assemble_proto(fields):
    packet = b''
    for k, v in fields.items():
        idx = int(k)
        if isinstance(v, list):
            for item in v:
                packet += build_field(idx, item)
        else:
            packet += build_field(idx, v)
    return packet

def aes_encrypt(plain):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    pad_len = 16 - (len(plain) % 16)
    if pad_len == 0:
        pad_len = 16
    return cipher.encrypt(plain + bytes([pad_len]) * pad_len)

def parse_proto(data):
    from google.protobuf.internal.decoder import _DecodeVarint, _DecodeVarint32
    pos, length = 0, len(data)
    result = {}
    while pos < length:
        key, pos = _DecodeVarint(data, pos)
        field = key >> 3
        wire = key & 7
        if wire == 0:
            val, pos = _DecodeVarint(data, pos)
        elif wire == 2:
            size, pos = _DecodeVarint32(data, pos)
            raw = data[pos:pos+size]
            pos += size
            try:
                val = parse_proto(raw)
            except:
                try:
                    val = raw.decode('utf-8')
                except:
                    val = raw.hex()
        elif wire == 5:
            val = int.from_bytes(data[pos:pos+4], 'little')
            pos += 4
        elif wire == 1:
            val = int.from_bytes(data[pos:pos+8], 'little')
            pos += 8
        else:
            raise Exception(f"Unknown wire type: {wire}")
        if field in result:
            if not isinstance(result[field], list):
                result[field] = [result[field]]
            result[field].append(val)
        else:
            result[field] = val
    return result

# ============================================================
#  HELPERS (from app.py)
# ============================================================
def generate_random_user_id():
    return f"Google|{str(uuid.uuid4())}"

def random_user_agent_msdk():
    devices = ["ASUS_AI2401_A", "SM-G998B", "CPH2095", "Pixel 6", "OnePlus 9 Pro", "Samsung Galaxy S23 Ultra"]
    device = random.choice(devices)
    version = random.choice(["9", "10", "11", "12", "13"])
    lang = random.choice(["en", "hi", "id", "th"])
    region = random.choice(["US", "IND", "ID", "TH"])
    return f"GarenaMSDK/4.0.42({device};Android {version};{lang};{region};)"

def random_user_agent_unity():
    return "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"

def random_nickname(prefix):
    adjectives = ["Cool", "Happy", "Fast", "Smart", "Brave", "Lucky", "Mighty", "Shadow", "Blaze", "Phoenix"]
    nouns = ["Tiger", "Eagle", "Wolf", "Dragon", "Falcon", "Viper", "Cobra", "Ninja", "Knight", "Ghost"]
    nickname = prefix + random.choice(adjectives) + random.choice(nouns) + ''.join(random.choices(string.digits, k=4))
    return nickname[:15]

def random_password(base):
    chars = string.ascii_letters + string.digits
    suffix = ''.join(random.choices(chars, k=6))
    return f"{base}_{suffix}"

def get_public_ip(session=None):
    try:
        if session:
            r = session.get('https://api.ipify.org', timeout=5)
        else:
            r = requests.get('https://api.ipify.org', timeout=5)
        return r.text
    except:
        return "27.59.69.226"

# ============================================================
#  CORE FUNCTIONS (from app.py — WORKING)
# ============================================================
def register_guest(session, password):
    """Register guest account — returns UID"""
    url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
    payload = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
    headers = {
        "User-Agent": random_user_agent_msdk(),
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive"
    }
    resp = session.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Register failed: {data}")
    return str(data["data"]["uid"])

def token_grant(session, uid, password):
    """Get access_token and open_id from UID + password"""
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    payload = {
        "uid": str(uid),
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": CLIENT_SECRET,
        "client_id": "100067"
    }
    headers = {
        "User-Agent": random_user_agent_msdk(),
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive"
    }
    resp = session.post(url, data=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        resp.raise_for_status()
    data = resp.json()
    access_token = data.get('access_token')
    open_id = data.get('open_id')
    if not access_token or not open_id:
        raise Exception(f"Token grant failed: {data}")
    return access_token, open_id

def major_register(session, nickname, access_token, open_id, region):
    """MajorRegister — returns parsed protobuf response"""
    if region.upper() in ["ME", "TH"]:
        base = "loginbp.common.ggbluefox.com"
    else:
        base = "loginbp.ggblueshark.com"
    url = f"https://{base}/MajorRegister"

    # XOR encode open_id (from app.py)
    xor_key = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
               0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    encoded = ''.join(chr(ord(c) ^ xor_key[i % len(xor_key)]) for i, c in enumerate(open_id))
    unicode_esc = ''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in encoded)
    field_bytes = codecs.decode(unicode_esc, 'unicode_escape').encode('latin1')

    lang = REGION_LANG.get(region.upper(), "en")
    
    # Field mapping from app.py
    fields = {
        "1": nickname,
        "2": access_token,
        "3": open_id,
        "5": 102000007,
        "6": 4,
        "7": 1,
        "13": 1,
        "14": field_bytes,
        "15": lang,
        "16": 2,
        "20": "2.127.16",
        "21": 1
    }
    plain = assemble_proto(fields)
    encrypted = aes_encrypt(plain)
    
    headers = {
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "Host": base,
        "ReleaseVersion": "OB54",
        "User-Agent": random_user_agent_unity(),
        "X-GA": "v1 1",
        "X-Unity-Version": "2022.3.47f1"
    }
    resp = session.post(url, headers=headers, data=encrypted, timeout=15)
    if resp.status_code != 200:
        resp.raise_for_status()
    return parse_proto(resp.content)

def major_login(session, access_token, open_id, region):
    """MajorLogin — returns parsed protobuf and JWT"""
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = get_public_ip(session)
    user_id = generate_random_user_id()
    lang = REGION_LANG.get(region.upper(), "en")
    
    # Field mapping from app.py
    fields = {
        3: now,
        4: "free fire",
        5: 1,
        7: "2.127.13",
        8: "Android OS 5.1.1 / API-22 (LMY48Z/rel.se.infra.20220128.171448)",
        9: "Handheld",
        10: "Jio",
        11: "WIFI",
        17: "Adreno (TM) 640",
        18: "OpenGL ES 3.0",
        19: user_id,
        20: ip,
        21: lang,
        22: open_id,
        23: 4,
        24: "Handheld",
        25: "realme RMX2189",
        26: region.upper(),
        29: access_token,
        33: "Jio",
        34: "WIFI",
        37: "7428b253defc164018c604a1ebbfebdf",
        73: "/data/app/com.dts.freefireth-1/lib/arm",
        75: "H4c322aeb56444feaa151d1ea91a8f7f2|/data/app/com.dts.freefireth-1/base.apk",
        76: 2,
        78: 2,
        79: 2,
        83: "OpenGLES2",
        85: "Mumbai",
        87: "android",
        88: "KqsHTywQqGHMgPbDY9P2mhkxXj/beObk/TFNpmgaucQwxyLu9hA478WEQCV0Mgaz9UivYUPpKNwPzgZhvDhSsUDMAFY=",
        90: '{"cur_rate":null,"support_etc2":false}',
        97: 1,
        98: 1,
        99: "4",
        100: "4"
    }
    packet = assemble_proto(fields)
    encrypted = aes_encrypt(packet)
    
    headers = {
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "ReleaseVersion": "OB54",
        "User-Agent": random_user_agent_unity(),
        "X-GA": "v1 1",
        "X-Unity-Version": "2022.3.47f1"
    }
    resp = session.post(url, headers=headers, data=encrypted, timeout=15)
    if resp.status_code != 200:
        resp.raise_for_status()
    decoded = parse_proto(resp.content)
    jwt = decoded.get(8)
    if isinstance(jwt, list):
        jwt = jwt[0]
    return decoded, jwt

def decode_account_id_from_jwt(jwt):
    """Extract account_id from JWT payload"""
    if not jwt:
        return None
    try:
        parts = jwt.split('.')
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        account_id = decoded.get('account_id') or decoded.get('external_id')
        if account_id:
            return str(account_id)
        return None
    except:
        return None

# ============================================================
#  ACCOUNT CREATION (from app.py — WORKING)
# ============================================================
def create_account(region, account_name, password_prefix, is_ghost=False):
    """Create a single account using app.py's working flow"""
    if EXIT_FLAG:
        return None
    
    session = requests.Session()
    session.verify = False
    
    for attempt in range(3):
        try:
            password = random_password(password_prefix)
            nickname = random_nickname(account_name)
            
            # Step 1: Register guest
            uid = register_guest(session, password)
            
            # Step 2: Get token
            access_token, open_id = token_grant(session, uid, password)
            
            # Step 3: Major Register
            reg_resp = major_register(session, nickname, access_token, open_id, region)
            game_uid = str(reg_resp.get(3))
            if not game_uid:
                raise Exception("No game_uid from MajorRegister")
            
            # Step 4: Major Login
            login_resp, jwt = major_login(session, access_token, open_id, region)
            
            # Step 5: Decode account ID
            account_id = decode_account_id_from_jwt(jwt)
            if not account_id:
                account_id = game_uid
            
            return {
                "uid": uid,
                "game_uid": game_uid,
                "password": password,
                "nickname": nickname,
                "region": "GHOST" if is_ghost else region,
                "account_id": account_id,
                "jwt_token": jwt,
                "access_token": access_token,
                "open_id": open_id,
                "status": "success"
            }
            
        except Exception as e:
            print(f"[!] Attempt {attempt+1} failed: {e}")
            time.sleep(random.uniform(1, 2) * (attempt + 1))
            continue
    
    return None

# ============================================================
#  RARITY & COUPLES CHECKING
# ============================================================
PATTERNS = {
    "R4": [r"(\d)\1{3,}", 3], "R3": [r"(\d)\1\1(\d)\2\2", 2],
    "S5": [r"(12345|23456|34567|45678|56789)", 4], "S4": [r"(0123|1234|2345|3456|4567|5678|6789|9876|8765|7654|6543|5432|4321|3210)", 3],
    "P6": [r"^(\d)(\d)(\d)\3\2\1$", 5], "P4": [r"^(\d)(\d)\2\1$", 3],
    "SPH": [r"(69|420|1337|007)", 4], "SPM": [r"(100|200|300|400|500|666|777|888|999)", 2],
    "QD": [r"(1111|2222|3333|4444|5555|6666|7777|8888|9999|0000)", 4],
    "MH": [r"^(\d{2,3})\1$", 3], "MM": [r"(\d{2})0\1", 2], "GD": [r"1618|0618", 3]
}

COMPILED_PATTERNS = {}
for ptype, (pattern, points) in PATTERNS.items():
    COMPILED_PATTERNS[ptype] = (re.compile(pattern), points)

def check_rarity(account_data):
    account_id = account_data.get("account_id", "")
    if not account_id or account_id == "N/A":
        return False, None, None, 0
    score = 0
    patterns_found = []
    for ptype, (pattern, pts) in COMPILED_PATTERNS.items():
        if pattern.search(account_id):
            score += pts
            patterns_found.append(ptype)
    digits = [int(d) for d in account_id if d.isdigit()]
    if len(set(digits)) == 1 and len(digits) >= 4:
        score += 5
        patterns_found.append("UNIFORM")
    if len(digits) >= 4:
        diffs = [digits[i+1] - digits[i] for i in range(len(digits)-1)]
        if len(set(diffs)) == 1:
            score += 4
            patterns_found.append("ARITHMETIC")
    if len(account_id) <= 8 and account_id.isdigit() and int(account_id) < 1000000:
        score += 3
        patterns_found.append("LOW_ID")
    if score >= RARITY_SCORE_THRESHOLD:
        reason = f"ID:{account_id} | Score:{score} | {','.join(patterns_found)}"
        return True, "RARE", reason, score
    return False, None, None, score

COUPLES_DATA = {}
COUPLES_LOCK = threading.Lock()

def check_couple(account_data, thread_id):
    account_id = account_data.get("account_id", "")
    if not account_id or account_id == "N/A":
        return False, None, None
    with COUPLES_LOCK:
        for stored_id, stored in list(COUPLES_DATA.items()):
            stored_aid = stored.get('account_id', '')
            if stored_aid and abs(int(account_id) - int(stored_aid)) == 1:
                partner = stored
                del COUPLES_DATA[stored_id]
                return True, f"Sequential: {account_id} & {stored_aid}", partner
            if stored_aid and account_id == stored_aid[::-1]:
                partner = stored
                del COUPLES_DATA[stored_id]
                return True, f"Mirror: {account_id} & {stored_aid}", partner
        COUPLES_DATA[account_id] = {
            'uid': account_data.get('uid', ''),
            'account_id': account_id,
            'name': account_data.get('nickname', ''),
            'password': account_data.get('password', ''),
            'region': account_data.get('region', ''),
            'thread_id': thread_id,
            'timestamp': datetime.now().isoformat()
        }
    return False, None, None

# ============================================================
#  SAVE FUNCTIONS
# ============================================================
def save_account_data(account_data, folder, filename=None):
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"accounts_{timestamp}.json"
    
    filepath = os.path.join(folder, filename)
    existing = []
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
        except:
            existing = []
    
    existing.append(account_data)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    return filepath

# ============================================================
#  TELEGRAM BOT
# ============================================================
user_sessions = {}
gen_threads = {}
stop_flags = {}
result_buffers = {}

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

# ============================================================
#  BOT COMMANDS
# ============================================================
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
    bot.send_message(
        user_id,
        "🌍 Select region:",
        reply_markup=region_keyboard()
    )

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
        "threads": 10
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
    bot.send_message(user_id, "🔢 Send number of accounts to generate (1-200):")
    bot.register_next_step_handler(msg, process_count)

def process_count(msg):
    user_id = msg.from_user.id
    try:
        count = int(msg.text.strip())
        if count <= 0 or count > 200:
            raise ValueError
        user_sessions[user_id]["count"] = count
    except:
        bot.send_message(user_id, "❌ Enter a number between 1 and 200.")
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
    
    bot.send_message(user_id, "⚡ Thread pool count (default 10, max 30):")
    bot.register_next_step_handler(msg, process_threads)

def process_threads(msg):
    user_id = msg.from_user.id
    try:
        threads = int(msg.text.strip())
        if threads > 0:
            user_sessions[user_id]["threads"] = min(threads, 30)
        else:
            user_sessions[user_id]["threads"] = 10
    except:
        user_sessions[user_id]["threads"] = 10
    
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

# ============================================================
#  GENERATOR WORKER
# ============================================================
def generator_worker(user_id, session):
    global RARITY_SCORE_THRESHOLD
    RARITY_SCORE_THRESHOLD = session["threshold"]
    
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
    rare_accounts = []
    couple_accounts = []
    
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
                if i % 3 == 0:
                    time.sleep(0.2)
            
            for future in as_completed(futures):
                if stop_flags.get(user_id, False):
                    break
                
                result = future.result()
                if not result or result.get("account_id", "N/A") == "N/A":
                    continue
                
                success += 1
                accounts.append(result)
                result_buffers[user_id].append(result)
                
                is_rare, rtype, reason, rscore = check_rarity(result)
                if is_rare:
                    rare += 1
                    rare_accounts.append(result)
                
                is_couple, creason, partner = check_couple(result, 0)
                if is_couple and partner:
                    couples += 1
                    couple_accounts.append({"account1": result, "account2": partner, "reason": creason})
                
                if success % 5 == 0:
                    try:
                        elapsed = time.time() - start_time
                        status_text = (
                            f"⏳ Generating... {success}/{total}\n"
                            f"Rare: {rare} | Couples: {couples}\n"
                            f"Rate: {success/elapsed:.1f}/s\n"
                            f"Elapsed: {elapsed:.1f}s"
                        )
                        if status_msg:
                            bot.edit_message_text(status_text, user_id, status_msg.message_id)
                        else:
                            status_msg = bot.send_message(user_id, status_text)
                    except:
                        pass
    
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")
    
    # Save everything
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if accounts:
        folder = os.path.join(BASE_FOLDER, "GHOST", "ACCOUNTS") if is_ghost else os.path.join(BASE_FOLDER, "ACCOUNTS")
        save_account_data(accounts, folder, f"accounts_{region}_{timestamp}.json")
    
    if rare_accounts:
        folder = os.path.join(BASE_FOLDER, "GHOST", "RAREACCOUNT") if is_ghost else os.path.join(BASE_FOLDER, "RARE ACCOUNTS")
        save_account_data(rare_accounts, folder, f"rare_{region}_{timestamp}.json")
    
    if couple_accounts:
        folder = os.path.join(BASE_FOLDER, "GHOST", "COUPLESACCOUNT") if is_ghost else os.path.join(BASE_FOLDER, "COUPLES ACCOUNTS")
        save_account_data(couple_accounts, folder, f"couples_{region}_{timestamp}.json")
    
    elapsed = time.time() - start_time
    
    # Send account file
    account_file = f"account_{region}_{timestamp}.json"
    with open(account_file, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
    
    try:
        with open(account_file, 'rb') as f:
            bot.send_document(
                user_id,
                f,
                caption=f"✅ <b>Generation Complete</b>\n\n"
                       f"Region: {region} {'(GHOST)' if is_ghost else ''}\n"
                       f"Generated: {success}\n"
                       f"Rare: {rare}\n"
                       f"Couples: {couples}\n"
                       f"Time: {elapsed:.1f}s\n"
                       f"Rate: {success/elapsed:.1f}/s\n\n"
                       f"📁 Files saved in RAO_GUEST_GEN/",
                reply_markup=main_menu()
            )
    except Exception as e:
        bot.send_message(
            user_id,
            f"✅ <b>Generation Complete</b>\n\n"
            f"Generated: {success}\n"
            f"Rare: {rare}\n"
            f"Couples: {couples}\n"
            f"Time: {elapsed:.1f}s",
            reply_markup=main_menu()
        )
    
    if os.path.exists(account_file):
        os.remove(account_file)
    
    gen_threads.pop(user_id, None)
    stop_flags.pop(user_id, None)
    result_buffers.pop(user_id, None)

# ============================================================
#  COMMAND: STOP
# ============================================================
@bot.message_handler(commands=['stop'])
@bot.callback_query_handler(func=lambda call: call.data == "stop")
def stop_cmd(call_or_msg):
    if hasattr(call_or_msg, 'from_user'):
        user_id = call_or_msg.from_user.id
    else:
        user_id = call_or_msg.from_user.id
        try:
            bot.edit_message_text("⏹ Stopping...", user_id, call_or_msg.message.message_id)
        except:
            pass
    
    stop_flags[user_id] = True
    
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
                    caption=f"⏹ <b>Stopped</b>\nAccounts collected: {len(results)}",
                    reply_markup=main_menu()
                )
        except:
            bot.send_message(
                user_id,
                f"⏹ Stopped. Collected {len(results)} accounts.",
                reply_markup=main_menu()
            )
        os.remove(partial_file)
    
    result_buffers.pop(user_id, None)

# ============================================================
#  COMMAND: STATS
# ============================================================
@bot.message_handler(commands=['stats'])
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats_cmd(call_or_msg):
    if hasattr(call_or_msg, 'from_user'):
        user_id = call_or_msg.from_user.id
    else:
        user_id = call_or_msg.from_user.id
        try:
            bot.edit_message_text("📊 Calculating...", user_id, call_or_msg.message.message_id)
        except:
            pass
    
    total_normal = 0
    total_rare = 0
    total_couples = 0
    
    for folder in [os.path.join(BASE_FOLDER, "ACCOUNTS"), os.path.join(BASE_FOLDER, "GHOST", "ACCOUNTS")]:
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
    
    for folder in [os.path.join(BASE_FOLDER, "RARE ACCOUNTS"), os.path.join(BASE_FOLDER, "GHOST", "RAREACCOUNT")]:
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
    
    for folder in [os.path.join(BASE_FOLDER, "COUPLES ACCOUNTS"), os.path.join(BASE_FOLDER, "GHOST", "COUPLESACCOUNT")]:
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
    
    stats_text = (
        f"📊 <b>DOPPY Generator Stats</b>\n\n"
        f"Normal Accounts: {total_normal}\n"
        f"Rare Accounts: {total_rare}\n"
        f"Couple Pairs: {total_couples}\n\n"
        f"📁 Saved in: {BASE_FOLDER}"
    )
    bot.send_message(user_id, stats_text, reply_markup=main_menu())

# ============================================================
#  COMMAND: VIEW
# ============================================================
@bot.message_handler(commands=['view'])
@bot.callback_query_handler(func=lambda call: call.data == "view")
def view_cmd(call_or_msg):
    if hasattr(call_or_msg, 'from_user'):
        user_id = call_or_msg.from_user.id
    else:
        user_id = call_or_msg.from_user.id
        try:
            bot.edit_message_text("📁 Fetching...", user_id, call_or_msg.message.message_id)
        except:
            pass
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📄 Normal", callback_data="view_normal"),
        InlineKeyboardButton("⭐ Rare", callback_data="view_rare"),
        InlineKeyboardButton("💑 Couples", callback_data="view_couples"),
        InlineKeyboardButton("🔙 Back", callback_data="cancel")
    )
    bot.send_message(user_id, "Select account type to view:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_"))
def view_type_cb(call):
    user_id = call.from_user.id
    view_type = call.data.replace("view_", "")
    
    if view_type == "normal":
        folders = [os.path.join(BASE_FOLDER, "ACCOUNTS"), os.path.join(BASE_FOLDER, "GHOST", "ACCOUNTS")]
    elif view_type == "rare":
        folders = [os.path.join(BASE_FOLDER, "RARE ACCOUNTS"), os.path.join(BASE_FOLDER, "GHOST", "RAREACCOUNT")]
    elif view_type == "couples":
        folders = [os.path.join(BASE_FOLDER, "COUPLES ACCOUNTS"), os.path.join(BASE_FOLDER, "GHOST", "COUPLESACCOUNT")]
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
    text = f"📄 <b>{view_type.upper()} Accounts</b> (last {len(recent)} of {len(all_accounts)})\n\n"
    
    for entry in recent:
        if view_type == "couples":
            text += f"💑 {entry.get('couple_id', entry.get('account1', {}).get('account_id', 'N/A'))}\n"
        else:
            text += f"🆔 {entry.get('account_id', 'N/A')} | {entry.get('nickname', entry.get('name', 'N/A'))}\n"
    
    bot.send_message(user_id, text[:4000], reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_cb(call):
    bot.edit_message_text("✅ Cancelled.", call.from_user.id, call.message.message_id)
    bot.send_message(call.from_user.id, "Back to menu.", reply_markup=main_menu())

# ============================================================
#  COMMAND: HELP
# ============================================================
@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.send_message(
        msg.from_user.id,
        "<b>📖 DOPPY Generator Bot Commands</b>\n\n"
        "/start - Show main menu\n"
        "/gen - Start generation flow\n"
        "/stop - Stop running generation\n"
        "/stats - Show total saved accounts\n"
        "/view - View recent accounts\n"
        "/help - This message\n\n"
        "<i>Accounts are saved in RAO_GUEST_GEN/ folder</i>",
        reply_markup=main_menu()
    )

# ============================================================
#  ERROR HANDLER
# ============================================================
@bot.message_handler(func=lambda msg: True)
def echo_all(msg):
    bot.reply_to(msg, "Unknown command. Send /help for available commands.")

# ============================================================
#  MAIN
# ============================================================
if __name__ == "__main__":
    print("🤖 DOPPY Telegram Bot starting...")
    print(f"Using token: {BOT_TOKEN[:10]}...")
    print(f"✓ Folders created in: {BASE_FOLDER}")
    print("✓ Using app.py engine (working protobuf)")
    print("✓ Bot ready")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
