
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from datetime import date, timedelta

WEIGHT_TO_PRIORITY = {1: "low", 2: "medium", 3: "high"}
DIFF_FACTOR = {"beginner": 1.3, "intermediate": 1.1, "advanced": 0.9}
BASE_SESSION_MIN = 40


@dataclass
class SubjectInput:
    name: str
    topics: list[str]
    weight: int


@dataclass
class PlanInput:
    title: str
    exam_date: date
    daily_hours: float
    difficulty: str
    subjects: list[SubjectInput]


@dataclass
class StudyTask:
    task_date: date
    start_minute: int
    subject: str | None
    topic: str
    task_type: str
    priority: str
    duration_minutes: int
    completed: bool = False


@dataclass
class _TopicQueueItem:
    subject: str
    topic: str
    weight: int
    priority: str
    sessions_needed: int
    done: int = 0


def format_time(minutes):
    h, m = divmod(minutes, 60)
    hr12 = h % 12 or 12
    return f"{hr12}:{m:02d} {'PM' if h >= 12 else 'AM'}"


def generate_schedule(plan):
    daily_minutes = max(60, round(plan.daily_hours * 60))
    factor = DIFF_FACTOR[plan.difficulty]
    focus_span = max(25, min(50, round(BASE_SESSION_MIN / factor)))
    start = date.today()
    days = max(1, (plan.exam_date - start).days)

    queue = []

    for s in plan.subjects:
        weight = min(3, max(1, s.weight))

        for topic in s.topics:
            sessions = max(1, round(weight * factor))

            queue.append(
                _TopicQueueItem(
                    subject=s.name,
                    topic=topic,
                    weight=weight,
                    priority=WEIGHT_TO_PRIORITY[weight],
                    sessions_needed=sessions
                )
            )

    queue.sort(key=lambda q: (-q.weight, q.subject))

    tasks = []
    queue_idx = 0
    sessions_placed = 0
    learn_phase_days = max(1, round(days * 0.75))

    for day in range(days):
        iso = start + timedelta(days=day)
        revision_phase = day >= learn_phase_days
        remaining = daily_minutes
        start_minute = 8 * 60
        sessions_today = 0

        while remaining >= 25:
            block = None
            task_type = "learn"
            subject = None
            label = ""
            priority = "medium"
            duration = focus_span

            if not revision_phase:
                practice_due = (
                    sessions_placed > 0
                    and sessions_placed % 3 == 0
                    and queue_idx > 0
                )

                if practice_due:
                    block = queue[max(0, queue_idx - 1)]
                    task_type = "practice"
                    subject = block.subject
                    label = f"Practice: {block.topic}"
                    priority = block.priority

                else:
                    if queue_idx >= len(queue):
                        break

                    block = queue[queue_idx]
                    task_type = "learn"
                    subject = block.subject
                    label = block.topic
                    priority = block.priority

            else:
                covered = queue[:queue_idx]

                if not covered:
                    break

                pick = covered[day % len(covered)]
                block = pick

                revise = sessions_today % 2 == 0
                task_type = "revise" if revise else "practice"

                subject = pick.subject

                label = (
                    f"Revise: {pick.topic}"
                    if revise
                    else f"Practice: {pick.topic}"
                )

                priority = pick.priority
                duration = (
                    round(focus_span * 0.8)
                    if revise else focus_span
                )

            if block is not None and task_type == "learn" and not revision_phase:
                block.done += 1

                if block.done >= block.sessions_needed:
                    queue_idx += 1

            sessions_placed += 1

            duration = min(duration, remaining)

            tasks.append(
                StudyTask(
                    task_date=iso,
                    start_minute=start_minute,
                    subject=subject,
                    topic=label,
                    task_type=task_type,
                    priority=priority,
                    duration_minutes=duration
                )
            )

            start_minute += duration
            remaining -= duration
            sessions_today += 1

            if remaining >= 10:
                break_min = min(15, remaining)

                tasks.append(
                    StudyTask(
                        task_date=iso,
                        start_minute=start_minute,
                        subject=None,
                        topic="Short break",
                        task_type="break",
                        priority="low",
                        duration_minutes=break_min
                    )
                )

                start_minute += break_min
                remaining -= break_min

        if queue_idx >= len(queue) and revision_phase:
            break

    if days > 0 and queue:
        first = queue[0]

        tasks.append(
            StudyTask(
                task_date=plan.exam_date,
                start_minute=8 * 60,
                subject=first.subject,
                topic=f"Final look-over: {first.topic}",
                task_type="revise",
                priority="high",
                duration_minutes=30
            )
        )

    tasks.sort(key=lambda t: (t.task_date, t.start_minute))

    return tasks


