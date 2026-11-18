
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class StudyPlanner {

    enum Difficulty {
        BEGINNER(1.3),
        INTERMEDIATE(1.1),
        ADVANCED(0.9);

        final double factor;

        Difficulty(double factor) {
            this.factor = factor;
        }
    }

    enum TaskType {
        LEARN, PRACTICE, REVISE, BREAK
    }

    public record SubjectInput(
            String name,
            List<String> topics,
            int weight
    ) {}

    public record PlanInput(
            String title,
            LocalDate examDate,
            double dailyHours,
            Difficulty difficulty,
            List<SubjectInput> subjects
    ) {}

    public record StudyTask(
            LocalDate taskDate,
            int startMinute,
            String subject,
            String topic,
            TaskType taskType,
            String priority,
            int durationMinutes,
            boolean completed
    ) {}

    static class TopicQueueItem {
        final String subject;
        final String topic;
        final int weight;
        final String priority;
        final int sessionsNeeded;
        int done = 0;

        TopicQueueItem(
                String subject,
                String topic,
                int weight,
                int sessionsNeeded
        ) {
            this.subject = subject;
            this.topic = topic;
            this.weight = weight;
            this.priority = weight == 1 ? "low"
                    : weight == 2 ? "medium" : "high";
            this.sessionsNeeded = sessionsNeeded;
        }
    }

    public static String formatTime(int minutes) {
        int h = minutes / 60;
        int m = minutes % 60;
        int hr12 = h % 12 == 0 ? 12 : h % 12;

        return String.format(
                "%d:%02d %s",
                hr12,
                m,
                h >= 12 ? "PM" : "AM"
        );
    }

    public static List<StudyTask> generateSchedule(PlanInput plan) {

        if (plan == null || plan.title() == null
                || plan.examDate() == null
                || plan.difficulty() == null
                || plan.subjects() == null
                || plan.subjects().isEmpty()
                || plan.dailyHours() <= 0
                || plan.examDate().isBefore(LocalDate.now().plusDays(1))) {
            throw new IllegalArgumentException(
                    "Invalid study plan details."
            );
        }

        int dailyMinutes = Math.max(
                60,
                (int) Math.round(plan.dailyHours() * 60)
        );

        double factor = plan.difficulty().factor;

        int focusSpan = Math.max(
                25,
                Math.min(50, (int) Math.round(40 / factor))
        );

        LocalDate start = LocalDate.now();

        int days = (int) Math.max(
                1,
                ChronoUnit.DAYS.between(start, plan.examDate())
        );

        int learnPhaseDays = Math.max(
                1,
                (int) Math.round(days * 0.75)
        );

        List<TopicQueueItem> queue = new ArrayList<>();

        for (SubjectInput s : plan.subjects()) {

            if (s.name() == null || s.name().isBlank()
                    || s.topics() == null || s.topics().isEmpty()) {
                throw new IllegalArgumentException(
                        "Every subject must have a name and topics."
                );
            }

            int weight = Math.min(3, Math.max(1, s.weight()));

            for (String topic : s.topics()) {

                if (topic == null || topic.isBlank()) {
                    continue;
                }

                int sessions = Math.max(
                        1,
                        (int) Math.round(weight * factor)
                );

                queue.add(
                        new TopicQueueItem(
                                s.name(),
                                topic,
                                weight,
                                sessions
                        )
                );
            }
        }

        queue.sort(
                Comparator.comparingInt(
                        (TopicQueueItem q) -> -q.weight
                ).thenComparing(q -> q.subject)
        );

        List<StudyTask> tasks = new ArrayList<>();

        int queueIdx = 0;
        int sessionsPlaced = 0;

        for (int day = 0; day < days; day++) {

            LocalDate iso = start.plusDays(day);

            boolean revisionPhase = day >= learnPhaseDays;

            int remaining = dailyMinutes;
            int startMinute = 8 * 60;
            int sessionsToday = 0;

            while (remaining >= 25) {

                TopicQueueItem block;
                TaskType taskType;
                String label;
                String priority;
                int duration = focusSpan;

                if (!revisionPhase) {

                    boolean practiceDue =
                            sessionsPlaced > 0
                            && sessionsPlaced % 3 == 0
                            && queueIdx > 0;

                    if (practiceDue) {

                        block = queue.get(queueIdx - 1);

                        taskType = TaskType.PRACTICE;

                        label = "Practice: " + block.topic;

                        priority = block.priority;

                    } else {

                        if (queueIdx >= queue.size()) {
                            break;
                        }

                        block = queue.get(queueIdx);

                        taskType = TaskType.LEARN;

                        label = block.topic;

                        priority = block.priority;
                    }

                } else {

                    if (queueIdx == 0) {
                        break;
                    }

                    List<TopicQueueItem> covered =
                            queue.subList(0, queueIdx);

                    TopicQueueItem pick =
                            covered.get(day % covered.size());

                    block = pick;

                    boolean revise = sessionsToday % 2 == 0;

                    taskType = revise
                            ? TaskType.REVISE
                            : TaskType.PRACTICE;

                    label = (revise ? "Revise: " : "Practice: ")
                            + pick.topic;

                    priority = pick.priority;

                    duration = revise
                            ? (int) Math.round(focusSpan * 0.8)
                            : focusSpan;
                }

                if (taskType == TaskType.LEARN
                        && !revisionPhase) {

                    block.done++;

                    if (block.done >= block.sessionsNeeded) {
                        queueIdx++;
                    }
                }

                sessionsPlaced++;

                duration = Math.min(duration, remaining);

                tasks.add(
                        new StudyTask(
                                iso,
                                startMinute,
                                block.subject,
                                label,
                                taskType,
                                priority,
                                duration,
                                false
                        )
                );

                startMinute += duration;
                remaining -= duration;
                sessionsToday++;

                if (remaining >= 10) {

                    int breakMin = Math.min(15, remaining);

                    tasks.add(
                            new StudyTask(
                                    iso,
                                    startMinute,
                                    null,
                                    "Short break",
                                    TaskType.BREAK,
                                    "low",
                                    breakMin,
                                    false
                            )
                    );

                    startMinute += breakMin;
                    remaining -= breakMin;
                }
            }

            if (queueIdx >= queue.size() && revisionPhase) {
                break;
            }
        }

        if (days > 0 && !queue.isEmpty()) {

            TopicQueueItem first = queue.get(0);

            tasks.add(
                    new StudyTask(
                            plan.examDate(),
                            8 * 60,
                            first.subject,
                            "Final look-over: " + first.topic,
                            TaskType.REVISE,
                            "high",
                            30,
                            false
                    )
            );
        }

        tasks.sort(
                Comparator.comparing(StudyTask::taskDate)
                        .thenComparingInt(StudyTask::startMinute)
        );

        return tasks;
    }

    public static void displaySchedule(
            PlanInput plan,
            List<StudyTask> tasks
    ) {

        System.out.println("\n======================================");
        System.out.println("          STUDYMATE AI");
        System.out.println("       PERSONALIZED STUDY PLAN");
        System.out.println("======================================");

        System.out.println("Plan: " + plan.title());
        System.out.println("Exam Date: " + plan.examDate());
        System.out.println("Daily Hours: " + plan.dailyHours());
        System.out.println("Difficulty: " + plan.difficulty());

        LocalDate current = null;

        for (StudyTask t : tasks) {

            if (!t.taskDate().equals(current)) {

                current = t.taskDate();

                System.out.println("\n--- " + current + " ---");
            }

            String clock = formatTime(t.startMinute())
                    + " (" + t.durationMinutes() + " min)";

            if (t.taskType() == TaskType.BREAK) {

                System.out.printf(
                        "  %-20s %s%n",
                        clock,
                        t.topic()
                );

            } else {

                System.out.printf(
                        "  %-20s [%s priority] %s - %s (%s)%n",
                        clock,
                        t.priority(),
                        t.subject(),
                        t.topic(),
                        t.taskType().name().toLowerCase()
                );
            }
        }

        long studyBlocks = tasks.stream()
                .filter(t -> t.taskType() != TaskType.BREAK)
                .count();

        System.out.println("\n======================================");
        System.out.println("Total Blocks: " + tasks.size());
        System.out.println("Study Sessions: " + studyBlocks);
        System.out.println("======================================");
    }

    public static void main(String[] args) {

        PlanInput plan = new PlanInput(
                "Final Exam Preparation",
                LocalDate.now().plusDays(10),
                4.0,
                Difficulty.INTERMEDIATE,
                List.of(
                        new SubjectInput(
                                "Mathematics",
                                List.of(
                                        "Quadratic Equations",
                                        "Trigonometry",
                                        "Statistics"
                                ),
                                3
                        ),
                        new SubjectInput(
                                "Biology",
                                List.of(
                                        "Cell Division",
                                        "Genetics",
                                        "Ecology"
                                ),
                                2
                        )
                )
        );

        List<StudyTask> tasks = generateSchedule(plan);

        displaySchedule(plan, tasks);
    }
}
