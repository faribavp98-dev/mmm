import os
import threading
from datetime import date

import telebot
from telebot import types

from app.main import db

TOKEN = os.getenv("BOT_TOKEN", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", os.getenv("RENDER_EXTERNAL_URL", "")).rstrip("/")
WEBHOOK_PATH = "/telegram/webhook"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=False) if TOKEN else None

STATUS_LABELS = {
    "todo": "شروع نشده",
    "doing": "در حال انجام",
    "review": "در انتظار بررسی",
    "done": "تکمیل شده",
}
PRIORITY_LABELS = {"normal": "عادی", "high": "بالا", "urgent": "فوری"}


def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 وضعیت", "🚀 پروژه‌ها")
    kb.row("📋 وظایف", "➕ پروژه جدید")
    kb.row("➕ وظیفه جدید", "ℹ️ راهنما")
    return kb


def fmt_task(row):
    due = row["due_date"] or "بدون ددلاین"
    project = row["project_title"] or "بدون پروژه"
    return (
        f"<b>#{row['id']} — {row['title']}</b>\n"
        f"وضعیت: {STATUS_LABELS.get(row['status'], row['status'])}\n"
        f"اولویت: {PRIORITY_LABELS.get(row['priority'], row['priority'])}\n"
        f"پروژه: {project}\n"
        f"ددلاین: {due}"
    )


def stats_text():
    c = db()
    total = c.execute("SELECT COUNT(*) n FROM tasks").fetchone()["n"]
    done = c.execute("SELECT COUNT(*) n FROM tasks WHERE status='done'").fetchone()["n"]
    doing = c.execute("SELECT COUNT(*) n FROM tasks WHERE status='doing'").fetchone()["n"]
    review = c.execute("SELECT COUNT(*) n FROM tasks WHERE status='review'").fetchone()["n"]
    todo = c.execute("SELECT COUNT(*) n FROM tasks WHERE status='todo'").fetchone()["n"]
    overdue = c.execute(
        "SELECT COUNT(*) n FROM tasks WHERE due_date IS NOT NULL AND due_date < ? AND status != 'done'",
        (date.today().isoformat(),),
    ).fetchone()["n"]
    projects = c.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"]
    return (
        "<b>📊 وضعیت مدیر تیم</b>\n\n"
        f"🚀 پروژه‌ها: <b>{projects}</b>\n"
        f"📋 کل وظایف: <b>{total}</b>\n"
        f"⏳ شروع نشده: <b>{todo}</b>\n"
        f"🔄 در حال انجام: <b>{doing}</b>\n"
        f"👀 در انتظار بررسی: <b>{review}</b>\n"
        f"✅ تکمیل شده: <b>{done}</b>\n"
        f"⚠️ عقب‌افتاده: <b>{overdue}</b>"
    )


def send_tasks(chat_id):
    c = db()
    rows = c.execute(
        """SELECT t.*, p.title project_title FROM tasks t
           LEFT JOIN projects p ON p.id=t.project_id
           ORDER BY CASE t.status WHEN 'todo' THEN 0 WHEN 'doing' THEN 1 WHEN 'review' THEN 2 ELSE 3 END, t.id DESC"""
    ).fetchall()
    if not rows:
        bot.send_message(chat_id, "📋 هنوز هیچ وظیفه‌ای ثبت نشده است.", reply_markup=menu())
        return
    for row in rows[:30]:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("▶️ انجام", callback_data=f"status:{row['id']}:doing"),
            types.InlineKeyboardButton("👀 بررسی", callback_data=f"status:{row['id']}:review"),
            types.InlineKeyboardButton("✅ تکمیل", callback_data=f"status:{row['id']}:done"),
            types.InlineKeyboardButton("🗑 حذف", callback_data=f"delete:{row['id']}"),
        )
        bot.send_message(chat_id, fmt_task(row), reply_markup=kb)


def send_projects(chat_id):
    c = db()
    rows = c.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    if not rows:
        bot.send_message(chat_id, "🚀 هنوز هیچ پروژه‌ای ثبت نشده است.", reply_markup=menu())
        return
    text = ["<b>🚀 پروژه‌ها</b>"]
    for r in rows[:50]:
        desc = r["description"] or "بدون توضیح"
        text.append(f"\n<b>#{r['id']} — {r['title']}</b>\n{desc}")
    bot.send_message(chat_id, "\n".join(text), reply_markup=menu())


def help_text():
    return (
        "<b>ℹ️ راهنمای ربات مدیر تیم</b>\n\n"
        "از دکمه‌های پایین برای مدیریت پروژه‌ها و وظایف استفاده کنید.\n\n"
        "دستورهای مستقیم:\n"
        "/start — شروع\n"
        "/stats — آمار\n"
        "/projects — پروژه‌ها\n"
        "/tasks — وظایف\n"
        "/addproject عنوان | توضیح\n"
        "/addtask عنوان | توضیح | project_id | priority | YYYY-MM-DD\n"
        "/status task_id todo|doing|review|done"
    )


