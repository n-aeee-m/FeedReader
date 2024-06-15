import sqlite3
import time
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE = os.getenv('FEED_DATABASE')


def add_feed_source(userId, source):
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    dt_date = int(time.strftime("%Y%m%d%H%M%S"))
    cur.execute("INSERT INTO sources VALUES (?, ?, ? )",
                (userId, source, dt_date))
    con.commit()
    con.close()


def is_already_present(userId, source):
    results = []
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    cur.execute(
        "SELECT * FROM sources WHERE URL=:source AND USERID=:userid", {"userid": userId, "source": source})
    for row in cur:
        results.append(row)
    con.close()
    if len(results):
        return True
    return False


def remove_feed_source(userId, source):
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    cur.execute(" DELETE FROM sources WHERE URL=:source AND USERID=:userid", {
                "userid": userId, "source": source})
    con.commit()
    con.close()


def get_sources(userId):
    results = []
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    cur.execute("SELECT URL FROM sources WHERE USERID=:userid",
                {"userid": userId})
    for row in cur:
        results.append(row[0])
    con.close()
    return results


def get_all_sources():
    results = []
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    cur.execute("SELECT * FROM sources")
    for row in cur:
        results.append({
            "userId": row[0],
            "url": row[1],
            "last_updated": row[2]
        })
    con.close()
    return results

def initialize_db():
    conn = sqlite3.connect('feeds.db')
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        userId INTEGER NOT NULL,
        url TEXT NOT NULL,
        last_updated INTEGER DEFAULT 0
    )
    ''')
    conn.commit()
    conn.close()

def get_all_sources():
    conn = sqlite3.connect('feeds.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM sources")
    sources = cur.fetchall()
    conn.close()
    return sources

# Include other database functions as needed

def update_source_timestamp(userId, source, time):
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    cur.execute("UPDATE sources SET last_updated=:dt_date WHERE URL=:source AND USERID=:userid", {
                "userid": userId, "source": source, "dt_date": time})
    con.commit()
    con.close()

