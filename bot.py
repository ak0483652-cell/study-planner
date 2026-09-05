import os
import json
import random
import logging
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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


# =========================
# SETUP
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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


# =========================
# MEMORY
# =========================

progress = {}
poll_data = {}


# =========================
# HELPERS
# =========================

def get_user(user_id):
    if user_id not in progress:
        progress[user_id] = {
            "xp": 0,
            "streak": 0,
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {},
            "topper_score": 0,
        }

    return progress[user_id]


def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💡 Doubt Buddy", callback_data="ask"),
            InlineKeyboardButton("📸 Snap & Solve", callback_data="photo"),
        ],
        [
            InlineKeyboardButton("📚 Study Corner", callback_data="search"),
            InlineKeyboardButton("🎯 Quick Quiz", callback_data="quiz"),
        ],
        [
            InlineKeyboardButton("🔥 Topper Mode", callback_data="topper"),
            InlineKeyboardButton("📊 My Progress", callback_data="progress"),
        ],
        [
            InlineKeyboardButton("⚡ Practice More", callback_data="weak"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def safe_reply(message, text):
    """
    Gemini text ko plain text me bhejte hain.
    Isse Markdown formatting ki wajah se Telegram errors nahi aayenge.
    """
    try:
        await message.reply_text(text)
    except Exception as e:
        logger.error(f"Reply error: {e}")
        await message.reply_text(
            "⚠️ Answer bhejne me problem aa gayi. Ek baar phir try karo."
        )


async def gemini_text(prompt):
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )

        if response and response.text:
            return response.text.strip()

        return "Sorry, mujhe iska answer generate nahi ho paaya."

    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return (
            "⚠️ Abhi answer generate nahi ho pa raha.\n"
            "Thodi der baad dobara try karo."
        )


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    get_user(user_id)

    context.user_data.clear()

    text = (
        "👋 Hey! Welcome to Study Help Bot 📚\n\n"
        "Yahan tum padhai ko simple aur interesting bana sakte ho.\n\n"
        "💡 Doubt pucho\n"
        "📸 Question ki photo bhejo\n"
        "🎯 Quiz khelo\n"
        "📊 Apni progress dekho\n"
        "🔥 Weak topics improve karo\n\n"
        "Neeche se koi option choose karo 👇"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================
# DOUBT SOLVER
# =========================

async def solve_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    question = update.message.text.strip()

    if not question:
        return

    context.user_data["waiting_for_doubt"] = False

    await update.message.reply_text("🧠 Soch raha hoon...")

    prompt = f"""
You are a friendly study tutor.

Student question:
{question}

Answer the student in simple Hinglish.

Rules:
- Explain step by step.
- Use very easy language.
- If it is Maths/Physics/Chemistry, show the steps.
- Give a small example where useful.
- Avoid unnecessary complicated words.
- Do not say that you are an AI.
- Make the answer useful for an exam.
"""

    answer = await gemini_text(prompt)

    await safe_reply(update.message, answer)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💡 Ask Another Doubt",
                callback_data="ask"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="home"
            )
        ]
    ])

    await update.message.reply_text(
        "Aur kuch puchna hai? 👇",
        reply_markup=keyboard,
    )


# =========================
# STUDY SEARCH
# =========================

async def study_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    topic = update.message.text.strip()

    if not topic:
        return

    context.user_data["waiting_for_search"] = False

    await update.message.reply_text("🔎 Topic prepare kar raha hoon...")

    prompt = f"""
You are a study assistant.

Topic:
{topic}

Explain this topic for a student.

Give:
1. Simple definition
2. Important concepts
3. Key points
4. Example
5. Exam-focused points
6. 3 quick revision questions

Use simple Hinglish.
Keep it structured and easy to revise.
"""

    answer = await gemini_text(prompt)

    await safe_reply(update.message, answer)

    await update.message.reply_text(
        "📚 Study Corner complete!",
        reply_markup=main_keyboard(),
    )