if bot:
    @bot.message_handler(commands=["start", "help"])
    def start(message):
        bot.send_message(message.chat.id, "سلام 👋\nبه <b>مدیر تیم</b> خوش آمدید.\n\nاز منوی زیر استفاده کنید.", reply_markup=menu())

    @bot.message_handler(commands=["stats"])
    def stats(message):
        bot.send_message(message.chat.id, stats_text(), reply_markup=menu())

    @bot.message_handler(commands=["projects"])
    def projects(message):
        send_projects(message.chat.id)

    @bot.message_handler(commands=["tasks"])
    def tasks(message):
        send_tasks(message.chat.id)

    @bot.message_handler(commands=["addproject"])
    def addproject(message):
        raw = message.text.partition(" ")[2].strip()
        parts = [x.strip() for x in raw.split("|", 1)]
        if not parts or not parts[0]:
            bot.reply_to(message, "فرمت صحیح:\n/addproject عنوان | توضیح")
            return
        title, desc = parts[0], parts[1] if len(parts) > 1 else ""
        c = db()
        cur = c.execute("INSERT INTO projects(title,description) VALUES(?,?)", (title, desc))
        c.commit()
        bot.send_message(message.chat.id, f"✅ پروژه <b>#{cur.lastrowid}</b> ایجاد شد.", reply_markup=menu())

    @bot.message_handler(commands=["addtask"])
    def addtask(message):
        raw = message.text.partition(" ")[2].strip()
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) < 1 or not parts[0]:
            bot.reply_to(message, "فرمت صحیح:\n/addtask عنوان | توضیح | project_id | priority | YYYY-MM-DD")
            return
        title = parts[0]
        desc = parts[1] if len(parts) > 1 else ""
        project_id = int(parts[2]) if len(parts) > 2 and parts[2] else None
        priority = parts[3] if len(parts) > 3 and parts[3] in PRIORITY_LABELS else "normal"
        due = parts[4] if len(parts) > 4 and parts[4] else None
        c = db()
        cur = c.execute(
            "INSERT INTO tasks(title,description,project_id,priority,due_date) VALUES(?,?,?,?,?)",
            (title, desc, project_id, priority, due),
        )
        c.commit()
        bot.send_message(message.chat.id, f"✅ وظیفه <b>#{cur.lastrowid}</b> ایجاد شد.", reply_markup=menu())

    @bot.message_handler(commands=["status"])
    def status(message):
        parts = message.text.split()
        if len(parts) != 3 or parts[2] not in STATUS_LABELS:
            bot.reply_to(message, "/status task_id todo|doing|review|done")
            return
        c = db()
        c.execute("UPDATE tasks SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (parts[2], int(parts[1])))
        c.commit()
        bot.send_message(message.chat.id, "✅ وضعیت وظیفه تغییر کرد.", reply_markup=menu())

    @bot.callback_query_handler(func=lambda call: call.data.startswith("status:"))
    def change_status(call):
        _, task_id, status_value = call.data.split(":")
        c = db()
        c.execute("UPDATE tasks SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status_value, int(task_id)))
        c.commit()
        bot.answer_callback_query(call.id, "وضعیت تغییر کرد")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, f"✅ وظیفه #{task_id}: {STATUS_LABELS[status_value]}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete:"))
    def delete_task(call):
        _, task_id = call.data.split(":")
        c = db()
        c.execute("DELETE FROM tasks WHERE id=?", (int(task_id),))
        c.commit()
        bot.answer_callback_query(call.id, "حذف شد")
        bot.edit_message_text(f"🗑 وظیفه #{task_id} حذف شد.", call.message.chat.id, call.message.message_id)

    @bot.message_handler(func=lambda message: True, content_types=["text"])
    def text_menu(message):
        text = message.text.strip()
        if text == "📊 وضعیت":
            bot.send_message(message.chat.id, stats_text(), reply_markup=menu())
        elif text == "🚀 پروژه‌ها":
            send_projects(message.chat.id)
        elif text == "📋 وظایف":
            send_tasks(message.chat.id)
        elif text == "ℹ️ راهنما":
            bot.send_message(message.chat.id, help_text(), reply_markup=menu())
        elif text == "➕ پروژه جدید":
            bot.send_message(message.chat.id, "برای ایجاد پروژه بنویسید:\n<code>/addproject عنوان | توضیح</code>", reply_markup=menu())
        elif text == "➕ وظیفه جدید":
            bot.send_message(message.chat.id, "برای ایجاد وظیفه بنویسید:\n<code>/addtask عنوان | توضیح | project_id | priority | YYYY-MM-DD</code>", reply_markup=menu())
        else:
            bot.send_message(message.chat.id, "دستور را متوجه نشدم. از منوی پایین استفاده کنید.", reply_markup=menu())


def setup_webhook():
    if not bot or not PUBLIC_URL:
        return False
    bot.remove_webhook()
    bot.set_webhook(url=PUBLIC_URL + WEBHOOK_PATH)
    return True


def webhook_update(payload):
    if not bot:
        return False
    update = types.Update.de_json(payload)
    bot.process_new_updates([update])
    return True
