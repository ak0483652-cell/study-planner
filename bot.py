import os
import json
from dotenv import load_dotenv

from google import genai

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
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in .env")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing in .env")


# =========================================================
# GEMINI
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# DATA
# =========================================================

# User progress
progress = {}

# Active Telegram polls
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

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎓 *Study Help Bot*\n\n"
        "🤖 Your AI-powered study assistant\n\n"
        "✨ Generate quizzes on ANY topic\n"
        "📚 Practice & improve your knowledge\n"
        "🏆 Track your score\n\n"
        "👇 Choose an option:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# =========================================================
# QUIZ COMMAND
# =========================================================

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_for_topic"] = True

    await update.message.reply_text(
        "🤖 *AI Quiz Generator*\n\n"
        "📚 Kis topic ka quiz chahiye?\n\n"
        "Bas topic ka naam bhejo 👇\n\n"
        "Examples:\n"
        "• Thermodynamics\n"
        "• Integration\n"
        "• Chemical Bonding\n"
        "• Cell Biology\n"
        "• Indian Economy\n\n"
        "✨ Tum koi bhi study topic likh sakte ho.",
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
        "🤖 *AI Quiz Generator*\n\n"
        "📚 Kis topic ka quiz chahiye?\n\n"
        "Bas topic ka naam bhejo 👇\n\n"
        "Examples:\n"
        "• Thermodynamics\n"
        "• Integration\n"
        "• Organic Chemistry\n"
        "• Photosynthesis\n"
        "• Probability\n\n"
        "✨ Koi bhi topic likh sakte ho.",
        parse_mode="Markdown"
    )


# =========================================================
# AI QUIZ GENERATOR
# =========================================================