class StudyMateAI:

    def __init__(self, root):
        self.root = root
        self.root.title("StudyMate AI - Smart Study Planner")
        self.root.geometry("1150x750")
        self.root.minsize(950, 650)

        self.subjects = []

        self.setup_style()
        self.create_interface()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            rowheight=30,
            font=("Segoe UI", 10)
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold")
        )

        style.configure(
            "TButton",
            font=("Segoe UI", 10, "bold"),
            padding=7
        )

    def create_interface(self):

        header = tk.Frame(self.root, bg="#172554", height=90)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="StudyMate AI",
            font=("Segoe UI", 25, "bold"),
            fg="white",
            bg="#172554"
        ).pack(pady=(12, 0))

        tk.Label(
            header,
            text="Personalized Smart Study Planner",
            font=("Segoe UI", 11),
            fg="#BFDBFE",
            bg="#172554"
        ).pack()

        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        left = ttk.LabelFrame(
            main,
            text="Study Plan Details",
            padding=15
        )
        left.pack(side="left", fill="y", padx=(0, 12))

        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="Plan Title").pack(anchor="w")

        self.title_entry = ttk.Entry(left, width=35)
        self.title_entry.pack(fill="x", pady=(4, 12))
        self.title_entry.insert(0, "Final Exam Preparation")

        ttk.Label(left, text="Exam Date (YYYY-MM-DD)").pack(anchor="w")

        self.date_entry = ttk.Entry(left, width=35)
        self.date_entry.pack(fill="x", pady=(4, 12))
        self.date_entry.insert(
            0,
            (date.today() + timedelta(days=10)).isoformat()
        )

        ttk.Label(left, text="Daily Study Hours").pack(anchor="w")

        self.hours_var = tk.StringVar(value="4")

        ttk.Combobox(
            left,
            textvariable=self.hours_var,
            values=["1", "2", "3", "4", "5", "6", "7", "8"],
            state="readonly",
            width=32
        ).pack(fill="x", pady=(4, 12))

        ttk.Label(left, text="Difficulty Level").pack(anchor="w")

        self.difficulty_var = tk.StringVar(value="intermediate")

        ttk.Combobox(
            left,
            textvariable=self.difficulty_var,
            values=["beginner", "intermediate", "advanced"],
            state="readonly",
            width=32
        ).pack(fill="x", pady=(4, 15))

        ttk.Separator(left).pack(fill="x", pady=8)

        ttk.Label(
            left,
            text="Add Subject",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=5)

        ttk.Label(left, text="Subject Name").pack(anchor="w")

        self.subject_entry = ttk.Entry(left)
        self.subject_entry.pack(fill="x", pady=4)

        ttk.Label(left, text="Topics (comma separated)").pack(anchor="w")

        self.topics_entry = ttk.Entry(left)
        self.topics_entry.pack(fill="x", pady=4)

        ttk.Label(left, text="Subject Difficulty").pack(anchor="w")

        self.weight_var = tk.StringVar(value="3 - Hard")

        ttk.Combobox(
            left,
            textvariable=self.weight_var,
            values=["1 - Easy", "2 - Moderate", "3 - Hard"],
            state="readonly"
        ).pack(fill="x", pady=4)

        ttk.Button(
            left,
            text="Add Subject",
            command=self.add_subject
        ).pack(fill="x", pady=8)

        ttk.Label(
            left,
            text="Added Subjects",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(10, 4))

        self.subject_list = tk.Listbox(
            left,
            height=7,
            width=35,
            font=("Segoe UI", 9)
        )
        self.subject_list.pack(fill="x")

        ttk.Button(
            left,
            text="Remove Selected Subject",
            command=self.remove_subject
        ).pack(fill="x", pady=7)

        ttk.Button(
            left,
            text="Generate Study Plan",
            command=self.generate
        ).pack(fill="x", pady=(12, 4))

        ttk.Button(
            left,
            text="Clear Timetable",
            command=self.clear_timetable
        ).pack(fill="x")

        ttk.Label(
            right,
            text="Your Personalized Timetable",
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w", pady=(0, 12))

        self.summary = tk.Label(
            right,
            text="Add your subjects and generate your study plan.",
            font=("Segoe UI", 10),
            fg="#475569",
            anchor="w"
        )
        self.summary.pack(fill="x", pady=(0, 12))

        table_frame = ttk.Frame(right)
        table_frame.pack(fill="both", expand=True)

        columns = (
            "date",
            "time",
            "subject",
            "topic",
            "type",
            "priority",
            "duration"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings"
        )

        headings = {
            "date": "Date",
            "time": "Start Time",
            "subject": "Subject",
            "topic": "Topic / Activity",
            "type": "Task Type",
            "priority": "Priority",
            "duration": "Duration"
        }

        widths = {
            "date": 105,
            "time": 90,
            "subject": 105,
            "topic": 190,
            "type": 85,
            "priority": 75,
            "duration": 75
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(
                col,
                width=widths[col],
                minwidth=60,
                anchor="center"
            )

        scrollbar_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )

        scrollbar_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )

        self.tree.pack(side="top", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")

        self.tree.tag_configure("learn", background="#DBEAFE")
        self.tree.tag_configure("practice", background="#FEF3C7")
        self.tree.tag_configure("revise", background="#DCFCE7")
        self.tree.tag_configure("break", background="#F1F5F9")

        footer = tk.Label(
            self.root,
            text="Study smarter, stay organized, achieve more!",
            bg="#172554",
            fg="white",
            font=("Segoe UI", 10),
            pady=9
        )
        footer.pack(fill="x", side="bottom")

    def add_subject(self):

        name = self.subject_entry.get().strip()
        topics_text = self.topics_entry.get().strip()

        if not name or not topics_text:
            messagebox.showwarning(
                "Missing Information",
                "Enter the subject name and topics."
            )
            return

        topics = [
            topic.strip()
            for topic in topics_text.split(",")
            if topic.strip()
        ]

        if not topics:
            messagebox.showwarning(
                "Missing Topics",
                "Enter at least one topic."
            )
            return

        weight = int(self.weight_var.get()[0])

        self.subjects.append(
            SubjectInput(
                name=name,
                topics=topics,
                weight=weight
            )
        )

        self.subject_list.insert(
            tk.END,
            f"{name} | {len(topics)} topics | {WEIGHT_TO_PRIORITY[weight]}"
        )

        self.subject_entry.delete(0, tk.END)
        self.topics_entry.delete(0, tk.END)

    def remove_subject(self):

        selected = self.subject_list.curselection()

        if not selected:
            messagebox.showwarning(
                "Select Subject",
                "Select a subject to remove."
            )
            return

        index = selected[0]

        self.subjects.pop(index)
        self.subject_list.delete(index)

    def clear_timetable(self):

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.summary.config(
            text="Timetable cleared. Generate a new study plan."
        )

    def generate(self):

        title = self.title_entry.get().strip()

        if not title:
            messagebox.showwarning(
                "Missing Title",
                "Enter a study plan title."
            )
            return

        if not self.subjects:
            messagebox.showwarning(
                "No Subjects",
                "Please add at least one subject."
            )
            return

        try:
            exam_date = date.fromisoformat(
                self.date_entry.get().strip()
            )

            if exam_date <= date.today():
                messagebox.showerror(
                    "Invalid Exam Date",
                    "Exam date must be in the future."
                )
                return

            daily_hours = float(self.hours_var.get())

            if daily_hours <= 0:
                raise ValueError

        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                "Enter a valid future date and daily study hours."
            )
            return

        plan = PlanInput(
            title=title,
            exam_date=exam_date,
            daily_hours=daily_hours,
            difficulty=self.difficulty_var.get(),
            subjects=self.subjects.copy()
        )

        tasks = generate_schedule(plan)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for task in tasks:

            subject = task.subject if task.subject else "-"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    task.task_date.strftime("%d-%m-%Y"),
                    format_time(task.start_minute),
                    subject,
                    task.topic,
                    task.task_type.title(),
                    task.priority.title(),
                    f"{task.duration_minutes} min"
                ),
                tags=(task.task_type,)
            )

        study_blocks = [
            task for task in tasks
            if task.task_type != "break"
        ]

        self.summary.config(
            text=(
                f"{title} | {len(tasks)} total blocks | "
                f"{len(study_blocks)} study sessions | "
                f"{daily_hours} hours/day"
            )
        )

        messagebox.showinfo(
            "Study Plan Generated",
            f"Your personalized study timetable is ready!\n\n"
            f"Total blocks: {len(tasks)}\n"
            f"Study sessions: {len(study_blocks)}"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = StudyMateAI(root)
    root.mainloop()
