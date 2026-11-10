#TODO: Libs
import asyncio
import csv
import json
import logging
import os
import random
import time
import threading
from collections import deque
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
from mysql.connector import pooling
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    JobQueue,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

# Load .env from the repo root when running outside systemd (local dev).
try:
    from dotenv import load_dotenv

    _REPO_ROOT = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:  # python-dotenv is optional at runtime
    pass


# ---------------------------------------------------------------------------
# Configuration
# All values come from the environment (.env). NEVER hardcode secrets here.
# ---------------------------------------------------------------------------
def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# TODO: Logging Config — centralized logger across the whole bot
_HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = _env("LOG_DIR", os.path.join(_HERE, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("smartgreengarden")
logger.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)

_file_handler = logging.FileHandler(os.path.join(LOG_DIR, "export.log"))
_file_handler.setLevel(logging.DEBUG)

_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
_console_handler.setFormatter(_formatter)
_file_handler.setFormatter(_formatter)

logger.addHandler(_console_handler)
logger.addHandler(_file_handler)

# TODO: Telegram Config
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("TELEGRAM_CHAT_ID", "")
# Comma-separated chat ids allowed to command the bot. Empty = allow the owner only.
TELEGRAM_ALLOWED_CHAT_IDS = {
    cid.strip()
    for cid in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", TELEGRAM_CHAT_ID).split(",")
    if cid.strip()
}

# TODO: MQTT Config
MQTT_BROKER = _env("MQTT_HOST", "127.0.0.1")
MQTT_PORT = _env_int("MQTT_PORT", 1883)
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "smartgreengarden")

MQTT_TOPIC = f"{MQTT_TOPIC_PREFIX}/sensor/data"
MQTT_TOPIC_NOTIF = f"{MQTT_TOPIC_PREFIX}/notification"
MQTT_TOPIC_CAL_TURB_START = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/turbidity/start"
MQTT_TOPIC_CAL_TURB_NEXT = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/turbidity/next"
MQTT_TOPIC_CAL_TURB_CANCEL = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/turbidity/cancel"
MQTT_TOPIC_CAL_TURB_STATUS = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/turbidity/status"
MQTT_TOPIC_REQUEST_DATA = f"{MQTT_TOPIC_PREFIX}/sensor/request_data"
MQTT_TOPIC_CAL_TDS1_MULTI_START = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/tds1/multi/start"
MQTT_TOPIC_CAL_TDS1_MULTI_SET = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/tds1/multi/set"
MQTT_TOPIC_CAL_TDS2_MULTI_START = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/tds2/multi/start"
MQTT_TOPIC_CAL_TDS2_MULTI_SET = f"{MQTT_TOPIC_PREFIX}/sensor/calibrate/tds2/multi/set"
MQTT_TOPIC_CAL_TDS1_SINGLE = f"{MQTT_TOPIC_PREFIX}/sensor/kalibrasi/tds1"
MQTT_TOPIC_CAL_TDS2_SINGLE = f"{MQTT_TOPIC_PREFIX}/sensor/kalibrasi/tds2"

# Actuator namespace: kept as its own prefix because the firmware publishes it.
MQTT_TOPIC_MODE = f"{MQTT_TOPIC_PREFIX}/system/mode"
MQTT_TOPIC_RELAY_IRIGASI = f"{MQTT_TOPIC_PREFIX}/relay/pompa_irigasi/command"
MQTT_TOPIC_RELAY_KURAS_TANDON = f"{MQTT_TOPIC_PREFIX}/relay/pengurasan_tandon/command"
MQTT_TOPIC_RELAY_KURAS = f"{MQTT_TOPIC_PREFIX}/relay/pengurasan/command"
MQTT_TOPIC_RELAY_PENGADUK = f"{MQTT_TOPIC_PREFIX}/relay/pengaduk_tandon/command"
MQTT_TOPIC_RELAY_VALVE_TANDON = f"{MQTT_TOPIC_PREFIX}/relay/valve_tandon/command"
MQTT_TOPIC_RELAY_POMPA_KURAS = f"{MQTT_TOPIC_PREFIX}/relay/pompa_kuras/command"

# TODO: Database (MariaDB)
DB_HOST = _env("DB_HOST", "127.0.0.1")
DB_PORT = _env_int("DB_PORT", 3306)
DB_USER = _env("DB_USER")
DB_PASSWORD = _env("DB_PASSWORD")
DB_NAME = _env("DB_NAME")
DB_TABLE = _env("DB_TABLE", "hydroponic_water_data_romy")
DB_TIME_COLUMN = _env("DB_TIME_COLUMN", "datetime")
DB_TIME_IS_STRING = _env_bool("DB_TIME_IS_STRING", False)
DB_TIME_STRING_FORMAT = os.getenv("DB_TIME_STRING_FORMAT", "%Y-%m-%d %H:%i:%s")

# TODO: EXPORT CONFIG
EXPORT_DIR = _env("EXPORT_DIR", os.path.join(_HERE, "exports"))
# Local CSV exports are transient — keep them out of git.
for _path in (EXPORT_DIR, LOG_DIR):
    try:
        os.makedirs(_path, exist_ok=True)
    except OSError:
        pass

# Whitelist of table_key -> (real table name, timestamp column).
EXPORTABLE_TABLES = {
    "sensor_data": {"table": DB_TABLE, "time_col": DB_TIME_COLUMN},
    "relay_logs": {"table": "relay_logs", "time_col": "event_time"},
}

# TODO: AUTH CONFIG
ACCESS_PASSWORD = _env("ACCESS_PASSWORD")
SESSION_TIMEOUT_SECONDS = _env_int("SESSION_TIMEOUT_SECONDS", 3600)
authed_sessions: dict[int, float] = {}

# NOTE: Define state
latest_data: dict             = {}
pending_alerts: list          = []
pending_cal_status: list      = []
last_mqtt_receive_unix: float = 0
turbidity_cal_active: bool   = False  # ponytail: active turbidity calibration session flag
mqtt_client: mqtt.Client | None = None
db_pool = None

# ponytail: lightweight per-sensor history ring buffers (maxlen=10) for sparklines & trends (0 extra RAM overhead)
sensor_history: dict[str, deque] = {}

system_state = {
    "mode": "auto",
    "relays": {
        "irigasi": "off",
        "kuras_tandon": "off",
        "kuras": "off",
        "pengaduk": "off",
        "valve_tandon": "off",
        "pompa_kuras": "off",
    }
}

relay_last_on: dict[str, float] = {}
RELAY_DISPLAY_NAMES = {
    "irigasi":       "Pompa Irigasi",
    "kuras_tandon":  "Kuras Tandon",
    "kuras":         "Pengurasan",
    "pengaduk":      "Pengaduk Tandon",
    "valve_tandon":  "Valve Tandon",
    "pompa_kuras":   "Pompa Kuras",
}

# NOTE: CATEGORIZED ALERTS SYSTEM
# ponytail: severity-badged alert helper adding icons and logging alerts
ALERT_ICONS = {
    "critical": "🚨",
    "warning":  "⚠️",
    "info":     "ℹ️",
    "system":   "⚙️",
}

def push_alert(message: str, level: str = "info"):
    lvl = level.lower()
    icon = ALERT_ICONS.get(lvl, "ℹ️")
    formatted_alert = f"{icon} <b>[{lvl.upper()}]</b> {message}"
    pending_alerts.append(formatted_alert)
    logger.info(f"Alert queued [{lvl.upper()}]: {message}")

# NOTE: ASCII & UNICODE VISUALIZATION HELPERS (0 RAM, Standard Lib Only)
# ponytail: 8-level Unicode sparkline characters
_SPARK_CHARS = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

def record_sensor_history(key: str, raw_val: str):
    try:
        val = float(raw_val)
        if key not in sensor_history:
            sensor_history[key] = deque(maxlen=10)
        sensor_history[key].append((time.time(), val))
    except (ValueError, TypeError):
        pass

# ponytail: render mini sparkline from ring buffer history
def render_sparkline(key: str) -> str:
    if key == "water_quality":
        return ""
    history = sensor_history.get(key)
    if not history or len(history) < 2:
        return ""
    vals = [v for _, v in history]
    min_v = min(vals)
    max_v = max(vals)
    span = max_v - min_v
    if span == 0:
        return f"[{_SPARK_CHARS[3] * len(vals)}]"
    
    spark_str = "".join(_SPARK_CHARS[min(7, max(0, int((v - min_v) / span * 7)))] for v in vals)
    return f"[{spark_str}]"

