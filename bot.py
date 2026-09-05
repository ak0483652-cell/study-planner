import os
import json
import asyncio

from dotenv import load_dotenv
from google import genai

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

# =========================
# ENVIRONMENT
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing")

# =========================
# GEMINI
# =========================

client = genai.Client(
    api_key=GEMINI_API_KEY
)

# =========================
# DATA
# =========================

progress = {}
poll_data = {}


def get_progress(user_id):

    if user_id not in progress:
        progress[user_id] = {
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {}
        }

    return progress[user_id]


# =========================
# MAIN MENU
# =========================

def main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "🤖 AI Doubt Solver",
                callback_data="doubt"
            ),
            InlineKeyboardButton(
                "🔍 Study Search",
                callback_data="search"
            )
        ],

        [
            InlineKeyboardButton(
                "📝 Generate AI Quiz",
                callback_data="quiz"
            ),
            InlineKeyboardButton(
                "📊 My Progress",
                callback_data="progress"
            )
        ],

        [
            InlineKeyboardButton(
                "🧠 Weak Topics",
                callback_data="weak"
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(

        "🎓 *STUDY HELP BOT*\n\n"

        "🤖 Your AI-powered study assistant\n\n"

        "✨ AI Doubt Solver\n"
        "🔍 Study Search\n"
        "📝 AI Quiz Generator\n"
        "📊 Progress Tracking\n"
        "🧠 Weak Topic Detector\n\n"

        "👇 Choose an option:",

        reply_markup=main_menu(),

        parse_mode="Markdown"
    )


# =========================
# AI DOUBT
# =========================

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["mode"] = "doubt"

    await update.message.reply_text(

        "🤖 *AI DOUBT SOLVER*\n\n"

        "Apna question bhejo.\n\n"

        "Example:\n"
        "• Explain Newton's second law\n"
        "• What is integration?\n"
        "• Explain Krebs cycle\n\n"

        "💡 Main simple language me explain karunga.",

        parse_mode="Markdown"
    )


async def solve_doubt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    question = update.message.text.strip()

    await update.message.reply_text(
        "🤖 Thinking..."
    )

    prompt = f"""

You are an expert student tutor.

Student question:

{question}

Answer in simple Hinglish.

Rules:
- Explain step by step.
- Use simple language.
- Give examples where useful.
- For numerical questions show calculations.
- Include important exam points.
- Avoid unnecessary complicated words.

"""

    try:

        response = await asyncio.to_thread(

            client.models.generate_content,

            model="gemini-3.6-flash",

            contents=prompt
        )

        answer = response.text.strip()

        await update.message.reply_text(

            "🤖 *AI EXPLANATION*\n\n"
            + answer,

            parse_mode="Markdown",

            reply_markup=main_menu()
        )

        context.user_data["mode"] = None

    except Exception as e:

        print("DOUBT ERROR:", e)

        await update.message.reply_text(
            "❌ AI answer generate nahi hua. Dobara try karo."
        )


# =========================
# SEARCH
# =========================

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["mode"] = "search"

    await update.message.reply_text(

        "🔍 *STUDY SEARCH*\n\n"

        "Jo topic search karna hai bhejo.\n\n"

        "Example:\n"
        "• Photosynthesis\n"
        "• Thermodynamics\n"
        "• Probability\n"
        "• Semiconductor",

        parse_mode="Markdown"
    )


async def study_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.message.text.strip()

    await update.message.reply_text(
        "🔍 Searching..."
    )

    prompt = f"""

You are an educational study assistant.

Topic:

{query}

Give a useful student-friendly study explanation.

Include:

1. Definition
2. Main concepts
3. Important points
4. Formulas/facts if applicable
5. Simple example
6. Exam-important points

Keep the answer clear and concise.

"""

    try:

        response = await asyncio.to_thread(

            client.models.generate_content,

            model="gemini-3.6-flash",

            contents=prompt
        )

        answer = response.text.strip()

        await update.message.reply_text(

            "🔍 *STUDY RESULT*\n\n"
            + answer,

            parse_mode="Markdown",

            reply_markup=main_menu()
        )

        context.user_data["mode"] = None

    except Exception as e:

        print("SEARCH ERROR:", e)

        await update.message.reply_text(
            "❌ Search result generate nahi hua."
        )


# =========================
# QUIZ COMMAND
# =========================

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_for_topic"] = True

    await update.message.reply_text(

        "📝 *AI QUIZ GENERATOR*\n\n"

        "Apna topic type karo.\n\n"

        "Examples:\n"
        "• Physics\n"
        "• Organic Chemistry\n"
        "• Integration\n"
        "• Biology\n"
        "• Thermodynamics\n\n"

        "👇 Topic bhejo:",

        parse_mode="Markdown"
    )


# =========================
# GENERATE QUIZ
# =========================

def generate_quiz(topic):

    prompt = f"""

You are an expert educational quiz generator.

Create exactly 5 MCQ questions about:

TOPIC: {topic}

Requirements:

- Exactly 5 questions.
- Exactly 4 options per question.
- Only one correct answer.
- Mix easy, medium and hard.
- Questions must be factually correct.
- Questions must be different.
- Give a short explanation.
- Stay strictly related to the topic.
- Suitable for students.
- Return ONLY valid JSON.
- No Markdown.
- No ```json.

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
    "explanation": "Short explanation"
  }}
]

"""

    response = client.models.generate_content(

        model="gemini-3.6-flash",

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

    if not isinstance(quiz_data, list):
        raise ValueError("Invalid quiz")

    if len(quiz_data) != 5:
        raise ValueError("Quiz must have 5 questions")

    for q in quiz_data:

        if "question" not in q:
            raise ValueError("Missing question")

        if "options" not in q:
            raise ValueError("Missing options")

        if "correct" not in q:
            raise ValueError("Missing correct answer")

        if "explanation" not in q:
            raise ValueError("Missing explanation")

        if len(q["options"]) != 4:
            raise ValueError("Need 4 options")

        if int(q["correct"]) not in [0, 1, 2, 3]:
            raise ValueError("Invalid correct answer")

    return quiz_data


# =========================
# RECEIVE TOPIC
# =========================

async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get(
        "waiting_for_topic"
    ):
        return

    topic = update.message.text.strip()

    context.user_data[
        "waiting_for_topic"
    ] = False

    await update.message.reply_text(

        f"🤖 Generating quiz for *{topic}*...",

        parse_mode="Markdown"
    )

    try:

        quiz_data = await asyncio.to_thread(

            generate_quiz,

            topic
        )

        user_id = update.effective_user.id

        context.user_data["quiz"] = quiz_data

        context.user_data[
            "quiz_topic"
        ] = topic

        context.user_data[
            "quiz_index"
        ] = 0

        context.user_data[
            "quiz_score"
        ] = 0

        await send_next_poll(
            update,
            context
        )

    except Exception as e:

        print("QUIZ ERROR:", e)

        await update.message.reply_text(

            "❌ Quiz generate nahi hua.\n\n"
            "Please topic dobara try karo."
        )


# =========================
# SEND POLL
# =========================

async def send_next_poll(
    update,
    context
):

    quiz_data = context.user_data.get(
        "quiz"
    )

    index = context.user_data.get(
        "quiz_index",
        0
    )

    if not quiz_data:

        return

    if index >= len(quiz_data):

        await finish_quiz(
            update,
            context
        )

        return

    question = quiz_data[index]

    message = await context.bot.send_poll(

        chat_id=update.effective_chat.id,

        question=(
            f"Q{index + 1}/5\n\n"
            + question["question"]
        ),

        options=question["options"],

        type="quiz",

        correct_option_id=int(
            question["correct"]
        ),

        is_anonymous=False
    )

    poll_data[
        message.poll.id
    ] = {

        "user_id":
            update.effective_user.id,

        "index":
            index
    }


# =========================
# POLL ANSWER
# =========================

async def poll_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    answer = update.poll_answer

    poll_id = answer.poll_id

    if poll_id not in poll_data:
        return

    data = poll_data[poll_id]

    user_id = answer.user.id

    if user_id != data["user_id"]:
        return

    index = data["index"]

    quiz_data = context.user_data.get(
        "quiz",
        []
    )

    if index >= len(quiz_data):
        return

    question = quiz_data[index]

    correct = int(
        question["correct"]
    )

    selected = (

        answer.option_ids[0]

        if answer.option_ids

        else -1
    )

    is_correct = (
        selected == correct
    )

    if is_correct:

        context.user_data[
            "quiz_score"
        ] += 1

        await context.bot.send_message(

            chat_id=user_id,

            text=(

                "✅ *Correct!*\n\n"

                "💡 "
                + question["explanation"]
            ),

            parse_mode="Markdown"
        )

    else:

        await context.bot.send_message(

            chat_id=user_id,

            text=(

                "❌ *Incorrect!*\n\n"

                f"✅ Correct answer: "
                f"*{question['options'][correct]}*\n\n"

                f"💡 {question['explanation']}"
            ),

            parse_mode="Markdown"
        )

    # Progress

    user_progress = get_progress(
        user_id
    )

    user_progress[
        "questions"
    ] += 1

    if is_correct:

        user_progress[
            "correct"
        ] += 1

    topic = context.user_data.get(
        "quiz_topic",
        "Unknown"
    )

    if topic not in user_progress[
        "topics"
    ]:

        user_progress[
            "topics"
        ][topic] = {

            "questions": 0,
            "correct": 0
        }

    user_progress[
        "topics"
    ][topic]["questions"] += 1

    if is_correct:

        user_progress[
            "topics"
        ][topic]["correct"] += 1

    context.user_data[
        "quiz_index"
    ] += 1

    await asyncio.sleep(1)

    await send_next_poll(
        update,
        context
    )


# =========================
# FINISH QUIZ
# =========================

async def finish_quiz(
    update,
    context
):

    user_id = update.effective_user.id

    score = context.user_data.get(
        "quiz_score",
        0
    )

    topic = context.user_data.get(
        "quiz_topic",
        "Unknown"
    )

    user_progress = get_progress(
        user_id
    )

    user_progress[
        "quizzes"
    ] += 1

    percentage = score * 20

    if percentage == 100:

        emoji = "🏆"
        result = "Perfect! Excellent work!"

    elif percentage >= 80:

        emoji = "🔥"
        result = "Great performance!"

    elif percentage >= 60:

        emoji = "👍"
        result = "Good job! Keep practicing."

    else:

        emoji = "📚"
        result = "Keep practicing. You will improve!"

    await context.bot.send_message(

        chat_id=user_id,

        text=(

            f"{emoji} *QUIZ COMPLETE*\n\n"

            f"📚 Topic: {topic}\n"
            f"🎯 Score: {score}/5\n"
            f"📈 Accuracy: {percentage}%\n\n"

            f"{result}"
        ),

        reply_markup=main_menu(),

        parse_mode="Markdown"
    )

    context.user_data.pop(
        "quiz",
        None
    )

    context.user_data.pop(
        "quiz_topic",
        None
    )

    context.user_data.pop(
        "quiz_index",
        None
    )

    context.user_data.pop(
        "quiz_score",
        None
    )


# =========================
# PROGRESS
# =========================

async def progress_command(
    update,
    context
):

    user_id = update.effective_user.id

    data = get_progress(
        user_id
    )

    questions = data["questions"]

    correct = data["correct"]

    accuracy = (

        correct / questions * 100

        if questions

        else 0
    )

    text = (

        "📊 *YOUR PROGRESS*\n\n"

        f"📝 Quizzes: {data['quizzes']}\n"
        f"❓ Questions: {questions}\n"
        f"✅ Correct: {correct}\n"
        f"🎯 Accuracy: {accuracy:.0f}%"
    )

    await update.message.reply_text(

        text,

        reply_markup=main_menu(),

        parse_mode="Markdown"
    )


# =========================
# WEAK TOPICS
# =========================

async def weak_topics(
    update,
    context
):

    user_id = update.effective_user.id

    data = get_progress(
        user_id
    )

    topics = data["topics"]

    if not topics:

        await update.message.reply_text(

            "🧠 *WEAK TOPICS*\n\n"

            "Abhi data nahi hai.\n"
            "Pehle kuch quizzes attempt karo!",

            reply_markup=main_menu(),

            parse_mode="Markdown"
        )

        return

    weak = []

    for topic, stats in topics.items():

        questions = stats["questions"]

        correct = stats["correct"]

        accuracy = (

            correct / questions * 100

            if questions

            else 0
        )

        if accuracy < 70:

            weak.append(
                (topic, accuracy)
            )

    if not weak:

        await update.message.reply_text(

            "🔥 *NO MAJOR WEAK TOPIC*\n\n"

            "Tumhari current performance 70%+ hai.",

            reply_markup=main_menu(),

            parse_mode="Markdown"
        )

        return

    weak.sort(
        key=lambda x: x[1]
    )

    text = "🧠 *YOUR WEAK TOPICS*\n\n"

    for topic, accuracy in weak:

        text += (

            f"🔴 *{topic}*\n"
            f"Accuracy: {accuracy:.0f}%\n\n"
        )

    text += (
        "💡 In topics ko revise karo "
        "aur dobara quiz attempt karo."
    )

    await update.message.reply_text(

        text,

        reply_markup=main_menu(),

        parse_mode="Markdown"
    )


# =========================
# BUTTON HANDLER
# =========================

async def button_handler(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    # AI DOUBT

    if query.data == "doubt":

        context.user_data["mode"] = "doubt"

        await query.message.reply_text(

            "🤖 *AI DOUBT SOLVER*\n\n"
            "Apna question bhejo:",

            parse_mode="Markdown"
        )

    # SEARCH

    elif query.data == "search":

        context.user_data["mode"] = "search"

        await query.message.reply_text(

            "🔍 *STUDY SEARCH*\n\n"
            "Apna topic bhejo:",

            parse_mode="Markdown"
        )

    # QUIZ

    elif query.data == "quiz":

        context.user_data[
            "waiting_for_topic"
        ] = True

        await query.message.reply_text(

            "📝 *AI QUIZ GENERATOR*\n\n"

            "Apna topic bhejo.\n\n"

            "Example:\n"
            "`Electrostatics`",

            parse_mode="Markdown"
        )

    # PROGRESS

    elif query.data == "progress":

        user_id = query.from_user.id

        data = get_progress(
            user_id
        )

        questions = data["questions"]

        correct = data["correct"]

        accuracy = (

            correct / questions * 100

            if questions

            else 0
        )

        await query.message.reply_text(

            "📊 *YOUR PROGRESS*\n\n"

            f"📝 Quizzes: {data['quizzes']}\n"
            f"❓ Questions: {questions}\n"
            f"✅ Correct: {correct}\n"
            f"🎯 Accuracy: {accuracy:.0f}%",

            reply_markup=main_menu(),

            parse_mode="Markdown"
        )

    # WEAK TOPICS

    elif query.data == "weak":

        user_id = query.from_user.id

        data = get_progress(
            user_id
        )

        topics = data["topics"]

        if not topics:

            await query.message.reply_text(

                "🧠 Abhi weak topics detect "
                "karne ke liye data nahi hai.",

                reply_markup=main_menu()
            )

            return

        weak = []

        for topic, stats in topics.items():

            questions = stats["questions"]

            correct = stats["correct"]

            accuracy = (

                correct / questions * 100

                if questions

                else 0
            )

            if accuracy < 70:

                weak.append(
                    (topic, accuracy)
                )

        if not weak:

            await query.message.reply_text(

                "🔥 No major weak topic!\n\n"
                "70%+ accuracy maintained.",

                reply_markup=main_menu()
            )

            return

        weak.sort(
            key=lambda x: x[1]
        )

        text = "🧠 *WEAK TOPICS*\n\n"

        for topic, accuracy in weak:

            text += (

                f"🔴 {topic} — "
                f"{accuracy:.0f}%\n"
            )

        await query.message.reply_text(

            text,

            reply_markup=main_menu(),

            parse_mode="Markdown"
        )


# =========================
# TEXT ROUTER
# =========================

async def text_router(
    update,
    context
):

    if context.user_data.get(
        "waiting_for_topic"
    ):

        await receive_topic(
            update,
            context
        )

        return

    mode = context.user_data.get(
        "mode"
    )

    if mode == "doubt":

        await solve_doubt(
            update,
            context
        )

        return

    if mode == "search":

        await study_search(
            update,
            context
        )

        return

    await update.message.reply_text(
        "👇 Menu se option choose karo:",
        reply_markup=main_menu()
    )


# =========================
# MAIN
# =========================

def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands

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
            weak_topics
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

    # Text

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router
        )
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

    print(
        "🚀 STUDY HELP BOT STARTING..."
    )

    if render_url:

        webhook_url = (
            f"{render_url}/telegram"
        )

        print(
            "🌐 Webhook:",
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


if __name__ == "__main__":
    main()