# =========================
# PHOTO SOLVER
# =========================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        await update.message.reply_text(
            "📸 Photo mil gayi!\n\n"
            "Question read karke solve kar raha hoon..."
        )

        photo = update.message.photo[-1]

        file = await context.bot.get_file(photo.file_id)

        image_bytes = await file.download_as_bytearray()

        image_part = types.Part.from_bytes(
            data=bytes(image_bytes),
            mime_type="image/jpeg",
        )

        prompt = """
You are a friendly study tutor.

Look at the question in the image and solve it.

Rules:
- First identify the question.
- Explain step by step.
- Use simple Hinglish.
- Show formulas and calculations clearly.
- Give the final answer clearly.
- If the image is unclear, tell the student what part is unclear.
"""

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                prompt,
                image_part,
            ],
        )

        if response and response.text:
            await safe_reply(update.message, response.text)
        else:
            await update.message.reply_text(
                "⚠️ Question clearly read nahi ho paaya."
            )

    except Exception as e:
        logger.error(f"Photo error: {e}")

        await update.message.reply_text(
            "⚠️ Photo solve karte time problem aa gayi.\n"
            "Clear photo bhejo aur dobara try karo."
        )


# =========================
# QUIZ GENERATION
# =========================

async def generate_quiz(topic):

    prompt = f"""
Create a quiz for a student.

Topic:
{topic}

Create exactly 5 multiple-choice questions.

Difficulty:
- Q1 easy
- Q2 easy-medium
- Q3 medium
- Q4 medium-hard
- Q5 hard

Return ONLY valid JSON.

Format:

[
  {{
    "question": "Question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct": 0,
    "explanation": "Short explanation"
  }}
]

Rules:
- correct must be 0, 1, 2 or 3.
- Exactly 4 options per question.
- Questions must be different.
- Do not include markdown.
- Do not include any text outside JSON.
"""

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )

        text = response.text.strip()

        # Remove possible markdown fences
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

        quiz = json.loads(text)

        if not isinstance(quiz, list):
            return None

        if len(quiz) < 5:
            return None

        return quiz[:5]

    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        return None


# =========================
# START QUIZ
# =========================

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_for_topic"] = True

    await update.message.reply_text(
        "🎯 Quick Quiz\n\n"
        "Kis topic ka quiz chahiye?\n\n"
        "Example:\n"
        "• Physics - Laws of Motion\n"
        "• Chemistry - Organic Chemistry\n"
        "• Maths - Quadratic Equation\n"
        "• Biology - Cell\n\n"
        "Topic type karke bhejo 👇"
    )


async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):

    topic = update.message.text.strip()

    context.user_data["waiting_for_topic"] = False

    await update.message.reply_text(
        f"🎯 {topic} ka quiz bana raha hoon..."
    )

    quiz = await generate_quiz(topic)

    if not quiz:
        await update.message.reply_text(
            "⚠️ Quiz generate nahi ho paaya.\n"
            "Thoda simple topic ke saath dobara try karo."
        )
        return

    user_id = update.effective_user.id
    get_user(user_id)

    context.user_data["quiz_topic"] = topic
    context.user_data["quiz_questions"] = quiz
    context.user_data["quiz_index"] = 0
    context.user_data["quiz_score"] = 0

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
        message = await context.bot.send_poll(
            chat_id=chat_id,
            question=f"Q{index + 1}/5\n\n{q['question']}",
            options=q["options"],
            type="quiz",
            correct_option_id=int(q["correct"]),
            is_anonymous=False,
        )

        poll_data[message.poll.id] = {
            "chat_id": chat_id,
            "user_id": context.user_data.get("quiz_user_id"),
            "question_index": index,
            "correct": int(q["correct"]),
            "explanation": q.get(
                "explanation",
                "Correct answer explained above."
            ),
        }

    except Exception as e:
        logger.error(f"Poll error: {e}")

        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Quiz question send nahi ho paaya."
        )


