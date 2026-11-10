#TODO: LIBS
import paho.mqtt.client as mqtt
import mysql.connector
import json
from datetime import datetime
import time
import os
import logging
import threading
import firebase_admin
import gzip
import shutil
from firebase_admin import credentials, db
from logging.handlers import TimedRotatingFileHandler

last_save_time = 0
last_message_time = 0
_firebase_ready = False

#NOTE: CONFIG
# All values come from the environment (.env). NEVER hardcode secrets here.
def _env(name, default=None):
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# Load .env from the repo root when running outside systemd (local dev).
try:
    from dotenv import load_dotenv

    _REPO_ROOT = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass

MQTT_BROKER = _env("MQTT_HOST", "localhost")
MQTT_PORT = _env_int("MQTT_PORT", 1883)
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None
MQTT_TOPIC = f"{os.getenv('MQTT_TOPIC_PREFIX', 'smartgreengarden')}/sensor/data"

MYSQL_HOST = _env("DB_HOST", "localhost")
MYSQL_USER = _env("DB_USER")
MYSQL_PASSWORD = _env("DB_PASSWORD")
MYSQL_DATABASE = _env("DB_NAME")
MYSQL_TABLE = _env("DB_TABLE", "hydroponic_water_data_romy")

# Firebase Realtime Database (optional — the logger runs fine without it).
FIREBASE_CRED_PATH = os.getenv("FIREBASE_CRED_PATH", "")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")
RTDB_ROOT_PATH = os.getenv("FIREBASE_RTDB_ROOT", "Hydroponic_Data")

# Save at most one row per N seconds, regardless of publish rate.
SAVE_THROTTLE_SECONDS = _env_int("SAVE_THROTTLE_SECONDS", 60)

#NOTE: LOGGING SETUP
_HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = _env("LOG_DIR", os.path.join(_HERE, "logs"))
LOG_FILE = os.path.join(LOG_DIR, "garden.log")
os.makedirs(LOG_DIR, exist_ok=True)

# Watchdog: how long we tolerate no message before logging it as a possible
# missed/late send. Tune this to your normal publish interval.
EXPECTED_INTERVAL_SECONDS = _env_int("EXPECTED_INTERVAL_SECONDS", 300)  # 5 minutes
WATCHDOG_CHECK_EVERY = 60        # check every 1 minute
LOG_BACKUP_COUNT = _env_int("LOG_BACKUP_COUNT", 30)

def _gzip_and_remove_original(source, dest):
    with open(source, 'rb') as f_in, gzip.open(f"{dest}.gz", 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(source)

file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",              # rotate once every day at midnight
    interval=1,
    backupCount=LOG_BACKUP_COUNT, # auto-delete rotated logs beyond this count
    encoding="utf-8"
)
file_handler.suffix = "%Y-%m-%d_%H-%M-%S"       # rotated files look like garden.log.2026-07-08
file_handler.rotator = _gzip_and_remove_original

console_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
        # logging.FileHandler(LOG_FILE, encoding="utf-8"),
        # logging.StreamHandler()
)

logging.info(f"📝 Logging to file: {LOG_FILE} (rotates daily, gzip-compressed, keeping last {LOG_BACKUP_COUNT} days)")