# ponytail: 10-char visual progress bar for percentages (e.g. water tanks)
def render_progress_bar(percent: float | int, length: int = 10) -> str:
    try:
        p = max(0.0, min(100.0, float(percent)))
    except (ValueError, TypeError):
        return f"[{'░' * length}]"
    filled = int(round((p / 100.0) * length))
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}]"

# ponytail: gauge meter showing current value relative to safe operating range
def render_gauge_bar(val: float, min_val: float, max_val: float, length: int = 10) -> str:
    if max_val <= min_val:
        return f"[{'─' * length}]"
    pos = int(round(((val - min_val) / (max_val - min_val)) * (length - 1)))
    pos = max(0, min(length - 1, pos))
    bar = ["─"] * length
    bar[pos] = "●"
    return f"[{''.join(bar)}]"

# ponytail: compute on-the-fly descriptive stats from ring buffer
def get_sensor_stats(key: str) -> dict | None:
    history = sensor_history.get(key)
    if not history:
        return None
    vals = [v for _, v in history]
    return {
        "count": len(vals),
        "latest": vals[-1],
        "min": min(vals),
        "max": max(vals),
        "avg": sum(vals) / len(vals),
        "sparkline": render_sparkline(key),
        "arrow": get_trend_arrow(key),
    }

# ponytail: calculate trend arrow by comparing oldest vs newest value in history deque
def get_trend_arrow(key: str) -> str:
    if key == "water_quality":
        return ""
    history = sensor_history.get(key)
    if not history or len(history) < 2:
        return ""
    oldest_val = history[0][1]
    newest_val = history[-1][1]
    diff = newest_val - oldest_val
    if abs(diff) < 0.01:
        return "→"
    return "↗" if diff > 0 else "↘"

