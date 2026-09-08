import os
import json
import time
import threading
from flask import Flask
import telebot
from telebot import types

# ================= بيانات البوت والمالك =================
BOT_TOKEN = "8941758329:AAExarUzaAMiABkBKpPjQAcordNyve8SmhI"
OWNER_ID = 1460392381
DATA_FILE = "config.json"
VIDEO_PATH = "video.mp4"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ================= إدارة وحفظ البيانات =================
DEFAULT_CAPTION = "⏱️ <b>تحدي العداد</b>\n━━━━━━━━━━━━\nالعداد: <code>00.00</code> ثانية\n\nاضغط <b>بدء</b> لتشغيل الحساب:"

def load_data():
    default_config = {
        "admins": [],
        "show_live": False,
        "mode": "private",  # 'private' أو 'public'
        "cached_video_id": None,
        "custom_caption": DEFAULT_CAPTION
    }
    if not os.path.exists(DATA_FILE):
        save_data(default_config)
        return default_config
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for key, val in default_config.items():
                if key not in data:
                    data[key] = val
            return data
    except Exception:
        return default_config

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

active_games = {}
active_triggers = {}  # {message_id: user_id_who_typed_3addad}
user_states = {}

# ================= سيرفر ويب لـ Render =================
@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= لوحة تحكم المالك =================
def get_panel_keyboard():
    data = load_data()
    status_live = "🟢 مفعل" if data.get("show_live", False) else "🔴 مخفي"
    mode_text = "🌐 عام (يرسل للجميع)" if data.get("mode") == "public" else "🔒 خاص (للإدارة فقط)"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"👁️ عرض العداد: {status_live}", callback_data="toggle_live"))
    markup.add(types.InlineKeyboardButton(f"⚙️ الوضع: {mode_text}", callback_data="toggle_mode"))
    markup.add(
        types.InlineKeyboardButton("📝 تعديل النص", callback_data="btn_edit_caption"),
        types.InlineKeyboardButton("🎬 تغيير الفيديو", callback_data="btn_change_video")
    )
    markup.add(
        types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="btn_add_admin"),
        types.InlineKeyboardButton("➖ حذف أدمن", callback_data="btn_del_admin")
    )
    markup.add(types.InlineKeyboardButton("👥 قائمة الأدمنية", callback_data="btn_list_admins"))
    return markup

@bot.message_handler(commands=['panel', 'control'])
def admin_panel(message):
    if message.chat.type == "private" and message.from_user.id == OWNER_ID:
        bot.send_message(
            message.chat.id,
            "<b>⚙️ لوحة تحكم بوت العداد:</b>\nتحكم بكافة الإعدادات والتفضيلات من هنا:",
            reply_markup=get_panel_keyboard(),
            parse_mode="HTML"
        )

@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.chat.type == "private":
        if message.from_user.id == OWNER_ID:
            bot.send_message(message.chat.id, "👑 أهلاً بك يا مالك البوت.\nأرسل الأمر /panel لفتح لوحة التحكم.")
        else:
            bot.send_message(message.chat.id, "👋 أهلاً بك في بوت العداد!\nتم تفعيل استلامك لنتائج التحديات.")