# =========================
# POLL ANSWER
# =========================

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    answer = update.poll_answer

    if answer.poll_id not in poll_data:
        return

    data = poll_data.pop(answer.poll_id)

    chat_id = data["chat_id"]
    user_id = data["user_id"]

    selected = answer.option_ids[0] if answer.option_ids else -1

    correct = data["correct"]
    explanation = data["explanation"]

    user = get_user(user_id)

    user["questions"] += 1

    if selected == correct:
        user["correct"] += 1
        user["xp"] += 20

        topic = context.user_data.get("quiz_topic", "General")

        if topic not in user["topics"]:
            user["topics"][topic] = {
                "correct": 0,
                "total": 0,
            }

        user["topics"][topic]["correct"] += 1
        user["topics"][topic]["total"] += 1

        context.user_data["quiz_score"] += 1

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ Correct!\n\n"
                f"💡 Explanation:\n{explanation}"
            ),
        )

    else:

        topic = context.user_data.get("quiz_topic", "General")

        if topic not in user["topics"]:
            user["topics"][topic] = {
                "correct": 0,
                "total": 0,
            }

        user["topics"][topic]["total"] += 1

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "❌ Not quite!\n\n"
                f"💡 Explanation:\n{explanation}"
            ),
        )

    context.user_data["quiz_index"] += 1

    await send_next_quiz_question(
        chat_id,
        context,
    )


async def finish_quiz(chat_id, context):

    user_id = context.user_data.get("quiz_user_id")

    if not user_id:
        # fallback
        user_id = context.user_data.get("user_id")

    user = get_user(user_id)

    score = context.user_data.get("quiz_score", 0)
    topic = context.user_data.get("quiz_topic", "General")

    user["quizzes"] += 1

    user["xp"] += score * 10

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🏁 Quiz Complete!\n\n"
            f"📚 Topic: {topic}\n"
            f"🎯 Score: {score}/5\n"
            f"⭐ XP earned: {score * 30}\n\n"
            + (
                "🔥 Excellent! Keep it up!"
                if score >= 4
                else
                "💪 Good try! Practice karke aur better kar sakte ho."
            )
        ),
        reply_markup=main_keyboard(),
    )

    context.user_data.pop("quiz_questions", None)
    context.user_data.pop("quiz_index", None)
    context.user_data.pop("quiz_score", None)


# =========================
# PROGRESS
# =========================

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    user = get_user(user_id)

    xp = user["xp"]

    level = (xp // 100) + 1

    total = user["questions"]
    correct = user["correct"]

    accuracy = 0

    if total:
        accuracy = round((correct / total) * 100)

    topic_lines = []

    for topic, stats in user["topics"].items():

        if stats["total"] > 0:

            acc = round(
                stats["correct"] /
                stats["total"] *
                100
            )

            topic_lines.append(
                f"• {topic}: {acc}%"
            )

    topics_text = "\n".join(topic_lines)

    if not topics_text:
        topics_text = "Abhi topic data nahi hai."

    text = (
        "📊 YOUR PROGRESS\n\n"
        f"⭐ Level: {level}\n"
        f"⚡ XP: {xp}\n"
        f"🔥 Streak: {user['streak']} days\n\n"
        f"🎯 Quizzes: {user['quizzes']}\n"
        f"📝 Questions: {total}\n"
        f"✅ Correct: {correct}\n"
        f"📈 Accuracy: {accuracy}%\n\n"
        "📚 Topic Performance:\n"
        f"{topics_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚡ Practice Weak Topics",
                callback_data="weak"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="home"
            )
        ]
    ])

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
    )


# =========================
# WEAK TOPICS
# =========================

