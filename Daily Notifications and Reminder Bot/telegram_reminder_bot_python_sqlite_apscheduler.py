"""
Telegram Reminder Bot — Daily Reminders & Task Notifications
-----------------------------------------------------------

Features
- Add one-off reminders at an exact local time or via simple relative syntax ("in 2h", "in 15m").
- Daily summary at a user-chosen local time (e.g., 09:00) listing all due-today tasks.
- List, complete, and remove tasks.
- Per-user timezone support using IANA tz names (e.g., America/Los_Angeles).
- Persists tasks in SQLite; re-schedules pending reminders on restart.

Quickstart
1) Create a Telegram bot with @BotFather and copy the token.
2) Python 3.10+ recommended. Install deps:
   pip install python-telegram-bot==21.4 APScheduler==3.10.4 python-dateutil==2.9.0.post0
3) Set env var TELEGRAM_BOT_TOKEN and run:
   python bot.py

Commands
/start – greet and brief help
/help – command reference
/settz <IANA_tz> – set your timezone (e.g., /settz America/Los_Angeles)
/add <when> | <text> – add a reminder
   Examples:
     /add 2025-09-01 09:00 | Pay rent
     /add in 2h | Stretch break
     /add today 18:30 | Start dinner
/list – show upcoming tasks
/done <id> – mark a task done
/remove <id> – delete a task
/daily <HH:MM>|off – set or turn off your daily summary time

Note: Use the vertical bar `|` to separate the time from the task text.
"""

import asyncio
import logging
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateutil import tz
from dateutil.parser import parse as parse_dt
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

