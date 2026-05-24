import os
import sqlite3
from pathlib import Path


DEFAULT_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


class ActivityRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS activities (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    max_participants INTEGER NOT NULL,
                    display_order INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(activity_name, email),
                    FOREIGN KEY(activity_name) REFERENCES activities(name) ON DELETE CASCADE
                );
                """
            )

            activity_count = connection.execute(
                "SELECT COUNT(*) FROM activities"
            ).fetchone()[0]
            if activity_count == 0:
                self._seed(connection)

    def _seed(self, connection: sqlite3.Connection) -> None:
        activity_rows = []
        registration_rows = []

        for display_order, (name, details) in enumerate(DEFAULT_ACTIVITIES.items()):
            activity_rows.append(
                (
                    name,
                    details["description"],
                    details["schedule"],
                    details["max_participants"],
                    display_order,
                )
            )
            for participant in details["participants"]:
                registration_rows.append((name, participant))

        connection.executemany(
            """
            INSERT INTO activities (name, description, schedule, max_participants, display_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            activity_rows,
        )
        connection.executemany(
            "INSERT INTO registrations (activity_name, email) VALUES (?, ?)",
            registration_rows,
        )

    def get_activities(self) -> dict[str, dict[str, object]]:
        with self._connect() as connection:
            activity_rows = connection.execute(
                """
                SELECT name, description, schedule, max_participants
                FROM activities
                ORDER BY display_order, name
                """
            ).fetchall()
            registration_rows = connection.execute(
                """
                SELECT activity_name, email
                FROM registrations
                ORDER BY activity_name, created_at, id
                """
            ).fetchall()

        participants_by_activity: dict[str, list[str]] = {
            row["name"]: [] for row in activity_rows
        }
        for row in registration_rows:
            participants_by_activity[row["activity_name"]].append(row["email"])

        return {
            row["name"]: {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": participants_by_activity[row["name"]],
            }
            for row in activity_rows
        }

    def signup(self, activity_name: str, email: str) -> None:
        with self._connect() as connection:
            activity = connection.execute(
                """
                SELECT name, max_participants
                FROM activities
                WHERE name = ?
                """,
                (activity_name,),
            ).fetchone()

            if activity is None:
                raise KeyError("Activity not found")

            participant_count = connection.execute(
                "SELECT COUNT(*) FROM registrations WHERE activity_name = ?",
                (activity_name,),
            ).fetchone()[0]

            if participant_count >= activity["max_participants"]:
                raise ValueError("Activity is full")

            try:
                connection.execute(
                    "INSERT INTO registrations (activity_name, email) VALUES (?, ?)",
                    (activity_name, email),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE" in str(error).upper():
                    raise ValueError("Student is already signed up") from error
                raise

    def unregister(self, activity_name: str, email: str) -> None:
        with self._connect() as connection:
            activity_exists = connection.execute(
                "SELECT 1 FROM activities WHERE name = ?",
                (activity_name,),
            ).fetchone()

            if activity_exists is None:
                raise KeyError("Activity not found")

            cursor = connection.execute(
                "DELETE FROM registrations WHERE activity_name = ? AND email = ?",
                (activity_name, email),
            )
            if cursor.rowcount == 0:
                raise ValueError("Student is not signed up for this activity")


def build_repository() -> ActivityRepository:
    db_path = os.getenv(
        "ACTIVITY_DB_PATH",
        str(Path(__file__).parent / "data" / "activities.db"),
    )
    return ActivityRepository(Path(db_path))