async def show_weak_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    user = get_user(user_id)

    weak = []

    for topic, stats in user["topics"].items():

        if stats["total"] >= 2:

            accuracy = (
                stats["correct"] /
                stats["total"]
            ) * 100

            if accuracy < 60:
                weak.append(
                    f"• {topic} — {round(accuracy)}%"
                )

    if weak:

        text = (
            "⚡ PRACTICE MORE\n\n"
            "In topics par thoda extra focus karo:\n\n"
            + "\n".join(weak)
            + "\n\n🎯 In topics ka quiz baar-baar practice karo."
        )

    else:

        text = (
            "🔥 Great job!\n\n"
            "Abhi koi major weak topic detect nahi hua.\n\n"
            "Regular practice continue rakho!"
        )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================
# TOPPER MODE
# =========================

async def topper_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    context.user_data["roadmap_step"] = 1
    context.user_data["roadmap"] = {}

    await update.message.reply_text(
        "🔥 TOPPER MODE\n\n"
        "Main tumhare liye personalised study roadmap banaunga.\n\n"
        "Pehle batao:\n\n"
        "🎯 Tumhara goal / exam kya hai?"
    )


async def roadmap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.strip()
    step = context.user_data.get("roadmap_step")

    roadmap = context.user_data.setdefault(
        "roadmap",
        {}
    )

    if step == 1:

        roadmap["goal"] = text
        context.user_data["roadmap_step"] = 2

        await update.message.reply_text(
            "📅 Exam ki date kya hai?\n\n"
            "Example: 15 December 2026"
        )

        return True

    if step == 2:

        roadmap["date"] = text
        context.user_data["roadmap_step"] = 3

        await update.message.reply_text(
            "📚 Tumhare subjects kaunse hain?\n\n"
            "Example:\n"
            "Physics, Chemistry, Maths"
        )

        return True

    if step == 3:

        roadmap["subjects"] = text
        context.user_data["roadmap_step"] = 4

        await update.message.reply_text(
            "⏰ Roz kitne hours padh sakte ho?"
        )

        return True

    if step == 4:

        roadmap["hours"] = text
        context.user_data["roadmap_step"] = 5

        await update.message.reply_text(
            "📈 Apna current level batao.\n\n"
            "Example:\n"
            "Beginner / Average / Good"
        )

        return True

    if step == 5:

        roadmap["level"] = text

        await update.message.reply_text(
            "🔥 Tumhara roadmap prepare kar raha hoon..."
        )

        prompt = f"""
Create a personalised study roadmap.

Goal:
{roadmap.get('goal')}

Exam date:
{roadmap.get('date')}

Subjects:
{roadmap.get('subjects')}

Daily study hours:
{roadmap.get('hours')}

Current level:
{roadmap.get('level')}

Give:
1. Overall strategy
2. Subject priority
3. Daily study structure
4. Weekly revision plan
5. Practice strategy
6. Test strategy
7. Important habits
8. Today's first mission

Use simple Hinglish.
Make it practical.
"""

        answer = await gemini_text(prompt)

        context.user_data["roadmap_step"] = None

        await safe_reply(update.message, answer)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔥 Today's Mission",
                    callback_data="mission"
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 My Progress",
                    callback_data="progress"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="home"
                )
            ]
        ])

        await update.message.reply_text(
            "Roadmap ready! 🚀",
            reply_markup=keyboard,
        )

        return True

    return False


# =========================
# DAILY MISSION
# =========================

async def daily_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):

    roadmap = context.user_data.get("roadmap", {})

    if not roadmap:
        await update.message.reply_text(
            "Pehle Topper Mode setup karo.",
            reply_markup=main_keyboard(),
        )
        return

    await update.message.reply_text(
        "🔥 Aaj ka mission bana raha hoon..."
    )

    prompt = f"""
Create one realistic study mission for today.

Goal:
{roadmap.get('goal')}

Subjects:
{roadmap.get('subjects')}

Daily hours:
{roadmap.get('hours')}

Current level:
{roadmap.get('level')}

Give:
- 3 study tasks
- 1 revision task
- 1 practice/test task
- short motivation

Use simple Hinglish.
"""

    answer = await gemini_text(prompt)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Complete Today",
                callback_data="complete_day"
            )
        ]
    ])

    await safe_reply(update.message, answer)

    await update.message.reply_text(
        "Mission complete karne ke baad button dabao 👇",
        reply_markup=keyboard,
    )


