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

# ================= حفظ واسترجاع البيانات =================
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {"admins": [], "show_live": False, "cached_video_id": None}
        save_data(data)
        return data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"admins": [], "show_live": False, "cached_video_id": None}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

active_games = {}
user_states = {}

# ================= سيرفر ويب لإبقاء البوت شغالاً على Render =================
@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= لوحة تحكم المالك =================
def get_panel_keyboard():
    data = load_data()
    status = "🟢 مفعل (يظهر بالكروب)" if data.get("show_live", False) else "🔴 معطل (مخفي بالكروب)"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_toggle = types.InlineKeyboardButton(f"👁️ عرض العداد: {status}", callback_data="toggle_live")
    btn_add_admin = types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="btn_add_admin")
    btn_del_admin = types.InlineKeyboardButton("➖ حذف أدمن", callback_data="btn_del_admin")
    btn_list_admins = types.InlineKeyboardButton("👥 قائمة الأدمنية", callback_data="btn_list_admins")
    
    markup.add(btn_toggle)
    markup.add(btn_add_admin, btn_del_admin)
    markup.add(btn_list_admins)
    return markup

@bot.message_handler(commands=['panel', 'control'])
def admin_panel(message):
    if message.chat.type == "private" and message.from_user.id == OWNER_ID:
        bot.send_message(
            message.chat.id,
            "<b>⚙️ لوحة تحكم بوت العداد:</b>\nتحكم بظهور العداد والأدمنية من الأزرار أدناه:",
            reply_markup=get_panel_keyboard(),
            parse_mode="HTML"
        )

@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.chat.type == "private":
        if message.from_user.id == OWNER_ID:
            bot.send_message(message.chat.id, "👑 أهلاً بك يا مالك البوت.\nأرسل الأمر /panel لفتح لوحة التحكم.")
        else:
            bot.send_message(message.chat.id, "👋 أهلاً بك!\nاضغط Start لتفعيل استقبال إشعارات البوت في حال تعيينك كأدمن.")

# ================= تفاعلات لوحة التحكم =================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("toggle_live", "btn_add_admin", "btn_del_admin", "btn_list_admins", "del_admin_")))
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
        bot.send_message(
            call.message.chat.id,
            "✍️ أرسل الآن <b>الآيدي الرقمي (ID)</b> الخاص بالأدمن:\n<i>(ملاحظة: تليجرام يتطلب الآيدي الرقمي حصراً)</i>",
            parse_mode="HTML"
        )
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

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_for_admin_id")
def receive_admin_id(msg):
    data = load_data()
    val = msg.text.strip().replace("@", "")
    
    if not val.isdigit():
        bot.send_message(msg.chat.id, "⚠️ يرجى إرسال الآيدي الرقمي حصراً (أرقام فقط).")
        user_states.pop(msg.from_user.id, None)
        return

    target = int(val)
    if target not in data["admins"]:
        data["admins"].append(target)
        save_data(data)
        bot.send_message(msg.chat.id, f"✅ تم حفظ الأدمن <code>{target}</code> بنجاح!\nتأكد أن يضغط الأدمن /start في البوت.", parse_mode="HTML")
    else:
        bot.send_message(msg.chat.id, "⚠️ هذا المعرّف مضاف مسبقاً.")
    
    user_states.pop(msg.from_user.id, None)

# ================= نظام اللعبة داخل الكروب مع الفيديو =================
@bot.message_handler(func=lambda msg: msg.text and msg.text.strip() == "عداد")
def counter_trigger(msg):
    data = load_data()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟢 بدء", callback_data="game_start"))

    caption_text = "⏱️ <b>تحدي العداد</b>\n━━━━━━━━━━━━\nالعداد: <code>00.00</code> ثانية\n\nاضغط <b>بدء</b> لتشغيل الحساب:"
    cached_id = data.get("cached_video_id")

    # إرسال الفيديو إما من التخزين المؤقت أو من الملف
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
                # حفظ file_id للاستخدام الفوري لاحقاً
                if sent_msg.animation:
                    data["cached_video_id"] = sent_msg.animation.file_id
                    save_data(data)
                elif sent_msg.video:
                    data["cached_video_id"] = sent_msg.video.file_id
                    save_data(data)
        else:
            # في حال لم يُرفع ملف الفيديو بعد
            sent_msg = bot.send_message(msg.chat.id, caption_text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ["game_start", "game_stop"])
def counter_logic(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    user = call.from_user
    username = f"@{user.username}" if user.username else "بدون يوزر"

    data = load_data()
    show_live = data.get("show_live", False)

    # 1. بدء العداد
    if call.data == "game_start":
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

        if session["user_id"] != user.id:
            bot.answer_callback_query(call.id, "⚠️ فقط اللاعب الذي بدأ التحدي يمكنه إيقافه!", show_alert=True)
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

        bot.answer_callback_query(call.id, f"توقفت عند {formatted_score} ثانية!")

        # تقرير النتيجة للمالك والأدمنية
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

        try:
            bot.send_message(OWNER_ID, report_text, parse_mode="HTML")
        except Exception:
            pass

        for adm in data.get("admins", []):
            try:
                bot.send_message(int(adm), report_text, parse_mode="HTML")
            except Exception:
                pass

        active_games.pop(msg_id, None)

# ================= تشغيل البوت =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("البوت شغال بنجاح...")
    bot.infinity_polling(skip_pending=True)
