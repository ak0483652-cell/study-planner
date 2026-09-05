import os
import json
import asyncio
import logging
from datetime import datetime, date

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ContextTypes,
    filters,
)
from google import genai
from google.genai import types


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Keep the model that was already working in your project.
MODEL = "gemini-3.6-flash"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in .env")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing in .env")

client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================================================
# IN-MEMORY USER DATA
# =========================================================

users = {}
poll_data = {}


def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "xp": 0,
            "streak": 0,
            "last_mission": None,
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {},
        }
    return users[user_id]


# =========================================================
# COMMON HELPERS
# =========================================================

def clear_mode(context):
    for key in [
        "mode",
        "study_topic",
        "difficulty",
        "current_question",
        "quiz_topic",
        "quiz_questions",
        "quiz_index",
        "quiz_score",
        "quiz_user_id",
        "roadmap_step",
        "roadmap",
        "generated_roadmap",
    ]:
        context.user_data.pop(key, None)


def menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💡 Doubt Buddy", callback_data="doubt"),
            InlineKeyboardButton("📸 Snap & Solve", callback_data="snap"),
        ],
        [
            InlineKeyboardButton("📚 Study Corner", callback_data="study"),
            InlineKeyboardButton("🎯 Quick Quiz", callback_data="quiz"),
        ],
        [
            InlineKeyboardButton("🔥 Topper Mode", callback_data="topper"),
            InlineKeyboardButton("📊 My Progress", callback_data="progress"),
        ],
        [
            InlineKeyboardButton("⚡ Practice More", callback_data="weak"),
        ],
    ])


def resolve_chat_id(update_or_message):
    """
    Some handlers receive a real Update object (has .effective_chat),
    others receive a Message object directly (has .chat_id).
    This works with either.
    """
    effective_chat = getattr(update_or_message, "effective_chat", None)
    if effective_chat is not None:
        return effective_chat.id
    return update_or_message.chat_id


class TypingIndicator:
    """
    Async context manager that keeps showing Telegram's
    "bot is typing..." animation (the little animated dots/circle)
    for as long as the `async with` block is running.

    Telegram auto-expires a single typing action after ~5 seconds,
    so this refreshes it every 4 seconds in the background until
    the actual work (e.g. a Gemini call) finishes.
    """

    def __init__(self, bot, chat_id, action="typing"):
        self.bot = bot
        self.chat_id = chat_id
        self.action = action
        self._task = None

    async def _loop(self):
        try:
            while True:
                try:
                    await self.bot.send_chat_action(chat_id=self.chat_id, action=self.action)
                except Exception:
                    logger.debug("send_chat_action failed", exc_info=True)
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    async def __aenter__(self):
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        return False


async def gemini_text(prompt):
    try:
        # generate_content is a blocking/synchronous SDK call. Running it
        # directly here would freeze the bot's event loop (no other user's
        # message, poll, or button click gets processed) until it returns.
        # asyncio.to_thread runs it in a background thread instead.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL,
            contents=prompt,
        )
        if response and response.text:
            return response.text.strip()
        return None
    except Exception as e:
        logger.error("Gemini text error", exc_info=True)
        return None


def parse_json_response(text):
    if not text:
        return None

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

    return None


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_mode(context)
    user = get_user(update.effective_user.id)

    await update.message.reply_text(
        "👋 Hey! Welcome to Study Help Bot 📚\n\n"
        "Tum yahan:\n"
        "💡 Doubts solve kar sakte ho\n"
        "📸 Photo se questions solve kara sakte ho\n"
        "📚 Easy/Hard practice kar sakte ho\n"
        "🎯 Quizzes khel sakte ho\n"
        "🔥 Personal study roadmap bana sakte ho\n"
        "📊 Apni progress track kar sakte ho\n\n"
        "Choose an option 👇",
        reply_markup=menu_keyboard(),
    )


# =========================================================
# DOUBT BUDDY
# =========================================================

