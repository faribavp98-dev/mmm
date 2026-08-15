import sqlite3
from pathlib import Path
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "team_demo.db"
DB.parent.mkdir(exist_ok=True)

app = FastAPI(title="مدیر تیم - نسخه آزمایشی")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        project_id INTEGER,
        status TEXT NOT NULL DEFAULT 'todo',
        priority TEXT NOT NULL DEFAULT 'normal',
        due_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    c.commit()

init()

class ProjectIn(BaseModel):
    title: str
    description: str = ""

class TaskIn(BaseModel):
    title: str
    description: str = ""
    project_id: int | None = None
    priority: str = "normal"
    due_date: str | None = None

@app.get("/")
def home():
    return FileResponse(BASE / "web" / "index.html")

@app.get("/api/stats")
def stats():
    c=db()
    total=c.execute("SELECT COUNT(*) n FROM tasks").fetchone()["n"]
    done=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='done'").fetchone()["n"]
    doing=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='doing'").fetchone()["n"]
    review=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='review'").fetchone()["n"]
    todo=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='todo'").fetchone()["n"]
    overdue=c.execute("""SELECT COUNT(*) n FROM tasks
                         WHERE due_date IS NOT NULL AND due_date < ?
                         AND status != 'done'""",(date.today().isoformat(),)).fetchone()["n"]
    projects=c.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"]
    return {"total":total,"done":done,"doing":doing,"review":review,
            "todo":todo,"overdue":overdue,"projects":projects}

@app.get("/api/projects")
def projects():
    c=db()
    return [dict(x) for x in c.execute("SELECT * FROM projects ORDER BY id DESC")]

@app.post("/api/projects")
def create_project(x: ProjectIn):
    if not x.title.strip():
        raise HTTPException(400,"عنوان پروژه الزامی است")
    c=db()
    cur=c.execute("INSERT INTO projects(title,description) VALUES(?,?)",
                  (x.title.strip(),x.description.strip()))
    c.commit()
    return {"id":cur.lastrowid}

@app.get("/api/tasks")
def tasks():
    c=db()
    rows=c.execute("""SELECT t.*, p.title project_title
                      FROM tasks t LEFT JOIN projects p ON p.id=t.project_id
                      ORDER BY
                      CASE t.status WHEN 'todo' THEN 0 WHEN 'doing' THEN 1
                      WHEN 'review' THEN 2 ELSE 3 END, t.id DESC""").fetchall()
    return [dict(x) for x in rows]

@app.post("/api/tasks")
def create_task(x: TaskIn):
    if not x.title.strip():
        raise HTTPException(400,"عنوان کار الزامی است")
    c=db()
    cur=c.execute("""INSERT INTO tasks(title,description,project_id,priority,due_date)
                     VALUES(?,?,?,?,?)""",
                  (x.title.strip(),x.description.strip(),x.project_id,x.priority,x.due_date))
    c.commit()
    return {"id":cur.lastrowid}

@app.patch("/api/tasks/{task_id}")
def update_task(task_id:int, payload:dict):
    status=payload.get("status")
    if status not in {"todo","doing","review","done"}:
        raise HTTPException(400,"وضعیت نامعتبر است")
    c=db()
    c.execute("UPDATE tasks SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
              (status,task_id))
    c.commit()
    return {"ok":True}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id:int):
    c=db()
    c.execute("DELETE FROM tasks WHERE id=?",(task_id,))
    c.commit()
    return {"ok":True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
