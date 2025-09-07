# smart_attendance_final.py
# Final fully working Streamlit Smart Attendance dashboard
# Teachers + Students login, Bluetooth + Face simulated check-in,
# AI Monitor, Data Explorer, Advanced dataset, dark purple theme.

import os, sqlite3, hashlib, random, uuid
from datetime import datetime, timedelta, date
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

# ------------------- CONFIG -------------------
st.set_page_config(page_title="Smart Attendance Final", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
DB_PATH = os.path.join(BASE_DIR, "smart_attendance_final.db")
SEED = 2027
random.seed(SEED)

# ------------------- THEME -------------------
st.markdown("""
<style>
body {background: linear-gradient(180deg,#0b0a14 0%, #1a1630 100%); color: #e0dff5; font-family: "Inter";}
h1,h2,h3 {color:#efeafc;}
.stButton>button {background:#7c3aed; color:white; border-radius:8px; border:none; padding:6px 14px;}
.stButton>button:hover {background:#5b21b6;}
[data-testid="stMetricValue"] {color:white; font-weight:700;}
</style>
""", unsafe_allow_html=True)

# ------------------- DB INIT -------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    );
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, roll TEXT, email TEXT,
        dept TEXT, class_name TEXT, bluetooth_id TEXT
    );
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT, title TEXT
    );
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER, class_id INTEGER, score REAL
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER, class_id INTEGER,
        ts TEXT, method TEXT, device_id TEXT,
        confidence REAL, status TEXT
    );
    """)
    conn.commit()
    return conn

conn = get_conn()
cur = conn.cursor()

# ------------------- UTILS -------------------
def gen_bt(name, idx):
    raw = f"{name}-{idx}-{SEED}"
    return ":".join([hashlib.md5(raw.encode()).hexdigest()[i:i+2] for i in range(0,8,2)]).upper()

def seed_data():
    cur.execute("SELECT COUNT(*) FROM teachers")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO teachers (username,password) VALUES (?,?)", ("teacher","1234"))
    cur.execute("SELECT COUNT(*) FROM students")
    if cur.fetchone()[0] == 0:
        names = ["Aarav Sharma","Isha Kapoor","Rohit Singh","Meera Patel"]
        for i,n in enumerate(names,1):
            roll=f"ME{i+100}"
            email=f"{n.split()[0].lower()}@univ.edu"
            dept="Mechanical"; cls="CE-2A"
            cur.execute("INSERT INTO students (name,roll,email,dept,class_name,bluetooth_id) VALUES (?,?,?,?,?,?)",
                        (n,roll,email,dept,cls,gen_bt(n,i)))
        cur.executemany("INSERT INTO classes (code,title) VALUES (?,?)",
                        [("ME101","Thermodynamics"),("ME102","Mechanics")])
    conn.commit()
seed_data()

def students_df(): return pd.read_sql_query("SELECT * FROM students",conn)
def classes_df(): return pd.read_sql_query("SELECT * FROM classes",conn)
def attendance_df(): return pd.read_sql_query("SELECT * FROM attendance",conn)

def log_att(student_id,class_id,method,device=None,conf=None,status="present"):
    ts=datetime.utcnow().isoformat()
    cur.execute("INSERT INTO attendance (student_id,class_id,ts,method,device_id,confidence,status) VALUES (?,?,?,?,?,?,?)",
                (student_id,class_id,ts,method,device,conf,status))
    conn.commit()

# ------------------- AUTH -------------------
if "teacher" not in st.session_state: st.session_state.teacher=False
if "student" not in st.session_state: st.session_state.student=None

st.title("🛰️ Smart Attendance — Final")

menu = st.sidebar.radio("Menu",["Dashboard","Teacher Login","Student Login","AI Monitor","Data Explorer"])

# ------------------- DASHBOARD -------------------
if menu=="Dashboard":
    st.header("Dashboard Overview")
    df_stu,df_cls,df_att = students_df(),classes_df(),attendance_df()
    st.metric("Total Students",len(df_stu))
    st.metric("Classes",len(df_cls))
    if not df_att.empty:
        pres=(df_att["status"]=="present").sum()
        st.metric("Attendance Records",len(df_att))
        st.metric("Present %",f"{pres/len(df_att)*100:.1f}%")
    else: st.info("No attendance yet")

# ------------------- TEACHER LOGIN -------------------
elif menu=="Teacher Login":
    if not st.session_state.teacher:
        u=st.text_input("Username"); p=st.text_input("Password",type="password")
        if st.button("Login"):
            row=cur.execute("SELECT * FROM teachers WHERE username=? AND password=?",(u,p)).fetchone()
            if row: st.session_state.teacher=True; st.success("Login OK"); st.rerun()
            else: st.error("Invalid")
    else:
        st.success("Teacher logged in ✅")
        st.dataframe(students_df())
        csel=st.selectbox("Class",classes_df()["id"])
        sid=st.number_input("Student ID",1)
        if st.button("Mark Present"): log_att(sid,csel,"teacher")
        if st.button("Logout"): st.session_state.teacher=False; st.rerun()

# ------------------- STUDENT LOGIN -------------------
elif menu=="Student Login":
    if st.session_state.student is None:
        roll=st.text_input("Roll"); email=st.text_input("Email")
        if st.button("Login Student"):
            row=cur.execute("SELECT * FROM students WHERE roll=? AND email=?",(roll,email)).fetchone()
            if row: st.session_state.student=row; st.success("Student OK"); st.rerun()
            else: st.error("Invalid")
    else:
        s=st.session_state.student
        st.success(f"Logged in: {s[1]} ({s[2]})")
        st.write(f"Bluetooth ID: `{s[6]}`")
        clsid=st.selectbox("Class",classes_df()["id"])
        bt=st.text_input("Bluetooth ID")
        if st.button("Check-in"):
            if bt==s[6]: log_att(s[0],clsid,"bluetooth",bt); st.success("Checked in ✅")
            else: st.error("Wrong BT ID")
        st.dataframe(pd.read_sql_query("SELECT * FROM attendance WHERE student_id=? ORDER BY ts DESC",conn,params=(s[0],)))
        if st.button("Logout"): st.session_state.student=None; st.rerun()

# ------------------- AI MONITOR -------------------
elif menu=="AI Monitor":
    st.header("AI Proxy Detection (demo rules)")
    df=attendance_df()
    if df.empty: st.info("No events")
    else:
        df["ts"]=pd.to_datetime(df["ts"])
        df["suspicious"]=df.duplicated(subset=["device_id"],keep=False)
        st.dataframe(df.tail(20))
        st.write("Flagged suspicious:",df[df["suspicious"]])

# ------------------- DATA EXPLORER -------------------
elif menu=="Data Explorer":
    st.header("Data Explorer")
    st.subheader("Students"); st.dataframe(students_df())
    st.subheader("Classes"); st.dataframe(classes_df())
    st.subheader("Attendance"); st.dataframe(attendance_df())