async def start_doubt(update, context):
    context.user_data["mode"] = "doubt"

    await update.message.reply_text(
        "💡 DOUBT BUDDY\n\n"
        "Apna question bhejo 👇\n\n"
        "Examples:\n"
        "• Explain Newton's Second Law\n"
        "• Solve x² + 5x + 6 = 0\n"
        "• Explain photosynthesis in easy words"
    )


async def solve_doubt(update, context):
    question = update.message.text.strip()
    if not question:
        return

    context.user_data["mode"] = None

    chat_id = resolve_chat_id(update)

    prompt = f"""
You are an expert but friendly personal study tutor.

Student question:
{question}

Answer in simple Hinglish.

Give:
📌 Concept
🧠 Easy Explanation
📝 Step-by-step Solution
✅ Final Answer
🎯 Exam Tip

Rules:
- Do not skip important calculation steps.
- For Maths show the working.
- For Physics show formula, substitution and units.
- For Chemistry show relevant equations/reactions.
- For theory subjects use simple examples.
- If the question has multiple parts, answer every part.
- Do not invent missing information.
- Do not mention that you are an AI.
"""

    async with TypingIndicator(context.bot, chat_id):
        answer = await gemini_text(prompt)

    if not answer:
        await update.message.reply_text(
            "⚠️ Answer generate nahi ho paaya. Question dobara bhejo."
        )
        return

    await update.message.reply_text(answer)
    await update.message.reply_text(
        "Aur doubt hai? 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Ask Another", callback_data="doubt")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
        ]),
    )


# =========================================================
# SNAP & SOLVE
# =========================================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = resolve_chat_id(update)
    try:
        # Photo upload feels natural with the "upload_photo" chat action.
        async with TypingIndicator(context.bot, chat_id, action="upload_photo"):
            photo = update.message.photo[-1]

            telegram_file = await context.bot.get_file(photo.file_id)
            image_bytes = await telegram_file.download_as_bytearray()

            if not image_bytes:
                raise ValueError("Telegram returned an empty image.")

            # Use Gemini's native image Part instead of manually constructing
            # a REST payload. This is more reliable with google-genai.
            image_part = types.Part.from_bytes(
                data=bytes(image_bytes),
                mime_type="image/jpeg",
            )

            prompt = """
You are an expert visual study tutor.

Look carefully at the attached image.

Read every visible part of the question and solve it.

IMPORTANT:
1. Identify the exact question before solving.
2. If there are multiple questions, solve them one by one.
3. Do not give only the final answer.
4. Maths: show formulas and every important calculation.
5. Physics: show formula, known values, substitution, units and result.
6. Chemistry: show equations/reactions and explain the concept.
7. Other subjects: explain clearly with relevant examples.
8. Use simple Hinglish.
9. If the image is genuinely unreadable, say exactly which part is unclear.
10. Never claim the image is unreadable if the text can actually be read.

Format:

📌 QUESTION
[read the question]

🧠 CONCEPT
[concept]

📝 STEP-BY-STEP SOLUTION
[complete solution]

✅ FINAL ANSWER
[final answer]

🎯 QUICK TIP
[short exam tip]
"""

            # Blocking SDK call - run in a background thread so the bot
            # keeps responding to other users/messages while this runs.
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=MODEL,
                contents=[prompt, image_part],
            )

        # response.text can itself raise (e.g. if Gemini's safety filters
        # blocked the image and there are no valid candidates), so this
        # needs its own guard instead of relying on the outer except only.
        try:
            answer_text = response.text if response else None
        except Exception:
            logger.error("Gemini image response had no usable text", exc_info=True)
            answer_text = None

        if not answer_text:
            await update.message.reply_text(
                "⚠️ Image se answer generate nahi ho paaya.\n"
                "Ho sakta hai photo unclear ho ya filter ho gaya ho.\n"
                "Please clear, straight photo bhejo."
            )
            return

        await update.message.reply_text(answer_text)

        await update.message.reply_text(
            "📸 Another question?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 Solve Another", callback_data="snap")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
            ]),
        )

    except Exception as e:
        logger.error("SNAP & SOLVE ERROR", exc_info=True)
        await update.message.reply_text(
            "❌ Snap & Solve me error aa gaya.\n\n"
            "Please clear photo bhejo aur dobara try karo."
        )