async def complete_day(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    user = get_user(user_id)

    user["xp"] += 50
    user["streak"] += 1

    await update.message.reply_text(
        "🎉 DAY COMPLETE!\n\n"
        "🔥 +1 Streak\n"
        "⭐ +50 XP\n\n"
        "Kal phir continue karna!"
    )


# =========================
# BUTTON HANDLER
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    # ---------------------
    # HOME
    # ---------------------

    if data == "home":

        context.user_data.clear()

        await query.message.reply_text(
            "🏠 Main Menu\n\nChoose an option 👇",
            reply_markup=main_keyboard(),
        )

        return

    # ---------------------
    # DOUBT
    # ---------------------

    if data == "ask":

        context.user_data["waiting_for_doubt"] = True
        context.user_data["waiting_for_topic"] = False
        context.user_data["waiting_for_search"] = False

        await query.message.reply_text(
            "💡 DOUBT BUDDY\n\n"
            "Apna question bhejo 👇\n\n"
            "Example:\n"
            "• Explain Newton's Second Law\n"
            "• Solve x² + 5x + 6 = 0\n"
            "• What is photosynthesis?\n"
            "• Explain integration in easy words"
        )

        return

    # ---------------------
    # PHOTO
    # ---------------------

    if data == "photo":

        await query.message.reply_text(
            "📸 Snap & Solve\n\n"
            "Question ki clear photo yahin send karo 👇"
        )

        return

    # ---------------------
    # SEARCH
    # ---------------------

    if data == "search":

        context.user_data["waiting_for_search"] = True
        context.user_data["waiting_for_doubt"] = False
        context.user_data["waiting_for_topic"] = False

        await query.message.reply_text(
            "📚 STUDY CORNER\n\n"
            "Kis topic ke baare me padhna hai?\n\n"
            "Example:\n"
            "• Thermodynamics\n"
            "• Organic Chemistry\n"
            "• Calculus\n"
            "• Cell Biology"
        )

        return

    # ---------------------
    # QUIZ
    # ---------------------

    if data == "quiz":

        context.user_data["waiting_for_topic"] = True
        context.user_data["waiting_for_doubt"] = False
        context.user_data["waiting_for_search"] = False

        await query.message.reply_text(
            "🎯 QUICK QUIZ\n\n"
            "Kis topic ka quiz chahiye?\n\n"
            "Example:\n"
            "Physics - Laws of Motion\n"
            "Chemistry - Periodic Table\n"
            "Maths - Quadratic Equation"
        )

        return

    # ---------------------
    # TOPPER
    # ---------------------

    if data == "topper":

        context.user_data.clear()
        context.user_data["roadmap_step"] = 1
        context.user_data["roadmap"] = {}

        await query.message.reply_text(
            "🔥 TOPPER MODE\n\n"
            "Tumhara personalised roadmap banate hain!\n\n"
            "🎯 Tumhara goal / exam kya hai?"
        )

        return

    # ---------------------
    # PROGRESS
    # ---------------------

    if data == "progress":

        user_id = update.effective_user.id
        user = get_user(user_id)

        xp = user["xp"]
        level = (xp // 100) + 1

        total = user["questions"]
        correct = user["correct"]

        accuracy = 0

        if total:
            accuracy = round(
                correct / total * 100
            )

        await query.message.reply_text(
            "📊 MY PROGRESS\n\n"
            f"⭐ Level: {level}\n"
            f"⚡ XP: {xp}\n"
            f"🔥 Streak: {user['streak']} days\n\n"
            f"🎯 Quizzes: {user['quizzes']}\n"
            f"📝 Questions: {total}\n"
            f"✅ Correct: {correct}\n"
            f"📈 Accuracy: {accuracy}%"
        )

        return

    # ---------------------
    # WEAK
    # ---------------------

    if data == "weak":

        user_id = update.effective_user.id
        user = get_user(user_id)

        weak = []

        for topic, stats in user["topics"].items():

            if stats["total"] >= 2:

                acc = (
                    stats["correct"] /
                    stats["total"]
                ) * 100

                if acc < 60:
                    weak.append(
                        f"• {topic}: {round(acc)}%"
                    )

        if weak:

            text = (
                "⚡ WEAK TOPICS\n\n"
                + "\n".join(weak)
                + "\n\n🎯 In topics par practice karo."
            )

        else:

            text = (
                "🔥 Abhi koi major weak topic nahi hai!\n\n"
                "Regular practice continue rakho."
            )

        await query.message.reply_text(
            text,
            reply_markup=main_keyboard(),
        )

        return

    # ---------------------
    # MISSION
    # ---------------------

    if data == "mission":

        roadmap = context.user_data.get(
            "roadmap",
            {}
        )

        if not roadmap:

            await query.message.reply_text(
                "Pehle Topper Mode setup karo."
            )

            return

        prompt = f"""
Create today's study mission.

Goal: {roadmap.get('goal')}
Subjects: {roadmap.get('subjects')}
Hours: {roadmap.get('hours')}
Level: {roadmap.get('level')}

Give 3 study tasks, revision and practice.
Simple Hinglish.
"""

        answer = await gemini_text(prompt)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Complete Today",
                    callback_data="complete_day"
                )
            ]
        ])

        await safe_reply(query.message, answer)

        await query.message.reply_text(
            "Mission complete hone ke baad 👇",
            reply_markup=keyboard,
        )

        return

    # ---------------------
    # COMPLETE DAY
    # ---------------------

    if data == "complete_day":

        user_id = update.effective_user.id
        user = get_user(user_id)

        user["xp"] += 50
        user["streak"] += 1

        await query.message.reply_text(
            "🎉 DAY COMPLETE!\n\n"
            "🔥 +1 Streak\n"
            "⭐ +50 XP\n\n"
            "Keep going! 🚀"
        )

        return


