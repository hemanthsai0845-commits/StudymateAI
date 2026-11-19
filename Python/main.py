import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
import json, os, hashlib, re

APP_DIR = os.path.join(os.path.expanduser('~'), '.studymate_ai')
os.makedirs(APP_DIR, exist_ok=True)
USER_FILE = os.path.join(APP_DIR, 'users.json')
PLAN_FILE = os.path.join(APP_DIR, 'plans.json')
BG = '#f7f8fc'
WHITE = '#ffffff'
BLUE = '#2563eb'
PURPLE = '#7c3aed'
DARK = '#111827'
MUTED = '#64748b'
BORDER = '#e2e8f0'
GREEN = '#059669'

@dataclass
class Task:
    day: str
    start: int
    subject: str
    topic: str
    kind: str
    priority: str
    minutes: int
    completed: bool = False


def read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def password_hash(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def clock_text(minutes):
    hour, minute = divmod(minutes, 60)
    return f"{hour % 12 or 12}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"


def extract_file_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.txt':
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    if ext == '.pdf':
        try:
            from pypdf import PdfReader
            return '\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
        except ImportError:
            raise RuntimeError('To read PDF files, install pypdf using: py -m pip install pypdf')
    if ext == '.docx':
        try:
            from docx import Document
            return '\n'.join(p.text for p in Document(path).paragraphs)
        except ImportError:
            raise RuntimeError('To read DOCX files, install python-docx using: py -m pip install python-docx')
    if ext == '.pptx':
        try:
            from pptx import Presentation
            prs = Presentation(path)
            return '\n'.join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, 'text'))
        except ImportError:
            raise RuntimeError('To read PPTX files, install python-pptx using: py -m pip install python-pptx')
    raise RuntimeError('Please choose a PDF, DOCX, PPTX or TXT file.')


def detect_topics(text):
    lines = []
    for raw in text.splitlines():
        line = re.sub(r'\s+', ' ', raw).strip(' •\t-–')
        if 4 <= len(line) <= 90 and not re.fullmatch(r'[\d\W]+', line):
            if line.lower() not in {x.lower() for x in lines}:
                lines.append(line)
    if not lines:
        words = re.findall(r'[A-Za-z][A-Za-z ]{3,}', text)
        lines = [w.strip() for w in words[:12]]
    return lines[:20]


def make_schedule(plan):
    start = date.fromisoformat(plan['exam_date'])
    today = date.today()
    days = max(1, (start - today).days)
    daily_minutes = int(float(plan['hours']) * 60)
    confidence = plan.get('confidence', 'Know some of it')
    focus = 35 if confidence == 'Starting fresh' else 40 if confidence == 'Know some of it' else 45
    topics = []
    for subject in plan['subjects']:
        for topic in subject['topics']:
            topics.append((subject['name'], topic, subject['weight']))
    if not topics:
        return []
    tasks = []
    topic_index = 0
    learn_days = max(1, int(days * .72))
    for offset in range(days):
        current = today + timedelta(days=offset)
        remaining = daily_minutes
        minute = 8 * 60
        count = 0
        while remaining >= 25:
            if offset < learn_days:
                subject, topic, weight = topics[topic_index % len(topics)]
                kind = 'Learn' if count % 3 != 2 else 'Practice'
                label = topic if kind == 'Learn' else 'Practice: ' + topic
                priority = 'High' if weight == 3 else 'Medium' if weight == 2 else 'Low'
                topic_index += 1
            else:
                subject, topic, weight = topics[(offset + count) % len(topics)]
                kind = 'Revise' if count % 2 == 0 else 'Practice'
                label = ('Revise: ' if kind == 'Revise' else 'Practice: ') + topic
                priority = 'High' if weight == 3 else 'Medium' if weight == 2 else 'Low'
            duration = min(focus, remaining)
            tasks.append(Task(current.isoformat(), minute, subject, label, kind, priority, duration))
            minute += duration
            remaining -= duration
            count += 1
            if remaining >= 10:
                pause = min(15, remaining)
                tasks.append(Task(current.isoformat(), minute, '', 'Short break', 'Break', 'Low', pause))
                minute += pause
                remaining -= pause
        if offset >= learn_days and offset >= min(days - 1, learn_days):
            pass
    tasks.append(Task(start.isoformat(), 8 * 60, topics[0][0], 'Final look-over: ' + topics[0][1], 'Revise', 'High', 30))
    return [asdict(t) for t in sorted(tasks, key=lambda x: (x.day, x.start))]