# =========================================================
# STUDY CORNER
# =========================================================

async def start_study(update, context):
    context.user_data["mode"] = "study_topic"

    await update.message.reply_text(
        "📚 STUDY CORNER\n\n"
        "Kis topic ki practice karni hai?\n\n"
        "Examples:\n"
        "• Newton's Laws\n"
        "• Quadratic Equations\n"
        "• Thermodynamics\n"
        "• Organic Chemistry\n\n"
        "Topic type karke bhejo 👇"
    )


async def study_topic_received(update, context):
    topic = update.message.text.strip()

    if not topic:
        return

    context.user_data["study_topic"] = topic
    context.user_data["mode"] = "study_difficulty"

    await update.message.reply_text(
        f"📚 Topic: {topic}\n\n"
        "Ab difficulty choose karo 👇",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Easy", callback_data="study_easy"),
                InlineKeyboardButton("🔴 Hard", callback_data="study_hard"),
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="home")
            ],
        ]),
    )


async def generate_practice_question(topic, difficulty):
    prompt = f"""
Create ONE high-quality practice question for a student.

Topic: {topic}
Difficulty: {difficulty}

Return ONLY valid JSON:

{{
  "question": "The question",
  "answer": "The correct final answer",
  "solution": "A complete step-by-step solution",
  "concept": "The concept being tested",
  "hint": "A useful hint without giving away the answer"
}}

Requirements:
- The question must be unambiguous and solvable.
- Difficulty must genuinely match {difficulty}.
- The official solution must actually solve the exact question.
- For numerical questions, verify the arithmetic.
- Do not use markdown outside JSON.
"""

    # NOTE: gemini_text is async - it must be awaited, otherwise this
    # would try to JSON-parse a coroutine object instead of real text.
    result = await gemini_text(prompt)
    return parse_json_response(result)


async def send_practice_question(update, context):
    topic = context.user_data.get("study_topic")
    difficulty = context.user_data.get("difficulty")
    chat_id = resolve_chat_id(update)

    async with TypingIndicator(context.bot, chat_id):
        question = await generate_practice_question(topic, difficulty)

    if not isinstance(question, dict):
        await update.reply_text(
            "⚠️ Question generate nahi ho paaya. Dobara try karo."
        )
        return

    required = ["question", "answer", "solution", "concept", "hint"]
    if not all(key in question for key in required):
        await update.reply_text(
            "⚠️ Question format incomplete tha. Dobara try karo."
        )
        return

    context.user_data["current_question"] = question
    context.user_data["mode"] = "study_answer"

    await update.reply_text(
        f"{'🟢 EASY' if difficulty == 'Easy' else '🔴 HARD'} QUESTION\n\n"
        f"📚 {topic}\n\n"
        f"{question['question']}\n\n"
        "✍️ Apna answer bhejo.\n"
        "💡 Hint ke liye `hint` likho."
    )


async def show_hint(update, context):
    question = context.user_data.get("current_question")

    if not question:
        await update.message.reply_text("Pehle ek practice question start karo.")
        return

    await update.message.reply_text(
        "💡 HINT\n\n" + str(question["hint"])
    )