# ponytail: freshness badge based on seconds elapsed since last_mqtt_receive_unix
def get_freshness_badge() -> str:
    if last_mqtt_receive_unix == 0:
        return "⚪ (belum ada data)"
    age = time.time() - last_mqtt_receive_unix
    if age < 30:
        return "🟢 Fresh"
    elif age < 300:
        return f"🟡 {int(age)}s lalu"
    else:
        mins = int(age // 60)
        return f"🔴 {mins}m lalu — cek ESP32"

# NOTE: AUTH HELPERS
def is_authed(user_id: int) -> bool:
    if user_id not in authed_sessions:
        return False
    if time.time() - authed_sessions[user_id] > SESSION_TIMEOUT_SECONDS:
        del authed_sessions[user_id]
        return False
    return True

def require_auth(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_authed(uid):
            await update.message.reply_text(
                "🔒 <b>Access Denied.</b>\n"
                "Please login first: /login <i>&lt;password&gt;</i>",
                parse_mode=ParseMode.HTML,
            )
            return
        # Refresh session timer on every command (inactivity-based expiry)
        authed_sessions[uid] = time.time()
        return await handler(update, context)
    return wrapper


# NOTE: DATABASE SETUP
_db_init_error: str = "" 

def init_db_pool():
    global db_pool, _db_init_error
    try:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="romy_pool",
            pool_size=5,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True,
        )
        _db_init_error = ""
        logger.info("✅ DB pool initialized")
    except Exception as e:
        _db_init_error = str(e)
        logger.error(f"❌ Failed to init DB pool: {e}")
        db_pool = None


def db_fetch_one(query, params=None):
    if db_pool is None:
        return None
    conn = None
    try:
        conn = db_pool.get_connection()
        cur  = conn.cursor()
        cur.execute(query, params or ())
        row = cur.fetchone()
        cur.close()
        return row
    except Exception as e:
        logger.error(f"❌ DB fetch error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_db_stats():
    total_row   = db_fetch_one(f"SELECT COUNT(*) FROM {DB_TABLE}")
    total_count = int(total_row[0]) if total_row and total_row[0] is not None else 0

    if DB_TIME_IS_STRING:
        today_q = f"""
            SELECT COUNT(*)
            FROM {DB_TABLE}
            WHERE DATE(STR_TO_DATE({DB_TIME_COLUMN}, %s)) = CURDATE()
        """
        today_row   = db_fetch_one(today_q, (DB_TIME_STRING_FORMAT,))
        today_count = int(today_row[0]) if today_row and today_row[0] is not None else 0

        last_q   = f"SELECT MAX(STR_TO_DATE({DB_TIME_COLUMN}, %s)) FROM {DB_TABLE}"
        last_row = db_fetch_one(last_q, (DB_TIME_STRING_FORMAT,))
    else:
        today_q     = f"SELECT COUNT(*) FROM {DB_TABLE} WHERE DATE({DB_TIME_COLUMN}) = CURDATE()"
        today_row   = db_fetch_one(today_q)
        today_count = int(today_row[0]) if today_row and today_row[0] is not None else 0

        last_row = db_fetch_one(f"SELECT MAX({DB_TIME_COLUMN}) FROM {DB_TABLE}")

    last_ts = last_row[0] if last_row else None
    return total_count, today_count, str(last_ts) if last_ts is not None else "N/A"

def log_relay_event(relay_name: str, state: str):
    if db_pool is None:
        return
    conn = None
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor()

        if state == "ON":
            cur.execute(
                "INSERT INTO relay_logs (relay_name, state, event_time, mode) "
                "VALUES (%s, %s, NOW(), %s)",
                (relay_name, "ON", system_state["mode"]),
            )
            relay_last_on[relay_name] = time.time()
        else:
            duration = None
            if relay_name in relay_last_on:
                duration = int(time.time() - relay_last_on[relay_name])
                del relay_last_on[relay_name]
            cur.execute(
                "INSERT INTO relay_logs (relay_name, state, event_time, duration_seconds, mode) "
                "VALUES (%s, %s, NOW(), %s, %s)",
                (relay_name, "OFF", duration, system_state["mode"]),
            )

        conn.commit()
        cur.close()
        logger.info(f"Relay event logged: {relay_name} -> {state}")
    except Exception as e:
        logger.error(f"❌ Relay log insert error: {e}")
    finally:
        if conn:
            conn.close()


def get_relay_logs(relay_name: str, limit: int = 10):
    if db_pool is None:
        return []
    conn = None
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT state, event_time, duration_seconds, mode "
            "FROM relay_logs WHERE relay_name = %s "
            "ORDER BY event_time DESC LIMIT %s",
            (relay_name, limit),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception as e:
        logger.error(f"❌ Relay log fetch error: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_relay_on_seconds(relay_name: str, period: str = "today") -> int:
    total = 0
    if db_pool is not None:
        conn = None
        try:
            conn = db_pool.get_connection()
            cur = conn.cursor()
            if period == "week":
                where_clause = (
                    "DATE(event_time) >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)"
                )
            else:
                where_clause = "DATE(event_time) = CURDATE()"

            cur.execute(
                f"SELECT COALESCE(SUM(duration_seconds), 0) FROM relay_logs "
                f"WHERE relay_name = %s AND state = 'OFF' AND {where_clause}",
                (relay_name,),
            )
            row = cur.fetchone()
            total = int(row[0]) if row and row[0] is not None else 0
            cur.close()
        except Exception as e:
            logger.error(f"❌ Relay stats error: {e}")
        finally:
            if conn:
                conn.close()

    if relay_name in relay_last_on:
        total += int(time.time() - relay_last_on[relay_name])

    return total


def format_duration(seconds: int) -> str:
    if seconds is None:
        return "N/A"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

# NOTE: CSV EXPORT & PREVIEW
def get_export_count(table_key: str, days: int | None = None) -> int:
    if table_key not in EXPORTABLE_TABLES or db_pool is None:
        return 0
    cfg = EXPORTABLE_TABLES[table_key]
    table, time_col = cfg["table"], cfg["time_col"]
    query = f"SELECT COUNT(*) FROM {table}"
    params = ()
    if days is not None:
        cutoff = datetime.now() - timedelta(days=days)
        query += f" WHERE {time_col} >= %s"
        params = (cutoff,)
    row = db_fetch_one(query, params)
    return int(row[0]) if row and row[0] is not None else 0

def export_table_to_csv(table_key: str, days: int | None = None):
    logger.debug(f"export_table_to_csv called | table_key={table_key} days={days}")

    if table_key not in EXPORTABLE_TABLES:
        logger.error(f"Rejected export: unknown table_key '{table_key}' (not in whitelist)")
        return None, 0

    if db_pool is None:
        logger.error("Export aborted: db_pool is None (DB not initialized/connected)")
        return None, 0

    cfg = EXPORTABLE_TABLES[table_key]
    table = cfg["table"]
    time_col = cfg["time_col"]

    query = f"SELECT * FROM {table}"
    params = ()
    if days is not None:
        cutoff = datetime.now() - timedelta(days=days)
        query += f" WHERE {time_col} >= %s"
        params = (cutoff,)
        logger.debug(f"Applying date filter: {time_col} >= {cutoff}")

    query += f" ORDER BY {time_col} DESC"
    logger.debug(f"Export query: {query} | params={params}")

    conn = None
    try:
        conn = db_pool.get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        cur.close()
        logger.info(f"Fetched {len(rows)} rows from '{table}' for export")
    except Exception as e:
        logger.error(f"Export query failed for table '{table}': {e}", exc_info=True)
        return None, 0
    finally:
        if conn:
            conn.close()

    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{table_key}_{timestamp}.csv"
        filepath = os.path.join(EXPORT_DIR, filename)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

        filesize = os.path.getsize(filepath)
        logger.info(f"CSV written: {filepath} ({filesize} bytes, {len(rows)} rows)")
        return filepath, len(rows)
    except Exception as e:
        logger.error(f"Failed writing CSV for table '{table}': {e}", exc_info=True)
        return None, 0


# TODO: HELPERS
def _clean_nan(value: str) -> str:
    if isinstance(value, str) and "nan" in value.lower():
        return value.replace("nan", "0.0")
    return value

# ponytail: derive water_quality state from raw values to prevent stale classification desync
def reevaluate_water_quality(data: dict) -> str:
    try:
        turb = float(data.get("turbidity", 0))
        d_tds = float(data.get("delta_tds", 0))
        levels = [float(data.get(f"level{i}", 100)) for i in range(1, 5) if f"level{i}" in data]

        if levels and any(lvl <= 30 for lvl in levels):
            return "4"  # Water Level Low
        if turb > 50:
            return "1" if d_tds <= 15 else "0"  # Sediment vs Nutrient Cloudiness
        if d_tds > 20:
            return "3"  # Nutrient Imbalance
        return "2"  # Normal
    except (ValueError, TypeError):
        return data.get("water_quality", "2")

def _sanitize_latest():
    clean = {k: _clean_nan(v) for k, v in latest_data.items()}
    if "turbidity" in clean or "water_quality" in clean:
        clean["water_quality"] = reevaluate_water_quality(clean)
    return clean


# NOTE: WATER QUALITY LABELS
WATER_QUALITY_LABELS = {
    "0": "🟡 Cloudy due to Nutrient",
    "1": "🟤 Cloudy due to Sediment",
    "2": "🟢 Normal / Clear",
    "3": "🟠 Nutrient Imbalance",
    "4": "🔴 Water Level Low",
}

def describe_water_quality(raw_value: str) -> str:
    return WATER_QUALITY_LABELS.get(str(raw_value).strip(), f"Unknown ({raw_value})")

# NOTE: WATER LEVEL CATEGORY & EMOJI
def describe_level_category(percent_value: str) -> tuple[str, str]:
    try:
        p = float(percent_value)
    except (ValueError, TypeError):
        return "Unknown", "⚪"
    if p <= 0:
        return "Empty", "⚪"
    if p <= 30:
        return "Low", "🔴"
    if p <= 75:
        return "Medium", "🟡"
    if p < 100:
        return "High", "🟢"
    return "Full", "🔵"


# NOTE: SENSOR DISPLAY METADATA
SENSOR_DISPLAY_META = {
    "tds1":          ("TDS Sensor 1",  "ppm",   None),
    "tds2":          ("TDS Sensor 2",  "ppm",   None),
    "delta_tds":     ("Delta TDS",     "%",     None),
    "turbidity":     ("Turbidity",     "NTU",   None),
    "flowrate":      ("Flow Rate",     "L/min", None),
    "level1":        ("Water Level 1", "%",     "level"),
    "level2":        ("Water Level 2", "%",     "level"),
    "level3":        ("Water Level 3", "%",     "level"),
    "level4":        ("Water Level 4", "%",     "level"),
    "water_quality": ("Water Quality", "",      "quality"),
}

# ponytail: format individual sensor line with sparkline, trend arrow, or progress bar
def format_sensor_value(data_key: str, raw_value: str) -> str:
    label, unit, kind = SENSOR_DISPLAY_META.get(data_key, (data_key.upper(), "", None))
    arrow = get_trend_arrow(data_key)
    arrow_str = f" {arrow}" if arrow else ""
    spark = render_sparkline(data_key)
    spark_str = f" <code>{spark}</code>" if spark else ""

    if kind == "quality":
        return f"<b>{label}</b>: {describe_water_quality(raw_value)}"

    if kind == "level":
        category, emoji = describe_level_category(raw_value)
        bar = render_progress_bar(raw_value, length=8)
        return f"<b>{label}</b>: <code>{bar}</code> {raw_value}% ({category}) {emoji}{arrow_str}"

    unit_suffix = f" {unit}" if unit else ""
    return f"<b>{label}</b>: {raw_value}{unit_suffix}{spark_str}{arrow_str}"


# NOTE: LOGIN / LOGOUT COMMANDS
async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        await update.message.delete()
    except Exception:
        pass

    if not context.args:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Usage: /login <i>&lt;password&gt;</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    if context.args[0] == ACCESS_PASSWORD:
        authed_sessions[uid] = time.time()
        logger.info(f"User {uid} ({update.effective_user.first_name}) logged in successfully")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"✅ <b>Login successful!</b> Welcome, {update.effective_user.first_name} 👋\n"
                f"Session active for <b>{SESSION_TIMEOUT_SECONDS // 60} minutes</b>.\n\n"
                "Type /help to see available commands & ASCII visualizations."
            ),
            parse_mode=ParseMode.HTML,
        )
    else:
        logger.warning(f"Failed login attempt for user {uid}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Incorrect password. Please try again.",
        )


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    authed_sessions.pop(update.effective_user.id, None)
    logger.info(f"User {update.effective_user.id} logged out")
    await update.message.reply_text("👋 Logged out successfully. See you!")


# NOTE: HELP COMMAND
@require_auth
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>📋 COMMAND LIST (v9 ASCII Edition)</b>\n\n"

        "<b>📊 ASCII &amp; SENSOR VISUALIZATION</b>\n"
        "<code>/all_data</code> — Full dashboard with sparklines &amp; tank bars\n"
        "<code>/tanks</code> — 🌊 Visual comparison of all 4 water tanks\n"
        "<code>/tds1</code>, <code>/tds2</code> — TDS stats, sparkline &amp; health\n"
        "<code>/turbidity</code> — Turbidity gauge meter &amp; stats\n"
        "<code>/delta_tds</code> — TDS difference meter &amp; sparkline\n"
        "<code>/flowrate</code> — Flow rate stat card &amp; trend\n"
        "<code>/level1</code>..<code>/level4</code> — Tank level visual card\n"
        "<code>/water_quality</code> — Water classification &amp; status\n\n"

        "<b>📦 DATABASE MONITORING</b>\n"
        "<code>/status</code> — System status, freshness, DB record counts\n\n"

        "<b>⚙️ CALIBRATION</b>\n"
        "<code>/cal_tds1 start|set|single [val]</code> — TDS1 calibration\n"
        "<code>/cal_tds2 start|set|single [val]</code> — TDS2 calibration\n"
        "<code>/calturb</code> — Start turbidity calibration (0/50/100 NTU)\n"
        "<code>/next</code> — Next calibration point\n"
        "<code>/cancelcal</code> — Cancel calibration\n\n"

        "<b>🕹️ MANUAL OVERRIDE</b>\n"
        "<code>/mode auto|manual</code> — Switch automation mode\n"
        "<code>/relaypanel</code> — Interactive relay control panel\n"
        "<code>/relay [name] [on/off]</code> — Control relay via text\n"
        "<code>/relaylog [name] [count]</code> — Recent ON/OFF history\n"
        "<code>/relaystats [name] [week]</code> — Total ON-time today/week\n\n"

        "<b>📤 EXPORT &amp; DB</b>\n"
        "<code>/export list|[table] [days]</code> — Export CSV table\n"
        "<code>/dbstatus [reconnect]</code> — Database health check\n\n"

        "<b>🔐 ACCOUNT</b>\n"
        "<code>/logout</code> — End session"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# NOTE: STATUS KEYBOARD & COMMAND
def build_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh:status"),
            InlineKeyboardButton("🌊 View Tanks", callback_data="refresh:tanks"),
        ]
    ])

