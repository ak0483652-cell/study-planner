import os
import json
import asyncio
from datetime import datetime, date

from dotenv import load_dotenv
from google import genai
from google.genai import types

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    PollAnswerHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in .env")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing in .env")


# =========================================================
# GEMINI
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)

MODEL = "gemini-3.6-flash"


# =========================================================
# DATA
# =========================================================

progress = {}

poll_data = {}


# =========================================================
# DEFAULT USER DATA
# =========================================================

def get_user_progress(user_id):

    if user_id not in progress:

        progress[user_id] = {
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {},
            "streak": 0,
            "last_active": None,
            "roadmap": {},
            "completed_days": [],
            "xp": 0,
        }

    return progress[user_id]


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "💡 Doubt Buddy",
                callback_data="ask"
            )
        ],

        [
            InlineKeyboardButton(
                "📷 Snap & Solve",
                callback_data="photo"
            )
        ],

        [
            InlineKeyboardButton(
                "📚 Study Corner",
                callback_data="search"
            )
        ],

        [
            InlineKeyboardButton(
                "🎯 Quick Quiz",
                callback_data="quiz"
            )
        ],

        [
            InlineKeyboardButton(
                "🗺️ Topper Mode",
                callback_data="topper"
            )
        ],

        [
            InlineKeyboardButton(
                "📈 My Progress",
                callback_data="progress"
            )
        ],

        [
            InlineKeyboardButton(
                "🎯 Practice More",
                callback_data="weak"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    await update.message.reply_text(

        "👋 *Hey! Welcome to Study Buddy!* 📚\n\n"

        "Yahan padhai ko thoda easy aur interesting banate hain 😄\n\n"

        "💡 *Doubt Buddy* — koi bhi doubt pucho\n"
        "📷 *Snap & Solve* — question ki photo bhejo\n"
        "📚 *Study Corner* — kisi bhi topic ko samjho\n"
        "🎯 *Quick Quiz* — preparation test karo\n"
        "🗺️ *Topper Mode* — apna complete study plan banao\n"
        "📈 *My Progress* — apni growth dekho\n"
        "🎯 *Practice More* — weak topics improve karo\n\n"

        "👇 *Chalo shuru karte hain!*",

        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# =========================================================
# DOUBT BUDDY
# =========================================================

async def ask_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["waiting_for_doubt"] = True

    await update.message.reply_text(

        "💡 *Doubt Buddy*\n\n"

        "Apna question bhejo.\n"
        "Main simple language mein step-by-step samjhaunga. 😄\n\n"

        "Example:\n"
        "👉 Explain Newton's Second Law\n"
        "👉 Solve this integration\n"
        "👉 What is photosynthesis?",

        parse_mode="Markdown"
    )


async def solve_doubt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get(
        "waiting_for_doubt"
    ):
        return

    question = update.message.text.strip()

    context.user_data[
        "waiting_for_doubt"
    ] = False

    await update.message.reply_text(
        "🤔 Soch raha hoon..."
    )

    try:

        prompt = f"""
You are a friendly study tutor.

Student question:
{question}

Answer in simple student-friendly language.

Rules:
- Explain step by step.
- Use examples if useful.
- Avoid unnecessary complexity.
- For numerical problems show calculations.
- Highlight the final answer.
"""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        await update.message.reply_text(
            "💡 *Doubt Buddy*\n\n"
            + response.text,
            parse_mode="Markdown"
        )

    except Exception as e:

        print("DOUBT ERROR:", e)

        await update.message.reply_text(
            "❌ Kuch problem aa gayi.\n"
            "Question dobara bhejo."
        )


# =========================================================
# PHOTO SOLVER
# =========================================================

async def photo_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data[
        "waiting_for_photo"
    ] = True

    await query.message.reply_text(

        "📷 *Snap & Solve*\n\n"

        "Apne question ki clear photo bhejo.\n\n"

        "Main:\n"
        "• Question read karunga\n"
        "• Steps dikhaunga\n"
        "• Final answer dunga\n\n"

        "📸 *Ab photo bhejo!*",

        parse_mode="Markdown"
    )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get(
        "waiting_for_photo"
    ):
        return

    context.user_data[
        "waiting_for_photo"
    ] = False

    await update.message.reply_text(
        "📷 Photo mil gayi!\n"
        "🔍 Question samajh raha hoon..."
    )

    try:

        photo = update.message.photo[-1]

        file = await context.bot.get_file(
            photo.file_id
        )

        image_bytes = await file.download_as_bytearray()

        prompt = """
You are a friendly study tutor.

Look carefully at the uploaded question image.

Solve the question for the student.

Give:
1. What the question asks
2. Given information
3. Step-by-step solution
4. Important formula/concept
5. Final answer

If the image is unclear, tell the student exactly what part is unclear.

Use simple student-friendly language.
"""

        image_part = types.Part.from_bytes(
            data=bytes(image_bytes),
            mime_type="image/jpeg"
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                prompt,
                image_part
            ]
        )

        await update.message.reply_text(
            "📷 *Snap & Solve Result*\n\n"
            + response.text,
            parse_mode="Markdown"
        )

    except Exception as e:

        print("PHOTO ERROR:", e)

        await update.message.reply_text(
            "❌ Photo solve nahi ho paya.\n\n"
            "Clear photo bhejo aur dobara try karo."
        )


# =========================================================
# STUDY CORNER
# =========================================================

async def search_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data[
        "waiting_for_search"
    ] = True

    await update.message.reply_text(

        "📚 *Study Corner*\n\n"

        "Kis topic ko easy language mein samajhna hai?\n\n"

        "Example:\n"
        "• Thermodynamics\n"
        "• Integration\n"
        "• Cell Division\n"
        "• Current Electricity",

        parse_mode="Markdown"
    )


async def study_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get(
        "waiting_for_search"
    ):
        return

    query = update.message.text.strip()

    context.user_data[
        "waiting_for_search"
    ] = False

    await update.message.reply_text(
        "📚 Topic prepare kar raha hoon..."
    )

    try:

        prompt = f"""
Explain this study topic to a student:

{query}

Structure:

📌 Simple Definition

🧠 Core Concept

🔑 Important Points

📝 Example

🎯 Exam Focus

⚡ Quick Revision

Use simple language.
"""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        await update.message.reply_text(
            "📚 *Study Corner*\n\n"
            + response.text,
            parse_mode="Markdown"
        )

    except Exception as e:

        print("SEARCH ERROR:", e)

        await update.message.reply_text(
            "❌ Topic explain nahi ho paya."
        )


# =========================================================
# QUICK QUIZ
# =========================================================

async def quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data[
        "waiting_for_topic"
    ] = True

    await update.message.reply_text(

        "🎯 *Quick Quiz*\n\n"

        "Kis topic ka quiz chahiye?\n\n"

        "Example:\n"
        "• Thermodynamics\n"
        "• Integration\n"
        "• Organic Chemistry\n"
        "• Probability\n\n"

        "👇 Topic bhejo:",

        parse_mode="Markdown"
    )


# =========================================================
# QUIZ GENERATOR
# =========================================================

def generate_quiz(topic):

    prompt = f"""
Create exactly 5 multiple-choice questions.

Topic:
{topic}

Requirements:
- Mix easy, medium and hard.
- Exactly 4 options.
- Only one correct answer.
- correct must be 0,1,2,3.
- Give short explanation.
- Questions must be different.
- Stay strictly on topic.

Return ONLY valid JSON.

Format:

[
 {{
   "question": "Question",
   "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
   ],
   "correct": 0,
   "explanation": "Explanation"
 }}
]
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    text = response.text.strip()

    if text.startswith("```"):

        text = text.replace(
            "```json",
            ""
        )

        text = text.replace(
            "```",
            ""
        )

        text = text.strip()

    quiz_data = json.loads(text)

    if not isinstance(
        quiz_data,
        list
    ):
        raise ValueError(
            "Invalid quiz"
        )

    if len(quiz_data) != 5:
        raise ValueError(
            "Quiz must contain 5 questions"
        )

    return quiz_data


# =========================================================
# RECEIVE QUIZ TOPIC
# =========================================================

async def receive_topic(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get(
        "waiting_for_topic"
    ):
        return

    topic = update.message.text.strip()

    if len(topic) < 2:

        await update.message.reply_text(
            "❌ Proper topic likho bhai."
        )

        return

    context.user_data[
        "waiting_for_topic"
    ] = False

    await update.message.reply_text(

        f"🎯 *Quick Quiz*\n\n"
        f"📚 Topic: *{topic}*\n"
        f"⏳ Questions ready ho rahe hain...",

        parse_mode="Markdown"
    )

    try:

        questions = await asyncio.to_thread(
            generate_quiz,
            topic
        )

        context.user_data[
            "quiz_questions"
        ] = questions

        context.user_data[
            "quiz_index"
        ] = 0

        context.user_data[
            "quiz_score"
        ] = 0

        context.user_data[
            "quiz_topic"
        ] = topic

        user_id = update.effective_user.id

        data = get_user_progress(
            user_id
        )

        data["quizzes"] += 1

        if topic not in data["topics"]:

            data["topics"][topic] = {
                "questions": 0,
                "correct": 0
            }

        await send_poll_question(
            update.effective_chat.id,
            context
        )

    except Exception as e:

        print("QUIZ ERROR:", e)

        await update.message.reply_text(
            "❌ Quiz generate nahi ho paya.\n\n"
            "Topic ko thoda specific karke try karo."
        )


# =========================================================
# SEND POLL
# =========================================================

async def send_poll_question(
    chat_id,
    context: ContextTypes.DEFAULT_TYPE
):

    questions = context.user_data.get(
        "quiz_questions",
        []
    )

    index = context.user_data.get(
        "quiz_index",
        0
    )

    if index >= len(questions):

        await finish_quiz(
            chat_id,
            context
        )

        return

    q = questions[index]

    message = await context.bot.send_poll(

        chat_id=chat_id,

        question=(
            f"📝 Q{index + 1}/"
            f"{len(questions)}\n\n"
            f"{q['question']}"
        ),

        options=q["options"],

        type="quiz",

        correct_option_id=int(
            q["correct"]
        ),

        is_anonymous=False
    )

    poll_data[
        message.poll.id
    ] = {

        "chat_id": chat_id,

        "correct": int(
            q["correct"]
        ),

        "explanation": q[
            "explanation"
        ],

        "topic": context.user_data.get(
            "quiz_topic",
            "General"
        ),

        "question_index": index
    }


# =========================================================
# POLL ANSWER
# =========================================================

async def poll_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    answer = update.poll_answer

    poll_id = answer.poll_id

    if poll_id not in poll_data:
        return

    data = poll_data.pop(
        poll_id
    )

    user_id = answer.user.id

    if not answer.option_ids:
        return

    selected = answer.option_ids[0]

    correct = data["correct"]

    topic = data["topic"]

    user_progress = get_user_progress(
        user_id
    )

    user_progress["questions"] += 1

    user_progress[
        "topics"
    ][topic]["questions"] += 1

    # -----------------------------------------
    # CORRECT
    # -----------------------------------------

    if selected == correct:

        context.user_data[
            "quiz_score"
        ] = (
            context.user_data.get(
                "quiz_score",
                0
            ) + 1
        )

        user_progress[
            "correct"
        ] += 1

        user_progress[
            "topics"
        ][topic]["correct"] += 1

        user_progress[
            "xp"
        ] += 10

        await context.bot.send_message(

            chat_id=data["chat_id"],

            text=(
                "✅ *Correct!*\n\n"
                f"💡 {data['explanation']}\n\n"
                "⭐ +10 XP"
            ),

            parse_mode="Markdown"
        )

    # -----------------------------------------
    # WRONG
    # -----------------------------------------

    else:

        await context.bot.send_message(

            chat_id=data["chat_id"],

            text=(
                "❌ *Not quite!*\n\n"
                f"💡 {data['explanation']}"
            ),

            parse_mode="Markdown"
        )

    # -----------------------------------------
    # NEXT QUESTION
    # -----------------------------------------

    context.user_data[
        "quiz_index"
    ] = (
        data["question_index"] + 1
    )

    await asyncio.sleep(0.5)

    await send_poll_question(
        data["chat_id"],
        context
    )


# =========================================================
# FINISH QUIZ
# =========================================================

async def finish_quiz(
    chat_id,
    context: ContextTypes.DEFAULT_TYPE
):

    score = context.user_data.get(
        "quiz_score",
        0
    )

    questions = context.user_data.get(
        "quiz_questions",
        []
    )

    topic = context.user_data.get(
        "quiz_topic",
        "General"
    )

    total = len(questions)

    if total == 0:
        return

    percentage = (
        score / total
    ) * 100

    if percentage >= 80:

        result = (
            "🔥 Excellent!\n"
            "Preparation strong hai."
        )

    elif percentage >= 60:

        result = (
            "👍 Good job!\n"
            "Thodi aur practice se aur better."
        )

    else:

        result = (
            "💪 Keep going!\n"
            "Weak areas ko target karo."
        )

    keyboard = [

        [
            InlineKeyboardButton(
                "🔄 Next Quiz",
                callback_data="next_quiz"
            )
        ],

        [
            InlineKeyboardButton(
                "📈 My Progress",
                callback_data="progress"
            )
        ],

        [
            InlineKeyboardButton(
                "🎯 Practice More",
                callback_data="weak"
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="menu"
            )
        ]
    ]

    await context.bot.send_message(

        chat_id=chat_id,

        text=(

            "🏆 *QUIZ COMPLETE!*\n\n"

            f"📚 Topic: *{topic}*\n"
            f"🎯 Score: *{score}/{total}*\n"
            f"📊 Accuracy: *{percentage:.0f}%*\n\n"

            f"{result}\n\n"

            "👇 Ab kya karna hai?"
        ),

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),

        parse_mode="Markdown"
    )


# =========================================================
# NEXT QUIZ
# =========================================================

async def next_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    topic = context.user_data.get(
        "quiz_topic"
    )

    if not topic:

        await query.message.reply_text(
            "🎯 Pehle ek topic choose karo."
        )

        return

    await query.message.reply_text(
        f"🔄 *{topic}* ka naya quiz ban raha hai...",
        parse_mode="Markdown"
    )

    try:

        questions = await asyncio.to_thread(
            generate_quiz,
            topic
        )

        context.user_data[
            "quiz_questions"
        ] = questions

        context.user_data[
            "quiz_index"
        ] = 0

        context.user_data[
            "quiz_score"
        ] = 0

        user_id = query.from_user.id

        get_user_progress(
            user_id
        )["quizzes"] += 1

        await send_poll_question(
            query.message.chat.id,
            context
        )

    except Exception as e:

        print("NEXT QUIZ ERROR:", e)

        await query.message.reply_text(
            "❌ Naya quiz generate nahi ho paya."
        )


# =========================================================
# TOPPER MODE START
# =========================================================

async def topper_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data[
        "roadmap_step"
    ] = "goal"

    await query.message.reply_text(

        "🏆 *TOPPER MODE*\n\n"

        "Ab hum tumhara personalised study plan banayenge. 🔥\n\n"

        "Sabse pehle batao:\n\n"

        "🎯 *Tumhara goal / exam kya hai?*\n\n"

        "Example:\n"
        "JEE Main\n"
        "NEET\n"
        "CA Foundation\n"
        "Boards",

        parse_mode="Markdown"
    )


# =========================================================
# ROADMAP TEXT HANDLER
# =========================================================

async def roadmap_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    step = context.user_data.get(
        "roadmap_step"
    )

    if not step:
        return False

    text = update.message.text.strip()

    # -----------------------------------------
    # GOAL
    # -----------------------------------------

    if step == "goal":

        context.user_data[
            "roadmap_goal"
        ] = text

        context.user_data[
            "roadmap_step"
        ] = "date"

        await update.message.reply_text(

            "📅 *Exam date kya hai?*\n\n"
            "Example:\n"
            "10 April 2027",

            parse_mode="Markdown"
        )

        return True

    # -----------------------------------------
    # DATE
    # -----------------------------------------

    if step == "date":

        context.user_data[
            "roadmap_date"
        ] = text

        context.user_data[
            "roadmap_step"
        ] = "subjects"

        await update.message.reply_text(

            "📚 *Kaun-kaun se subjects hain?*\n\n"
            "Example:\n"
            "Physics, Chemistry, Maths",

            parse_mode="Markdown"
        )

        return True

    # -----------------------------------------
    # SUBJECTS
    # -----------------------------------------

    if step == "subjects":

        context.user_data[
            "roadmap_subjects"
        ] = text

        context.user_data[
            "roadmap_step"
        ] = "hours"

        await update.message.reply_text(

            "⏰ *Roz kitne hours realistically padh sakte ho?*\n\n"
            "Example:\n"
            "5 hours",

            parse_mode="Markdown"
        )

        return True

    # -----------------------------------------
    # HOURS
    # -----------------------------------------

    if step == "hours":

        context.user_data[
            "roadmap_hours"
        ] = text

        context.user_data[
            "roadmap_step"
        ] = "level"

        await update.message.reply_text(

            "📊 *Current preparation level?*\n\n"

            "1️⃣ Beginner\n"
            "2️⃣ Average\n"
            "3️⃣ Strong\n\n"

            "Bas ek option bhejo.",

            parse_mode="Markdown"
        )

        return True

    # -----------------------------------------
    # LEVEL
    # -----------------------------------------

    if step == "level":

        level = text.lower()

        if "1" in level or "begin" in level:
            level = "Beginner"

        elif "3" in level or "strong" in level:
            level = "Strong"

        else:
            level = "Average"

        context.user_data[
            "roadmap_level"
        ] = level

        await create_roadmap(
            update,
            context
        )

        return True

    return False


# =========================================================
# CREATE ROADMAP
# =========================================================

async def create_roadmap(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    goal = context.user_data.get(
        "roadmap_goal",
        "Exam"
    )

    exam_date = context.user_data.get(
        "roadmap_date",
        "Not specified"
    )

    subjects = context.user_data.get(
        "roadmap_subjects",
        "All subjects"
    )

    hours = context.user_data.get(
        "roadmap_hours",
        "5"
    )

    level = context.user_data.get(
        "roadmap_level",
        "Average"
    )

    await update.message.reply_text(
        "🏆 *Topper plan ban raha hai...*\n\n"
        "Strategy + revision + tests + weak topics sab set kar raha hoon 🔥",
        parse_mode="Markdown"
    )

    prompt = f"""
Create a high-quality personalized study roadmap.

Student goal:
{goal}

Exam date:
{exam_date}

Subjects:
{subjects}

Daily study time:
{hours}

Current level:
{level}

Create a practical topper-style plan.

Include:

1. Overall strategy
2. Phase 1 - Build concepts
3. Phase 2 - Master concepts
4. Phase 3 - PYQs and practice
5. Phase 4 - Mock tests
6. Final revision phase
7. Weekly structure
8. Daily study structure
9. Revision strategy
10. Mock test strategy
11. Mistake notebook strategy
12. Weak-topic strategy
13. Daily question targets
14. Sunday review system

Make it motivating but realistic.

Do not create an impossible timetable.
"""

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        roadmap = response.text

        user_id = update.effective_user.id

        progress_data = get_user_progress(
            user_id
        )

        progress_data[
            "roadmap"
        ] = {

            "goal": goal,

            "exam_date": exam_date,

            "subjects": subjects,

            "hours": hours,

            "level": level,

            "plan": roadmap,

            "created": str(
                date.today()
            )
        }

        context.user_data[
            "roadmap_step"
        ] = None

        keyboard = [

            [
                InlineKeyboardButton(
                    "📅 Today's Mission",
                    callback_data="mission"
                )
            ],

            [
                InlineKeyboardButton(
                    "📈 My Progress",
                    callback_data="progress"
                )
            ],

            [
                InlineKeyboardButton(
                    "🎯 Practice More",
                    callback_data="weak"
                )
            ]
        ]

        await update.message.reply_text(

            "🏆 *TOPPER MODE ACTIVATED!*\n\n"

            f"🎯 Goal: *{goal}*\n"
            f"📅 Exam: *{exam_date}*\n"
            f"⏰ Daily: *{hours}*\n"
            f"📊 Level: *{level}*\n\n"

            "━━━━━━━━━━━━━━\n\n"

            + roadmap,

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="Markdown"
        )

    except Exception as e:

        print("ROADMAP ERROR:", e)

        await update.message.reply_text(
            "❌ Roadmap generate nahi ho paya.\n"
            "Dobara Topper Mode try karo."
        )


# =========================================================
# DAILY MISSION
# =========================================================

async def daily_mission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    data = get_user_progress(
        user_id
    )

    roadmap = data.get(
        "roadmap"
    )

    if not roadmap:

        await query.message.reply_text(
            "🗺️ Pehle Topper Mode mein apna roadmap banao."
        )

        return

    goal = roadmap.get(
        "goal",
        "Your Goal"
    )

    subjects = roadmap.get(
        "subjects",
        "Your Subjects"
    )

    hours = roadmap.get(
        "hours",
        "5"
    )

    # Use study plan to generate today's mission
    prompt = f"""
Create today's study mission.

Goal:
{goal}

Subjects:
{subjects}

Daily study time:
{hours}

Student should get:

⚡ Concept Block
📝 Practice Block
🔄 Revision Block
📚 PYQ Block
🧠 Mistake Review

Make a realistic one-day mission.
"""

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ Complete Today",
                    callback_data="complete_day"
                )
            ]

        ]

        await query.message.reply_text(

            "📅 *TODAY'S MISSION*\n\n"
            + response.text
            + "\n\n🔥 Focus on consistency, not perfection.",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="Markdown"
        )

    except Exception as e:

        print("MISSION ERROR:", e)

        await query.message.reply_text(
            "❌ Today's mission nahi ban payi."
        )


# =========================================================
# COMPLETE DAY
# =========================================================

async def complete_day(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    data = get_user_progress(
        user_id
    )

    today = str(
        date.today()
    )

    if today in data[
        "completed_days"
    ]:

        await query.message.reply_text(
            "✅ Aaj ka mission already complete hai! 🔥"
        )

        return

    data[
        "completed_days"
    ].append(today)

    data["xp"] += 50

    data["streak"] += 1

    await query.message.reply_text(

        "🏆 *DAY COMPLETE!*\n\n"

        "✅ Today's mission completed\n"
        f"🔥 Current streak: {data['streak']} days\n"
        f"⭐ +50 XP\n\n"

        "Kal phir attack karna hai. 💪",

        parse_mode="Markdown"
    )


# =========================================================
# PROGRESS
# =========================================================

async def progress_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    data = get_user_progress(
        user_id
    )

    questions = data[
        "questions"
    ]

    correct = data[
        "correct"
    ]

    accuracy = (
        correct / questions * 100
        if questions
        else 0
    )

    xp = data.get(
        "xp",
        0
    )

    level = (
        xp // 100
    ) + 1

    message = (

        "📈 *MY PROGRESS*\n\n"

        f"🏆 Level: *{level}*\n"
        f"⭐ XP: *{xp}*\n"
        f"🎯 Quizzes: *{data['quizzes']}*\n"
        f"📝 Questions: *{questions}*\n"
        f"✅ Correct: *{correct}*\n"
        f"📊 Accuracy: *{accuracy:.0f}%*\n"
        f"🔥 Streak: *{data['streak']} days*\n"
    )

    if data["topics"]:

        message += "\n📚 *TOPIC PERFORMANCE*\n\n"

        for topic, stats in data[
            "topics"
        ].items():

            q = stats[
                "questions"
            ]

            c = stats[
                "correct"
            ]

            topic_accuracy = (
                c / q * 100
                if q
                else 0
            )

            if topic_accuracy >= 80:
                icon = "🟢"

            elif topic_accuracy >= 60:
                icon = "🟡"

            else:
                icon = "🔴"

            message += (
                f"{icon} {topic}: "
                f"{topic_accuracy:.0f}%\n"
            )

    # Topper score
    consistency = min(
        data["streak"] * 10,
        100
    )

    accuracy_score = min(
        accuracy,
        100
    )

    topper_score = int(
        (
            accuracy_score
            + consistency
        ) / 2
    )

    message += (
        "\n🏆 *TOPPER SCORE*\n\n"
        f"📊 Accuracy: {accuracy_score:.0f}%\n"
        f"🔥 Consistency: {consistency}%\n"
        f"🏅 Overall: *{topper_score}%*"
    )

    await update.message.reply_text(
        message,
        parse_mode="Markdown"
    )


# =========================================================
# WEAK TOPICS
# =========================================================

async def weak_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    data = get_user_progress(
        user_id
    )

    topics = data.get(
        "topics",
        {}
    )

    if not topics:

        await update.message.reply_text(

            "🎯 *Practice More*\n\n"

            "Abhi enough data nahi hai.\n"
            "Kuch quizzes complete karo, phir main tumhare weak areas identify karunga.",

            parse_mode="Markdown"
        )

        return

    weak = []

    for topic, stats in topics.items():

        q = stats[
            "questions"
        ]

        c = stats[
            "correct"
        ]

        if q:

            accuracy = (
                c / q
            ) * 100

            if accuracy < 60:

                weak.append(
                    (
                        topic,
                        accuracy
                    )
                )

    weak.sort(
        key=lambda x: x[1]
    )

    if not weak:

        await update.message.reply_text(

            "🔥 *Great!*\n\n"
            "Abhi koi major weak topic nahi mila.\n\n"
            "Keep pushing! 🏆",

            parse_mode="Markdown"
        )

        return

    message = (
        "🎯 *PRACTICE MORE*\n\n"
        "Ye topics abhi priority par hain:\n\n"
    )

    for topic, accuracy in weak:

        message += (
            f"🔴 *{topic}*\n"
            f"   Accuracy: {accuracy:.0f}%\n"
            f"   👉 Extra practice recommended\n\n"
        )

    message += (
        "💡 Tip: Pehle sabse low accuracy wale topic ko target karo."
    )

    await update.message.reply_text(
        message,
        parse_mode="Markdown"
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    # -----------------------------------------
    # DOUBT
    # -----------------------------------------

    if data == "ask":

        context.user_data[
            "waiting_for_doubt"
        ] = True

        await query.message.reply_text(

            "💡 *Doubt Buddy*\n\n"
            "Apna question bhejo:",

            parse_mode="Markdown"
        )

    # -----------------------------------------
    # PHOTO
    # -----------------------------------------

    elif data == "photo":

        await photo_button(
            update,
            context
        )

    # -----------------------------------------
    # SEARCH
    # -----------------------------------------

    elif data == "search":

        context.user_data[
            "waiting_for_search"
        ] = True

        await query.message.reply_text(

            "📚 *Study Corner*\n\n"
            "Kis topic ko samajhna hai?",

            parse_mode="Markdown"
        )

    # -----------------------------------------
    # QUIZ
    # -----------------------------------------

    elif data in [
        "quiz",
        "generate_quiz"
    ]:

        context.user_data[
            "waiting_for_topic"
        ] = True

        await query.message.reply_text(

            "🎯 *Quick Quiz*\n\n"

            "Topic bhejo.\n\n"

            "Example:\n"
            "Electrostatics\n"
            "Integration\n"
            "Thermodynamics",

            parse_mode="Markdown"
        )

    # -----------------------------------------
    # TOPPER MODE
    # -----------------------------------------

    elif data == "topper":

        await topper_start(
            update,
            context
        )

    # -----------------------------------------
    # DAILY MISSION
    # -----------------------------------------

    elif data == "mission":

        await daily_mission(
            update,
            context
        )

    # -----------------------------------------
    # COMPLETE DAY
    # -----------------------------------------

    elif data == "complete_day":

        await complete_day(
            update,
            context
        )

    # -----------------------------------------
    # NEXT QUIZ
    # -----------------------------------------

    elif data == "next_quiz":

        await next_quiz(
            update,
            context
        )

    # -----------------------------------------
    # PROGRESS
    # -----------------------------------------

    elif data == "progress":

        user_id = query.from_user.id

        data_progress = get_user_progress(
            user_id
        )

        questions = data_progress[
            "questions"
        ]

        correct = data_progress[
            "correct"
        ]

        accuracy = (
            correct / questions * 100
            if questions
            else 0
        )

        await query.message.reply_text(

            "📈 *MY PROGRESS*\n\n"

            f"🏆 Level: "
            f"{(data_progress.get('xp', 0) // 100) + 1}\n"

            f"⭐ XP: "
            f"{data_progress.get('xp', 0)}\n"

            f"🎯 Quizzes: "
            f"{data_progress['quizzes']}\n"

            f"📝 Questions: "
            f"{questions}\n"

            f"✅ Correct: "
            f"{correct}\n"

            f"📊 Accuracy: "
            f"{accuracy:.0f}%\n"

            f"🔥 Streak: "
            f"{data_progress['streak']} days",

            parse_mode="Markdown"
        )

    # -----------------------------------------
    # WEAK TOPICS
    # -----------------------------------------

    elif data == "weak":

        user_id = query.from_user.id

        data_progress = get_user_progress(
            user_id
        )

        topics = data_progress[
            "topics"
        ]

        weak = []

        for topic, stats in topics.items():

            q = stats[
                "questions"
            ]

            c = stats[
                "correct"
            ]

            if q:

                acc = (
                    c / q
                ) * 100

                if acc < 60:

                    weak.append(
                        (
                            topic,
                            acc
                        )
                    )

        if not weak:

            await query.message.reply_text(

                "🔥 *No major weak topic!*\n\n"
                "Keep practicing and maintain the level. 🏆",

                parse_mode="Markdown"
            )

        else:

            message = (
                "🎯 *PRACTICE MORE*\n\n"
            )

            weak.sort(
                key=lambda x: x[1]
            )

            for topic, acc in weak:

                message += (
                    f"🔴 *{topic}*\n"
                    f"Accuracy: {acc:.0f}%\n\n"
                )

            await query.message.reply_text(
                message,
                parse_mode="Markdown"
            )

    # -----------------------------------------
    # MAIN MENU
    # -----------------------------------------

    elif data == "menu":

        await query.message.reply_text(

            "🏠 *Main Menu*\n\n"
            "👇 Choose what you want to do:",

            reply_markup=main_menu(),

            parse_mode="Markdown"
        )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # Roadmap first
    if context.user_data.get(
        "roadmap_step"
    ):

        handled = await roadmap_handler(
            update,
            context
        )

        if handled:
            return

    # Quiz topic
    if context.user_data.get(
        "waiting_for_topic"
    ):

        await receive_topic(
            update,
            context
        )

        return

    # Doubt
    if context.user_data.get(
        "waiting_for_doubt"
    ):

        await solve_doubt(
            update,
            context
        )

        return

    # Study search
    if context.user_data.get(
        "waiting_for_search"
    ):

        await study_search(
            update,
            context
        )

        return

    await update.message.reply_text(

        "👇 *Main Menu*",

        reply_markup=main_menu(),

        parse_mode="Markdown"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "ERROR:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------
    # COMMANDS
    # -----------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "ask",
            ask_command
        )
    )

    app.add_handler(
        CommandHandler(
            "search",
            search_command
        )
    )

    app.add_handler(
        CommandHandler(
            "quiz",
            quiz
        )
    )

    app.add_handler(
        CommandHandler(
            "progress",
            progress_command
        )
    )

    app.add_handler(
        CommandHandler(
            "weak",
            weak_command
        )
    )

    # -----------------------------------------
    # BUTTONS
    # -----------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # -----------------------------------------
    # POLL ANSWERS
    # -----------------------------------------

    app.add_handler(
        PollAnswerHandler(
            poll_answer
        )
    )

    # -----------------------------------------
    # PHOTO
    # -----------------------------------------

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # -----------------------------------------
    # TEXT
    # -----------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    # -----------------------------------------
    # ERROR
    # -----------------------------------------

    app.add_error_handler(
        error_handler
    )

    # -----------------------------------------
    # RENDER
    # -----------------------------------------

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

        print(
            "🌐 Running on Render Webhook"
        )

        print(
            webhook_url
        )

        app.run_webhook(

            listen="0.0.0.0",

            port=port,

            url_path="telegram",

            webhook_url=webhook_url
        )

    else:

        print(
            "💻 Running locally..."
        )

        app.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
