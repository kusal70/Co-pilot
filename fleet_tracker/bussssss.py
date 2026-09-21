import asyncio
import csv
import os
import random
import sqlite3
import threading
import time
import tkinter as tk
import requests
from dotenv import load_dotenv

from datetime import datetime, timedelta, timezone
from tkinter import filedialog, messagebox, ttk

import tkintermapview
from PIL import Image, ImageDraw, ImageTk

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ============================================================
# CONFIGURATION
# ============================================================

DB_FILE = "fleet_tracker.db"

DEFAULT_LAT = 17.7289
DEFAULT_LNG = 83.3034

GPS_UPDATE_INTERVAL = 3
REMOTE_POLL_INTERVAL = 3

STALE_LOCATION_SECONDS = 120

load_dotenv()

# ============================================================
# MAP MARKER ICONS
# ============================================================
def create_map_icon(kind):
    """Create a small custom marker icon so drivers and students
    are visually distinct on the map."""
    size = 42
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # White outer circle gives the icon a clean map-pin badge look.
    draw.ellipse((2, 2, size - 2, size - 2), fill="white", outline="#222222", width=2)

    if kind == "driver":
        # Bus symbol
        draw.rounded_rectangle((10, 9, 32, 29), radius=4, fill="#e53935")
        draw.rectangle((13, 12, 29, 20), fill="#dff5ff")
        draw.rectangle((15, 14, 20, 18), fill="#9ed8ef")
        draw.rectangle((22, 14, 27, 18), fill="#9ed8ef")
        draw.ellipse((12, 25, 18, 31), fill="#222222")
        draw.ellipse((24, 25, 30, 31), fill="#222222")
        draw.line((21, 20, 21, 29), fill="white", width=1)

    elif kind == "student":
        # Person symbol
        draw.ellipse((16, 8, 26, 18), fill="#1565c0")
        draw.rounded_rectangle((11, 18, 31, 33), radius=7, fill="#1565c0")
        draw.rectangle((14, 21, 28, 28), fill="#42a5f5")

    else:
        draw.ellipse((15, 15, 27, 27), fill="#757575")

    return ImageTk.PhotoImage(image.resize((36, 36), Image.Resampling.LANCZOS))


def ensure_map_icons(widget):
    """Keep PhotoImage references alive for tkintermapview markers."""
    widget.driver_icon = create_map_icon("driver")
    widget.student_icon = create_map_icon("student")


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

# Replace these with YOUR Supabase project details.

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()

SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()


def supabase_headers():

    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }


def supabase_enabled():
    """Return True when a usable Supabase URL and public key are configured."""
    url = str(SUPABASE_URL or "").strip()
    key = str(SUPABASE_ANON_KEY or "").strip()

    if not url or not key:
        return False

    if not url.startswith("https://"):
        return False

    if ".supabase.co" not in url:
        return False

    if "YOUR-PROJECT" in url or "YOUR-SUPABASE" in key:
        return False

    return True


# ============================================================
# REMOTE GPS FUNCTIONS
# ============================================================
def parse_utc_timestamp(value):
    """Parse a Supabase timestamp and return a timezone-aware UTC datetime."""
    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)