def build_status_message_text() -> str:
    total_count, today_count, last_ts_str = get_db_stats()

    if last_mqtt_receive_unix > 0 and (time.time() - last_mqtt_receive_unix) > 600:
        status_text = "Warning ⚠️ (No data for > 10 min)"
    else:
        status_text = "Normal ✅"

    mode_str = system_state["mode"].upper()
    r = system_state["relays"]
    badge = get_freshness_badge()

    return (
        f"🖥️ <b>Device Status:</b> {status_text}\n"
        f"⏱️ <b>Data Freshness:</b> {badge}\n"
        f"📡 <b>MQTT Broker:</b> {MQTT_BROKER}:{MQTT_PORT}\n"
        f"🗃️ <b>Database:</b> {DB_NAME}.{DB_TABLE}\n\n"
        f"⏱️ <b>Last DB Record:</b> {last_ts_str}\n"
        f"📥 <b>Entries Today:</b> {today_count}\n"
        f"📊 <b>Total DB Records:</b> {total_count}\n\n"

        f"🕹️ <b>System Mode:</b> {mode_str}\n"
        f"🔌 <b>Relay States:</b>\n"
        f"  ├ Pompa Irigasi: {r.get('irigasi', 'off')}\n"
        f"  ├ Kuras Tandon Seq: {r.get('kuras_tandon', 'off')}\n"
        f"  ├ Kuras Buang Seq: {r.get('kuras', 'off')}\n"
        f"  ├ Pengaduk: {r.get('pengaduk', 'off')}\n"
        f"  ├ Valve Tandon (Direct): {r.get('valve_tandon', 'off')}\n"
        f"  └ Pompa Kuras (Direct): {r.get('pompa_kuras', 'off')}\n"
    )

@require_auth
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = await asyncio.to_thread(build_status_message_text)
    await update.message.reply_text(
        msg_text,
        reply_markup=build_status_keyboard(),
        parse_mode=ParseMode.HTML
    )


# NOTE: ALL DATA FORMATTING & COMMAND (Upgraded with Structured Visual Sections)
def build_formatted_data_block(clean: dict) -> str:
    sections = []
    
    # 1. Water Quality Header
    if "water_quality" in clean:
        sections.append(f"🌱 <b>WATER QUALITY:</b> {describe_water_quality(clean['water_quality'])}\n")

    # 2. Nutrients & Physical Sensors
    phys_lines = ["🧪 <b>NUTRIENTS &amp; WATER PARAMETERS</b>"]
    for k in ["tds1", "tds2", "delta_tds", "turbidity", "flowrate"]:
        if k in clean:
            phys_lines.append(f"• {format_sensor_value(k, clean[k])}")
    sections.append("\n".join(phys_lines))

    # 3. Water Reservoir Levels with Visual Progress Bars
    level_lines = ["\n🌊 <b>WATER RESERVOIR LEVELS</b>"]
    tank_names = {
        "level1": "Tank 1 (Main Tandon)",
        "level2": "Tank 2 (Mixing/Feed)",
        "level3": "Tank 3 (Nutrient A/B)",
        "level4": "Tank 4 (Drain/Return)",
    }
    has_levels = False
    for k in ["level1", "level2", "level3", "level4"]:
        if k in clean:
            has_levels = True
            raw = clean[k]
            cat, emoji = describe_level_category(raw)
            bar = render_progress_bar(raw, length=10)
            arrow = get_trend_arrow(k)
            arrow_str = f" {arrow}" if arrow else ""
            tname = tank_names.get(k, k.upper())
            level_lines.append(f"• <b>{tname}</b>:\n  <code>{bar}</code> <b>{raw}%</b> ({cat}) {emoji}{arrow_str}")
    if has_levels:
        sections.append("\n".join(level_lines))

    # 4. Unmapped extra keys
    known = {"water_quality", "tds1", "tds2", "delta_tds", "turbidity", "flowrate", "level1", "level2", "level3", "level4"}
    unmapped = [f"• <b>{k}</b>: {v}" for k, v in clean.items() if k not in known]
    if unmapped:
        sections.append("\n📦 <b>OTHER METRICS</b>\n" + "\n".join(unmapped))

    return "\n\n".join(sections)


def build_all_data_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh:all_data"),
            InlineKeyboardButton("🌊 Tanks Detail", callback_data="refresh:tanks"),
        ]
    ])

@require_auth
async def cmd_all_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not latest_data:
        await update.message.reply_text("⚠️ No sensor data available yet.")
        return

    if mqtt_client:
        mqtt_client.publish(MQTT_TOPIC_REQUEST_DATA, "1")

    await asyncio.sleep(2.0)

    clean = _sanitize_latest()
    lines = build_formatted_data_block(clean)
    badge = get_freshness_badge()
    msg   = f"<b>📊 LATEST SENSOR DASHBOARD</b> ({badge})\n⏱️ <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n{lines}"
    await update.message.reply_text(
        msg,
        reply_markup=build_all_data_keyboard(),
        parse_mode=ParseMode.HTML
    )


# NOTE: TANKS VISUAL COMPARISON COMMAND (New feature)
def build_tanks_overview_text() -> str:
    clean = _sanitize_latest()
    tank_configs = [
        ("level1", "Tank 1 (Main Tandon)"),
        ("level2", "Tank 2 (Mixing Basin)"),
        ("level3", "Tank 3 (Nutrient Buffer)"),
        ("level4", "Tank 4 (Drain/Overflow)"),
    ]
    lines = [
        "<b>🌊 WATER TANKS ASCII OVERVIEW</b>",
        f"Freshness: {get_freshness_badge()} | ⏱️ <code>{time.strftime('%H:%M:%S')}</code>\n",
    ]
    for key, name in tank_configs:
        raw_val = clean.get(key, "0")
        cat, emoji = describe_level_category(raw_val)
        bar = render_progress_bar(raw_val, length=12)
        arrow = get_trend_arrow(key)
        arrow_str = f" {arrow}" if arrow else ""
        spark = render_sparkline(key)
        spark_str = f"  Trend: <code>{spark}</code>" if spark else ""
        lines.append(f"<b>{name}</b> {emoji}")
        lines.append(f"<code>{bar}</code> <b>{raw_val}%</b> — <i>{cat}</i>{arrow_str}{spark_str}\n")

    return "\n".join(lines)

@require_auth
async def cmd_tanks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = build_tanks_overview_text()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Tanks", callback_data="refresh:tanks")]])
    await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# NOTE: RELAY PANEL & KEYBOARD
def build_relay_panel_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, label in RELAY_DISPLAY_NAMES.items():
        is_on = "on" in str(system_state["relays"].get(key, "")).lower()
        btn_on_text = f"🟢 {label} ON" if is_on else f"{label} ON"
        btn_off_text = f"🔴 {label} OFF" if not is_on else f"{label} OFF"
        rows.append([
            InlineKeyboardButton(btn_on_text, callback_data=f"relay:{key}:on"),
            InlineKeyboardButton(btn_off_text, callback_data=f"relay:{key}:off"),
        ])
    rows.append([InlineKeyboardButton("🔄 Refresh Panel", callback_data="relay:refresh")])
    return InlineKeyboardMarkup(rows)

@require_auth
async def cmd_relaypanel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode_str = system_state["mode"].upper()
    text = (
        f"<b>🎛️ RELAY CONTROL PANEL</b>\n"
        f"System Mode: <b>{mode_str}</b>\n\n"
        f"Tap a button below to toggle relay state:"
    )
    await update.message.reply_text(
        text,
        reply_markup=build_relay_panel_keyboard(),
        parse_mode=ParseMode.HTML
    )