class StudyMateApp:
    def __init__(self, root):
        self.root = root
        self.root.title('StudyMate AI')
        self.root.geometry('1180x790')
        self.root.minsize(900, 650)
        self.root.configure(bg=BG)
        self.users = read_json(USER_FILE, {})
        self.all_plans = read_json(PLAN_FILE, {})
        self.email = None
        self.current_plan = None
        self.subject_rows = []
        self.uploaded_topics = []
        self.show_auth()

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def card(self, parent, **kwargs):
        return tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1, **kwargs)

    def button(self, parent, text, command, primary=False, **kwargs):
        color = BLUE if primary else '#eef2ff'
        fg = WHITE if primary else '#1e40af'
        return tk.Button(parent, text=text, command=command, bg=color, fg=fg,
                         activebackground=PURPLE if primary else '#dbeafe', activeforeground=WHITE if primary else '#1e40af',
                         relief='flat', bd=0, cursor='hand2', font=('Segoe UI', 10, 'bold'), padx=16, pady=10, **kwargs)

    def show_auth(self):
        self.clear()
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(expand=True, fill='both')
        box = tk.Frame(outer, bg=BG)
        box.place(relx=.5, rely=.48, anchor='center', width=470)
        tk.Label(box, text='🎓', bg='#5b4be8', fg=WHITE, font=('Segoe UI Emoji', 27), width=3, height=1).pack(pady=(0, 15))
        tk.Label(box, text='StudyMate AI', bg=BG, fg=DARK, font=('Segoe UI', 25, 'bold')).pack()
        tk.Label(box, text='Your AI-powered study planner', bg=BG, fg=MUTED, font=('Segoe UI', 13)).pack(pady=(5, 28))
        panel = self.card(box)
        panel.pack(fill='x')
        tabs = tk.Frame(panel, bg='#f1f5f9')
        tabs.pack(fill='x', padx=28, pady=(28, 22))
        self.auth_mode = tk.StringVar(value='signin')
        self.auth_tabs = {}
        for mode, label in [('signin', 'Sign in'), ('signup', 'Create account')]:
            b = tk.Button(tabs, text=label, command=lambda m=mode: self.set_auth_mode(m), relief='flat', bd=0,
                          font=('Segoe UI', 10, 'bold'), pady=11, cursor='hand2')
            b.pack(side='left', expand=True, fill='x', padx=3, pady=3)
            self.auth_tabs[mode] = b
        form = tk.Frame(panel, bg=WHITE)
        form.pack(fill='x', padx=28, pady=(0, 28))
        tk.Label(form, text='Email', bg=WHITE, fg=DARK, font=('Segoe UI', 11)).pack(anchor='w')
        self.email_entry = self.entry(form, 'you@school.edu')
        self.email_entry.pack(fill='x', pady=(7, 18))
        tk.Label(form, text='Password', bg=WHITE, fg=DARK, font=('Segoe UI', 11)).pack(anchor='w')
        self.password_entry = tk.Entry(form, font=('Segoe UI', 11), show='•', relief='solid', bd=1, highlightthickness=0)
        self.password_entry.pack(fill='x', ipady=11, pady=(7, 20))
        self.auth_action = self.button(form, 'Sign in', self.authenticate, True)
        self.auth_action.pack(fill='x')
        self.set_auth_mode('signin')

    def entry(self, parent, placeholder=''):
        e = tk.Entry(parent, font=('Segoe UI', 11), relief='solid', bd=1, highlightthickness=0)
        if placeholder:
            e.insert(0, placeholder)
        return e

    def set_auth_mode(self, mode):
        self.auth_mode.set(mode)
        for key, b in self.auth_tabs.items():
            b.configure(bg=WHITE if key == mode else '#f1f5f9', fg=DARK if key == mode else MUTED)
        self.auth_action.configure(text='Sign in' if mode == 'signin' else 'Create account')

    def authenticate(self):
        email = self.email_entry.get().strip().lower()
        password = self.password_entry.get()
        if '@' not in email or len(password) < 6:
            messagebox.showwarning('Check details', 'Enter a valid email and a password with at least 6 characters.')
            return
        if self.auth_mode.get() == 'signup':
            if email in self.users:
                messagebox.showerror('Account exists', 'An account with this email already exists.')
                return
            self.users[email] = password_hash(password)
            write_json(USER_FILE, self.users)
            messagebox.showinfo('Account created', 'Your account has been created. You can now sign in.')
            self.set_auth_mode('signin')
        else:
            if self.users.get(email) != password_hash(password):
                messagebox.showerror('Sign in failed', 'Email or password is incorrect. Create an account if you are new.')
                return
            self.email = email
            self.show_dashboard() if self.all_plans.get(email) else self.show_plan_form()

    def topbar(self):
        bar = tk.Frame(self.root, bg=WHITE, height=62, highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill='x')
        tk.Label(bar, text='🎓  StudyMate AI', bg=WHITE, fg=DARK, font=('Segoe UI', 15, 'bold')).pack(side='left', padx=28, pady=14)
        tk.Label(bar, text=self.email or '', bg=WHITE, fg=MUTED, font=('Segoe UI', 10)).pack(side='right', padx=(10, 25))
        self.button(bar, '↪ Sign out', self.show_auth).pack(side='right', pady=10)

    def show_plan_form(self, plan=None):
        self.clear()
        self.topbar()
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill='both', expand=True)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(wrap, orient='vertical', command=canvas.yview)
        content = tk.Frame(canvas, bg=BG)
        content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=content, anchor='nw', width=1080)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True, padx=(35, 0), pady=20)
        scroll.pack(side='right', fill='y', padx=(0, 25), pady=20)
        tk.Label(content, text='Plan your path to exam success', bg=BG, fg=DARK, font=('Segoe UI', 23, 'bold')).pack(pady=(10, 5))
        tk.Label(content, text='Tell us your subjects, syllabus topics, exam date and how much time you can study each day.', bg=BG, fg=MUTED, font=('Segoe UI', 11)).pack(pady=(0, 22))
        panel = self.card(content)
        panel.pack(fill='x', padx=8, pady=5)
        inside = tk.Frame(panel, bg=WHITE)
        inside.pack(fill='x', padx=24, pady=22)
        tk.Label(inside, text='Plan name', bg=WHITE, fg=DARK, font=('Segoe UI', 11)).pack(anchor='w')
        self.plan_name = self.entry(inside, plan.get('title', 'Exam Prep Plan') if plan else 'Exam Prep Plan')
        self.plan_name.pack(fill='x', ipady=9, pady=(6, 16))
        row = tk.Frame(inside, bg=WHITE)
        row.pack(fill='x')
        left = tk.Frame(row, bg=WHITE)
        left.pack(side='left', fill='x', expand=True, padx=(0, 18))
        right = tk.Frame(row, bg=WHITE)
        right.pack(side='left', fill='x', expand=True)
        tk.Label(left, text='Exam date (YYYY-MM-DD)', bg=WHITE, fg=DARK, font=('Segoe UI', 11)).pack(anchor='w')
        self.exam_date = self.entry(left, plan.get('exam_date', (date.today()+timedelta(days=11)).isoformat()) if plan else (date.today()+timedelta(days=11)).isoformat())
        self.exam_date.pack(fill='x', ipady=9, pady=(6, 16))
        self.hours = tk.IntVar(value=int(plan.get('hours', 4)) if plan else 4)
        self.hours_label = tk.Label(right, text=f'Study hours per day: {self.hours.get()}', bg=WHITE, fg=DARK, font=('Segoe UI', 11))
        self.hours_label.pack(anchor='w')
        tk.Scale(right, from_=1, to=10, orient='horizontal', variable=self.hours, bg=WHITE, highlightthickness=0, troughcolor='#dbeafe', command=lambda v: self.hours_label.configure(text=f'Study hours per day: {int(float(v))}')).pack(fill='x', pady=(4, 16))
        tk.Label(inside, text='How confident are you with this material?', bg=WHITE, fg=DARK, font=('Segoe UI', 11)).pack(anchor='w', pady=(2, 8))
        self.confidence = tk.StringVar(value=plan.get('confidence', 'Know some of it') if plan else 'Know some of it')
        conf = tk.Frame(inside, bg=WHITE)
        conf.pack(fill='x', pady=(0, 18))
        for value, desc in [('Starting fresh', 'More time per topic'), ('Know some of it', 'Balanced pace'), ('Mostly confident', 'Faster, deeper practice')]:
            rb = tk.Radiobutton(conf, text=value+'\n'+desc, variable=self.confidence, value=value, bg=WHITE, fg=DARK, selectcolor='#eff6ff', font=('Segoe UI', 10), indicatoron=0, relief='solid', bd=1, padx=10, pady=10, anchor='w')
            rb.pack(side='left', expand=True, fill='x', padx=3)
        upload = tk.Frame(inside, bg='#f8fafc', highlightbackground=BORDER, highlightthickness=1)
        upload.pack(fill='x', pady=(0, 18))
        tk.Label(upload, text='Upload a syllabus or lecture file', bg='#f8fafc', fg=DARK, font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=14, pady=(12, 4))
        self.upload_status = tk.Label(upload, text='PDF, DOCX, PPTX or TXT · select a file to extract topics', bg='#f8fafc', fg=MUTED, font=('Segoe UI', 9))
        self.upload_status.pack(anchor='w', padx=14)
        self.button(upload, '＋  Choose file', self.upload_file).pack(anchor='w', padx=14, pady=10)
        self.summary_box = tk.Label(upload, text='', bg='#f8fafc', fg='#334155', justify='left', wraplength=950, font=('Segoe UI', 9))
        self.summary_box.pack(anchor='w', padx=14, pady=(0, 8))
        tk.Label(inside, text='Subjects & syllabus topics', bg=WHITE, fg=DARK, font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(5, 8))
        self.subject_area = tk.Frame(inside, bg=WHITE)
        self.subject_area.pack(fill='x')
        self.subject_rows = []
        if plan and plan.get('subjects'):
            for s in plan['subjects']:
                self.add_subject_row(s['name'], '\n'.join(s['topics']), s.get('weight', 2))
        else:
            self.add_subject_row()
        self.button(inside, '+ Add subject', self.add_subject_row).pack(anchor='e', pady=10)
        self.button(inside, '✨  Generate my study plan', self.generate_plan, True).pack(fill='x', pady=(8, 0))

    def add_subject_row(self, name='', topics='', weight=2):
        row = tk.Frame(self.subject_area, bg='#fbfcff', highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill='x', pady=5)
        top = tk.Frame(row, bg='#fbfcff')
        top.pack(fill='x', padx=12, pady=(10, 5))
        name_entry = self.entry(top, name)
        name_entry.pack(side='left', fill='x', expand=True, ipady=7, padx=(0, 8))
        weight_var = tk.StringVar(value={1:'Easy',2:'Moderate',3:'Hard'}.get(weight, 'Moderate'))
        ttk.Combobox(top, textvariable=weight_var, values=['Easy','Moderate','Hard'], state='readonly', width=12).pack(side='left')
        topics_text = tk.Text(row, height=3, font=('Segoe UI', 10), relief='solid', bd=1, wrap='word')
        topics_text.pack(fill='x', padx=12, pady=(2, 10))
        topics_text.insert('1.0', topics)
        record = {'frame':row, 'name':name_entry, 'topics':topics_text, 'weight':weight_var}
        self.subject_rows.append(record)

    def upload_file(self):
        path = filedialog.askopenfilename(filetypes=[('Study files', '*.pdf *.docx *.pptx *.txt'), ('All files', '*.*')])
        if not path:
            return
        try:
            text = extract_file_text(path)
            self.uploaded_topics = detect_topics(text)
            self.upload_status.configure(text=os.path.basename(path) + '  ·  Read successfully', fg=GREEN)
            self.summary_box.configure(text='Extracted text preview: ' + re.sub(r'\s+', ' ', text)[:500] + ('...' if len(text) > 500 else ''))
            if self.subject_rows:
                first = self.subject_rows[0]
                if not first['name'].get().strip():
                    first['name'].insert(0, os.path.splitext(os.path.basename(path))[0])
                first['topics'].delete('1.0', 'end')
                first['topics'].insert('1.0', '\n'.join(self.uploaded_topics))
            messagebox.showinfo('Syllabus processed', f'{len(self.uploaded_topics)} possible topics were extracted. Review and edit them before generating the plan.')
        except Exception as exc:
            messagebox.showerror('File upload', str(exc))

    def generate_plan(self):
        title = self.plan_name.get().strip()
        if not title:
            messagebox.showwarning('Plan name required', 'Enter a name for your study plan.')
            return
        try:
            exam = date.fromisoformat(self.exam_date.get().strip())
            if exam <= date.today():
                raise ValueError
        except ValueError:
            messagebox.showerror('Invalid date', 'Enter a future exam date in YYYY-MM-DD format.')
            return
        subjects = []
        for row in self.subject_rows:
            name = row['name'].get().strip()
            topics = [x.strip(' •\t-') for x in row['topics'].get('1.0', 'end').splitlines() if x.strip(' •\t-')]
            if name and topics:
                subjects.append({'name':name, 'topics':topics, 'weight':{'Easy':1,'Moderate':2,'Hard':3}[row['weight'].get()]})
        if not subjects:
            messagebox.showwarning('Add subjects', 'Add at least one subject and one topic.')
            return
        plan = {'id':str(int(datetime.now().timestamp())), 'title':title, 'exam_date':exam.isoformat(), 'hours':self.hours.get(), 'confidence':self.confidence.get(), 'subjects':subjects}
        plan['tasks'] = make_schedule(plan)
        plans = self.all_plans.setdefault(self.email, [])
        plans.insert(0, plan)
        self.all_plans[self.email] = plans
        write_json(PLAN_FILE, self.all_plans)
        self.current_plan = plan
        self.show_dashboard()

    def show_dashboard(self):
        self.clear()
        self.topbar()
        plans = self.all_plans.get(self.email, [])
        if not plans:
            self.show_plan_form()
            return
        if self.current_plan is None or self.current_plan not in plans:
            self.current_plan = plans[0]
        self.render_dashboard()

    def render_dashboard(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True, padx=28, pady=22)
        side = tk.Frame(body, bg=BG, width=285)
        side.pack(side='left', fill='y', padx=(0, 20))
        side.pack_propagate(False)
        main = tk.Frame(body, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        plan = self.current_plan
        tasks = plan['tasks']
        completed = sum(1 for t in tasks if t.get('completed'))
        total_study = sum(1 for t in tasks if t['kind'] != 'Break')
        progress = int(completed / max(1,total_study) * 100)
        exam = date.fromisoformat(plan['exam_date'])
        days_left = max(0, (exam-date.today()).days)
        hero = tk.Frame(side, bg='#5146e5')
        hero.pack(fill='x', pady=(0, 14))
        tk.Label(hero, text=plan['title'], bg='#5146e5', fg=WHITE, font=('Segoe UI', 15, 'bold'), wraplength=240).pack(anchor='w', padx=17, pady=(17, 5))
        tk.Label(hero, text=f'▦  Exam {exam.strftime("%a, %b %d")} · {days_left} days left', bg='#5146e5', fg='#e0e7ff', font=('Segoe UI', 9)).pack(anchor='w', padx=17, pady=3)
        actions = tk.Frame(hero, bg='#5146e5')
        actions.pack(fill='x', padx=12, pady=13)
        tk.Button(actions, text='✎ Edit plan', command=lambda:self.show_plan_form(plan), bg='#7169ed', fg=WHITE, relief='flat', padx=8, pady=8).pack(side='left', expand=True, fill='x', padx=3)
        tk.Button(actions, text='↻ Regenerate', command=self.regenerate, bg='#7169ed', fg=WHITE, relief='flat', padx=8, pady=8).pack(side='left', expand=True, fill='x', padx=3)
        self.stat_card(side, 'Plan completion', f'{progress}%', f'{completed} of {total_study} study sessions completed')
        grid = tk.Frame(side, bg=BG)
        grid.pack(fill='x', pady=7)
        self.mini_stat(grid, '◎', f'{progress}%', 'Overall progress', '#2563eb', 0, 0)
        hours_done = sum(t['minutes'] for t in tasks if t.get('completed'))/60
        self.mini_stat(grid, '☷', f'{plan["hours"]}h', 'Study time planned', '#8b5cf6', 0, 1)
        self.mini_stat(grid, '♨', '0 days', 'Current streak', '#f97316', 1, 0)
        self.mini_stat(grid, '↗', str(total_study-completed), 'Sessions left', '#059669', 1, 1)
        tk.Label(side, text='Saved plans', bg=BG, fg=DARK, font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(14, 7))
        for p in self.all_plans.get(self.email, [])[:4]:
            tk.Button(side, text=p['title']+'\nExam '+date.fromisoformat(p['exam_date']).strftime('%b %d'), anchor='w', bg='#eff6ff' if p is plan else WHITE, fg='#1d4ed8', relief='flat', padx=12, pady=10, command=lambda x=p:self.switch_plan(x)).pack(fill='x', pady=3)
        self.button(side, '+ New study plan', lambda:self.show_plan_form()).pack(fill='x', pady=(12, 0))
        cal = self.card(main)
        cal.pack(fill='x', pady=(0, 18))
        month = date.today().replace(day=1)
        tk.Label(cal, text=month.strftime('%B %Y'), bg=WHITE, fg=DARK, font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=18, pady=14)
        calgrid = tk.Frame(cal, bg=WHITE)
        calgrid.pack(fill='x', padx=16, pady=(0, 14))
        for c, dayname in enumerate(['S','M','T','W','T','F','S']):
            tk.Label(calgrid, text=dayname, bg=WHITE, fg='#94a3b8', width=8, font=('Segoe UI', 9)).grid(row=0,column=c,pady=5)
        import calendar
        weeks = calendar.monthcalendar(month.year, month.month)
        for r, week in enumerate(weeks, start=1):
            for c, daynum in enumerate(week):
                if daynum:
                    d = date(month.year, month.month, daynum).isoformat()
                    count = sum(1 for t in tasks if t['day']==d)
                    active = daynum == date.today().day
                    tk.Label(calgrid, text=str(daynum)+('\n•••' if count else ''), bg=BLUE if active else WHITE, fg=WHITE if active else DARK, width=8, height=2, font=('Segoe UI', 9)).grid(row=r,column=c,pady=2)
        selected_day = date.today().isoformat()
        todays = [t for t in tasks if t['day'] == selected_day]
        if not todays:
            upcoming = [t for t in tasks if t['day'] >= selected_day]
            if upcoming:
                selected_day = upcoming[0]['day']
                todays = [t for t in tasks if t['day'] == selected_day]
        heading = datetime.fromisoformat(selected_day).strftime('%A, %B %d') if selected_day else 'Study sessions'
        head = tk.Frame(main, bg=BG)
        head.pack(fill='x', pady=(0, 10))
        tk.Label(head, text=heading, bg=BG, fg=DARK, font=('Segoe UI', 15, 'bold')).pack(side='left')
        tk.Label(head, text=f'{sum(1 for t in todays if t.get("completed"))}/{sum(1 for t in todays if t["kind"]!="Break")} study sessions done', bg=BG, fg=MUTED, font=('Segoe UI', 9)).pack(side='right')
        session_canvas = tk.Canvas(main, bg=BG, highlightthickness=0)
        sy = ttk.Scrollbar(main, orient='vertical', command=session_canvas.yview)
        session_frame = tk.Frame(session_canvas, bg=BG)
        session_frame.bind('<Configure>', lambda e: session_canvas.configure(scrollregion=session_canvas.bbox('all')))
        session_window = session_canvas.create_window((0,0), window=session_frame, anchor='nw')
        session_canvas.bind('<Configure>', lambda e: session_canvas.itemconfigure(session_window, width=e.width))
        session_canvas.configure(yscrollcommand=sy.set)
        session_canvas.pack(side='left', fill='both', expand=True)
        sy.pack(side='right', fill='y')
        for task in todays:
            self.session_card(session_frame, task)

    def stat_card(self, parent, title, value, note):
        c = self.card(parent); c.pack(fill='x', pady=(0,10))
        tk.Label(c,text=title,bg=WHITE,fg=DARK,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=15,pady=(12,2))
        tk.Label(c,text=value,bg=WHITE,fg=BLUE,font=('Segoe UI',18,'bold')).pack(anchor='w',padx=15)
        tk.Label(c,text=note,bg=WHITE,fg=MUTED,font=('Segoe UI',9),wraplength=250).pack(anchor='w',padx=15,pady=(2,12))

    def mini_stat(self, parent, icon, value, label, color, r, c):
        box = self.card(parent); box.grid(row=r,column=c,sticky='nsew',padx=4,pady=4)
        parent.grid_columnconfigure(c,weight=1)
        tk.Label(box,text=icon,bg=color,fg=WHITE,font=('Segoe UI',13,'bold'),width=2).pack(anchor='w',padx=10,pady=(10,5))
        tk.Label(box,text=value,bg=WHITE,fg=DARK,font=('Segoe UI',16,'bold')).pack(anchor='w',padx=10)
        tk.Label(box,text=label,bg=WHITE,fg=MUTED,font=('Segoe UI',8),wraplength=105).pack(anchor='w',padx=10,pady=(0,10))

    def session_card(self, parent, task):
        done = task.get('completed', False)
        color = '#f0fdf4' if done else WHITE
        border = '#a7f3d0' if done else BORDER
        card = tk.Frame(parent, bg=color, highlightbackground=border, highlightthickness=1)
        card.pack(fill='x', pady=5)
        line = tk.Frame(card, bg=color)
        line.pack(fill='x', padx=12, pady=12)
        var = tk.BooleanVar(value=done)
        def toggle():
            task['completed'] = var.get()
            write_json(PLAN_FILE, self.all_plans)
            self.show_dashboard()
        tk.Checkbutton(line, variable=var, command=toggle, bg=color, activebackground=color, fg=GREEN, selectcolor=color).pack(side='left', padx=(0,8))
        center = tk.Frame(line, bg=color)
        center.pack(side='left', fill='x', expand=True)
        title = task['topic']
        tk.Label(center, text=title, bg=color, fg=DARK, font=('Segoe UI', 10, 'bold' if not done else 'normal'), anchor='w').pack(anchor='w')
        details = f"{clock_text(task['start'])} · {task['minutes']} min"
        if task['subject']:
            details += '   |   ' + task['subject']
        tk.Label(center, text=details, bg=color, fg=MUTED, font=('Segoe UI', 9), anchor='w').pack(anchor='w', pady=(3,0))
        tk.Label(line, text=task['kind']+'  ·  '+task['priority'], bg='#eff6ff' if task['kind']!='Break' else '#f1f5f9', fg='#1d4ed8' if task['kind']!='Break' else MUTED, font=('Segoe UI', 8), padx=8, pady=5).pack(side='right')

    def switch_plan(self, plan):
        self.current_plan = plan
        self.show_dashboard()

    def regenerate(self):
        self.current_plan['tasks'] = make_schedule(self.current_plan)
        write_json(PLAN_FILE, self.all_plans)
        self.show_dashboard()


if __name__ == '__main__':
    root = tk.Tk()
    app = StudyMateApp(root)
    root.mainloop()
