
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass
from datetime import date, timedelta
import csv

WEIGHT_TO_PRIORITY = {
    1: "Low",
    2: "Medium",
    3: "High"
}

DIFF_FACTOR = {
    "Beginner": 1.3,
    "Intermediate": 1.1,
    "Advanced": 0.9
}

BASE_SESSION_MIN = 40


@dataclass
class SubjectInput:
    name: str
    topics: list
    weight: int


@dataclass
class PlanInput:
    title: str
    exam_date: date
    daily_hours: float
    difficulty: str
    subjects: list


@dataclass
class StudyTask:
    task_date: date
    start_minute: int
    subject: str
    topic: str
    task_type: str
    priority: str
    duration_minutes: int


@dataclass
class TopicQueueItem:
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

    focus_span = max(
        25,
        min(50, round(BASE_SESSION_MIN / factor))
    )

    start = date.today()

    days = max(
        1,
        (plan.exam_date - start).days
    )

    learn_phase_days = max(
        1,
        round(days * 0.75)
    )

    queue = []

    for subject in plan.subjects:

        weight = min(3, max(1, subject.weight))

        for topic in subject.topics:

            sessions = max(
                1,
                round(weight * factor)
            )

            queue.append(
                TopicQueueItem(
                    subject=subject.name,
                    topic=topic,
                    weight=weight,
                    priority=WEIGHT_TO_PRIORITY[weight],
                    sessions_needed=sessions
                )
            )

    queue.sort(
        key=lambda q: (-q.weight, q.subject)
    )

    tasks = []

    queue_idx = 0
    sessions_placed = 0

    for day in range(days):

        current_date = start + timedelta(days=day)

        revision_phase = day >= learn_phase_days

        remaining = daily_minutes
        start_minute = 8 * 60
        sessions_today = 0

        while remaining >= 25:

            block = None
            task_type = "Learn"
            subject_name = ""
            label = ""
            priority = "Medium"
            duration = focus_span

            if not revision_phase:

                practice_due = (
                    sessions_placed > 0
                    and sessions_placed % 3 == 0
                    and queue_idx > 0
                )

                if practice_due:

                    block = queue[queue_idx - 1]

                    task_type = "Practice"

                    label = f"Practice: {block.topic}"

                    subject_name = block.subject

                    priority = block.priority

                else:

                    if queue_idx >= len(queue):
                        break

                    block = queue[queue_idx]

                    task_type = "Learn"

                    label = block.topic

                    subject_name = block.subject

                    priority = block.priority

            else:

                covered = queue[:queue_idx]

                if not covered:
                    break

                block = covered[day % len(covered)]

                revise = sessions_today % 2 == 0

                task_type = (
                    "Revise" if revise else "Practice"
                )

                label = (
                    f"Revise: {block.topic}"
                    if revise
                    else f"Practice: {block.topic}"
                )

                subject_name = block.subject

                priority = block.priority

                if revise:
                    duration = round(focus_span * 0.8)

            if (
                block is not None
                and task_type == "Learn"
                and not revision_phase
            ):

                block.done += 1

                if block.done >= block.sessions_needed:
                    queue_idx += 1

            sessions_placed += 1

            duration = min(duration, remaining)

            tasks.append(
                StudyTask(
                    task_date=current_date,
                    start_minute=start_minute,
                    subject=subject_name,
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

                break_minutes = min(15, remaining)

                tasks.append(
                    StudyTask(
                        task_date=current_date,
                        start_minute=start_minute,
                        subject="",
                        topic="Short Break",
                        task_type="Break",
                        priority="Low",
                        duration_minutes=break_minutes
                    )
                )

                start_minute += break_minutes
                remaining -= break_minutes

        if queue_idx >= len(queue) and revision_phase:
            break

    if queue:

        first = queue[0]

        tasks.append(
            StudyTask(
                task_date=plan.exam_date,
                start_minute=8 * 60,
                subject=first.subject,
                topic=f"Final Look-over: {first.topic}",
                task_type="Revise",
                priority="High",
                duration_minutes=30
            )
        )

    tasks.sort(
        key=lambda t: (t.task_date, t.start_minute)
    )

    return tasks


class StudyMateAI:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "StudyMate AI - Smart Study Planner"
        )

        self.root.geometry("1200x760")

        self.root.minsize(1000, 650)

        self.root.configure(bg="#F1F5F9")

        self.subjects = []
        self.tasks = []

        self.setup_style()
        self.create_interface()

    def setup_style(self):

        style = ttk.Style()

        style.theme_use("clam")

        style.configure(
            "Treeview",
            background="white",
            foreground="#1E293B",
            rowheight=32,
            fieldbackground="white",
            font=("Segoe UI", 9)
        )

        style.configure(
            "Treeview.Heading",
            background="#E2E8F0",
            foreground="#172554",
            font=("Segoe UI", 9, "bold"),
            padding=8
        )

        style.map(
            "Treeview",
            background=[("selected", "#BFDBFE")],
            foreground=[("selected", "#172554")]
        )

        style.configure(
            "TButton",
            font=("Segoe UI", 9, "bold"),
            padding=7
        )

        style.configure(
            "TLabel",
            font=("Segoe UI", 9)
        )

        style.configure(
            "TLabelframe.Label",
            font=("Segoe UI", 10, "bold"),
            foreground="#172554"
        )

    def create_interface(self):

        header = tk.Frame(
            self.root,
            bg="#172554",
            height=100
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="StudyMate AI",
            font=("Segoe UI", 26, "bold"),
            bg="#172554",
            fg="white"
        ).pack(pady=(15, 0))

        tk.Label(
            header,
            text="Your Personal AI Study Planner",
            font=("Segoe UI", 10),
            bg="#172554",
            fg="#BFDBFE"
        ).pack()

        main = tk.Frame(
            self.root,
            bg="#F1F5F9"
        )

        main.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=15
        )

        left = tk.Frame(
            main,
            bg="white",
            width=340
        )

        left.pack(
            side="left",
            fill="y",
            padx=(0, 12)
        )

        left.pack_propagate(False)

        right = tk.Frame(
            main,
            bg="white"
        )

        right.pack(
            side="right",
            fill="both",
            expand=True
        )

        self.create_input_panel(left)
        self.create_timetable_panel(right)

        footer = tk.Label(
            self.root,
            text="Study Smarter | Stay Organized | Achieve More",
            bg="#172554",
            fg="white",
            font=("Segoe UI", 9),
            pady=8
        )

        footer.pack(fill="x", side="bottom")

    def create_input_panel(self, parent):

        tk.Label(
            parent,
            text="STUDY PLAN DETAILS",
            font=("Segoe UI", 14, "bold"),
            bg="white",
            fg="#172554"
        ).pack(anchor="w", padx=15, pady=(15, 12))

        form = tk.Frame(parent, bg="white")
        form.pack(fill="x", padx=15)

        def add_label(text):

            tk.Label(
                form,
                text=text,
                bg="white",
                fg="#334155",
                font=("Segoe UI", 9, "bold")
            ).pack(anchor="w", pady=(7, 3))

        add_label("Study Plan Title")

        self.title_entry = ttk.Entry(form)
        self.title_entry.pack(fill="x")
        self.title_entry.insert(0, "Final Exam Preparation")

        add_label("Exam Date (YYYY-MM-DD)")

        self.date_entry = ttk.Entry(form)
        self.date_entry.pack(fill="x")

        self.date_entry.insert(
            0,
            (date.today() + timedelta(days=10)).isoformat()
        )

        add_label("Daily Study Hours")

        self.hours_var = tk.StringVar(value="4")

        ttk.Combobox(
            form,
            textvariable=self.hours_var,
            values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            state="readonly"
        ).pack(fill="x")

        add_label("Learning Difficulty")

        self.difficulty_var = tk.StringVar(
            value="Intermediate"
        )

        ttk.Combobox(
            form,
            textvariable=self.difficulty_var,
            values=["Beginner", "Intermediate", "Advanced"],
            state="readonly"
        ).pack(fill="x")

        separator = ttk.Separator(
            parent,
            orient="horizontal"
        )

        separator.pack(
            fill="x",
            padx=15,
            pady=12
        )

        tk.Label(
            parent,
            text="ADD SUBJECTS",
            font=("Segoe UI", 12, "bold"),
            bg="white",
            fg="#172554"
        ).pack(anchor="w", padx=15, pady=5)

        subject_form = tk.Frame(parent, bg="white")
        subject_form.pack(fill="x", padx=15)

        tk.Label(
            subject_form,
            text="Subject Name",
            bg="white"
        ).pack(anchor="w")

        self.subject_entry = ttk.Entry(subject_form)
        self.subject_entry.pack(fill="x", pady=3)

        tk.Label(
            subject_form,
            text="Topics (separate with commas)",
            bg="white"
        ).pack(anchor="w", pady=(5, 0))

        self.topics_entry = ttk.Entry(subject_form)
        self.topics_entry.pack(fill="x", pady=3)

        tk.Label(
            subject_form,
            text="Subject Difficulty",
            bg="white"
        ).pack(anchor="w", pady=(5, 0))

        self.weight_var = tk.StringVar(value="3 - Hard")

        ttk.Combobox(
            subject_form,
            textvariable=self.weight_var,
            values=[
                "1 - Easy",
                "2 - Moderate",
                "3 - Hard"
            ],
            state="readonly"
        ).pack(fill="x", pady=3)

        ttk.Button(
            subject_form,
            text="+ Add Subject",
            command=self.add_subject
        ).pack(fill="x", pady=8)

        tk.Label(
            parent,
            text="YOUR SUBJECTS",
            font=("Segoe UI", 10, "bold"),
            bg="white",
            fg="#172554"
        ).pack(anchor="w", padx=15, pady=(5, 3))

        self.subject_tree = ttk.Treeview(
            parent,
            columns=("subject", "topics", "weight"),
            show="headings",
            height=5
        )

        self.subject_tree.heading(
            "subject",
            text="Subject"
        )

        self.subject_tree.heading(
            "topics",
            text="Topics"
        )

        self.subject_tree.heading(
            "weight",
            text="Level"
        )

        self.subject_tree.column(
            "subject", width=125
        )

        self.subject_tree.column(
            "topics", width=55, anchor="center"
        )

        self.subject_tree.column(
            "weight", width=75, anchor="center"
        )

        self.subject_tree.pack(
            fill="x",
            padx=15,
            pady=3
        )

        ttk.Button(
            parent,
            text="Remove Selected Subject",
            command=self.remove_subject
        ).pack(fill="x", padx=15, pady=5)

        ttk.Button(
            parent,
            text="GENERATE STUDY PLAN",
            command=self.generate
        ).pack(fill="x", padx=15, pady=(12, 5))

        ttk.Button(
            parent,
            text="Clear All",
            command=self.clear_all
        ).pack(fill="x", padx=15, pady=3)

    def create_timetable_panel(self, parent):

        tk.Label(
            parent,
            text="YOUR PERSONALIZED TIMETABLE",
            font=("Segoe UI", 16, "bold"),
            bg="white",
            fg="#172554"
        ).pack(anchor="w", padx=15, pady=(15, 5))

        self.summary = tk.Label(
            parent,
            text="Add subjects and generate your study plan.",
            font=("Segoe UI", 9),
            bg="white",
            fg="#64748B"
        )

        self.summary.pack(
            anchor="w",
            padx=15,
            pady=(0, 12)
        )

        stats = tk.Frame(
            parent,
            bg="white"
        )

        stats.pack(fill="x", padx=15, pady=5)

        self.total_label = self.create_stat(
            stats, "TOTAL BLOCKS", "0"
        )

        self.study_label = self.create_stat(
            stats, "STUDY SESSIONS", "0"
        )

        self.break_label = self.create_stat(
            stats, "BREAKS", "0"
        )

        table_frame = tk.Frame(
            parent,
            bg="white"
        )

        table_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=10
        )

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
            "date": 95,
            "time": 85,
            "subject": 105,
            "topic": 190,
            "type": 85,
            "priority": 75,
            "duration": 75
        }

        for col in columns:

            self.tree.heading(
                col,
                text=headings[col]
            )

            self.tree.column(
                col,
                width=widths[col],
                minwidth=55,
                anchor="center"
            )

        scroll_y = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.tree.yview
        )

        scroll_x = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )

        self.tree.pack(
            side="top",
            fill="both",
            expand=True
        )

        scroll_y.pack(
            side="right",
            fill="y"
        )

        scroll_x.pack(
            side="bottom",
            fill="x"
        )

        self.tree.tag_configure(
            "Learn",
            background="#DBEAFE"
        )

        self.tree.tag_configure(
            "Practice",
            background="#FEF3C7"
        )

        self.tree.tag_configure(
            "Revise",
            background="#DCFCE7"
        )

        self.tree.tag_configure(
            "Break",
            background="#F1F5F9"
        )

        ttk.Button(
            parent,
            text="Export Timetable to CSV",
            command=self.export_csv
        ).pack(anchor="e", padx=15, pady=(0, 15))

    def create_stat(self, parent, title, value):

        card = tk.Frame(
            parent,
            bg="#EFF6FF",
            padx=12,
            pady=8
        )

        card.pack(
            side="left",
            fill="x",
            expand=True,
            padx=4
        )

        tk.Label(
            card,
            text=title,
            bg="#EFF6FF",
            fg="#475569",
            font=("Segoe UI", 8, "bold")
        ).pack()

        label = tk.Label(
            card,
            text=value,
            bg="#EFF6FF",
            fg="#1D4ED8",
            font=("Segoe UI", 17, "bold")
        )

        label.pack()

        return label

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
                "Invalid Topics",
                "Enter at least one topic."
            )

            return

        if any(s.name.lower() == name.lower() for s in self.subjects):

            messagebox.showwarning(
                "Duplicate Subject",
                "This subject has already been added."
            )

            return

        weight = int(self.weight_var.get()[0])

        subject = SubjectInput(
            name=name,
            topics=topics,
            weight=weight
        )

        self.subjects.append(subject)

        self.subject_tree.insert(
            "",
            "end",
            values=(
                name,
                len(topics),
                WEIGHT_TO_PRIORITY[weight]
            )
        )

        self.subject_entry.delete(0, tk.END)
        self.topics_entry.delete(0, tk.END)

    def remove_subject(self):

        selected = self.subject_tree.selection()

        if not selected:

            messagebox.showwarning(
                "Select Subject",
                "Select a subject to remove."
            )

            return

        for item in selected:

            index = self.subject_tree.index(item)

            self.subjects.pop(index)

            self.subject_tree.delete(item)

    def generate(self):

        title = self.title_entry.get().strip()

        if not title:

            messagebox.showwarning(
                "Missing Title",
                "Enter your study plan title."
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
                    "Please enter a future exam date."
                )

                return

            daily_hours = float(self.hours_var.get())

            if daily_hours <= 0 or daily_hours > 24:
                raise ValueError

        except ValueError:

            messagebox.showerror(
                "Invalid Input",
                "Check the exam date and daily study hours."
            )

            return

        plan = PlanInput(
            title=title,
            exam_date=exam_date,
            daily_hours=daily_hours,
            difficulty=self.difficulty_var.get(),
            subjects=self.subjects.copy()
        )

        self.tasks = generate_schedule(plan)

        self.display_timetable(plan)

    def display_timetable(self, plan):

        for item in self.tree.get_children():
            self.tree.delete(item)

        for task in self.tasks:

            self.tree.insert(
                "",
                "end",
                values=(
                    task.task_date.strftime("%d-%m-%Y"),
                    format_time(task.start_minute),
                    task.subject if task.subject else "-",
                    task.topic,
                    task.task_type,
                    task.priority,
                    f"{task.duration_minutes} min"
                ),
                tags=(task.task_type,)
            )

        study_sessions = sum(
            1 for t in self.tasks
            if t.task_type != "Break"
        )

        breaks = sum(
            1 for t in self.tasks
            if t.task_type == "Break"
        )

        self.total_label.config(
            text=str(len(self.tasks))
        )

        self.study_label.config(
            text=str(study_sessions)
        )

        self.break_label.config(
            text=str(breaks)
        )

        self.summary.config(
            text=(
                f"{plan.title} | "
                f"{plan.exam_date} | "
                f"{plan.daily_hours} hours/day | "
                f"{plan.difficulty}"
            )
        )

        messagebox.showinfo(
            "Study Plan Generated",
            "Your personalized study timetable is ready!\n\n"
            f"Total Blocks: {len(self.tasks)}\n"
            f"Study Sessions: {study_sessions}\n"
            f"Breaks: {breaks}"
        )

    def export_csv(self):

        if not self.tasks:

            messagebox.showwarning(
                "No Timetable",
                "Generate a study plan before exporting."
            )

            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="StudyMateAI_Timetable.csv"
        )

        if not filename:
            return

        try:

            with open(
                filename,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "Date",
                    "Start Time",
                    "Subject",
                    "Topic",
                    "Task Type",
                    "Priority",
                    "Duration"
                ])

                for task in self.tasks:

                    writer.writerow([
                        task.task_date,
                        format_time(task.start_minute),
                        task.subject,
                        task.topic,
                        task.task_type,
                        task.priority,
                        task.duration_minutes
                    ])

            messagebox.showinfo(
                "Export Successful",
                "Your timetable has been exported successfully."
            )

        except OSError as error:

            messagebox.showerror(
                "Export Error",
                str(error)
            )

    def clear_all(self):

        if not messagebox.askyesno(
            "Clear All",
            "Are you sure you want to clear all subjects and timetable?"
        ):
            return

        self.subjects.clear()
        self.tasks.clear()

        for item in self.subject_tree.get_children():
            self.subject_tree.delete(item)

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.total_label.config(text="0")
        self.study_label.config(text="0")
        self.break_label.config(text="0")

        self.summary.config(
            text="Add subjects and generate your study plan."
        )


if __name__ == "__main__":

    root = tk.Tk()

    app = StudyMateAI(root)

    root.mainloop()