# NOTE: CALLBACK HANDLERS FOR INLINE KEYBOARDS
async def callback_relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not is_authed(uid):
        await query.answer("🔒 Session expired. Please login again with /login", show_alert=True)
        return

    authed_sessions[uid] = time.time()
    await query.answer()

    data = query.data.split(":")
    if len(data) == 3:
        target, state = data[1], data[2]
        if system_state.get("mode", "").lower() == "auto":
            await query.answer("⚠️ System is in AUTO mode! Switch to /mode manual first.", show_alert=True)
            return
        topic_map = {
            "irigasi": MQTT_TOPIC_RELAY_IRIGASI,
            "kuras_tandon": MQTT_TOPIC_RELAY_KURAS_TANDON,
            "kuras": MQTT_TOPIC_RELAY_KURAS,
            "pengaduk": MQTT_TOPIC_RELAY_PENGADUK,
            "valve_tandon": MQTT_TOPIC_RELAY_VALVE_TANDON,
            "pompa_kuras": MQTT_TOPIC_RELAY_POMPA_KURAS,
        }
        if target in topic_map and state in ["on", "off"]:
            val = "1" if state == "on" else "0"
            if mqtt_client:
                mqtt_client.publish(topic_map[target], val)
                system_state["relays"][target] = "ON 🟢" if state == "on" else "OFF 🔴"
            else:
                logger.warning(f"MQTT client not connected, could not toggle relay '{target}'")
            await asyncio.sleep(0.5)

    mode_str = system_state["mode"].upper()
    text = (
        f"<b>🎛️ RELAY CONTROL PANEL</b>\n"
        f"System Mode: <b>{mode_str}</b>\n\n"
        f"Tap a button below to toggle relay state:"
    )
    try:
        await query.edit_message_text(
            text,
            reply_markup=build_relay_panel_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise

async def callback_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not is_authed(uid):
        await query.answer("🔒 Session expired. Please login again with /login", show_alert=True)
        return

    authed_sessions[uid] = time.time()
    await query.answer("🔄 Refreshing...")

    target = query.data.split(":")[1]
    try:
        if target == "all_data":
            if mqtt_client:
                mqtt_client.publish(MQTT_TOPIC_REQUEST_DATA, "1")
            await asyncio.sleep(2.0)
            clean = _sanitize_latest()
            lines = build_formatted_data_block(clean)
            badge = get_freshness_badge()
            msg   = f"<b>📊 LATEST SENSOR DASHBOARD</b> ({badge})\n⏱️ <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n{lines}"
            await query.edit_message_text(
                msg,
                reply_markup=build_all_data_keyboard(),
                parse_mode=ParseMode.HTML
            )
        elif target == "status":
            msg_text = await asyncio.to_thread(build_status_message_text)
            await query.edit_message_text(
                msg_text,
                reply_markup=build_status_keyboard(),
                parse_mode=ParseMode.HTML
            )
        elif target == "tanks":
            text = build_tanks_overview_text()
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Tanks", callback_data="refresh:tanks")]])
            await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


async def callback_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if not is_authed(uid):
        await query.answer("🔒 Session expired. Please login again with /login", show_alert=True)
        return

    authed_sessions[uid] = time.time()
    await query.answer()

    parts = query.data.split(":")
    action = parts[1]

    if action == "cancel":
        logger.info(f"User {uid} cancelled CSV export")
        await query.edit_message_text("❌ Export cancelled.")
        return

    if action == "confirm" and len(parts) >= 4:
        table_key = parts[2]
        days = int(parts[3]) if parts[3] != "all" else None

        await query.edit_message_text(
            f"⏳ Exporting <b>{table_key}</b>, please wait...", parse_mode=ParseMode.HTML
        )

        filepath, row_count = await asyncio.to_thread(export_table_to_csv, table_key, days)

        if filepath is None or row_count == 0:
            msg = "❌ Export failed. Check log for details." if filepath is None else "⚠️ Export completed but table/range had 0 rows."
            await query.edit_message_text(msg)
            return

        try:
            with open(filepath, "rb") as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename=os.path.basename(filepath),
                    caption=f"📦 {table_key} export — {row_count} rows" + (f" (last {days}d)" if days else " (all)"),
                    write_timeout=120,
                    read_timeout=120,
                )
            logger.info(f"Sent export file to user {uid}: {filepath} ({row_count} rows)")
            await query.edit_message_text(
                f"✅ Export completed! Sent <b>{row_count} rows</b> for <code>{table_key}</code>.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send export file to Telegram: {e}", exc_info=True)
            await query.edit_message_text("❌ File was exported but failed to send via Telegram. Check log.")
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up temp export file: {filepath}")
                except Exception as clean_err:
                    logger.warning(f"Failed to remove temp file {filepath}: {clean_err}")


# NOTE: SINGLE SENSOR ENHANCED STAT CARDS (ASCII Rich View)
_SENSOR_KEY_MAP = {
    "tds1":          "tds1",
    "tds2":          "tds2",
    "delta_tds":     "delta_tds",
    "turbidity":     "turbidity",
    "flowrate":      "flowrate",
    "level1":        "level1",
    "level2":        "level2",
    "level3":        "level3",
    "level4":        "level4",
    "water_quality": "water_quality",
}

# ponytail: dynamic rich ASCII detail card per sensor
def _make_sensor_handler(data_key: str):
    @require_auth
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        clean = _sanitize_latest()
        if data_key not in clean:
            await update.message.reply_text("⚠️ Data not available yet.")
            return

        raw_val = clean[data_key]
        label, unit, kind = SENSOR_DISPLAY_META.get(data_key, (data_key.upper(), "", None))
        stats = get_sensor_stats(data_key)
        arrow = get_trend_arrow(data_key)
        arrow_str = f" {arrow}" if arrow else ""

        # Specialized presentation per sensor type
        if kind == "quality":
            desc = describe_water_quality(raw_val)
            msg = (
                f"🌱 <b>WATER QUALITY STATUS</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Classification:</b> {desc}\n"
                f"• <b>Status code:</b> <code>{raw_val}</code>\n"
                f"• <b>Evaluation:</b> Automated heuristic check\n"
                f"• <b>Freshness:</b> {get_freshness_badge()}"
            )
        elif kind == "level":
            cat, emoji = describe_level_category(raw_val)
            bar = render_progress_bar(raw_val, length=12)
            spark = render_sparkline(data_key)
            spark_line = f"\n• <b>Recent Trend:</b> <code>{spark}</code>{arrow_str}" if spark else ""
            stat_line = ""
            if stats and stats["count"] >= 2:
                stat_line = f"\n• <b>Min / Max / Avg:</b> {stats['min']:.0f}% / {stats['max']:.0f}% / {stats['avg']:.1f}%"
            msg = (
                f"🌊 <b>{label.upper()}</b> {emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Level Gauge:</b> <code>{bar}</code> <b>{raw_val}%</b>\n"
                f"• <b>Category:</b> {cat}{arrow_str}{spark_line}{stat_line}\n"
                f"• <b>Freshness:</b> {get_freshness_badge()}"
            )
        elif data_key == "turbidity":
            try:
                t_val = float(raw_val)
                gauge = render_gauge_bar(t_val, min_val=0, max_val=100, length=12)
                health = "🟢 Clear (Normal)" if t_val <= 50 else "🟤 Cloudy / High Turbidity ⚠️"
            except (ValueError, TypeError):
                gauge, health = "[────────────]", "Unknown"
            spark = render_sparkline(data_key)
            spark_line = f"\n• <b>Recent Trend:</b> <code>{spark}</code>{arrow_str}" if spark else ""
            stat_line = ""
            if stats and stats["count"] >= 2:
                stat_line = f"\n• <b>Min / Max / Avg:</b> {stats['min']:.1f} / {stats['max']:.1f} / {stats['avg']:.1f} NTU"
            msg = (
                f"🧪 <b>TURBIDITY SENSOR</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Reading:</b> <b>{raw_val} NTU</b>{arrow_str}\n"
                f"• <b>Range [0-100]:</b> <code>{gauge}</code>\n"
                f"• <b>Condition:</b> {health}{spark_line}{stat_line}\n"
                f"• <b>Freshness:</b> {get_freshness_badge()}"
            )
        elif data_key in ["tds1", "tds2"]:
            try:
                tds_val = float(raw_val)
                gauge = render_gauge_bar(tds_val, min_val=0, max_val=2000, length=12)
                health = "🟢 Optimal Hydroponics" if 500 <= tds_val <= 1400 else "⚠️ Check Nutrition"
            except (ValueError, TypeError):
                gauge, health = "[────────────]", "Unknown"
            spark = render_sparkline(data_key)
            spark_line = f"\n• <b>Recent Trend:</b> <code>{spark}</code>{arrow_str}" if spark else ""
            stat_line = ""
            if stats and stats["count"] >= 2:
                stat_line = f"\n• <b>Min / Max / Avg:</b> {stats['min']:.1f} / {stats['max']:.1f} / {stats['avg']:.1f} ppm"
            msg = (
                f"🧪 <b>{label.upper()}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Reading:</b> <b>{raw_val} ppm</b>{arrow_str}\n"
                f"• <b>Range [0-2000]:</b> <code>{gauge}</code>\n"
                f"• <b>Target Health:</b> {health}{spark_line}{stat_line}\n"
                f"• <b>Freshness:</b> {get_freshness_badge()}"
            )
        else:
            unit_suffix = f" {unit}" if unit else ""
            spark = render_sparkline(data_key)
            spark_line = f"\n• <b>Recent Trend:</b> <code>{spark}</code>{arrow_str}" if spark else ""
            stat_line = ""
            if stats and stats["count"] >= 2:
                stat_line = f"\n• <b>Min / Max / Avg:</b> {stats['min']:.1f} / {stats['max']:.1f} / {stats['avg']:.1f}{unit_suffix}"
            msg = (
                f"📊 <b>{label.upper()}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Reading:</b> <b>{raw_val}{unit_suffix}</b>{arrow_str}{spark_line}{stat_line}\n"
                f"• <b>Freshness:</b> {get_freshness_badge()}"
            )

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    return handler