# =========================
# TEXT HANDLER
# =========================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    # Topper Mode conversation
    if context.user_data.get("roadmap_step"):
        handled = await roadmap_handler(
            update,
            context,
        )

        if handled:
            return

    # Quiz topic
    if context.user_data.get("waiting_for_topic"):
        await receive_topic(
            update,
            context,
        )
        return

    # Study Corner
    if context.user_data.get("waiting_for_search"):
        await study_search(
            update,
            context,
        )
        return

    # Doubt Buddy
    if context.user_data.get("waiting_for_doubt"):
        await solve_doubt(
            update,
            context,
        )
        return

    # IMPORTANT:
    # Agar user direct question type kare
    # bina button dabaye bhi answer milega.
    await solve_doubt(
        update,
        context,
    )


# =========================
# ERROR HANDLER
# =========================

async def error_handler(update, context):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error,
    )


# =========================
# MAIN
# =========================

def main():

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # Buttons
    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # Quiz polls
    app.add_handler(
        PollAnswerHandler(
            poll_answer
        )
    )

    # Photos
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo,
        )
    )

    # Normal text
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    app.add_error_handler(
        error_handler
    )

    # =========================
    # RENDER WEBHOOK
    # =========================

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    render_url = os.environ.get(
        "RENDER_EXTERNAL_URL"
    )

    if render_url:

        webhook_url = (
            f"{render_url}/telegram"
        )

        logger.info(
            f"Starting webhook: {webhook_url}"
        )

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram",
            webhook_url=webhook_url,
        )

    else:

        logger.info(
            "Starting bot with polling..."
        )

        app.run_polling()


if __name__ == "__main__":
    main()