def upload_driver_location(
    driver,
    lat,
    lng
):
    if not supabase_enabled():
        print("Supabase is not configured.")
        return False

    url = SUPABASE_URL.rstrip("/") + "/rest/v1/bus_locations"

    payload = {
        "driver": str(driver),
        "lat": float(lat),
        "lng": float(lng),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    headers = supabase_headers()

    try:
        # Update the driver's existing row when possible. This avoids
        # requiring a unique constraint on the driver column.
        response = requests.patch(
            url,
            headers=headers,
            params={"driver": f"eq.{driver}"},
            json=payload,
            timeout=10
        )

        if response.status_code not in (200, 204):
            print(
                "Supabase update error:",
                response.status_code,
                response.text
            )
            return False

        # Supabase returns [] when no existing row matched.
        if response.text.strip() in ("", "[]"):
            insert_headers = supabase_headers()
            response = requests.post(
                url,
                headers=insert_headers,
                json=payload,
                timeout=10
            )

            if response.status_code not in (200, 201):
                print(
                    "Supabase insert error:",
                    response.status_code,
                    response.text
                )
                return False

        return True

    except requests.RequestException as error:
        print("Internet/GPS upload error:", error)
        return False


def get_remote_bus_locations():

    if not supabase_enabled():

        return []

    url = (
        SUPABASE_URL.rstrip("/")
        + "/rest/v1/bus_locations"
    )

    params = {
        "select": "driver,lat,lng,updated_at",
        "order": "updated_at.desc"
    }

    try:

        response = requests.get(
            url,
            headers=supabase_headers(),
            params=params,
            timeout=10
        )

        if response.status_code != 200:

            print(
                "Supabase download error:",
                response.status_code,
                response.text
            )

            return []

        return response.json()

    except requests.RequestException as error:

        print(
            "Remote location error:",
            error
        )

        return []


def delete_remote_driver(driver):

    if not supabase_enabled():
        return

    url = (
        SUPABASE_URL.rstrip("/")
        + "/rest/v1/bus_locations"
    )

    params = {
        "driver": f"eq.{driver}"
    }

    try:

        requests.delete(
            url,
            headers=supabase_headers(),
            params=params,
            timeout=10
        )

    except requests.RequestException as error:

        print(
            "Remote delete error:",
            error
        )


# ============================================================
# LOCAL DATABASE
# ============================================================

def get_db_connection():

    conn = sqlite3.connect(
        DB_FILE,
        timeout=10
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            timestamp DATETIME NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO config
        (key, value)
        VALUES ('global_gps', 'ON')
    """)

    conn.commit()

    conn.close()


init_db()


# ============================================================
# MAIN APPLICATION
# ============================================================

class FleetTrackerApp(tk.Tk):

    def __init__(self):

        super().__init__()

        self.title("BUS MAPS")

        self.geometry(
            "1200x750"
        )

        self.minsize(
            1000,
            650
        )

        self.configure(
            bg="#121212"
        )

        self.container = tk.Frame(
            self,
            bg="#121212"
        )

        self.container.pack(
            fill="both",
            expand=True
        )

        self.container.grid_rowconfigure(
            0,
            weight=1
        )

        self.container.grid_columnconfigure(
            0,
            weight=1
        )

        self.frames = {}

        self.current_user = None
        self.current_role = None

        for FrameClass in (
            LoginScreen,
            DeveloperScreen,
            DriverScreen,
            StudentScreen
        ):

            frame = FrameClass(
                self.container,
                self
            )

            name = FrameClass.__name__

            self.frames[name] = frame

            frame.grid(
                row=0,
                column=0,
                sticky="nsew"
            )

        self.show_frame(
            "LoginScreen"
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    def show_frame(
        self,
        name
    ):

        frame = self.frames[name]

        frame.tkraise()

        if hasattr(
            frame,
            "on_show"
        ):

            frame.on_show()

    def logout(self):
        self.current_user = None
        self.current_role = None
        self.show_frame(
            "LoginScreen"
        )

    def on_close(self):
        self.destroy()


# ============================================================
# LOGIN SCREEN
# ============================================================

class LoginScreen(tk.Frame):

    def __init__(
        self,
        parent,
        controller
    ):

        super().__init__(
            parent,
            bg="#121212"
        )

        self.controller = controller

        box = tk.Frame(
            self,
            bg="#1e1e1e",
            padx=45,
            pady=45
        )

        box.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        tk.Label(
            box,
            text="🚌 BUS MAPS",
            font=(
                "Arial",
                26,
                "bold"
            ),
            bg="#1e1e1e",
            fg="white"
        ).pack(
            pady=(0, 8)
        )

        tk.Label(
            box,
            text="Live Fleet Tracking",
            font=("Arial", 11),
            bg="#1e1e1e",
            fg="#888888"
        ).pack(
            pady=(0, 25)
        )

        tk.Label(
            box,
            text="Username",
            bg="#1e1e1e",
            fg="#bbbbbb"
        ).pack(
            anchor="w"
        )

        self.user_entry = tk.Entry(
            box,
            font=("Arial", 14),
            width=28
        )

        self.user_entry.pack(
            pady=(5, 15)
        )

        tk.Label(
            box,
            text="Password",
            bg="#1e1e1e",
            fg="#bbbbbb"
        ).pack(
            anchor="w"
        )

        self.pass_entry = tk.Entry(
            box,
            font=("Arial", 14),
            width=28,
            show="*"
        )

        self.pass_entry.pack(
            pady=(5, 25)
        )

        tk.Button(
            box,
            text="SECURE LOGIN",
            bg="#007bff",
            fg="white",
            font=(
                "Arial",
                12,
                "bold"
            ),
            command=self.authenticate,
            width=24,
            pady=8,
            relief="flat"
        ).pack()

        self.pass_entry.bind(
            "<Return>",
            lambda event:
            self.authenticate()
        )

    def on_show(self):

        self.user_entry.delete(
            0,
            tk.END
        )

        self.pass_entry.delete(
            0,
            tk.END
        )

        self.user_entry.focus_set()

    def authenticate(self):

        username = (
            self.user_entry
            .get()
            .strip()
        )

        password = (
            self.pass_entry
            .get()
        )

        if not username or not password:

            messagebox.showwarning(
                "Login",
                "Enter username and password."
            )

            return

        admin_username = os.getenv(
            "BUSMAPS_ADMIN_USER",
            "kusal10"
        )

        admin_password = os.getenv(
            "BUSMAPS_ADMIN_PASSWORD",
            ""
        )

        if (
            username == admin_username
            and password == admin_password
        ):

            self.controller.current_user = username
            self.controller.current_role = "developer"

            self.controller.show_frame(
                "DeveloperScreen"
            )

            return

        try:

            conn = get_db_connection()

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

            conn.close()

        except sqlite3.Error as error:

            messagebox.showerror(
                "Database Error",
                str(error)
            )

            return

        if user:

            try:

                valid = check_password_hash(
                    user["password"],
                    password
                )

            except Exception:

                valid = False

            if valid:

                self.controller.current_user = username
                self.controller.current_role = user["role"]

                if user["role"] == "driver":

                    self.controller.show_frame(
                        "DriverScreen"
                    )

                    return

                if user["role"] == "student":

                    self.controller.show_frame(
                        "StudentScreen"
                    )

                    return

        messagebox.showerror(
            "Login Failed",
            "Invalid username or password."
        )


# ============================================================
# DEVELOPER SCREEN
# ============================================================

class DeveloperScreen(tk.Frame):

    def __init__(
        self,
        parent,
        controller
    ):

        super().__init__(
            parent,
            bg="#121212"
        )

        self.controller = controller

        self.markers = {}

        self.dev_marker = None
        self.driver_locations = {}
        ensure_map_icons(self)

        header = tk.Frame(
            self,
            bg="#1e1e1e",
            pady=12,
            padx=20
        )

        header.pack(
            fill="x"
        )

        tk.Label(
            header,
            text="Developer Workspace",
            font=(
                "Arial",
                17,
                "bold"
            ),
            bg="#1e1e1e",
            fg="white"
        ).pack(
            side="left"
        )

        tk.Label(
            header,
            text="  • ONLINE FLEET MONITOR",
            font=(
                "Arial",
                9,
                "bold"
            ),
            bg="#1e1e1e",
            fg="#00d4ff"
        ).pack(
            side="left"
        )

        tk.Button(
            header,
            text="Logout",
            bg="#dc3545",
            fg="white",
            command=self.controller.logout
        ).pack(
            side="right"
        )

        main = tk.Frame(
            self,
            bg="#121212"
        )

        main.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=15
        )

        left = tk.Frame(
            main,
            bg="#1e1e1e",
            width=300
        )

        left.pack(
            side="left",
            fill="y",
            padx=(0, 15)
        )

        left.pack_propagate(False)

        tk.Label(
            left,
            text="Provision Users",
            font=(
                "Arial",
                14,
                "bold"
            ),
            bg="#1e1e1e",
            fg="white"
        ).pack(
            anchor="w",
            padx=15,
            pady=(15, 8)
        )

        self.new_user_entry = tk.Entry(
            left
        )

        self.new_user_entry.pack(
            fill="x",
            padx=15,
            pady=5
        )

        self.new_user_entry.insert(
            0,
            "Username"
        )

        self.new_pass_entry = tk.Entry(
            left,
            show="*"
        )

        self.new_pass_entry.pack(
            fill="x",
            padx=15,
            pady=5
        )

        self.role_var = tk.StringVar(
            value="driver"
        )

        ttk.Combobox(
            left,
            textvariable=self.role_var,
            values=[
                "driver",
                "student"
            ],
            state="readonly"
        ).pack(
            fill="x",
            padx=15,
            pady=5
        )

        tk.Button(
            left,
            text="Create Account",
            bg="#28a745",
            fg="white",
            command=self.create_user
        ).pack(
            fill="x",
            padx=15,
            pady=(8, 20)
        )

        tk.Label(
            left,
            text="Active Accounts",
            font=(
                "Arial",
                14,
                "bold"
            ),
            bg="#1e1e1e",
            fg="white"
        ).pack(
            anchor="w",
            padx=15
        )

        self.user_listbox = tk.Listbox(
            left,
            bg="#2a2a2a",
            fg="white",
            selectbackground="#007bff",
            height=8
        )

        self.user_listbox.pack(
            fill="x",
            padx=15,
            pady=5
        )

        tk.Button(
            left,
            text="Delete Selected User",
            bg="#dc3545",
            fg="white",
            command=self.delete_user
        ).pack(
            fill="x",
            padx=15
        )

        tk.Label(
            left,
            text="Global GPS",
            font=(
                "Arial",
                14,
                "bold"
            ),
            bg="#1e1e1e",
            fg="white"
        ).pack(
            anchor="w",
            padx=15,
            pady=(25, 5)
        )

        self.gps_status_lbl = tk.Label(
            left,
            text="UNKNOWN",
            font=(
                "Arial",
                13,
                "bold"
            ),
            bg="#1e1e1e"
        )

        self.gps_status_lbl.pack(
            anchor="w",
            padx=15
        )

        tk.Button(
            left,
            text="Toggle Master GPS",
            bg="#ffc107",
            fg="black",
            command=self.toggle_gps
        ).pack(
            fill="x",
            padx=15,
            pady=10
        )

        tk.Label(
            left,
            text="Live Drivers",
            font=("Arial", 14, "bold"),
            bg="#1e1e1e",
            fg="white"
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.driver_listbox = tk.Listbox(
            left,
            bg="#2a2a2a",
            fg="white",
            selectbackground="#007bff",
            selectforeground="white",
            height=8,
            activestyle="none"
        )
        self.driver_listbox.pack(fill="x", padx=15, pady=(0, 10))
        self.driver_listbox.bind("<ButtonRelease-1>", self.on_driver_selected)

        right = tk.Frame(
            main,
            bg="#121212"
        )

        right.pack(
            side="right",
            fill="both",
            expand=True
        )

        self.map_widget = (
            tkintermapview.TkinterMapView(
                right,
                corner_radius=8
            )
        )

        self.map_widget.pack(
            fill="both",
            expand=True,
            pady=(0, 10)
        )

        self.map_widget.set_tile_server(
            "https://mt0.google.com/vt/"
            "lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
            max_zoom=22
        )