# NOTE: TDS1 CALIBRATION
@require_auth
async def cmd_cal_tds1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage:\n"
            "<code>/cal_tds1 start</code> — start multi-point calibration\n"
            "<code>/cal_tds1 set [value]</code> — record multi-point step\n"
            "<code>/cal_tds1 single [value]</code> — single-point calibration (e.g. /cal_tds1 single 800)",
            parse_mode=ParseMode.HTML
        )
        return

    if not mqtt_client:
        await update.message.reply_text("Command failed: MQTT client not initialized.")
        return

    arg = context.args[0].lower()

    if arg == "start":
        mqtt_client.publish(MQTT_TOPIC_CAL_TDS1_MULTI_START, "1")
        push_alert("TDS1 Multi-Point Calibration Started", level="system")
        await update.message.reply_text(
            "🔧 <b>TDS1 Multi-Point Calibration Started</b>\n"
            "Place probe in solution, wait 30s, then send: <code>/cal_tds1 set [ppm]</code>",
            parse_mode=ParseMode.HTML
        )
    elif arg == "set":
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: <code>/cal_tds1 set [ppm_value]</code>", parse_mode=ParseMode.HTML)
            return
        try:
            val = float(context.args[1])
            if not (0 <= val <= 5000):
                await update.message.reply_text("❌ Value out of range. TDS must be between 0 and 5000 ppm.")
                return
            mqtt_client.publish(MQTT_TOPIC_CAL_TDS1_MULTI_SET, str(val))
            push_alert(f"TDS1 calibration point recorded: {val} ppm", level="system")
            await update.message.reply_text(f"✅ TDS1 multi-point step sent: <b>{val} ppm</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Value must be a valid number.")
    elif arg == "single":
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: <code>/cal_tds1 single [ppm_value]</code>", parse_mode=ParseMode.HTML)
            return
        try:
            val = float(context.args[1])
            if not (0 <= val <= 5000):
                await update.message.reply_text("❌ Value out of range. TDS must be between 0 and 5000 ppm.")
                return
            res = mqtt_client.publish(MQTT_TOPIC_CAL_TDS1_SINGLE, str(val))
            if res.rc == mqtt.MQTT_ERR_SUCCESS:
                push_alert(f"TDS1 Single-Point Calibration sent: {val} ppm", level="system")
                await update.message.reply_text(
                    f"✅ <b>TDS1 Single-Point Calibration Sent:</b> {val} ppm\n"
                    f"<i>Sampling readings on ESP32... check status updates shortly.</i>",
                    parse_mode=ParseMode.HTML
                )
            else:
                logger.error(f"MQTT Publish Failed for TDS1 single-point cal (code {res.rc})")
                await update.message.reply_text(f"❌ MQTT Publish Failed (code {res.rc}). Check broker connection.")
        except ValueError:
            await update.message.reply_text("❌ Value must be a valid number.")
    else:
        await update.message.reply_text("❌ Unknown subcommand. Use <code>start</code>, <code>set</code>, or <code>single</code>.", parse_mode=ParseMode.HTML)


