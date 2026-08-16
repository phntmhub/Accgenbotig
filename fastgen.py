# language: Python, file: doppy_bot.py, runtime: Python 3.8+
# DOPPY Free Fire Guest Account Generator + Activator
# Token: 7604781380:AAGFXiQlP-2csorQGXPO3Id4gj9Lcw8e2D0

import os
import sys
import json
import threading
import time
import random
import string
import base64
import codecs
import re
import uuid
import queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
import urllib3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== BOT CONFIG ==========
BOT_TOKEN = "8666894951:AAGpPy7mOl4ghn3XjGGd1hat7dZ4E6-eUNA"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ========== CRYPTO CONSTANTS (from app.py) ==========
AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
NICK_XOR_KEY = b'1e5898ccb8dfdd921f9bdea848768b64a201'
REGION_LANG = {
    "IND":"hi", "BR":"pt", "US":"en", "ID":"id", "TH":"th",
    "VN":"vi", "ME":"ar", "SG":"ms", "PK":"ur", "BD":"bn",
    "EUROPE":"fr", "RU":"ru", "NA":"na", "SAC":"es", "TW":"zh"
}
SUPPORTED_REGIONS = {
    "1": "IND", "2": "BR", "3": "US", "4": "ID", "5": "TH",
    "6": "VN", "7": "ME", "8": "SG", "9": "PK", "10": "BD",
    "11": "EUROPE", "12": "RU", "13": "NA", "14": "SAC", "15": "TW"
}

# ========== PROTOBUF HELPERS ==========
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
        raise TypeError

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
            raise Exception
        if field in result:
            if not isinstance(result[field], list):
                result[field] = [result[field]]
            result[field].append(val)
        else:
            result[field] = val
    return result

# ========== DEVICE / RANDOM HELPERS ==========
DEVICES = ["ASUS_AI2401_A", "SM-G998B", "CPH2095", "Pixel 6", "OnePlus 9 Pro",
           "Samsung Galaxy S23 Ultra", "iPhone 14 Pro Max", "Xiaomi 13 Pro",
           "Redmi Note 10 Pro", "Moto G100", "OPPO Find X3", "Vivo X60 Pro"]
CARRIERS = ["Jio", "Airtel", "Vodafone Idea", "BSNL", "T-Mobile", "Verizon", "AT&T", "Orange"]
CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Ranchi", "Kolkata", "Pune"]

def random_device_info():
    return random.choice(DEVICES), random.choice(CARRIERS), random.choice(CITIES)

def random_user_agent_msdk():
    device = random.choice(DEVICES)
    version = random.choice(["9", "10", "11", "12", "13"])
    lang = random.choice(["en", "hi", "id", "th"])
    region = random.choice(["US", "IND", "ID", "TH"])
    return f"GarenaMSDK/4.0.42({device} ;Android {version};{lang};{region};)"

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

def get_public_ip():
    try:
        r = requests.get('https://api.ipify.org', timeout=5)
        return r.text
    except:
        return "1.2.3.4"

# ========== CORE GENERATION FUNCTIONS ==========
def create_session():
    s = requests.Session()
    s.verify = False
    adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=2)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s

def register_guest(session, password):
    url = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
    payload = {"app_id":100067, "client_type":2, "password":password, "source":2}
    headers = {
        "User-Agent": random_user_agent_msdk(),
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive"
    }
    resp = session.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Register failed: {data}")
    return str(data["data"]["uid"])

def token_grant(session, uid, password):
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
    resp.raise_for_status()
    data = resp.json()
    access_token = data.get('access_token')
    open_id = data.get('open_id')
    if not access_token or not open_id:
        raise Exception(f"Token grant failed: {data}")
    return access_token, open_id

def major_register(session, nick_prefix, access_token, open_id, region):
    if region.upper() in ["ME", "TH"]:
        base = "loginbp.common.ggbluefox.com"
    else:
        base = "loginbp.ggblueshark.com"
    url = f"https://{base}/MajorRegister"

    exp_digits = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'}
    num = random.randint(1,99999)
    suffix = ''.join(exp_digits[d] for d in f"{num:05d}")
    nickname = nick_prefix[:7] + suffix
    lang = REGION_LANG.get(region.upper(), "en")
    xor_key = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
               0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
    encoded = ''.join(chr(ord(c) ^ xor_key[i % len(xor_key)]) for i, c in enumerate(open_id))
    unicode_esc = ''.join(c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in encoded)
    field_bytes = codecs.decode(unicode_esc, 'unicode_escape').encode('latin1')
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
        "Accept-Encoding":"gzip",
        "Authorization":"Bearer",
        "Connection":"Keep-Alive",
        "Content-Type":"application/x-www-form-urlencoded",
        "Expect":"100-continue",
        "Host": base,
        "ReleaseVersion":"OB54",
        "User-Agent": random_user_agent_unity(),
        "X-GA":"v1 1",
        "X-Unity-Version":"2022.3.47f1"
    }
    resp = session.post(url, headers=headers, data=encrypted, timeout=15)
    resp.raise_for_status()
    return parse_proto(resp.content)

