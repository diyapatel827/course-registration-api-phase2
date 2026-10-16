from collections import OrderedDict
from typing import Dict, List, Optional, Any
import re

from bs4 import BeautifulSoup
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

app = FastAPI(title="Student Academic History API", version="1.0.0")

# Each student owns an independent record. This is in-memory storage for the assignment.
students: Dict[str, Dict[str, list]] = {}


class HistoryCourse(BaseModel):
    course_code: str
    term: str
    credits_earned: int = 0
    status: str


class HistoryUpdate(BaseModel):
    history: List[HistoryCourse] = Field(default_factory=list)


class PlannedCourse(BaseModel):
    course_code: str
    term: str


class PlanUpdate(BaseModel):
    planned_courses: List[PlannedCourse] = Field(default_factory=list)


def _norm(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _grade_rank(grade: str) -> int:
    """Numeric grades outrank letter grades, which outrank P/blank/other."""
    grade = _norm(grade)
    if not grade:
        return 0
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", grade):
        return 3
    if re.fullmatch(r"[A-Za-z][+-]?", grade) and grade.upper() != "P":
        return 2
    if grade.upper() == "P":
        return 1
    return 1


def _credits_int(value: str) -> int:
    value = _norm(value)
    match = re.search(r"-?\d+", value)
    if not match:
        return 0
    try:
        return int(match.group(0))
    except ValueError:
        return 0


def parse_transcript(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    # OrderedDict preserves the first appearance of each unique (course_code, term).
    selected = OrderedDict()

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        header_idx: Optional[int] = None
        col_map: Dict[str, int] = {}

        for i, row in enumerate(rows):
            cells = row.find_all(["th", "td"], recursive=False)
            labels = [_norm(c.get_text(" ", strip=True)).lower() for c in cells]
            # Identify the relevant transcript table by its column headings.
            status_i = next((j for j, x in enumerate(labels) if x == "status"), None)
            course_i = next((j for j, x in enumerate(labels) if x == "course"), None)
            term_i = next((j for j, x in enumerate(labels) if x == "term"), None)
            credits_i = next((j for j, x in enumerate(labels) if x == "credits"), None)
            grade_i = next((j for j, x in enumerate(labels) if x == "grade"), None)
            if None not in (status_i, course_i, term_i, credits_i, grade_i):
                header_idx = i
                col_map = {
                    "status": status_i,
                    "course": course_i,
                    "term": term_i,
                    "credits": credits_i,
                    "grade": grade_i,
                }
                break

        if header_idx is None:
            continue

        for row in rows[header_idx + 1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            max_index = max(col_map.values())
            if len(cells) <= max_index:
                continue
            values = [_norm(c.get_text(" ", strip=True)) for c in cells]
            status = values[col_map["status"]]
            term = values[col_map["term"]]
            course_code = values[col_map["course"]]
            grade = values[col_map["grade"]]
            credits = _credits_int(values[col_map["credits"]])

            if status not in {"Completed", "In-Progress", "Attempted"} or not term or not course_code:
                continue

            # If a Course cell includes a title after the code, retain the code portion.
            # Hyphenated course codes are expected; don't hardcode any particular course.
            code_match = re.match(r"^([A-Za-z]{2,}-\d{4}(?:-[A-Za-z0-9]+)*)", course_code)
            if code_match:
                course_code = code_match.group(1)

            record = {
                "course_code": course_code,
                "term": term,
                "credits_earned": credits,
                "status": status,
            }
            key = (course_code, term)
            rank = (_grade_rank(grade), credits)
            old = selected.get(key)
            if old is None or rank > old["_rank"]:
                selected[key] = {"record": record, "_rank": rank}

    return [item["record"] for item in selected.values()]


def _ensure_student(student_id: str) -> dict:
    if student_id not in students:
        raise HTTPException(status_code=404, detail="Student not found")
    return students[student_id]


@app.get("/")
def root():
    return {"status": "ok", "service": "Student Academic History API"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/students/{student_id}/history/import", status_code=201)
async def import_history(student_id: str, file: UploadFile = File(...)):
    content = await file.read()
    html = content.decode("utf-8", errors="replace")
    history = parse_transcript(html)
    students[student_id] = {"history": history, "plan": []}
    return {"status": "success", "past_courses_imported": len(history)}


@app.put("/api/v1/students/{student_id}/history")
def update_history(student_id: str, body: HistoryUpdate):
    student = _ensure_student(student_id)
    student["history"] = [course.model_dump() for course in body.history]
    return {"status": "success", "message": "Academic history updated successfully"}


@app.delete("/api/v1/students/{student_id}/history")
def delete_history(student_id: str):
    student = _ensure_student(student_id)
    student["history"] = []
    return {"status": "success", "message": "Academic history cleared successfully"}


@app.post("/api/v1/students/{student_id}/plan")
def save_plan(student_id: str, body: PlanUpdate):
    student = _ensure_student(student_id)
    student["plan"] = [course.model_dump() for course in body.planned_courses]
    return {"status": "success", "planned_courses_saved": len(student["plan"])}


@app.put("/api/v1/students/{student_id}/plan")
def replace_plan(student_id: str, body: PlanUpdate):
    student = _ensure_student(student_id)
    student["plan"] = [course.model_dump() for course in body.planned_courses]
    return {"status": "success", "planned_courses_saved": len(student["plan"])}


@app.delete("/api/v1/students/{student_id}/plan")
def delete_plan(student_id: str):
    student = _ensure_student(student_id)
    student["plan"] = []
    return {"status": "success", "message": "Plan cleared successfully"}


@app.get("/api/v1/students/{student_id}/profile")
def get_profile(student_id: str):
    student = _ensure_student(student_id)
    # Keep this top-level schema exact as required by the assignment.
    return {
        "student_id": student_id,
        "history": student["history"],
        "plan": student["plan"],
    }