async def check_practice_answer(update, context):
    student_answer = update.message.text.strip()
    question = context.user_data.get("current_question")

    if not question:
        await update.message.reply_text(
            "Pehle Study Corner se question start karo."
        )
        return

    if student_answer.lower() in {"hint", "help", "h"}:
        await show_hint(update, context)
        return

    chat_id = resolve_chat_id(update)

    prompt = f"""
You are an exacting but friendly teacher checking a student's answer.

QUESTION:
{question["question"]}

CORRECT ANSWER:
{question["answer"]}

OFFICIAL SOLUTION:
{question["solution"]}

CONCEPT:
{question["concept"]}

STUDENT ANSWER:
{student_answer}

Compare the student's answer with the official answer.

Give:
1. 🟢 Correct / 🟡 Partially Correct / 🔴 Incorrect
2. What the student did right.
3. What is wrong or missing.
4. The REAL correct solution, step by step.
5. ✅ Final answer.
6. 🎯 One exam tip.

Do not blindly mark it correct.
For numerical answers, allow reasonable equivalent forms/rounding.
Use simple Hinglish.
"""

    async with TypingIndicator(context.bot, chat_id):
        result = await gemini_text(prompt)

    if not result:
        await update.message.reply_text(
            "⚠️ Answer check nahi ho paaya. Dobara bhejo."
        )
        return

    user = get_user(update.effective_user.id)
    user["questions"] += 1

    # Track practice as a topic attempt. The evaluator remains the source
    # of truth for correctness; exact automated parsing is intentionally avoided.
    topic_stats = user["topics"].setdefault(
        context.user_data.get("study_topic", "General"),
        {"correct": 0, "total": 0},
    )
    topic_stats["total"] += 1

    await update.message.reply_text(result)

    await update.message.reply_text(
        "Next kya karna hai? 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Next Question", callback_data="next_practice")],
            [InlineKeyboardButton("🔄 Change Difficulty", callback_data="change_difficulty")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
        ]),
    )


# =========================================================
# QUICK QUIZ
# =========================================================

async def generate_quiz(topic):
    prompt = f"""
Create exactly 5 high-quality MCQ questions on:
{topic}

Return ONLY valid JSON in this exact structure:

[
  {{
    "question": "Question",
    "options": ["A", "B", "C", "D"],
    "correct": 0,
    "explanation": "Why the correct answer is correct"
  }}
]

Rules:
- Exactly 5 questions.
- Exactly 4 options per question.
- correct is 0, 1, 2 or 3.
- Q1 easy, Q2 easy-medium, Q3 medium, Q4 medium-hard, Q5 hard.
- Questions must be unambiguous.
- No markdown.
"""

    # NOTE: gemini_text is async - must be awaited (was missing before,
    # which meant quizzes never actually parsed correctly).
    result = await gemini_text(prompt)
    quiz = parse_json_response(result)

    if not isinstance(quiz, list) or len(quiz) < 5:
        return None

    clean = []
    for q in quiz[:5]:
        if (
            isinstance(q, dict)
            and isinstance(q.get("options"), list)
            and len(q["options"]) == 4
            and "question" in q
            and "correct" in q
        ):
            clean.append(q)

    return clean if len(clean) == 5 else None


async def start_quiz(update, context):
    context.user_data["mode"] = "quiz_topic"

    await update.message.reply_text(
        "🎯 QUICK QUIZ\n\n"
        "Kis topic ka quiz chahiye?\n\n"
        "Example:\n"
        "Physics - Laws of Motion\n"
        "Maths - Integration\n"
        "Chemistry - Chemical Bonding"
    )


async def receive_quiz_topic(update, context):
    topic = update.message.text.strip()
    chat_id = resolve_chat_id(update)

    async with TypingIndicator(context.bot, chat_id):
        quiz = await generate_quiz(topic)

    if not quiz:
        await update.message.reply_text(
            "⚠️ Quiz generate nahi ho paaya. Dobara try karo."
        )
        return

    user_id = update.effective_user.id
    get_user(user_id)

    context.user_data["quiz_user_id"] = user_id
    context.user_data["quiz_topic"] = topic
    context.user_data["quiz_questions"] = quiz
    context.user_data["quiz_index"] = 0
    context.user_data["quiz_score"] = 0
    context.user_data["mode"] = None

    await send_next_quiz_question(
        update.effective_chat.id,
        context,
    )


async def send_next_quiz_question(chat_id, context):
    questions = context.user_data.get("quiz_questions", [])
    index = context.user_data.get("quiz_index", 0)

    if index >= len(questions):
        await finish_quiz(chat_id, context)
        return

    q = questions[index]

    try:
        correct = int(q["correct"])
        if correct not in range(4):
            raise ValueError("Invalid correct option.")

        poll = await context.bot.send_poll(
            chat_id=chat_id,
            question=f"Q{index + 1}/5\n\n{q['question']}",
            options=[str(x) for x in q["options"]],
            type="quiz",
            correct_option_id=correct,
            is_anonymous=False,
        )

        poll_data[poll.poll.id] = {
            "chat_id": chat_id,
            "user_id": context.user_data["quiz_user_id"],
            "correct": correct,
            "explanation": q.get("explanation", "Correct answer explained."),
            "topic": context.user_data.get("quiz_topic", "General"),
        }

    except Exception:
        logger.error("Poll send error", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Quiz question send nahi ho paaya."
        )


