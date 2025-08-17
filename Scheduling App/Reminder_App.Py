#!/usr/bin/env python3
"""
reminder_app.py

Simple reminder scheduler:
- Persistent storage in SQLite (reminders.db)
- Use APScheduler for scheduling
- Desktop notifications via plyer (optional)
- CLI to add/list/remove reminders and to run the scheduler

Supported reminder types:
- one-off by absolute datetime: YYYY-MM-DD HH:MM (24-hour)
- one-off by time today/tomorrow by HH:MM when --time is used without date
- relative: --in-minutes N
- recurring: --recurring daily|weekly
"""

import argparse
import sqlite3
import threading
import sys
from datetime import datetime, timedelta, time as dtime
import uuid
import os
import traceback

try:
    from plyer import notification
    _HAS_PLYER = True
except Exception:
    _HAS_PLYER = False

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

DB_PATH = os.path.join(os.path.dirname(__file__), "reminders.db")
DATE_FORMAT = "%Y-%m-%d %H:%M"

# --- DB helpers ---
def init_db(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id TEXT PRIMARY KEY,
        message TEXT NOT NULL,
        time TEXT NOT NULL,
        recurring TEXT, -- 'daily', 'weekly', or NULL
        enabled INTEGER NOT NULL DEFAULT 1
    )
    """)
    conn.commit()

def add_reminder_db(conn, reminder_id, message, time_str, recurring):
    cur = conn.cursor()
    cur.execute("INSERT INTO reminders (id,message,time,recurring,enabled) VALUES (?, ?, ?, ?, 1)",
                (reminder_id, message, time_str, recurring))
    conn.commit()

def list_reminders_db(conn):
    cur = conn.cursor()
    cur.execute("SELECT id,message,time,recurring,enabled FROM reminders ORDER BY time")
    return cur.fetchall()

def get_reminder_db(conn, reminder_id):
    cur = conn.cursor()
    cur.execute("SELECT id,message,time,recurring,enabled FROM reminders WHERE id = ?", (reminder_id,))
    return cur.fetchone()

def remove_reminder_db(conn, reminder_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    return cur.rowcount

def disable_reminder_db(conn, reminder_id):
    cur = conn.cursor()
    cur.execute("UPDATE reminders SET enabled = 0 WHERE id = ?", (reminder_id,))
    conn.commit()

# --- Notification action ---
def send_notification(title, message):
    # Try desktop notification first (plyer)
    print(f"[REMINDER] {title} -> {message}")
    if _HAS_PLYER:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="RemindMe",
                timeout=10
            )
        except Exception as e:
            print("Failed to send desktop notification:", e)

# --- Scheduling logic ---
def schedule_from_db(scheduler, conn):
    reminders = list_reminders_db(conn)
    now = datetime.now()
    for rid, msg, timestr, recurring, enabled in reminders:
        if not enabled:
            continue
        # timestr either full datetime ("YYYY-mm-dd HH:MM") or simple "HH:MM" for recurring daily/weekly
        try:
            if recurring is None:
                # parse absolute datetime if possible
                dt = None
                try:
                    dt = datetime.strptime(timestr, DATE_FORMAT)
                except ValueError:
                    # maybe it's "HH:MM" meaning next occurrence of that time
                    try:
                        hhmm = datetime.strptime(timestr, "%H:%M").time()
                        dt_candidate = datetime.combine(now.date(), hhmm)
                        if dt_candidate <= now:
                            dt_candidate += timedelta(days=1)
                        dt = dt_candidate
                    except ValueError:
                        print(f"Unrecognized time format for reminder {rid}: {timestr}")
                        continue
                if dt <= now:
                    # if a non-recurring reminder is in the past, skip (or could trigger immediately)
                    print(f"Skipping past one-off reminder {rid} scheduled at {dt}")
                    continue
                trigger = DateTrigger(run_date=dt)
                scheduler.add_job(run_reminder, trigger=trigger, args=[rid, msg, conn], id=rid)
                print(f"Scheduled one-off reminder {rid} at {dt}")
            else:
                # recurring
                if recurring.lower() == "daily":
                    # time should be HH:MM or full datetime; prefer HH:MM
                    try:
                        hhmm = datetime.strptime(timestr, "%H:%M").time()
                    except ValueError:
                        try:
                            full = datetime.strptime(timestr, DATE_FORMAT)
                            hhmm = full.time()
                        except ValueError:
                            print(f"Unrecognized time for recurring reminder {rid}: {timestr}")
                            continue
                    trigger = CronTrigger(hour=hhmm.hour, minute=hhmm.minute)
                    scheduler.add_job(run_reminder, trigger=trigger, args=[rid, msg, conn], id=rid)
                    print(f"Scheduled daily reminder {rid} at {hhmm}")
                elif recurring.lower() == "weekly":
                    # default to the weekday encoded in timestr if full datetime, else use today
                    try:
                        full = datetime.strptime(timestr, DATE_FORMAT)
                        dow = full.weekday()  # 0=Mon
                        hhmm = full.time()
                        trigger = CronTrigger(day_of_week=dow, hour=hhmm.hour, minute=hhmm.minute)
                        scheduler.add_job(run_reminder, trigger=trigger, args=[rid, msg, conn], id=rid)
                        print(f"Scheduled weekly reminder {rid} on weekday {dow} at {hhmm}")
                    except ValueError:
                        # assume HH:MM and use today's weekday
                        try:
                            hhmm = datetime.strptime(timestr, "%H:%M").time()
                            # day_of_week omitted => every day at time; but we want weekly — fallback to Monday
                            # If user expects weekly but only provided time, schedule weekly on today's weekday
                            dow = datetime.now().weekday()
                            trigger = CronTrigger(day_of_week=dow, hour=hhmm.hour, minute=hhmm.minute)
                            scheduler.add_job(run_reminder, trigger=trigger, args=[rid, msg, conn], id=rid)
                            print(f"Scheduled weekly reminder {rid} on weekday {dow} at {hhmm}")
                        except ValueError:
                            print(f"Unrecognized time for weekly reminder {rid}: {timestr}")
                            continue
                else:
                    print(f"Unknown recurring type for {rid}: {recurring}")
        except Exception as e:
            print("Failed to schedule", rid, ":", e)
            traceback.print_exc()

def run_reminder(reminder_id, message, conn):
    # Called by scheduler when a reminder triggers.
    tstamp = datetime.now().strftime(DATE_FORMAT)
    title = f"Reminder ({tstamp})"
    send_notification(title, message)

    # if the reminder is one-off, disable it (so it doesn't re-run after app restart)
    r = get_reminder_db(conn, reminder_id)
    if r:
        _, _, timestr, recurring, enabled = r
        if recurring is None or recurring == "":
            # mark disabled
            disable_reminder_db(conn, reminder_id)

# --- CLI handlers ---
def cmd_add(args):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # Determine time string to store
    if args.in_minutes is not None:
        dt = datetime.now() + timedelta(minutes=args.in_minutes)
        timestr = dt.strftime(DATE_FORMAT)
        recurring = None
    elif args.time:
        # Try detect full datetime first, then HH:MM
        t = args.time.strip()
        parsed = None
        try:
            parsed = datetime.strptime(t, DATE_FORMAT)
            timestr = parsed.strftime(DATE_FORMAT)
        except ValueError:
            # try HH:MM
            try:
                hhmm = datetime.strptime(t, "%H:%M").time()
                timestr = hhmm.strftime("%H:%M")
            except ValueError:
                print("Time must be either 'YYYY-MM-DD HH:MM' or 'HH:MM' (24-hour) or use --in-minutes.")
                return
        recurring = args.recurring
    else:
        print("You must specify --time or --in-minutes.")
        return

    rid = str(uuid.uuid4())[:8]
    add_reminder_db(conn, rid, args.msg, timestr, recurring)
    print(f"Added reminder {rid}: '{args.msg}' at {timestr}" + (f" recurring={recurring}" if recurring else ""))

def cmd_list(args):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    allr = list_reminders_db(conn)
    if not allr:
        print("No reminders found.")
        return
    print("Reminders:")
    for rid, msg, timestr, recurring, enabled in allr:
        status = "enabled" if enabled else "disabled"
        print(f"  id: {rid} | {timestr} | {recurring or 'one-off'} | {status} | {msg}")

def cmd_remove(args):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    n = remove_reminder_db(conn, args.id)
    if n:
        print(f"Removed reminder {args.id}")
    else:
        print(f"No reminder with id {args.id} found.")

def cmd_run(args):
    # Start scheduler and schedule all enabled reminders.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    init_db(conn)
    scheduler = BackgroundScheduler()
    scheduler.start(paused=True)
    schedule_from_db(scheduler, conn)
    scheduler.resume()
    print("Scheduler running. Press Ctrl-C to quit.")
    try:
        # Keep main thread alive
        while True:
            # sleep in short intervals to be responsive to Ctrl-C
            threading.Event().wait(1)
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down scheduler...")
        scheduler.shutdown()

# --- Argparse setup ---
def build_parser():
    p = argparse.ArgumentParser(prog="reminder_app", description="Simple reminder scheduler")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a reminder")
    p_add.add_argument("--time", help="Absolute time 'YYYY-MM-DD HH:MM' or 'HH:MM' (24-hour). If HH:MM alone, interpreted as next occurrence.")
    p_add.add_argument("--in-minutes", type=int, help="Schedule reminder N minutes from now")
    p_add.add_argument("--msg", required=True, help="Reminder message")
    p_add.add_argument("--recurring", choices=["daily", "weekly"], help="Make reminder recurring")

    p_list = sub.add_parser("list", help="List reminders")

    p_remove = sub.add_parser("remove", help="Remove reminder")
    p_remove.add_argument("--id", required=True, help="Reminder id to remove")

    p_run = sub.add_parser("run", help="Run the scheduler (load reminders and start)")
    return p

def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "add":
        cmd_add(args)
    elif args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "remove":
        cmd_remove(args)
    elif args.cmd == "run":
        cmd_run(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
