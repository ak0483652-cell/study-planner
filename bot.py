import os
import json

from dotenv import load_dotenv
from google import genai

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    raise ValueError("BOT_TOKEN is missing")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing")


# =========================================================
# GEMINI
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# DATA
# =========================================================

progress = {}

poll_data = {}


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "📝 Generate AI Quiz",
                callback_data="generate_quiz"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 My Progress",
                callback_data="progress"
            )
        ]
    ]

    await update.message.reply_text(
        "🎓 *STUDY HELP BOT*\n\n"
        "🤖 Your AI-powered study assistant\n\n"
        "✨ Generate a quiz on ANY topic\n"
        "📚 Practice with AI questions\n"
        "🏆 Get your score\n"
        "📊 Track your progress\n\n"
        "👇 Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# =========================================================
# QUIZ COMMAND
# =========================================================

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_for_topic"] = True

    await update.message.reply_text(
        "🤖 *AI QUIZ GENERATOR*\n\n"
        "✍️ Apna study topic type karo.\n\n"
        "Examples:\n"
        "• Thermodynamics\n"
        "• Integration\n"
        "• Organic Chemistry\n"
        "• Human Digestive System\n"
        "• Probability\n\n"
        "👇 Ab apna topic bhejo:",
        parse_mode="Markdown"
    )


# =========================================================
# GENERATE QUIZ BUTTON
# =========================================================

async def generate_quiz_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data["waiting_for_topic"] = True

    await query.message.reply_text(
        "🤖 *AI QUIZ GENERATOR*\n\n"
        "✍️ Apna study topic type karo.\n\n"
        "Example:\n"
        "`Newton's Laws`\n"
        "`Electrostatics`\n"
        "`Chemical Bonding`\n"
        "`Cell Biology`\n\n"
        "👇 Topic bhejo:",
        parse_mode="Markdown"
    )


# =========================================================
# GEMINI QUIZ GENERATOR
# =========================================================

def generate_quiz(topic):

    prompt = f"""
You are an expert educational quiz generator.

Create exactly 5 multiple-choice questions about:

TOPIC: {topic}

Requirements:

- Questions must be factually correct.
- Mix easy, medium and hard questions.
- Exactly 4 options per question.
- Only one option is correct.
- correct must be 0, 1, 2 or 3.
- Give a short explanation.
- Do not repeat questions.
- Keep questions suitable for students.
- Stay strictly related to the requested topic.
- Return ONLY valid JSON.
- Do not use markdown.
- Do not use ```json.

Return exactly:

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
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    quiz = json.loads(text)

    if not isinstance(quiz, list):
        raise ValueError("Invalid quiz")

    if len(quiz) != 5:
        raise ValueError("Quiz must contain 5 questions")

    for q in quiz:

        if not all(
            key in q
            for key in [
                "question",
                "options",
                "correct",
                "explanation"
            ]
        ):
            raise ValueError("Invalid question")

        if len(q["options"]) != 4:
            raise ValueError("Need exactly 4 options")

        if int(q["correct"]) not in [0, 1, 2, 3]:
            raise ValueError("Invalid correct answer")

    return quiz


# =========================================================
# RECEIVE TOPIC
# =========================================================

async def receive_topic(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.user_data.get("waiting_for_topic"):
        return

    topic = update.message.text.strip()

    if len(topic) < 2:

        await update.message.reply_text(
            "❌ Proper topic likho bhai.\n\n"
            "Example: Thermodynamics"
        )

        return

    context.user_data["waiting_for_topic"] = False

    await update.message.reply_text(
        f"🤖 *AI Quiz generate ho raha hai...*\n\n"
        f"📚 Topic: *{topic}*\n"
        f"⏳ Please wait...",
        parse_mode="Markdown"
    )

    try:

        questions = generate_quiz(topic)

        context.user_data["quiz_questions"] = questions
        context.user_data["quiz_index"] = 0
        context.user_data["quiz_score"] = 0
        context.user_data["quiz_topic"] = topic

        user_id = update.effective_user.id

        if user_id not in progress:

            progress[user_id] = {
                "quizzes": 0,
                "questions": 0,
                "correct": 0,
                "topics": {}
            }

        progress[user_id]["quizzes"] += 1

        if topic not in progress[user_id]["topics"]:

            progress[user_id]["topics"][topic] = {
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
            "❌ Quiz generate nahi ho paaya.\n\n"
            "Topic ko thoda specific karke try karo."
        )


# =========================================================
# SEND TELEGRAM NATIVE QUIZ
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
            f"📝 Q{index + 1}/{len(questions)}\n\n"
            f"{q['question']}"
        ),

        options=q["options"],

        type="quiz",

        correct_option_id=int(
            q["correct"]
        ),

        is_anonymous=False
    )

    poll_data[message.poll.id] = {

        "chat_id": chat_id,

        "correct": int(
            q["correct"]
        ),

        "explanation": q["explanation"],

        "topic": context.user_data.get(
            "quiz_topic",
            "Unknown"
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

    data = poll_data[poll_id]

    user_id = answer.user.id

    if not answer.option_ids:
        return

    selected = answer.option_ids[0]

    correct = data["correct"]

    topic = data["topic"]

    if user_id not in progress:

        progress[user_id] = {
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {}
        }

    progress[user_id]["questions"] += 1

    if topic not in progress[user_id]["topics"]:

        progress[user_id]["topics"][topic] = {
            "questions": 0,
            "correct": 0
        }

    progress[user_id]["topics"][topic]["questions"] += 1


    # =====================================================
    # CORRECT
    # =====================================================

    if selected == correct:

        context.user_data["quiz_score"] = (
            context.user_data.get(
                "quiz_score",
                0
            ) + 1
        )

        progress[user_id]["correct"] += 1

        progress[user_id]["topics"][topic]["correct"] += 1

        await context.bot.send_message(
            chat_id=data["chat_id"],
            text=(
                "✅ *Correct!*\n\n"
                f"💡 {data['explanation']}"
            ),
            parse_mode="Markdown"
        )


    # =====================================================
    # WRONG
    # =====================================================

    else:

        await context.bot.send_message(
            chat_id=data["chat_id"],
            text=(
                "❌ *Wrong!*\n\n"
                f"💡 {data['explanation']}"
            ),
            parse_mode="Markdown"
        )


    # Next question

    context.user_data["quiz_index"] = (
        context.user_data.get(
            "quiz_index",
            0
        ) + 1
    )

    del poll_data[poll_id]

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

        result = "🔥 Excellent! Your preparation is strong."

    elif percentage >= 60:

        result = "👍 Good job! Keep practicing."

    else:

        result = "📚 More practice needed. Keep going!"


    await context.bot.send_message(

        chat_id=chat_id,

        text=(
            "🏆 *AI QUIZ COMPLETED!*\n\n"

            f"📚 Topic: *{topic}*\n"
            f"🎯 Score: *{score}/{total}*\n"
            f"📊 Accuracy: *{percentage:.0f}%*\n\n"

            f"{result}\n\n"

            "🤖 Use /quiz to start another quiz."
        ),

        parse_mode="Markdown"
    )


    # Clear current quiz

    context.user_data.pop(
        "quiz_questions",
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

    context.user_data.pop(
        "quiz_topic",
        None
    )


# =========================================================
# PROGRESS
# =========================================================

async def progress_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    data = progress.get(
        user_id,
        {
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {}
        }
    )

    total_questions = data["questions"]
    correct = data["correct"]

    accuracy = (
        correct / total_questions * 100
        if total_questions
        else 0
    )

    message = (
        "📊 *YOUR PROGRESS*\n\n"
        f"📝 Quizzes: {data['quizzes']}\n"
        f"❓ Questions: {total_questions}\n"
        f"✅ Correct: {correct}\n"
        f"🎯 Accuracy: {accuracy:.0f}%\n"
    )

    topics = data.get("topics", {})

    if topics:

        message += "\n📚 *TOPICS*\n\n"

        for topic, stats in topics.items():

            q = stats["questions"]
            c = stats["correct"]

            topic_accuracy = (
                c / q * 100
                if q
                else 0
            )

            message += (
                f"• {topic}: "
                f"{topic_accuracy:.0f}%\n"
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

    if query.data == "generate_quiz":

        context.user_data["waiting_for_topic"] = True

        await query.message.reply_text(
            "🤖 *AI QUIZ GENERATOR*\n\n"
            "✍️ Apna topic type karo.\n\n"
            "Example:\n"
            "`Electrostatics`\n"
            "`Integration`\n"
            "`Organic Chemistry`\n\n"
            "👇 Topic bhejo:",
            parse_mode="Markdown"
        )


    elif query.data == "progress":

        user_id = query.from_user.id

        data = progress.get(
            user_id,
            {
                "quizzes": 0,
                "questions": 0,
                "correct": 0
            }
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
            parse_mode="Markdown"
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

    # Commands

    app.add_handler(
        CommandHandler(
            "start",
            start
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

    # Buttons

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # Student topic

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_topic
        )
    )

    # Native Telegram polls

    app.add_handler(
        PollAnswerHandler(
            poll_answer
        )
    )

    # =====================================================
    # RENDER WEBHOOK
    # =====================================================

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
            f"🔗 Webhook: {webhook_url}"
        )

        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram",
            webhook_url=webhook_url
        )

    else:

        # Local computer testing

        print(
            "💻 Running locally with polling"
        )

        app.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