def major_login(session, access_token, open_id, region):
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model, carrier, city = random_device_info()
    ip = get_public_ip()
    lang = REGION_LANG.get(region.upper(), "en")
    
    def q(n):
        out=[]
        while True:
            b = n & 0x7F
            n >>= 7
            if n: b |= 0x80
            out.append(b)
            if not n: break
        return bytes(out)
    def fi(f, v): return q((f<<3)|0) + q(v)
    def fs(f, v):
        data = v.encode() if isinstance(v, str) else v
        return q((f<<3)|2) + q(len(data)) + data

    user_id = f"Google|{str(uuid.uuid4())}"
    fields = {
        3: now,
        4: "free fire",
        5: 1,
        7: "2.127.13",
        8: "Android OS 5.1.1 / API-22 (LMY48Z/rel.se.infra.20220128.171448)",
        9: "Handheld",
        10: carrier,
        11: "WIFI",
        17: "Adreno (TM) 640",
        18: "OpenGL ES 3.0",
        19: user_id,
        20: ip,
        21: lang,
        22: open_id,
        23: 4,
        24: "Handheld",
        25: model,
        26: region.upper(),
        29: access_token,
        33: carrier,
        34: "WIFI",
        37: "7428b253defc164018c604a1ebbfebdf",
        73: "/data/app/com.dts.freefireth-1/lib/arm",
        75: "H4c322aeb56444feaa151d1ea91a8f7f2|/data/app/com.dts.freefireth-1/base.apk",
        76: 2,
        78: 2,
        79: 2,
        83: "OpenGLES2",
        85: city,
        87: "android",
        88: "KqsHTywQqGHMgPbDY9P2mhkxXj/beObk/TFNpmgaucQwxyLu9hA478WEQCV0Mgaz9UivYUPpKNwPzgZhvDhSsUDMAFY=",
        90: '{"cur_rate":null,"support_etc2":false}',
        97: 1,
        98: 1,
        99: "4",
        100: "4"
    }
    packet = b''
    for k, v in fields.items():
        if isinstance(v, int):
            packet += fi(k, v)
        elif isinstance(v, (str, bytes)):
            packet += fs(k, v)
    encrypted = aes_encrypt(packet)
    headers = {
        "Accept-Encoding":"gzip",
        "Connection":"Keep-Alive",
        "Content-Type":"application/x-www-form-urlencoded",
        "Expect":"100-continue",
        "ReleaseVersion":"OB54",
        "User-Agent": random_user_agent_unity(),
        "X-GA":"v1 1",
        "X-Unity-Version":"2022.3.47f1"
    }
    resp = session.post(url, headers=headers, data=encrypted, timeout=15)
    resp.raise_for_status()
    decoded = parse_proto(resp.content)
    jwt = decoded.get(8)
    if isinstance(jwt, list):
        jwt = jwt[0]
    return decoded, jwt

def build_getlogindata_payload(jwt, open_id, uid):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = {
        3: now,
        4: "free fire",
        5: 1,
        7: "1.126.15",
        8: "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
        9: "Handheld",
        10: "Vi India",
        11: "WIFI",
        12: 1600,
        13: 720,
        14: "320",
        15: "ARM64 FP ASIMD AES | 2301 | 8",
        16: 2799,
        17: "PowerVR Rogue GE8320",
        18: "OpenGL ES 3.2 build 1.1@5425693",
        19: f"Google|{uid}",
        20: "27.59.69.226",
        21: "en",
        22: open_id,
        23: 4,
        24: "Handheld",
        25: "realme RMX2189",
        26: "IND",
        29: jwt,
        30: 1,
        41: "Vi India",
        42: "WIFI",
        57: "7428b253defc164018c604a1ebbfebdf",
        60: 19799,
        61: 1198,
        62: 5056,
        64: 1430,
        65: 19999,
        66: 1198,
        67: 19799,
        70: 4,
        73: 2,
        76: 1,
        78: 6,
        79: 2,
        81: "64",
        83: "2019120816",
        86: "OpenGLES2",
        87: 3071,
        88: 8,
        90: "New Delhi",
        91: "DL",
        92: 13080,
        93: "3rd_party",
        94: "KqsHTw+Xui+7NiknuVG39jBvqfcBIE++vNayjgpDtOGFORTYgMixv5qmFWsOvq136YMoizYxRRPFTZxTOkFnCjln760=",
        95: 111207,
        96: '{"cur_rate":null,"support_etc2":false}',
        97: 1,
        99: "30",
        100: "38",
        102: "47504412000e085134"
    }
    return assemble_proto(fields)