# ================= تفاعلات أزرار لوحة التحكم =================
@bot.callback_query_handler(func=lambda call: call.data in ["toggle_live", "toggle_mode", "btn_edit_caption", "btn_change_video", "btn_add_admin", "btn_del_admin", "btn_list_admins"] or call.data.startswith("del_admin_"))
def panel_actions(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "عذراً، هذا الأمر للمالك فقط!", show_alert=True)
        return

    data = load_data()

    if call.data == "toggle_live":
        data["show_live"] = not data.get("show_live", False)
        save_data(data)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_panel_keyboard())
        except Exception:
            pass
        bot.answer_callback_query(call.id, "تم تغيير حالة إظهار العداد.")

    elif call.data == "toggle_mode":
        data["mode"] = "public" if data.get("mode") == "private" else "private"
        save_data(data)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_panel_keyboard())
        except Exception:
            pass
        status_msg = "أصبح عاماً (ترسل النتيجة للاعب)" if data["mode"] == "public" else "أصبح خاصاً (للإدارة فقط)"
        bot.answer_callback_query(call.id, f"تم التغيير: البوت {status_msg}")

    elif call.data == "btn_edit_caption":
        user_states[call.from_user.id] = "waiting_for_caption"
        bot.send_message(call.message.chat.id, "✍️ أرسل الآن النص (الكليشة) الجديد الذي تريده أن يظهر تحت الفيديو:")
        bot.answer_callback_query(call.id)

    elif call.data == "btn_change_video":
        user_states[call.from_user.id] = "waiting_for_video"
        bot.send_message(call.message.chat.id, "🎬 أرسل الآن الفيديو الجديد أو صورة الـ GIF مباشرة هنا بالمحادثة:")
        bot.answer_callback_query(call.id)

    elif call.data == "btn_list_admins":
        admins = data.get("admins", [])
        if not admins:
            bot.send_message(call.message.chat.id, "📋 لا يوجد أدمنية مضافين حالياً.")
        else:
            text = "👥 <b>قائمة الأدمنية المضافين:</b>\n" + "\n".join([f"• <code>{adm}</code>" for adm in admins])
            bot.send_message(call.message.chat.id, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == "btn_add_admin":
        user_states[call.from_user.id] = "waiting_for_admin_id"
        bot.send_message(call.message.chat.id, "✍️ أرسل الآن <b>الآيدي الرقمي (ID)</b> الخاص بالأدمن المطلوب إضافته:", parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == "btn_del_admin":
        admins = data.get("admins", [])
        if not admins:
            bot.answer_callback_query(call.id, "لا يوجد أدمنية لحذفهم!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup()
        for adm in admins:
            markup.add(types.InlineKeyboardButton(f"❌ حذف {adm}", callback_data=f"del_admin_{adm}"))
        bot.send_message(call.message.chat.id, "اختر الأدمن المراد حذفه من القائمة:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("del_admin_"):
        target_str = call.data.replace("del_admin_", "")
        target = int(target_str) if target_str.isdigit() else target_str
        if target in data.get("admins", []):
            data["admins"].remove(target)
            save_data(data)
            bot.answer_callback_query(call.id, f"تم حذف {target} بنجاح.")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
        else:
            bot.answer_callback_query(call.id, "لم يتم العثور على هذا الأدمن.")

# ================= معالجة الرسائل الخاصة بلوحة التحكم =================
@bot.message_handler(func=lambda msg: msg.chat.type == "private" and msg.from_user.id in user_states, content_types=['text', 'video', 'animation', 'document'])
def handle_owner_inputs(msg):
    state = user_states.get(msg.from_user.id)
    data = load_data()

    if state == "waiting_for_admin_id":
        val = msg.text.strip().replace("@", "") if msg.text else ""
        if not val.isdigit():
            bot.send_message(msg.chat.id, "⚠️ يرجى إرسال أرقام الآيدي فقط.")
            user_states.pop(msg.from_user.id, None)
            return
        target = int(val)
        if target not in data["admins"]:
            data["admins"].append(target)
            save_data(data)
            bot.send_message(msg.chat.id, f"✅ تم حفظ الأدمن <code>{target}</code> بنجاح!", parse_mode="HTML")
        else:
            bot.send_message(msg.chat.id, "⚠️ هذا المعرّف مضاف مسبقاً.")

    elif state == "waiting_for_caption":
        if msg.text:
            data["custom_caption"] = msg.text
            save_data(data)
            bot.send_message(msg.chat.id, "✅ تم تحديث كليشة الفيديو بنجاح!")
        else:
            bot.send_message(msg.chat.id, "⚠️ يرجى إرسال رسالة نصية.")

    elif state == "waiting_for_video":
        file_id = None
        if msg.animation:
            file_id = msg.animation.file_id
        elif msg.video:
            file_id = msg.video.file_id
        elif msg.document and msg.document.mime_type and "video" in msg.document.mime_type:
            file_id = msg.document.file_id

        if file_id:
            data["cached_video_id"] = file_id
            save_data(data)
            bot.send_message(msg.chat.id, "✅ تم تعيين وحفظ الفيديو الجديد بنجاح!")
        else:
            bot.send_message(msg.chat.id, "⚠️ يرجى إرسال ملف فيديو أو GIF حصراً.")

    user_states.pop(msg.from_user.id, None)

# ================= نظام اللعبة داخل المجموعات =================
@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "عداد")
def counter_trigger(msg):
    data = load_data()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟢 بدء", callback_data="game_start"))

    caption_text = data.get("custom_caption", DEFAULT_CAPTION)
    cached_id = data.get("cached_video_id")

    sent_msg = None
    if cached_id:
        try:
            sent_msg = bot.send_animation(msg.chat.id, cached_id, caption=caption_text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            cached_id = None

    if not sent_msg:
        if os.path.exists(VIDEO_PATH):
            with open(VIDEO_PATH, "rb") as video_file:
                sent_msg = bot.send_animation(msg.chat.id, video_file, caption=caption_text, reply_markup=markup, parse_mode="HTML")
                if sent_msg.animation:
                    data["cached_video_id"] = sent_msg.animation.file_id
                    save_data(data)
                elif sent_msg.video:
                    data["cached_video_id"] = sent_msg.video.file_id
                    save_data(data)
        else:
            sent_msg = bot.send_message(msg.chat.id, caption_text, reply_markup=markup, parse_mode="HTML")

    if sent_msg:
        # تسجيل الشخص الذي فتح التحدي لمنع التخريب
        active_triggers[sent_msg.message_id] = msg.from_user.id

@bot.callback_query_handler(func=lambda call: call.data in ["game_start", "game_stop"])
def counter_logic(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    user = call.from_user
    username = f"@{user.username}" if user.username else "بدون يوزر"

    data = load_data()
    show_live = data.get("show_live", False)
    mode = data.get("mode", "private")

    # 1. بدء العداد
    if call.data == "game_start":
        creator_id = active_triggers.get(msg_id)
        # التحقق: فقط كاتب "عداد" أو مالك البوت يمكنه الضغط على بدء
        if creator_id and user.id != creator_id and user.id != OWNER_ID:
            bot.answer_callback_query(call.id, "⚠️ فقط الشخص الذي كتب كلمة «عداد» أو المالك يمكنه بدء التحدي!", show_alert=True)
            return

        active_games[msg_id] = {
            "user_id": user.id,
            "start_time": time.time(),
            "is_running": True
        }

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔴 إيقاف", callback_data="game_stop"))

        run_caption = f"⏱️ <b>تحدي العداد</b>\n━━━━━━━━━━━━\n👤 اللاعب: <b>{user.first_name}</b>\nالعداد: <code>يحسب الآن... ⏳</code>"

        try:
            bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=run_caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=run_caption, reply_markup=markup, parse_mode="HTML")
            except Exception:
                pass

        bot.answer_callback_query(call.id, "تم تشغيل العداد!")

        if show_live:
            def live_updater():
                while active_games.get(msg_id, {}).get("is_running", False):
                    elapsed = time.time() - active_games[msg_id]["start_time"]
                    if elapsed >= 100.00:
                        break
                    live_caption = f"⏱️ <b>تحدي العداد</b>\n━━━━━━━━━━━━\n👤 اللاعب: <b>{user.first_name}</b>\nالعداد: <code>{elapsed:.2f}</code> ثانية"
                    try:
                        bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=live_caption, reply_markup=markup, parse_mode="HTML")
                    except Exception:
                        pass
                    time.sleep(1.5)
            threading.Thread(target=live_updater, daemon=True).start()

    # 2. إيقاف العداد
    elif call.data == "game_stop":
        session = active_games.get(msg_id)
        if not session or not session.get("is_running"):
            bot.answer_callback_query(call.id, "العداد متوقف بالفعل!", show_alert=True)
            return

        # التحقق: فقط اللاعب الذي ضغط بدء أو المالك يمكنه الإيقاف
        if session["user_id"] != user.id and user.id != OWNER_ID:
            bot.answer_callback_query(call.id, "⚠️ فقط اللاعب الذي بدأ التحدي أو المالك يمكنه إيقافه!", show_alert=True)
            return

        stop_time = time.time()
        session["is_running"] = False
        elapsed = min(stop_time - session["start_time"], 100.00)
        formatted_score = f"{elapsed:.2f}"

        stop_caption = f"🛑 <b>تم إيقاف العداد!</b>\n━━━━━━━━━━━━\n👤 اللاعب: <b>{user.first_name}</b>\nتم إرسال النتيجة للإدارة."

        try:
            bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=stop_caption, reply_markup=None, parse_mode="HTML")
        except Exception:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=stop_caption, reply_markup=None, parse_mode="HTML")
            except Exception:
                pass

        # تنبيه علوي بدون إظهار أي رقم للاعب
        bot.answer_callback_query(call.id, "تم إيقاف العداد بنجاح! ✅")

        # تقرير النتيجة الكامل
        chat_title = call.message.chat.title if call.message.chat.title else "محادثة خاصة"
        report_text = (
            f"🎯 <b>نتيجة جديدة لتحدي العداد:</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>اللاعب:</b> {user.first_name}\n"
            f"🏷️ <b>اليوزر:</b> {username}\n"
            f"🆔 <b>الآيدي:</b> <code>{user.id}</code>\n"
            f"⏱️ <b>الوقت الدقيق:</b> <code>{formatted_score}</code> ثانية\n"
            f"💬 <b>المجموعة:</b> {chat_title}"
        )

        # 1. إذا كان الوضع عاماً: إرسال النتيجة للاعب بالخاص
        if mode == "public":
            try:
                bot.send_message(
                    user.id,
                    f"⏱️ <b>نتيجتك في تحدي العداد:</b>\nالوقت المسجل: <code>{formatted_score}</code> ثانية!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # 2. إرسال التقرير للمالك دائماً
        try:
            bot.send_message(OWNER_ID, report_text, parse_mode="HTML")
        except Exception:
            pass

        # 3. إرسال التقرير للأدمنية
        for adm in data.get("admins", []):
            try:
                bot.send_message(int(adm), report_text, parse_mode="HTML")
            except Exception:
                pass

        active_games.pop(msg_id, None)
        active_triggers.pop(msg_id, None)

# ================= تشغيل البوت =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("البوت شغال بكافة الميزات الاحترافية...")
    bot.infinity_polling(skip_pending=True)