#NOTE: DATABASE INIT
def setup_database():
    logging.info("⚙️ Checking MySQL database setup...")
    db_connection = None
    try:
        db_connection = mysql.connector.connect(
            host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE
        )
        cursor = db_connection.cursor()

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {MYSQL_TABLE} (
            id INT(11) AUTO_INCREMENT PRIMARY KEY,
            datetime DATETIME NOT NULL,
            tds1_ppm DECIMAL(10,2),
            tds2_ppm DECIMAL(10,2),
            delta_tds DECIMAL(5,2),
            turbidity DECIMAL(10,2),
            flow_rate DECIMAL(10,2),
            water_level_1_percent DECIMAL(5,2),
            water_level_1_status VARCHAR(10),
            water_level_2_percent DECIMAL(5,2),
            water_level_2_status VARCHAR(10),
            water_level_3_percent DECIMAL(5,2),
            water_level_3_status VARCHAR(10),
            water_level_4_percent DECIMAL(5,2),
            water_level_4_status VARCHAR(10),
            water_quality INT,
            uploaded_to_cloud TINYINT(1) DEFAULT 0
        )
        """
        cursor.execute(create_table_query)
        db_connection.commit()
        logging.info(f"🗄️ MySQL table '{MYSQL_TABLE}' is ready.")

    except mysql.connector.Error as err:
        logging.error(f"❌ Error setting up database: {err}")
        exit(1)
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()

def send_to_realtimedb_structured(data_dict, timestamp_obj):
    # Cloud upload is optional: if Firebase never initialised, skip quietly.
    if not _firebase_ready:
        return False, "Firebase not initialised"

    date_str = timestamp_obj.strftime('%Y-%m-%d')
    time_str = timestamp_obj.strftime('%H-%M')
    full_path = f"{RTDB_ROOT_PATH}/{date_str}/{time_str}"

    try:
        ref = db.reference(full_path)
        ref.set(data_dict)
        logging.info(f"☁️ Data successfully sent to RTDB at path: {full_path}")
        return True, None
    except Exception as e:
        logging.error(f"❌ Error sending to Realtime Database: {e} (path attempted: {full_path})")
        return False, str(e)

#NOTE: MQTT CALLBACKS
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info("✅ Successfully connected to Local MQTT Broker")
        client.subscribe(MQTT_TOPIC)
        logging.info(f"📥 Listening to topic: {MQTT_TOPIC}")
    else:
        logging.error(f"❌ Failed to connect to MQTT Broker, status code: {rc}")

def on_disconnect(client, userdata, disconnect_flags=None, reason_code=None, properties=None, *args):
    # paho-mqtt v2 callback signature can vary slightly; this handles common cases
    logging.warning(f"⚠️ MQTT disconnected from broker. reason_code={reason_code}. "
                     f"Data will NOT be received until reconnection succeeds.")

def on_message(client, userdata, msg):
    global last_save_time, last_message_time

    current_time = time.time()
    last_message_time = current_time  # mark that a message DID arrive, even if we throttle-skip it

    if (current_time - last_save_time) < SAVE_THROTTLE_SECONDS:
        logging.info(
            f"⏭️ Message received but skipped "
            f"(within {SAVE_THROTTLE_SECONDS}s throttle window)."
        )
        return

    last_save_time = current_time

    payload = msg.payload.decode()
    timestamp_lokal = datetime.now()
    logging.info(f"📩 [{timestamp_lokal.strftime('%Y-%m-%d %H:%M:%S')}] Message received and PROCESSING...")
    logging.info(f"   Payload: {payload}")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        logging.error(f"❌ Error processing JSON data: {e} | Raw payload: {payload}")
        return

    def get_level_category(percent):
        if percent <= 0: return "Empty"
        elif percent <= 25: return "Low"
        elif percent <= 50: return "Medium"
        elif percent <= 75: return "High"
        else: return "Full"

    def get_water_quality_label(prediction_int):
        labels = {
            0: "Cloudy:Nutrient",
            1: "Cloudy:Sediment",
            2: "Normal",
            3: "Nutrient Imbalance",
            4: "Level Low",
            -1: "Unknown Data"
        }
        return labels.get(prediction_int, "Unknown Data")

    raw_quality_int = int(data.get("water_quality", -1))

    # Firmware sends `flowrate`; some payloads used `flowRate`. Accept both.
    flow_value = data.get("flowrate", data.get("flowRate", 0.0))

    sensor_data = {
        'tds1_ppm': float(data.get("tds1", 0.0)),
        'tds2_ppm': float(data.get("tds2", 0.0)),
        'delta_tds': float(data.get("delta_tds", 0.0)),
        # Column is INT: store the code, not the label.
        'water_quality_code': raw_quality_int,
        'water_quality_label': get_water_quality_label(raw_quality_int),
        'turbidity': float(data.get("turbidity", 0.0)),
        'flow_rate': float(flow_value),
        'level1_percent': float(data.get("level1", 0.0)),
        'level2_percent': float(data.get("level2", 0.0)),
        'level3_percent': float(data.get("level3", 0.0)),
        'level4_percent': float(data.get("level4", 0.0)),
        'timestamp_iso': timestamp_lokal.isoformat()
    }
    sensor_data['level1_status'] = get_level_category(sensor_data['level1_percent'])
    sensor_data['level2_status'] = get_level_category(sensor_data['level2_percent'])
    sensor_data['level3_status'] = get_level_category(sensor_data['level3_percent'])
    sensor_data['level4_status'] = get_level_category(sensor_data['level4_percent'])

    cloud_success, cloud_error = send_to_realtimedb_structured(sensor_data, timestamp_lokal)
    if not cloud_success:
        logging.error(f"❌ Cloud upload FAILED for record at {timestamp_lokal.isoformat()}. Reason: {cloud_error}")

    db_connection = None
    try:
        db_connection = mysql.connector.connect(
            host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DATABASE
        )
        cursor = db_connection.cursor()

        #NOTE: INSERT
        query = f"""
        INSERT INTO {MYSQL_TABLE} (
            datetime, tds1_ppm, tds2_ppm, delta_tds, turbidity, flow_rate,
            water_level_1_percent, water_level_1_status, water_level_2_percent, water_level_2_status,
            water_level_3_percent, water_level_3_status, water_level_4_percent, water_level_4_status,
            water_quality, uploaded_to_cloud
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            timestamp_lokal,
            sensor_data['tds1_ppm'],
            sensor_data['tds2_ppm'],
            sensor_data['delta_tds'],
            sensor_data['turbidity'],
            sensor_data['flow_rate'],
            sensor_data['level1_percent'],
            sensor_data['level1_status'],
            sensor_data['level2_percent'],
            sensor_data['level2_status'],
            sensor_data['level3_percent'],
            sensor_data['level3_status'],
            sensor_data['level4_percent'],
            sensor_data['level4_status'],
            sensor_data['water_quality_code'],
            1 if cloud_success else 0
        )
        cursor.execute(query, values)
        db_connection.commit()
        logging.info("🗄️ Data successfully saved to MySQL.")

    except mysql.connector.Error as err:
        logging.error(f"❌ Error saving to MySQL: {err} | Data attempted: {sensor_data}")
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()