def send_getlogindata(session, jwt, open_id, uid):
    plain = build_getlogindata_payload(jwt, open_id, uid)
    encrypted = aes_encrypt(plain)
    url = "https://client.ind.freefiremobile.com/GetLoginData"
    headers = {
        "Host": "client.ind.freefiremobile.com",
        "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": f"Bearer {jwt}",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB54",
        "Content-Type": "application/octet-stream",
        "X-Unity-Version": "2022.3.47f1"
    }
    resp = session.post(url, headers=headers, data=encrypted, timeout=15)
    return resp.status_code

def generate_full_account(region, name_prefix, pass_base):
    """Generate and activate one account"""
    session = create_session()
    password = random_password(pass_base)
    nickname = random_nickname(name_prefix)
    
    try:
        uid = register_guest(session, password)
        access_token, open_id = token_grant(session, uid, password)
        major_register(session, nickname, access_token, open_id, region)
        _, jwt = major_login(session, access_token, open_id, region)
        
        # Activate
        status = send_getlogindata(session, jwt, open_id, uid)
        activated = status == 200
        
        # Decode nickname from JWT
        try:
            parts = jwt.split('.')
            payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
            decoded = json.loads(base64.b64decode(payload))
            raw = decoded.get("nickname")
            if raw:
                decoded_nick = base64.b64decode(raw)
                nick = bytes([decoded_nick[i] ^ NICK_XOR_KEY[i % len(NICK_XOR_KEY)] for i in range(len(decoded_nick))])
                nickname = nick.decode('utf-8', errors='ignore')
        except:
            pass
        
        return {
            "uid": uid,
            "game_uid": str(major_register(session, nickname, access_token, open_id, region).get(3, "N/A")),
            "password": password,
            "nickname": nickname,
            "region": region,
            "activated": activated,
            "jwt": jwt,
            "open_id": open_id,
            "access_token": access_token
        }
    except Exception as e:
        return None

# ========== TELEGRAM BOT ==========
user_sessions = {}
gen_threads = {}
stop_flags = {}
result_buffers = {}