def generate_quiz(topic):

    prompt = f"""
You are an expert educational quiz generator.

Create exactly 5 multiple-choice questions about:

TOPIC: {topic}

Requirements:

1. Questions must be factually correct.
2. Mix easy, medium and hard questions.
3. Each question must have exactly 4 options.
4. Only ONE option can be correct.
5. correct must be 0, 1, 2 or 3.
6. Give a short explanation.
7. Do not repeat questions.
8. Questions should be suitable for students.
9. Stay strictly related to the requested topic.
10. Return ONLY valid JSON.
11. Do NOT use markdown.
12. Do NOT use ```json.

Return exactly this format:

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

    # Remove markdown if Gemini accidentally adds it
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    quiz = json.loads(text)

    # Basic validation
    if not isinstance(quiz, list):
        raise ValueError("Invalid quiz format")

    if len(quiz) != 5:
        raise ValueError("Quiz must contain 5 questions")

    for question in quiz:

        if "question" not in question:
            raise ValueError("Question missing")

        if "options" not in question:
            raise ValueError("Options missing")

        if "correct" not in question:
            raise ValueError("Correct answer missing")

        if "explanation" not in question:
            raise ValueError("Explanation missing")

        if len(question["options"]) != 4:
            raise ValueError("Must have exactly 4 options")

        if int(question["correct"]) not in [0, 1, 2, 3]:
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
            "❌ Thoda proper topic likho bhai.\n\n"
            "Example: Thermodynamics"
        )

        return

    # Stop waiting
    context.user_data["waiting_for_topic"] = False

    await update.message.reply_text(
        f"🤖 *AI Quiz Generate Ho Raha Hai...*\n\n"
        f"📚 Topic: *{topic}*\n\n"
        "⏳ Please wait...",
        parse_mode="Markdown"
    )

    try:

        # Generate AI questions
        questions = generate_quiz(topic)

        # Save quiz
        context.user_data["quiz_questions"] = questions
        context.user_data["quiz_index"] = 0
        context.user_data["quiz_score"] = 0
        context.user_data["quiz_topic"] = topic

        # User progress
        user_id = update.effective_user.id

        if user_id not in progress:

            progress[user_id] = {
                "quizzes": 0,
                "questions": 0,
                "correct": 0,
                "topics": {}
            }

        progress[user_id]["quizzes"] += 1

        # Save topic
        if topic not in progress[user_id]["topics"]:
            progress[user_id]["topics"][topic] = {
                "questions": 0,
                "correct": 0
            }

        # Send first poll
        await send_poll_question(
            update.effective_chat.id,
            context
        )

    except Exception as e:

        print("AI QUIZ ERROR:", e)

        await update.message.reply_text(
            "❌ Quiz generate nahi ho paaya.\n\n"
            "Please topic ko thoda simple/specific karke "
            "dobara try karo."
        )


# =========================================================
# SEND NATIVE TELEGRAM QUIZ POLL
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

    # Quiz finished
    if index >= len(questions):

        await finish_quiz(
            chat_id,
            context
        )

        return

    question = questions[index]

    poll_message = await context.bot.send_poll(

        chat_id=chat_id,

        question=(
            f"📝 Q{index + 1}/{len(questions)}\n\n"
            f"{question['question']}"
        ),

        options=question["options"],

        type="quiz",

        correct_option_id=int(
            question["correct"]
        ),

        is_anonymous=False
    )

    # Save poll information
    poll_data[poll_message.poll.id] = {

        "chat_id": chat_id,

        "correct": int(
            question["correct"]
        ),

        "explanation": question["explanation"],

        "question_index": index,

        "topic": context.user_data.get(
            "quiz_topic",
            "Unknown"
        )
    }


# =========================================================
# HANDLE POLL ANSWER
# =========================================================

async def poll_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    answer = update.poll_answer

    poll_id = answer.poll_id

    # Unknown poll
    if poll_id not in poll_data:
        return

    data = poll_data[poll_id]

    user_id = answer.user.id

    # No answer
    if not answer.option_ids:
        return

    selected = answer.option_ids[0]

    correct = data["correct"]

    topic = data["topic"]

    # Create progress if necessary
    if user_id not in progress:

        progress[user_id] = {
            "quizzes": 0,
            "questions": 0,
            "correct": 0,
            "topics": {}
        }

    # Update total questions
    progress[user_id]["questions"] += 1

    # Update topic statistics
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

        # Update quiz score
        current_score = context.user_data.get(
            "quiz_score",
            0
        )

        context.user_data["quiz_score"] = (
            current_score + 1
        )

        # Update progress
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

    # Remove old poll
    del poll_data[poll_id]

    # Send next question
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

    # Result message
    if percentage >= 80:

        result = (
            "🔥 Excellent!\n"
            "Your preparation is looking strong."
        )

    elif percentage >= 60:

        result = (
            "👍 Good job!\n"
            "Keep practicing to improve."
        )

    else:

        result = (
            "📚 More practice needed.\n"
            "Don't worry, keep learning!"
        )

    await context.bot.send_message(

        chat_id=chat_id,

        text=(
            "🏆 *AI QUIZ COMPLETED!*\n\n"

            f"📚 Topic: *{topic}*\n"
            f"🎯 Score: *{score}/{total}*\n"
            f"📊 Accuracy: *{percentage:.0f}%*\n\n"

            f"{result}\n\n"

            "🤖 Want another quiz?\n"
            "Use /quiz"
        ),

        parse_mode="Markdown"
    )

    # Clear quiz
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

    quizzes = data["quizzes"]
    questions = data["questions"]
    correct = data["correct"]

    if questions > 0:

        accuracy = (
            correct / questions
        ) * 100

    else:

        accuracy = 0

    message = (
        "📊 *YOUR PROGRESS*\n\n"

        f"📝 AI Quizzes: {quizzes}\n"
        f"❓ Questions: {questions}\n"
        f"✅ Correct: {correct}\n"
        f"🎯 Accuracy: {accuracy:.0f}%\n"
    )

    # Topics
    topics = data.get(
        "topics",
        {}
    )

    if topics:

        message += "\n📚 *TOPICS*\n\n"

        for topic, stats in topics.items():

            topic_questions = stats["questions"]
            topic_correct = stats["correct"]

            if topic_questions > 0:

                topic_accuracy = (
                    topic_correct /
                    topic_questions
                ) * 100

            else:

                topic_accuracy = 0

            message += (
                f"• {topic}: "
                f"{topic_accuracy:.0f}%\n"
            )

    message += (
        "\n🚀 Keep studying and improve your score!"
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

        context.user_data[
            "waiting_for_topic"
        ] = True

        await query.message.reply_text(

            "🤖 *AI Quiz Generator*\n\n"

            "✍️ Apna topic type karo.\n\n"

            "Example:\n"
            "`Thermodynamics`\n"
            "`Integration`\n"
            "`Organic Chemistry`\n"
            "`Cell Biology`\n\n"

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
                "correct": 0,
                "topics": {}
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

    # Student topic messages
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_topic
        )
    )

    # Telegram native quiz polls
    app.add_handler(
        PollAnswerHandler(
            poll_answer
        )
    )

    print(
        "🤖 AI Study Help Bot is running..."
    )

    app.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
    
