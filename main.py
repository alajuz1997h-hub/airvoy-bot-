import os
import time
import random
import requests

# 1. ضع توكن بوت تليجرام هنا (أو اجلبه من متغيرات البيئة)
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_بوت_تليجرام_هنا")

BASE_URL = "https://airvoyapp-backend.onrender.com/api/tasks/wall"
ASSIGN_URL = f"{BASE_URL}/assign/"
SUBMIT_URL = f"{BASE_URL}/submit/"

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
user_tokens = {}

def send_tg_message(chat_id, text):
    """إرسال رسالة تليجرام للمستخدم"""
    try:
        requests.post(f"{TG_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Error sending TG msg: {e}")

def solve_attention(payload):
    """حل المسألة الحسابية"""
    attn = payload.get("attention")
    if not attn:
        return None
    try:
        x, y, op = int(attn.get("x", 0)), int(attn.get("y", 0)), attn.get("op", "+")
        return (x - y) if op == "-" else (x + y)
    except Exception:
        return None

def process_airvoy_tasks(chat_id, token):
    headers = {
        "host": "airvoyapp-backend.onrender.com",
        "content-type": "application/json",
        "accept": "*/*",
        "authorization": f"Bearer {token.strip()}",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15",
        "origin": "https://airvoyapp-backend.onrender.com",
        "referer": f"{BASE_URL}/"
    }

    send_tg_message(chat_id, "🚀 *بدء تنفيذ الـ 16 مهمة تتابعياً بأقصى سرعة...*")

    completed_count = 0

    for i in range(1, 17):
        try:
            # 1. طلب التعيين
            res = requests.post(ASSIGN_URL, headers=headers, json={}, timeout=15)
            if res.status_code == 401:
                send_tg_message(chat_id, "❌ *خطأ 401:* انتهت صلاحية التوكن. أرسل توكن جديد.")
                return
            if res.status_code != 200:
                send_tg_message(chat_id, f"⚠️ خطأ اتصال في المهمة {i} ({res.status_code})")
                return

            data = res.json()
            if data.get("error") or not data.get("task"):
                reason = data.get("reason", data.get("error", "لا توجد مهام متاحة"))
                send_tg_message(chat_id, f"⚠️ توقف عند المهمة {i}: `{reason}`")
                return

            assignment_id = data.get("assignment_id")
            task = data.get("task", {})
            min_seconds = task.get("min_seconds", 10)
            attn_ans = solve_attention(task.get("payload", {}))

            # انتظار الحد الأدنى للسيرفر (10 ثوانٍ)
            time.sleep(min_seconds + 0.2)

            # 2. إرسال الحل
            choice = random.choice(["a", "b"])
            body = {"assignment_id": assignment_id, "answer": choice}
            if attn_ans is not None:
                body["attn_answer"] = attn_ans

            sub_res = requests.post(SUBMIT_URL, headers=headers, json=body, timeout=15)
            if sub_res.status_code == 200:
                result = sub_res.json()
                if result.get("outcome") == "too_fast":
                    retry_wait = result.get("retry_in", 2)
                    time.sleep(retry_wait)
                    sub_res = requests.post(SUBMIT_URL, headers=headers, json=body, timeout=15)
                    result = sub_res.json()

                if result.get("credited", False):
                    completed_count += 1
                    # إرسال تحديث كل 4 مهام لتقليل كثرة الرسائل
                    if i % 4 == 0 or i == 16:
                        send_tg_message(chat_id, f"✅ تم إنجاز *[{i}/16]* مهمة بنجاح.")
            else:
                send_tg_message(chat_id, f"❌ فشل إرسال المهمة {i}")
                return

            time.sleep(0.3)

        except Exception as e:
            send_tg_message(chat_id, f"❌ حدث خطأ غير متوقع: `{e}`")
            return

    send_tg_message(chat_id, f"🎉 *اكتملت جميع المهام بنجاح ({completed_count}/16)!*\nادخل التطبيق الآن واضغط زر Claim.")

def main():
    print("=== البوت يعمل على السيرفر ويستمع لرسائل تليجرام ===")
    last_update_id = 0

    while True:
        try:
            res = requests.get(f"{TG_API}/getUpdates", params={"offset": last_update_id + 1, "timeout": 20}, timeout=25)
            if res.status_code == 200:
                updates = res.json().get("result", [])
                for upd in updates:
                    last_update_id = upd["update_id"]
                    msg = upd.get("message", {})
                    text = msg.get("text", "").strip()
                    chat_id = msg.get("chat", {}).get("id")

                    if not text or not chat_id:
                        continue

                    if text == "/start":
                        send_tg_message(chat_id, "👋 *مرحباً بك في بوت Airvoy السحابي!*\n\n1️⃣ أرسل التوكن الخاص بك هنا.\n2️⃣ بعد حفظه، أرسل `/run` للبدء فوراً.")
                    elif text == "/run":
                        token = user_tokens.get(chat_id)
                        if not token:
                            send_tg_message(chat_id, "❌ لم ترسل التوكن بعد! أرسل التوكن أولاً.")
                        else:
                            process_airvoy_tasks(chat_id, token)
                    else:
                        token = text.split("Bearer ")[1].split()[0].strip() if "Bearer " in text else text
                        user_tokens[chat_id] = token
                        send_tg_message(chat_id, "✅ *تم حفظ التوكن بنجاح!* أرسل الآن أمر `/run` لبدء التجميع.")
        except Exception:
            time.sleep(2)

if __name__ == "__main__":
    main()