async def poll_answer(update, context):
    answer = update.poll_answer
    data = poll_data.pop(answer.poll_id, None)

    if not data:
        return

    selected = answer.option_ids[0] if answer.option_ids else -1
    user_id = data["user_id"]
    user = get_user(user_id)

    user["questions"] += 1

    topic_stats = user["topics"].setdefault(
        data["topic"],
        {"correct": 0, "total": 0},
    )
    topic_stats["total"] += 1

    if selected == data["correct"]:
        user["correct"] += 1
        user["xp"] += 20
        topic_stats["correct"] += 1
        context.user_data["quiz_score"] = (
            context.user_data.get("quiz_score", 0) + 1
        )

        result_text = (
            "✅ Correct!\n\n"
            f"💡 {data['explanation']}"
        )
    else:
        result_text = (
            "❌ Incorrect!\n\n"
            f"💡 {data['explanation']}"
        )

    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=result_text,
    )

    context.user_data["quiz_index"] = (
        context.user_data.get("quiz_index", 0) + 1
    )

    await send_next_quiz_question(
        data["chat_id"],
        context,
    )


async def finish_quiz(chat_id, context):
    user_id = context.user_data.get("quiz_user_id")
    if not user_id:
        return

    user = get_user(user_id)
    score = context.user_data.get("quiz_score", 0)
    topic = context.user_data.get("quiz_topic", "General")

    user["quizzes"] += 1
    earned_xp = score * 10
    user["xp"] += earned_xp

    if score == 5:
        message = "🏆 PERFECT SCORE!"
    elif score >= 4:
        message = "🔥 Excellent!"
    elif score >= 3:
        message = "👍 Good job!"
    else:
        message = "💪 Keep practicing!"

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🏁 QUIZ COMPLETE!\n\n"
            f"📚 Topic: {topic}\n"
            f"🎯 Score: {score}/5\n"
            f"⭐ XP Earned: +{earned_xp}\n\n"
            f"{message}"
        ),
        reply_markup=menu_keyboard(),
    )


# =========================================================
# TOPPER MODE
# =========================================================

async def start_topper(update, context):
    context.user_data.clear()
    context.user_data["mode"] = "topper_goal"
    context.user_data["roadmap"] = {}

    await update.message.reply_text(
        "🔥 TOPPER MODE\n\n"
        "Main tumhare liye proper personalised roadmap banaunga.\n\n"
        "🎯 Goal / Exam kya hai?\n\n"
        "Example: JEE 2027 / Boards / CA Foundation"
    )


async def topper_router(update, context):
    text = update.message.text.strip()
    mode = context.user_data.get("mode")
    roadmap = context.user_data.setdefault("roadmap", {})

    if mode == "topper_goal":
        roadmap["goal"] = text
        context.user_data["mode"] = "topper_date"
        await update.message.reply_text(
            "📅 Exam date kya hai?\n\n"
            "Example: 15 May 2027"
        )
        return

    if mode == "topper_date":
        roadmap["date"] = text
        context.user_data["mode"] = "topper_subjects"
        await update.message.reply_text(
            "📚 Subjects batao.\n\n"
            "Example: Physics, Chemistry, Maths"
        )
        return

    if mode == "topper_subjects":
        roadmap["subjects"] = text
        context.user_data["mode"] = "topper_hours"
        await update.message.reply_text(
            "⏰ Roz realistically kitne hours padh sakte ho?"
        )
        return

    if mode == "topper_hours":
        roadmap["hours"] = text
        context.user_data["mode"] = "topper_level"
        await update.message.reply_text(
            "📈 Current preparation level?\n\n"
            "Beginner / Average / Good"
        )
        return

    if mode == "topper_level":
        roadmap["level"] = text
        await create_roadmap(update, context)