@require_auth
async def cmd_cal_tds2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage:\n"
            "<code>/cal_tds2 start</code> — start multi-point calibration\n"
            "<code>/cal_tds2 set [value]</code> — record multi-point step\n"
            "<code>/cal_tds2 single [value]</code> — single-point calibration (e.g. /cal_tds2 single 800)",
            parse_mode=ParseMode.HTML
        )
        return

    if not mqtt_client:
        await update.message.reply_text("Command failed: MQTT client not initialized.")
        return

    arg = context.args[0].lower()

    if arg == "start":
        mqtt_client.publish(MQTT_TOPIC_CAL_TDS2_MULTI_START, "1")
        push_alert("TDS2 Multi-Point Calibration Started", level="system")
        await update.message.reply_text(
            "🔧 <b>TDS2 Multi-Point Calibration Started</b>\n"
            "Place probe in solution, wait 30s, then send: <code>/cal_tds2 set [ppm]</code>",
            parse_mode=ParseMode.HTML
        )
    elif arg == "set":
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: <code>/cal_tds2 set [ppm_value]</code>", parse_mode=ParseMode.HTML)
            return
        try:
            val = float(context.args[1])
            if not (0 <= val <= 5000):
                await update.message.reply_text("❌ Value out of range. TDS must be between 0 and 5000 ppm.")
                return
            mqtt_client.publish(MQTT_TOPIC_CAL_TDS2_MULTI_SET, str(val))
            push_alert(f"TDS2 calibration point recorded: {val} ppm", level="system")
            await update.message.reply_text(f"✅ TDS2 multi-point step sent: <b>{val} ppm</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await update.message.reply_text("❌ Value must be a valid number.")
    elif arg == "single":
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: <code>/cal_tds2 single [ppm_value]</code>", parse_mode=ParseMode.HTML)
            return
        try:
            val = float(context.args[1])
            if not (0 <= val <= 5000):
                await update.message.reply_text("❌ Value out of range. TDS must be between 0 and 5000 ppm.")
                return
            res = mqtt_client.publish(MQTT_TOPIC_CAL_TDS2_SINGLE, str(val))
            if res.rc == mqtt.MQTT_ERR_SUCCESS:
                push_alert(f"TDS2 Single-Point Calibration sent: {val} ppm", level="system")
                await update.message.reply_text(
                    f"✅ <b>TDS2 Single-Point Calibration Sent:</b> {val} ppm\n"
                    f"<i>Sampling readings on ESP32... check status updates shortly.</i>",
                    parse_mode=ParseMode.HTML
                )
            else:
                logger.error(f"MQTT Publish Failed for TDS2 single-point cal (code {res.rc})")
                await update.message.reply_text(f"❌ MQTT Publish Failed (code {res.rc}). Check broker connection.")
        except ValueError:
            await update.message.reply_text("❌ Value must be a valid number.")
    else:
        await update.message.reply_text("❌ Unknown subcommand. Use <code>start</code>, <code>set</code>, or <code>single</code>.", parse_mode=ParseMode.HTML)


# NOTE: TURBIDITY CALIBRATION
@require_auth
async def cmd_calturb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global turbidity_cal_active
    if not mqtt_client:
        await update.message.reply_text("❌ MQTT not connected.")
        return
    turbidity_cal_active = True
    mqtt_client.publish(MQTT_TOPIC_CAL_TURB_START, "1")
    push_alert("Turbidity Calibration Started", level="system")
    await update.message.reply_text(
        "🔧 <b>Turbidity Calibration Started</b>\n\n"
        "Dip the sensor into the <b>0 NTU</b> solution (distilled water).\n"
        "Wait 30 seconds until the voltage stabilises.\n\n"
        "Monitor the live voltage here, then send /next when stable.",
        parse_mode=ParseMode.HTML
    )


@require_auth
async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not mqtt_client:
        await update.message.reply_text("❌ MQTT not connected.")
        return
    if not turbidity_cal_active:
        await update.message.reply_text("⚠️ No turbidity calibration in progress. Start first with <code>/calturb</code>", parse_mode=ParseMode.HTML)
        return
    mqtt_client.publish(MQTT_TOPIC_CAL_TURB_NEXT, "1")
    await update.message.reply_text("📊 Recording calibration point...")


@require_auth
async def cmd_cancelcal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global turbidity_cal_active
    if not mqtt_client:
        await update.message.reply_text("❌ MQTT not connected.")
        return
    turbidity_cal_active = False
    mqtt_client.publish(MQTT_TOPIC_CAL_TURB_CANCEL, "1")
    push_alert("Turbidity calibration cancelled", level="system")
    await update.message.reply_text("⚠️ Turbidity calibration cancelled.")


# NOTE: MANUAL/OVERRIDE SYSTEM
@require_auth
async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ["auto", "manual"]:
        await update.message.reply_text("❌ Usage: /mode [auto | manual]")
        return
    
    mode = context.args[0].lower()
    
    if mqtt_client:
        mqtt_client.publish(MQTT_TOPIC_MODE, mode)
        push_alert(f"System mode set to <b>{mode.upper()}</b>", level="system")
        await update.message.reply_text(
            f"⚙️ System mode successfully set to: <b>{mode.upper()}</b>", 
            parse_mode=ParseMode.HTML
        )
    else:
        logger.warning("MQTT not connected, cannot change mode")
        await update.message.reply_text("❌ MQTT not connected. Cannot change mode.")

@require_auth
async def cmd_relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
         await update.message.reply_text("❌ Usage: /relay [name] [on | off]\nNames: irigasi, kuras_tandon, kuras, pengaduk, valve_tandon, pompa_kuras")
         return
         
    target = context.args[0].lower()
    state = context.args[1].lower()
    
    if state not in ["on", "off"]:
        await update.message.reply_text("❌ State must be exactly 'on' or 'off'.")
        return
        
    val = "1" if state == "on" else "0"

    topic_map = {
        "irigasi": MQTT_TOPIC_RELAY_IRIGASI,
        "kuras_tandon": MQTT_TOPIC_RELAY_KURAS_TANDON,
        "kuras": MQTT_TOPIC_RELAY_KURAS,
        "pengaduk": MQTT_TOPIC_RELAY_PENGADUK,
        "valve_tandon": MQTT_TOPIC_RELAY_VALVE_TANDON,
        "pompa_kuras": MQTT_TOPIC_RELAY_POMPA_KURAS,
    }
    
    if target not in topic_map:
         await update.message.reply_text("❌ Invalid relay name.\nUse: irigasi, kuras_tandon, kuras, pengaduk, valve_tandon, or pompa_kuras.")
         return

    if system_state.get("mode", "").lower() == "auto":
        await update.message.reply_text(
            "⚠️ <b>Cannot control relay in AUTO mode.</b>\nPlease switch mode first using: <code>/mode manual</code>",
            parse_mode=ParseMode.HTML,
        )
        return
         
    if mqtt_client:
         mqtt_client.publish(topic_map[target], val)
         logger.info(f"Command /relay executed: {target} -> {state}")
         await update.message.reply_text(
             f"🔌 Relay <b>{target}</b> turned <b>{state.upper()}</b>", 
             parse_mode=ParseMode.HTML
         )
    else:
         logger.warning(f"MQTT not connected, cannot command relay {target}")
         await update.message.reply_text("❌ MQTT not connected. Cannot trigger relay.")

@require_auth
async def cmd_relaylog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /relaylog [name] [count]\n"
            "Names: irigasi, kuras_tandon, kuras, pengaduk, valve_tandon, pompa_kuras\n"
            "e.g. /relaylog irigasi 10"
        )
        return

    relay_name = context.args[0].lower()
    if relay_name not in RELAY_DISPLAY_NAMES:
        await update.message.reply_text("❌ Invalid relay name.\nUse: irigasi, kuras_tandon, kuras, pengaduk, valve_tandon, or pompa_kuras.")
        return

    limit = 10
    if len(context.args) > 1:
        try:
            limit = max(1, min(30, int(context.args[1])))
        except ValueError:
            pass

    rows = await asyncio.to_thread(get_relay_logs, relay_name, limit)
    if not rows:
        await update.message.reply_text("⚠️ No log entries found for this relay yet.")
        return

    label = RELAY_DISPLAY_NAMES[relay_name]
    lines = [f"<b>📜 RELAY LOG — {label}</b>\n"]
    for state, event_time, duration, mode in rows:
        icon = "🟢" if state == "ON" else "🔴"
        ts = event_time.strftime("%Y-%m-%d %H:%M:%S")
        mode_tag = f" [{mode}]" if mode else ""
        if state == "OFF" and duration is not None:
            lines.append(f"{icon} {ts} — OFF (was ON for {format_duration(duration)}){mode_tag}")
        else:
            lines.append(f"{icon} {ts} — {state}{mode_tag}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@require_auth
async def cmd_relaystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = [a.lower() for a in context.args]

    period = "week" if "week" in args else "today"
    relay_args = [a for a in args if a != "week"]

    if relay_args:
        relay_name = relay_args[0]
        if relay_name not in RELAY_DISPLAY_NAMES:
            await update.message.reply_text("❌ Invalid relay name.\nUse: irigasi, kuras_tandon, kuras, pengaduk, valve_tandon, or pompa_kuras.")
            return
        names_to_show = [relay_name]
    else:
        names_to_show = list(RELAY_DISPLAY_NAMES.keys())

    period_label = "THIS WEEK" if period == "week" else "TODAY"
    lines = [f"<b>📊 RELAY ON-TIME — {period_label}</b>\n"]
    for name in names_to_show:
        seconds = await asyncio.to_thread(get_relay_on_seconds, name, period)
        is_running = "  ⏳ running now" if name in relay_last_on else ""
        lines.append(f"• <b>{RELAY_DISPLAY_NAMES[name]}</b>: {format_duration(seconds)}{is_running}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

# NOTE: DB STATUS / RECONNECT COMMAND
@require_auth
async def cmd_dbstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db_pool is not None:
        row = await asyncio.to_thread(db_fetch_one, "SELECT 1")
        if row:
            await update.message.reply_text(
                f"✅ <b>Database OK</b>\n"
                f"Host: {DB_HOST}:{DB_PORT}\n"
                f"DB: {DB_NAME}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                "⚠️ DB pool exists but ping failed. Try /dbstatus reconnect"
            )
        return

    if context.args and context.args[0].lower() == "reconnect":
        await update.message.reply_text("🔄 Attempting DB reconnect...")
        await asyncio.to_thread(init_db_pool)
        if db_pool is not None:
            await update.message.reply_text("✅ Reconnected successfully!")
        else:
            await update.message.reply_text(
                f"❌ Reconnect failed:\n<code>{_db_init_error}</code>",
                parse_mode=ParseMode.HTML,
            )
    else:
        await update.message.reply_text(
            f"❌ <b>Database not connected</b>\n"
            f"Error: <code>{_db_init_error or 'unknown'}</code>\n\n"
            f"Run /dbstatus reconnect to retry.",
            parse_mode=ParseMode.HTML,
        )


@require_auth
async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = [a.lower() for a in context.args]
    logger.debug(f"/export invoked by user_id={uid} args={context.args}")

    if not args or args[0] == "list":
        available = "\n".join(f"• <code>{k}</code>" for k in EXPORTABLE_TABLES)
        await update.message.reply_text(
            "❌ Usage: /export [table] [days]\n\n"
            "<b>Available tables:</b>\n" + available + "\n\n"
            "e.g. <code>/export sensor_data</code> (all rows)\n"
            "e.g. <code>/export sensor_data 7</code> (last 7 days)",
            parse_mode=ParseMode.HTML,
        )
        return

    table_key = args[0]
    if table_key not in EXPORTABLE_TABLES:
        logger.warning(f"User {uid} requested unknown export table '{table_key}'")
        await update.message.reply_text(
            f"❌ Unknown table '{table_key}'. Use /export list to see options."
        )
        return

    days = None
    if len(args) > 1:
        try:
            days = max(1, int(args[1]))
        except ValueError:
            logger.warning(f"User {uid} passed non-integer days value: '{args[1]}'")
            await update.message.reply_text("❌ Days must be a whole number, e.g. /export sensor_data 7")
            return

    row_count = await asyncio.to_thread(get_export_count, table_key, days)
    range_str = f"last {days} days" if days else "all time"

    confirm_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Lanjutkan", callback_data=f"export:confirm:{table_key}:{days or 'all'}"),
            InlineKeyboardButton("❌ Batal", callback_data="export:cancel"),
        ]
    ])

    preview_msg = (
        f"📦 <b>EXPORT PREVIEW</b>\n"
        f"Table: <code>{table_key}</code>\n"
        f"Time Range: <b>{range_str}</b>\n"
        f"Estimated Rows: <b>{row_count}</b>\n\n"
        f"Do you want to proceed with generating and downloading this CSV?"
    )

    await update.message.reply_text(
        preview_msg,
        reply_markup=confirm_kb,
        parse_mode=ParseMode.HTML
    )


# NOTE: SCHEDULED JOBS
async def job_auto_send_sensor(context: ContextTypes.DEFAULT_TYPE):
    if not latest_data:
        return
    clean = _sanitize_latest()
    lines = build_formatted_data_block(clean)
    badge = get_freshness_badge()
    msg   = (
        f"<b>⏰ SCHEDULED SENSOR UPDATE</b> ({badge})\n"
        f"⏱️ <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>\n\n{lines}"
    )
    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode=ParseMode.HTML
    )

async def job_forward_esp_alert(context: ContextTypes.DEFAULT_TYPE):
    global pending_alerts
    while pending_alerts:
        try:
            alert_msg = pending_alerts.pop(0)
        except IndexError:
            break
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"<b>SYSTEM ALERT</b>\n\n{alert_msg}",
            parse_mode=ParseMode.HTML
        )