#NOTE: WATCHDOG (detects late/missing data so you have proof of gaps)
def data_watchdog():
    global last_message_time
    while True:
        time.sleep(WATCHDOG_CHECK_EVERY)
        if last_message_time == 0:
            continue  # no message received yet since startup
        gap = time.time() - last_message_time
        if gap > EXPECTED_INTERVAL_SECONDS:
            logging.warning(
                f"⏰ No MQTT message received for {int(gap)}s "
                f"(expected every ~{EXPECTED_INTERVAL_SECONDS}s). "
                f"Possible sensor, network, or broker issue on the sending side."
            )

#NOTE: MAIN
if __name__ == "__main__":
    setup_database()

    try:
        if not FIREBASE_CRED_PATH:
            raise RuntimeError("FIREBASE_CRED_PATH not set — cloud upload disabled")

        if not os.path.exists(FIREBASE_CRED_PATH):
            raise FileNotFoundError(f"Firebase credential file not found at: {FIREBASE_CRED_PATH}")

        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DATABASE_URL
        })
        _firebase_ready = True
        logging.info("🔥 Successfully connected to Firebase Realtime Database")
    except Exception as e:
        logging.warning("⚠️ Firebase unavailable — running with local MySQL only.")
        logging.warning(f"   Reason: {e}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="PythonSubscriberRaspi")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        logging.info(f"🔗 Connecting to MQTT Broker at {MQTT_BROKER}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logging.error("❌ Failed to connect to MQTT Broker completely. Check if Mosquitto is running.")
        logging.error(f"   Error: {e}")
        exit(1)

    # Start watchdog thread
    watchdog_thread = threading.Thread(target=data_watchdog, daemon=True)
    watchdog_thread.start()

    client.loop_start()
    logging.info("🚀 Program ready to receive data. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("\n🚪 Stopping program...")
        client.loop_stop()
        client.disconnect()
        logging.info("✅ MQTT Connection closed. Program stopped.")