async def create_roadmap(update, context):
    roadmap = context.user_data["roadmap"]
    chat_id = resolve_chat_id(update)

    prompt = f"""
You are an expert academic planner.

Create a REALISTIC, detailed and personalised study roadmap.

Student:
Goal/Exam: {roadmap["goal"]}
Exam Date: {roadmap["date"]}
Subjects: {roadmap["subjects"]}
Daily Study Hours: {roadmap["hours"]}
Current Level: {roadmap["level"]}

First calculate the approximate time available until the exam.
Then create a practical plan that fits the student's available hours.

The roadmap MUST contain:

🔥 1. FINAL TARGET
What the student should achieve before the exam.

📅 2. PREPARATION PHASES
Phase 1 - Foundation
Phase 2 - Syllabus/Concept Completion
Phase 3 - Question Practice
Phase 4 - Revision
Phase 5 - Mock Tests / Final Revision

For each phase give duration, subjects and measurable targets.

📚 3. SUBJECT-WISE STRATEGY
For every subject:
- Priority
- What to study first
- Practice method
- Revision method
- Test strategy

🗓️ 4. WEEKLY SYSTEM
Give a repeatable Monday-Sunday structure.

⏰ 5. DAILY ROUTINE
Create a realistic daily timetable within the given hours.
Include breaks.

📝 6. QUESTION PRACTICE PLAN
Daily and weekly question targets.

🔄 7. REVISION SYSTEM
Use a sensible spaced-revision approach.

🧪 8. MOCK TEST PLAN
When to start mocks, frequency, analysis method.

⚡ 9. WEAK TOPIC SYSTEM
How the student should detect and fix weak chapters.

🚨 10. LAST 30 DAYS
Give a focused final-month strategy.

🔥 11. FIRST 7 DAYS
Give EXACT Day 1, Day 2 ... Day 7 tasks.

🎯 12. TODAY'S MISSION
Give today's tasks based on the student's level and available hours.

Rules:
- Do not make an impossible topper-style timetable.
- Do not assume the student can study 15+ hours.
- Keep it practical.
- Use simple Hinglish.
- Use clear headings.
- Make targets measurable.
- If the exact exam date format is unclear, still make the best reasonable plan from the information supplied.
"""

    async with TypingIndicator(context.bot, chat_id):
        answer = await gemini_text(prompt)

        if not answer:
            for fallback_model in ["gemini-3.8-flash", "gemini-3.5-flash"]:
                if fallback_model == MODEL:
                    continue
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=fallback_model,
                        contents=prompt,
                    )
                    if response and response.text:
                        answer = response.text.strip()
                        break
                except Exception:
                    logger.error("Roadmap fallback failed", exc_info=True)

    if not answer:
        await update.message.reply_text(
            "⚠️ Roadmap generate nahi ho paaya.\n\n"
            "API/model response nahi mila. `/start` se dobara Topper Mode try karo."
        )
        return

    context.user_data["generated_roadmap"] = answer
    context.user_data["mode"] = None

    await update.message.reply_text(answer)

    await update.message.reply_text(
        "🚀 Roadmap ready! Ab kya karna hai?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Today's Mission", callback_data="mission")],
            [InlineKeyboardButton("📚 Study Corner", callback_data="study")],
            [InlineKeyboardButton("📊 My Progress", callback_data="progress")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
        ]),
    )


async def daily_mission(update, context):
    roadmap = context.user_data.get("generated_roadmap")

    if not roadmap:
        await update.reply_text(
            "Pehle Topper Mode me roadmap banao."
        )
        return

    chat_id = resolve_chat_id(update)

    prompt = f"""
Here is the student's personalised roadmap:

{roadmap}

Create today's exact study mission.

Include:
1. Total study time
2. Task 1 with duration and target
3. Task 2 with duration and target
4. Task 3 with duration and target
5. Revision
6. Questions/test
7. End-of-day target

Make it achievable in the student's available hours.
Use simple Hinglish.
"""

    async with TypingIndicator(context.bot, chat_id):
        answer = await gemini_text(prompt)

    if not answer:
        await update.reply_text(
            "⚠️ Today's mission generate nahi ho paaya."
        )
        return

    await update.reply_text(answer)

    await update.reply_text(
        "Mission complete hone ke baad 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Complete Today", callback_data="complete_day")]
        ]),
    )