async def job_forward_cal_status(context: ContextTypes.DEFAULT_TYPE):
    global pending_cal_status
    while pending_cal_status:
        try:
            status_msg = pending_cal_status.pop(0)
        except IndexError:
            break
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🔧 <b>SENSOR CALIBRATION STATUS</b>\n\n<code>{status_msg}</code>",
            parse_mode=ParseMode.HTML
        )


# NOTE: MQTT CALLBACKS
def on_connect(client, userdata, flags, rc):
    logger.info("✅ Connected to MQTT Broker")
    client.subscribe(MQTT_TOPIC)
    client.subscribe(MQTT_TOPIC_NOTIF)
    client.subscribe(MQTT_TOPIC_CAL_TURB_STATUS)
    client.subscribe(MQTT_TOPIC_MODE)
    client.subscribe(MQTT_TOPIC_RELAY_IRIGASI)
    client.subscribe(MQTT_TOPIC_RELAY_KURAS_TANDON)
    client.subscribe(MQTT_TOPIC_RELAY_KURAS)
    client.subscribe(MQTT_TOPIC_RELAY_PENGADUK)
    client.subscribe(MQTT_TOPIC_RELAY_VALVE_TANDON)
    client.subscribe(MQTT_TOPIC_RELAY_POMPA_KURAS)
    logger.info("Subscribed to MQTT sensor data, notifications, calibration status, mode, & relays")

def on_disconnect(client, userdata, rc):
    logger.warning(f"⚠️ MQTT DISCONNECTED (rc={rc})")

def on_message(client, userdata, msg):
    global last_mqtt_receive_unix
    try:
        payload = msg.payload.decode()
        if "nan" in payload.lower():
            payload = payload.replace("nan", "0.0")

        if msg.topic == MQTT_TOPIC_MODE:
            system_state["mode"] = payload.lower()
            push_alert(f"System mode synced via MQTT: <b>{payload.upper()}</b>", level="system")
            return
            
        topic_to_relay = {
            MQTT_TOPIC_RELAY_IRIGASI: "irigasi",
            MQTT_TOPIC_RELAY_KURAS_TANDON: "kuras_tandon",
            MQTT_TOPIC_RELAY_KURAS: "kuras",
            MQTT_TOPIC_RELAY_PENGADUK: "pengaduk",
            MQTT_TOPIC_RELAY_VALVE_TANDON: "valve_tandon",
            MQTT_TOPIC_RELAY_POMPA_KURAS: "pompa_kuras",
        }
        
        if msg.topic in topic_to_relay:
            relay_name = topic_to_relay[msg.topic]
            new_state = "ON" if payload == "1" else "OFF"
            system_state["relays"][relay_name] = "ON 🟢" if payload == "1" else "OFF 🔴"
            log_relay_event(relay_name, new_state)
            return

        if msg.topic == MQTT_TOPIC_CAL_TURB_STATUS:
            pending_cal_status.append(payload)
            logger.info(f"🔧 [CAL STATUS via turb-topic]: {payload}")
            return

        if msg.topic == MQTT_TOPIC_NOTIF:
            data = json.loads(payload)
            if "alert" in data:
                alert_text = str(data["alert"])
                level = data.get("level")
                if not level:
                    low_text = alert_text.lower()
                    if any(w in low_text for w in ["normal", "ok", "success", "info", "cleared"]):
                        level = "info"
                    else:
                        level = "warning"
                push_alert(alert_text, level=level)
                logger.info(f"🔔 [ESP32 ALERT]: {alert_text}")
            return

        elif msg.topic == MQTT_TOPIC:
            data = json.loads(payload)
            logger.debug(f"📥 [ESP32→BOT] Sensor payload received: {data}")
            for k, v in data.items():
                k_lower = k.lower()
                val_str = str(v)
                latest_data[k_lower] = val_str
                record_sensor_history(k_lower, val_str)
            last_mqtt_receive_unix = time.time()
    except Exception as e:
        logger.error(f"❌ MQTT message parsing error: {e}")


# NOTE: DEV MODE — simulated sensor data for testing without hardware
def _simulate_sensor_data():
    global last_mqtt_receive_unix
    while True:
        sim_payload = {
            "tds1":          str(round(random.uniform(700, 1100), 2)),
            "tds2":          str(round(random.uniform(700, 1100), 2)),
            "turbidity":     str(round(random.uniform(5, 45), 2)),
            "delta_tds":     str(round(random.uniform(0, 15), 2)),
            "water_quality": random.choice(["2", "2", "2", "0", "1", "3"]),
            "flowrate":      str(round(random.uniform(2, 12), 2)),
            "level1":        str(random.randint(60, 95)),
            "level2":        str(random.randint(40, 80)),
            "level3":        str(random.randint(20, 50)),
            "level4":        str(random.randint(10, 40)),
        }
        for k, v in sim_payload.items():
            latest_data[k] = v
            record_sensor_history(k, v)
        last_mqtt_receive_unix = time.time()
        logger.debug(f"🔧 [DEV] Simulated data: {latest_data}")
        time.sleep(5)


# NOTE: MAIN
def main():
    global mqtt_client
    init_db_pool()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # NOTE: Auth commands
    app.add_handler(CommandHandler("login",      cmd_login))
    app.add_handler(CommandHandler("logout",     cmd_logout))
    
    # NOTE: Protected commands
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("status",     cmd_status))
    app.add_handler(CommandHandler("all_data",   cmd_all_data))
    app.add_handler(CommandHandler("tanks",      cmd_tanks))
    app.add_handler(CommandHandler("relaypanel", cmd_relaypanel))
    app.add_handler(CommandHandler("cal_tds1",   cmd_cal_tds1))
    app.add_handler(CommandHandler("cal_tds2",   cmd_cal_tds2))
    app.add_handler(CommandHandler("calturb",    cmd_calturb))
    app.add_handler(CommandHandler("next",       cmd_next))
    app.add_handler(CommandHandler("cancelcal",  cmd_cancelcal))
    app.add_handler(CommandHandler("mode",       cmd_mode))
    app.add_handler(CommandHandler("relay",      cmd_relay))
    app.add_handler(CommandHandler("relaylog",   cmd_relaylog))
    app.add_handler(CommandHandler("relaystats", cmd_relaystats))
    app.add_handler(CommandHandler("export",     cmd_export))
    app.add_handler(CommandHandler("dbstatus",   cmd_dbstatus))

    # NOTE: Callback query handlers
    app.add_handler(CallbackQueryHandler(callback_relay,   pattern=r"^relay:"))
    app.add_handler(CallbackQueryHandler(callback_refresh, pattern=r"^refresh:"))
    app.add_handler(CallbackQueryHandler(callback_export,  pattern=r"^export:"))

    for cmd_name, sensor_key in _SENSOR_KEY_MAP.items():
        app.add_handler(CommandHandler(cmd_name, _make_sensor_handler(sensor_key)))

    job_queue: JobQueue = app.job_queue
    job_queue.run_repeating(job_auto_send_sensor,   interval=300, first=10)
    job_queue.run_repeating(job_forward_esp_alert,  interval=5,   first=5)
    job_queue.run_repeating(job_forward_cal_status, interval=1,   first=1)

    dev_mode = False
    try:
        # paho-mqtt 2.x requires an explicit callback API version.
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USERNAME:
            mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

        mqtt_thread = threading.Thread(target=mqtt_client.loop_forever, daemon=True)
        mqtt_thread.start()

        logger.info("✅ MQTT connected — running in production mode")
    except Exception as e:
        if not _env_bool("ALLOW_DEV_MODE", False):
            logger.error(f"❌ MQTT unavailable ({e}) and ALLOW_DEV_MODE is off — exiting")
            raise
        dev_mode = True
        logger.warning(f"⚠️ MQTT unavailable ({e}) — falling back to DEV MODE")
        sim_thread = threading.Thread(target=_simulate_sensor_data, daemon=True)
        sim_thread.start()

    # Startup notification
    async def post_init(app_: Application):
        mode = "DEV MODE 🔧" if dev_mode else "PRODUCTION ✅"
        await app_.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                f"✅ <b>LIVING LAB — SMART GREEN GARDEN BOT ONLINE (v9 ASCII Edition)</b>\n"
                f"Mode: {mode}\n"
                f"ASCII &amp; Sparkline visualizations active!"
            ),
            parse_mode=ParseMode.HTML,
        )

    app.post_init = post_init

    # Shutdown notification
    async def post_shutdown(app_: Application):
        await app_.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "🔴 <b>LIVING LAB — SMART GREEN GARDEN BOT OFFLINE (v9)</b>\n"
                "System has been shut down."
            ),
            parse_mode=ParseMode.HTML,
        )

    app.post_shutdown = post_shutdown

    logger.info("🤖 Bot starting polling loop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