def region_keyboard():
    kb = InlineKeyboardMarkup(row_width=4)
    regions = ["IND", "BR", "US", "ID", "TH", "VN", "ME", "SG", "PK", "BD", "EUROPE", "RU", "NA", "SAC", "TW"]
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

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    bot.send_message(
        msg.from_user.id,
        f"<b>🔥 DOPPY Guest Generator Bot</b>\n\n"
        f"Generate + activate Free Fire guest accounts.\n"
        f"15 regions supported. Auto-activation included.\n\n"
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
    
    user_sessions[user_id] = {
        "region": region,
        "name_prefix": None,
        "pass_base": None,
        "count": None,
        "threads": 5
    }
    
    bot.edit_message_text(
        f"📝 Region set: <b>{region}</b>\n"
        f"Send /setname to choose name prefix.",
        chat_id=user_id,
        message_id=call.message.message_id
    )

@bot.message_handler(commands=['setname'])
def setname_cmd(msg):
    user_id = msg.from_user.id
    if user_id not in user_sessions:
        bot.send_message(user_id, "Start /gen first.")
        return
    bot.send_message(user_id, "✏️ Send name prefix (e.g., <code>Doppy</code>):")
    bot.register_next_step_handler(msg, process_name)

def process_name(msg):
    user_id = msg.from_user.id
    user_sessions[user_id]["name_prefix"] = msg.text.strip() or "Doppy"
    bot.send_message(user_id, "🔑 Send password base:")
    bot.register_next_step_handler(msg, process_pass)

def process_pass(msg):
    user_id = msg.from_user.id
    user_sessions[user_id]["pass_base"] = msg.text.strip() or "Doppy"
    bot.send_message(user_id, "🔢 Number of accounts to generate (1-500):")
    bot.register_next_step_handler(msg, process_count)

def process_count(msg):
    user_id = msg.from_user.id
    try:
        count = int(msg.text.strip())
        if count <= 0 or count > 500:
            raise ValueError
        user_sessions[user_id]["count"] = count
    except:
        bot.send_message(user_id, "❌ Enter a number between 1 and 500.")
        bot.register_next_step_handler(msg, process_count)
        return
    
    session = user_sessions[user_id]
    bot.send_message(
        user_id,
        f"✅ <b>Configuration confirmed</b>\n"
        f"Region: {session['region']}\n"
        f"Name: {session['name_prefix']}\n"
        f"Count: {session['count']}\n"
        f"Threads: {session['threads']}\n\n"
        f"🚀 Starting generation + activation...",
        reply_markup=main_menu()
    )
    
    stop_flags[user_id] = False
    result_buffers[user_id] = []
    t = threading.Thread(target=generator_worker, args=(user_id, session))
    t.daemon = True
    gen_threads[user_id] = t
    t.start()

def generator_worker(user_id, session):
    total = session["count"]
    success = 0
    activated = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=session["threads"]) as executor:
        futures = []
        for i in range(total):
            if stop_flags.get(user_id, False):
                break
            futures.append(
                executor.submit(
                    generate_full_account,
                    session["region"],
                    session["name_prefix"],
                    session["pass_base"]
                )
            )
        
        for future in as_completed(futures):
            if stop_flags.get(user_id, False):
                break
            result = future.result()
            if result:
                success += 1
                if result.get("activated"):
                    activated += 1
                result_buffers[user_id].append(result)
                
                # Save to file
                with open(f"accounts_{session['region']}.json", "a") as f:
                    json.dump(result, f)
                    f.write("\n")
                
                if success % 5 == 0:
                    elapsed = time.time() - start_time
                    try:
                        bot.edit_message_text(
                            f"⏳ Generating... {success}/{total}\n"
                            f"Activated: {activated}\n"
                            f"Elapsed: {elapsed:.1f}s",
                            chat_id=user_id,
                            message_id=bot.send_message(user_id, "⏳ Working...").message_id
                        )
                    except:
                        pass
    
    elapsed = time.time() - start_time
    summary = (
        f"✅ <b>Generation Complete</b>\n\n"
        f"Accounts: {success}\n"
        f"Activated: {activated}\n"
        f"Time: {elapsed:.1f}s\n\n"
        f"Use /view to see saved accounts."
    )
    bot.send_message(user_id, summary, reply_markup=main_menu())
    gen_threads.pop(user_id, None)
    stop_flags.pop(user_id, None)

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
    if user_id in gen_threads and gen_threads[user_id].is_alive():
        gen_threads[user_id].join(timeout=2)
    bot.send_message(user_id, "⏹ Generation stopped.", reply_markup=main_menu())

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
    
    total = 0
    for f in os.listdir('.'):
        if f.startswith('accounts_') and f.endswith('.json'):
            try:
                with open(f, 'r') as file:
                    data = file.read().strip().split('\n')
                    total += len([l for l in data if l.strip()])
            except:
                pass
    
    bot.send_message(
        user_id,
        f"📊 <b>DOPPY Generator Stats</b>\n\n"
        f"Total Accounts: {total}",
        reply_markup=main_menu()
    )

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
    
    # Find latest file
    files = [f for f in os.listdir('.') if f.startswith('accounts_') and f.endswith('.json')]
    if not files:
        bot.send_message(user_id, "No accounts found.", reply_markup=main_menu())
        return
    
    latest = sorted(files)[-1]
    try:
        with open(latest, 'r') as f:
            lines = f.read().strip().split('\n')
            if not lines:
                bot.send_message(user_id, "Empty file.")
                return
            recent = lines[-10:]
            text = f"📄 <b>Recent Accounts</b> (from {latest})\n\n"
            for line in recent:
                try:
                    data = json.loads(line)
                    status = "✅" if data.get('activated') else "❌"
                    text += f"{status} UID: {data.get('uid', 'N/A')} | {data.get('nickname', 'N/A')}\n"
                except:
                    pass
            bot.send_message(user_id, text[:4000], reply_markup=main_menu())
    except Exception as e:
        bot.send_message(user_id, f"Error: {str(e)}", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_cb(call):
    bot.edit_message_text("✅ Cancelled.", call.from_user.id, call.message.message_id)

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
        "/help - This message",
        reply_markup=main_menu()
    )

if __name__ == "__main__":
    print("🤖 DOPPY Telegram Bot starting...")
    print(f"Token: {BOT_TOKEN[:10]}...")
    bot.infinity_polling(timeout=60)