async def complete_day(update, context):
    user_id = update.from_user.id
    user = get_user(user_id)

    today = date.today().isoformat()

    # Prevent repeated clicks on the same day's mission.
    if user["last_mission"] == today:
        await update.reply_text(
            "✅ Aaj ka mission already complete marked hai!"
        )
        return

    user["last_mission"] = today
    user["xp"] += 50
    user["streak"] += 1

    await update.reply_text(
        "🎉 TODAY COMPLETE!\n\n"
        "⭐ +50 XP\n"
        "🔥 +1 Streak\n\n"
        "Kal phir continue karna! 🚀"
    )


# =========================================================
# PROGRESS / WEAK TOPICS
# =========================================================

async def show_progress(update, context):
    user = get_user(update.effective_user.id)

    total = user["questions"]
    accuracy = round(user["correct"] / total * 100) if total else 0
    level = user["xp"] // 100 + 1

    topic_lines = []
    for topic, stats in user["topics"].items():
        if stats["total"]:
            acc = round(stats["correct"] / stats["total"] * 100)
            topic_lines.append(f"• {topic}: {acc}%")

    topics = "\n".join(topic_lines) if topic_lines else "No topic data yet."

    await update.message.reply_text(
        "📊 MY PROGRESS\n\n"
        f"⭐ Level: {level}\n"
        f"⚡ XP: {user['xp']}\n"
        f"🔥 Streak: {user['streak']} days\n\n"
        f"🎯 Quizzes: {user['quizzes']}\n"
        f"📝 Questions: {total}\n"
        f"✅ Correct: {user['correct']}\n"
        f"📈 Accuracy: {accuracy}%\n\n"
        "📚 Topic Performance:\n"
        f"{topics}",
        reply_markup=menu_keyboard(),
    )