DB_PATH = os.environ.get("REMINDER_BOT_DB", "reminders.db")
DEFAULT_TZ = "UTC"
DAILY_SUMMARY_DEFAULT = None  # HH:MM string or None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------- DB LAYER ----------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  chat_id INTEGER PRIMARY KEY,
  tz TEXT NOT NULL DEFAULT 'UTC',
  daily_time TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  due_utc TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0,
  created_utc TEXT NOT NULL
);
"""


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db_connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


# ---------------------- UTILITIES ----------------------
def get_user_tz(chat_id: int) -> str:
    with closing(db_connect()) as conn:
        cur = conn.execute("SELECT tz FROM users WHERE chat_id=?", (chat_id,))
        row = cur.fetchone()
        return row["tz"] if row else DEFAULT_TZ


def set_user_tz(chat_id: int, tzname: str, daily_time: str | None = None):
    with closing(db_connect()) as conn:
        conn.execute(
            "INSERT INTO users(chat_id, tz, daily_time) VALUES(?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET tz=excluded.tz, daily_time=COALESCE(excluded.daily_time, users.daily_time)",
            (chat_id, tzname, daily_time),
        )
        conn.commit()


def set_user_daily(chat_id: int, daily_time: str | None):
    with closing(db_connect()) as conn:
        conn.execute(
            "INSERT INTO users(chat_id, tz, daily_time) VALUES(?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET daily_time=excluded.daily_time",
            (chat_id, get_user_tz(chat_id), daily_time),
        )
        conn.commit()


def add_task(chat_id: int, text: str, due_utc: datetime) -> int:
    with closing(db_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO tasks(chat_id, text, due_utc, created_utc) VALUES(?,?,?,?)",
            (chat_id, text, due_utc.isoformat(), datetime.utcnow().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def list_tasks(chat_id: int, include_done: bool = False):
    q = "SELECT id, text, due_utc, done FROM tasks WHERE chat_id=? "
    if not include_done:
        q += "AND done=0 "
    q += "ORDER BY datetime(due_utc) ASC"
    with closing(db_connect()) as conn:
        return [dict(r) for r in conn.execute(q, (chat_id,))]


def mark_done(chat_id: int, task_id: int) -> bool:
    with closing(db_connect()) as conn:
        cur = conn.execute(
            "UPDATE tasks SET done=1 WHERE chat_id=? AND id=? AND done=0",
            (chat_id, task_id),
        )
        conn.commit()
        return cur.rowcount > 0


def remove_task(chat_id: int, task_id: int) -> bool:
    with closing(db_connect()) as conn:
        cur = conn.execute("DELETE FROM tasks WHERE chat_id=? AND id=?", (chat_id, task_id))
        conn.commit()
        return cur.rowcount > 0


# ---------------------- PARSING ----------------------
RELATIVE_RE = re.compile(r"^in\s+(\d+)\s*([mhd])$", re.IGNORECASE)
TODAY_RE = re.compile(r"^(today|tomorrow)\s+(\d{1,2}:\d{2})$", re.IGNORECASE)


def to_utc(dt_local: datetime, tzname: str) -> datetime:
    z = ZoneInfo(tzname)
    return dt_local.replace(tzinfo=z).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def from_utc(dt_utc: datetime, tzname: str) -> datetime:
    return dt_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(tzname))


def parse_when(when_str: str, tzname: str) -> datetime:
    when_str = when_str.strip()
    m = RELATIVE_RE.match(when_str)
    if m:
        qty, unit = int(m.group(1)), m.group(2).lower()
        delta = {"m": timedelta(minutes=qty), "h": timedelta(hours=qty), "d": timedelta(days=qty)}[unit]
        return datetime.utcnow() + delta

    m2 = TODAY_RE.match(when_str)
    if m2:
        day_word, hhmm = m2.groups()
        today_local = datetime.now(ZoneInfo(tzname)).date()
        if day_word.lower() == "tomorrow":
            target_date = today_local + timedelta(days=1)
        else:
            target_date = today_local
        h, mi = map(int, hhmm.split(":"))
        dt_local = datetime.combine(target_date, time(h, mi))
        return to_utc(dt_local, tzname)

    # Try absolute parsing (dateutil handles many formats, assume naive is local tz)
    try:
        dt = parse_dt(when_str, fuzzy=True)
        if dt.tzinfo is None:
            dt = to_utc(dt, tzname)
        else:
            dt = dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        return dt
    except Exception as e:
        raise ValueError("Sorry, I couldn't parse that time. Try formats like '2025-09-01 09:00', 'today 18:30', or 'in 2h'.")


# ---------------------- SCHEDULER ----------------------
scheduler = AsyncIOScheduler()


async def send_reminder(app: Application, chat_id: int, task_id: int):
    # Fetch task; skip if done or missing
    with closing(db_connect()) as conn:
        cur = conn.execute("SELECT id, text, due_utc, done FROM tasks WHERE id=? AND chat_id=?", (task_id, chat_id))
        row = cur.fetchone()
    if not row or row["done"]:
        return

    tzname = get_user_tz(chat_id)
    due_local = from_utc(datetime.fromisoformat(row["due_utc"]), tzname)
    text = row["text"]

    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⏰ *Reminder:* {escape_md(text)}\n"
                f"🗓️ Due: {due_local.strftime('%Y-%m-%d %H:%M')} ({tzname})"
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        logger.exception("Failed to send reminder: %s", e)


async def send_daily_summary(app: Application, chat_id: int):
    tzname = get_user_tz(chat_id)
    now_local = datetime.now(ZoneInfo(tzname))
    start_utc = to_utc(datetime.combine(now_local.date(), time(0, 0)), tzname)
    end_utc = to_utc(datetime.combine(now_local.date(), time(23, 59)), tzname)

    with closing(db_connect()) as conn:
        rows = conn.execute(
            "SELECT id, text, due_utc FROM tasks WHERE chat_id=? AND done=0 AND datetime(due_utc) BETWEEN ? AND ? ORDER BY datetime(due_utc)",
            (chat_id, start_utc.isoformat(), end_utc.isoformat()),
        ).fetchall()

    if not rows:
        body = "No tasks due today. Have a great day!"
    else:
        items = []
        for r in rows:
            local = from_utc(datetime.fromisoformat(r["due_utc"]), tzname)
            items.append(f"• [{r['id']}] {escape_md(r['text'])} — {local.strftime('%H:%M')}")
        body = "\n".join(items)

    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=f"🗒️ *Today's summary* ({now_local.strftime('%Y-%m-%d')}, {tzname})\n\n" + body,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        logger.exception("Failed to send daily summary: %s", e)


# ---------------------- TELEGRAM HANDLERS ----------------------
def escape_md(text: str) -> str:
    # Minimal escape for MarkdownV2 special characters
    return re.sub(r"([_*>\\[\\]()~`>#+\-=|{}.!])", r"\\\\\1", text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Ensure user row exists
    set_user_tz(chat_id, get_user_tz(chat_id))
    await update.message.reply_text(
        "Hi! I can remind you about important tasks.\n\n"
        "Set your timezone first (once):\n"
        "  /settz America/Los_Angeles\n\n"
        "Add a reminder (use '|' to split time and text):\n"
        "  /add 2025-09-01 09:00 | Pay rent\n"
        "  /add today 18:30 | Start dinner\n"
        "  /add in 2h | Stretch break\n\n"
        "Daily summary at a set time:\n"
        "  /daily 09:00   or   /daily off\n\n"
        "Other commands: /list, /done <id>, /remove <id>, /help"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def settz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /settz <IANA_tz>  (e.g., America/Los_Angeles)")
        return
    tzname = context.args[0]
    try:
        ZoneInfo(tzname)
    except ZoneInfoNotFoundError:
        await update.message.reply_text("Invalid timezone. Try something like America/New_York or Europe/London.")
        return
    set_user_tz(chat_id, tzname)
    await update.message.reply_text(f"Timezone set to {tzname}.")


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    if "|" not in text:
        await update.message.reply_text("Usage: /add <when> | <task text>\nExample: /add today 18:30 | Start dinner")
        return
    when_part, task_part = [s.strip() for s in text.split("|", 1)]
    when_part = when_part[len("/add"):].strip()
    if not task_part:
        await update.message.reply_text("Please include task text after the '|'.")
        return
    tzname = get_user_tz(chat_id)
    try:
        due_utc = parse_when(when_part, tzname)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    if due_utc < datetime.utcnow() + timedelta(seconds=5):
        await update.message.reply_text("That time is in the past. Please choose a future time.")
        return

    task_id = add_task(chat_id, task_part, due_utc)

    # Schedule reminder
    context.application.job_queue.run_once(
        lambda ctx: asyncio.create_task(send_reminder(context.application, chat_id, task_id)),
        when=(due_utc - datetime.utcnow()),
        name=f"reminder_{chat_id}_{task_id}",
    )

    due_local = from_utc(due_utc, tzname)
    await update.message.reply_text(
        f"Added task [{task_id}] for {due_local.strftime('%Y-%m-%d %H:%M')} ({tzname})."
    )


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    tzname = get_user_tz(chat_id)
    rows = list_tasks(chat_id)
    if not rows:
        await update.message.reply_text("No upcoming tasks.")
        return
    lines = []
    for r in rows:
        due_local = from_utc(datetime.fromisoformat(r["due_utc"]), tzname)
        lines.append(f"[{r['id']}] {r['text']} — {due_local.strftime('%Y-%m-%d %H:%M')} ({tzname})")
    await update.message.reply_text("\n".join(lines))


async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /done <id>")
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Task id must be a number.")
        return
    if mark_done(chat_id, tid):
        await update.message.reply_text(f"Marked task [{tid}] as done.")
    else:
        await update.message.reply_text("Couldn't find an active task with that id.")


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /remove <id>")
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Task id must be a number.")
        return
    if remove_task(chat_id, tid):
        await update.message.reply_text(f"Removed task [{tid}].")
    else:
        await update.message.reply_text("Couldn't find a task with that id.")


async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /daily <HH:MM>|off")
        return
    arg = context.args[0].lower()
    if arg == "off":
        set_user_daily(chat_id, None)
        await update.message.reply_text("Daily summary turned off.")
        return
    # validate HH:MM
    if not re.match(r"^\d{2}:\d{2}$", arg):
        await update.message.reply_text("Please provide time as HH:MM (e.g., 09:00) or 'off'.")
        return
    set_user_daily(chat_id, arg)
    await update.message.reply_text(f"Daily summary set to {arg} (your local time).")


# ---------------------- RESCHEDULING & DAILY TICKS ----------------------
async def reschedule_pending(app: Application):
    """On startup, schedule all future, unfinished tasks."""
    with closing(db_connect()) as conn:
        rows = conn.execute(
            "SELECT id, chat_id, due_utc FROM tasks WHERE done=0 AND datetime(due_utc) > datetime('now')"
        ).fetchall()
    for r in rows:
        due_utc = datetime.fromisoformat(r["due_utc"])
        delay = (due_utc - datetime.utcnow()).total_seconds()
        app.job_queue.run_once(
            lambda ctx, chat_id=r["chat_id"], task_id=r["id"]: asyncio.create_task(send_reminder(app, chat_id, task_id)),
            when=max(1, delay),
            name=f"reminder_{r['chat_id']}_{r['id']}",
        )
    logger.info("Rescheduled %d pending reminders", len(rows))


async def schedule_daily_ticks(app: Application):
    """Every minute, check who needs a daily summary right now and send it."""
    async def tick(context: ContextTypes.DEFAULT_TYPE):
        with closing(db_connect()) as conn:
            users = conn.execute("SELECT chat_id, tz, daily_time FROM users WHERE daily_time IS NOT NULL").fetchall()
        now_utc = datetime.utcnow().replace(second=0, microsecond=0)
        for u in users:
            tzname = u["tz"]
            hhmm = u["daily_time"]
            try:
                z = ZoneInfo(tzname)
            except Exception:
                continue
            now_local = datetime.now(z).replace(second=0, microsecond=0)
            target_h, target_m = map(int, hhmm.split(":"))
            if now_local.time() == time(target_h, target_m):
                asyncio.create_task(send_daily_summary(app, u["chat_id"]))

    app.job_queue.run_repeating(tick, interval=60, first=0)


# ---------------------- APP BOOT ----------------------
async def main():
    init_db()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Please set TELEGRAM_BOT_TOKEN environment variable.")

    application = Application.builder().token(token).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("settz", settz))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("done", done_cmd))
    application.add_handler(CommandHandler("remove", remove_cmd))
    application.add_handler(CommandHandler("daily", daily_cmd))

    # On start: schedule pending tasks and daily ticks
    application.post_init = lambda app: asyncio.gather(reschedule_pending(app), schedule_daily_ticks(app))

    await application.run_polling(close_loop=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