async def show_weak(update, context):
    user = get_user(update.effective_user.id)
    weak = []

    for topic, stats in user["topics"].items():
        if stats["total"] >= 2:
            acc = stats["correct"] / stats["total"] * 100
            if acc < 60:
                weak.append(f"• {topic}: {round(acc)}%")

    if weak:
        text = (
            "⚡ WEAK TOPICS\n\n"
            "Extra practice ki zarurat:\n\n"
            + "\n".join(weak)
            + "\n\n🎯 Study Corner se in topics ko Easy → Hard practice karo."
        )
    else:
        text = (
            "🔥 Abhi koi major weak topic detect nahi hua.\n\n"
            "More questions solve karoge to tracking aur accurate hogi."
        )

    await update.message.reply_text(
        text,
        reply_markup=menu_keyboard(),
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "home":
        clear_mode(context)
        await query.message.reply_text(
            "🏠 Main Menu\n\nChoose an option 👇",
            reply_markup=menu_keyboard(),
        )
        return

    if data == "doubt":
        clear_mode(context)
        context.user_data["mode"] = "doubt"
        await query.message.reply_text(
            "💡 DOUBT BUDDY\n\n"
            "Apna question bhejo 👇\n\n"
            "Example:\n"
            "Solve x² + 5x + 6 = 0"
        )
        return

    if data == "snap":
        clear_mode(context)
        context.user_data["mode"] = "snap"
        await query.message.reply_text(
            "📸 SNAP & SOLVE\n\n"
            "Question ki clear photo bhejo 👇\n\n"
            "Photo aate hi complete solution milega."
        )
        return

    if data == "study":
        clear_mode(context)
        context.user_data["mode"] = "study_topic"
        await query.message.reply_text(
            "📚 STUDY CORNER\n\n"
            "Topic bhejo 👇\n\n"
            "Example: Newton's Laws / Integration / Organic Chemistry"
        )
        return

    if data == "study_easy":
        context.user_data["difficulty"] = "Easy"
        await query.message.reply_text(
            "🟢 EASY MODE\n\nQuestion prepare kar raha hoon..."
        )
        await send_practice_question(query.message, context)
        return

    if data == "study_hard":
        context.user_data["difficulty"] = "Hard"
        await query.message.reply_text(
            "🔴 HARD MODE\n\nChallenging question prepare kar raha hoon..."
        )
        await send_practice_question(query.message, context)
        return

    if data == "change_difficulty":
        context.user_data["mode"] = "study_difficulty"
        await query.message.reply_text(
            "Difficulty choose karo 👇",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Easy", callback_data="study_easy"),
                    InlineKeyboardButton("🔴 Hard", callback_data="study_hard"),
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
            ]),
        )
        return

    if data == "next_practice":
        await query.message.reply_text(
            "🧠 Next question generate kar raha hoon..."
        )
        await send_practice_question(query.message, context)
        return

    if data == "quiz":
        clear_mode(context)
        context.user_data["mode"] = "quiz_topic"
        await query.message.reply_text(
            "🎯 QUICK QUIZ\n\n"
            "Kis topic ka quiz chahiye?"
        )
        return

    if data == "topper":
        clear_mode(context)
        context.user_data["mode"] = "topper_goal"
        context.user_data["roadmap"] = {}
        await query.message.reply_text(
            "🔥 TOPPER MODE\n\n"
            "🎯 Goal / Exam kya hai?"
        )
        return

    if data == "mission":
        await daily_mission(query.message, context)
        return

    if data == "complete_day":
        await complete_day(query.message, context)
        return

    if data == "progress":
        user = get_user(update.effective_user.id)
        total = user["questions"]
        accuracy = round(user["correct"] / total * 100) if total else 0
        level = user["xp"] // 100 + 1

        await query.message.reply_text(
            "📊 MY PROGRESS\n\n"
            f"⭐ Level: {level}\n"
            f"⚡ XP: {user['xp']}\n"
            f"🔥 Streak: {user['streak']} days\n\n"
            f"🎯 Quizzes: {user['quizzes']}\n"
            f"📝 Questions: {total}\n"
            f"✅ Correct: {user['correct']}\n"
            f"📈 Accuracy: {accuracy}%",
            reply_markup=menu_keyboard(),
        )
        return

    if data == "weak":
        user = get_user(update.effective_user.id)
        weak = []

        for topic, stats in user["topics"].items():
            if stats["total"] >= 2:
                acc = stats["correct"] / stats["total"] * 100
                if acc < 60:
                    weak.append(f"• {topic}: {round(acc)}%")

        text = (
            "⚡ WEAK TOPICS\n\n"
            + ("\n".join(weak) if weak else "🔥 No major weak topic detected yet.")
        )

        await query.message.reply_text(
            text,
            reply_markup=menu_keyboard(),
        )
        return


# =========================================================
# TEXT ROUTER
# =========================================================

async def text_handler(update, context):
    if not update.message or not update.message.text:
        return

    mode = context.user_data.get("mode")

    if mode == "doubt" or mode is None:
        await solve_doubt(update, context)
        return

    if mode == "study_topic":
        await study_topic_received(update, context)
        return

    if mode == "study_answer":
        await check_practice_answer(update, context)
        return

    if mode == "quiz_topic":
        await receive_quiz_topic(update, context)
        return

    if mode and mode.startswith("topper_"):
        await topper_router(update, context)
        return

    # Fallback: every normal text message can be treated as a doubt.
    await solve_doubt(update, context)


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update, context):
    logger.error("Unhandled bot error", exc_info=context.error)


# =========================================================
# MAIN
# =========================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(PollAnswerHandler(poll_answer))

    # PHOTO MUST be registered separately from text.
    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    app.add_error_handler(error_handler)

    port = int(os.environ.get("PORT", "10000"))
    render_url = os.environ.get("RENDER_EXTERNAL_URL")

    if render_url:
        webhook_url = f"{render_url}/telegram"

        logger.info("Starting webhook: %s", webhook_url)

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram",
            webhook_url=webhook_url,
        )
    else:
        logger.info("Starting polling...")
        app.run_polling()


if __name__ == "__main__":
    main()
