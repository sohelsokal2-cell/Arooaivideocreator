import os
import uuid
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.config import TELEGRAM_BOT_TOKEN
from app.services.script_generator import generate_script
from app.services.voice_engine import generate_speech
from app.services.character_service import get_or_create_character
from app.services.lip_sync_client import render_lip_sync
from app.services.video_composer import compose_final_video

logger = logging.getLogger(__name__)

# State cache for user sessions
user_sessions = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command with an inviting welcome keyboard."""
    welcome_text = (
        "👋 **স্বাগতম! আমি আপনার AI Stand-Up Comedy Reels Agent!**\n\n"
        "🎬 আমি আপনার জন্য:\n"
        "• ভাইরাল কমেডি আইডিয়া ও স্ক্রিপ্ট লিখব\n"
        "• মানুষের মতো স্বাভাবিক ভয়েস তৈরি করব\n"
        "• স্টেজে দাঁড়ানো কমেডিয়ানের মুখে লিপ-সিঙ্ক করাব\n"
        "• রঙিন রিলস ক্যাপশন ও ব্যাকগ্রাউন্ড মিউজিক বসিয়ে ভিডিও বানিয়ে দেব!\n\n"
        "👉 শুরু করতে নিচের **'নতুন ভিডিও তৈরি করুন'** বাটনে চাপুন:"
    )
    keyboard = [
        [InlineKeyboardButton("🎬 নতুন ভিডিও তৈরি করুন", callback_data="action_new_video")]
    ]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback router for interactive buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "lang": "bn",
            "character": "default",
            "topic": "auto",
            "script": "",
            "awaiting_topic_input": False
        }

    session = user_sessions[user_id]

    # Step 1: Start New Video -> Select Language
    if data == "action_new_video":
        keyboard = [
            [
                InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"),
                InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="lang_hi"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            ]
        ]
        await query.edit_message_text("🌐 **১ম ধাপ: ভিডিওর ভাষা নির্বাচন করুন:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # Step 2: Language Chosen -> Select Character
    elif data.startswith("lang_"):
        session["lang"] = data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton("👩 ডিফল্ট কমেডিয়ান (স্ট্যান্ড-আপ গাল)", callback_data="char_default")],
            [InlineKeyboardButton("🎨 নতুন ক্যারেক্টার (AI দিয়ে তৈরি)", callback_data="char_dynamic")]
        ]
        await query.edit_message_text("🎭 **২য় ধাপ: চরিত্র বা অ্যাভাটার নির্বাচন করুন:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # Step 3: Character Chosen -> Select Topic Mode
    elif data.startswith("char_"):
        session["character"] = data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton("🎲 অটোমেটিক ভাইরাল আইডিয়া", callback_data="topic_auto")],
            [InlineKeyboardButton("✍️ আমি নিজে টপিক লিখব", callback_data="topic_custom")]
        ]
        await query.edit_message_text("💡 **৩য় ধাপ: কমেডি স্ক্রিপ্টের টপিক:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # Step 4A: Topic is Auto -> Generate Script Immediately
    elif data == "topic_auto":
        session["topic"] = "auto"
        await query.edit_message_text("⏳ *Gemini AI দিয়ে স্ক্রিপ্ট ও পাঞ্চলাইন তৈরি করা হচ্ছে...*", parse_mode="Markdown")
        await process_script_generation(query, session)

    # Step 4B: Topic is Custom -> Prompt user to type in chat
    elif data == "topic_custom":
        session["awaiting_topic_input"] = True
        await query.edit_message_text("✍️ আপনি কী বিষয়ের ওপর ভিডিও চান? চ্যাটে বাংলায়, হিন্দিতে বা ইংরেজিতে লিখে পাঠান (যেমন: *অফিসের প্যারা* বা *বিয়ে নিয়ে জোক*):", parse_mode="Markdown")

    # Step 5: Regenerate Script
    elif data == "script_regenerate":
        await query.edit_message_text("🔄 *নতুন আঙ্গিকে স্ক্রিপ্ট পুনরায় লেখা হচ্ছে...*", parse_mode="Markdown")
        await process_script_generation(query, session)

    # Step 6: User Approves Script -> START FULL PRODUCTION!
    elif data == "script_approve":
        await query.edit_message_text("🚀 **অনুমোদন পাওয়া গেছে! ভিডিও প্রোডাকশন শুরু হচ্ছে...**\n\n⏱️ অনুগ্রহ করে ১-২ মিনিট অপেক্ষা করুন...", parse_mode="Markdown")
        await execute_full_video_pipeline(query, session)

    # Cancel
    elif data == "script_cancel":
        await query.edit_message_text("❌ ভিডিও তৈরি বাতিল করা হয়েছে। নতুন ভিডিওর জন্য /create লিখুন।")

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input when user types a custom topic."""
    user_id = update.message.from_user.id
    if user_id in user_sessions and user_sessions[user_id].get("awaiting_topic_input"):
        user_sessions[user_id]["awaiting_topic_input"] = False
        user_sessions[user_id]["topic"] = update.message.text.strip()
        msg = await update.message.reply_text("⏳ *আপনার টপিক নিয়ে কমেডি স্ক্রিপ্ট তৈরি হচ্ছে...*", parse_mode="Markdown")
        await process_script_generation(msg, user_sessions[user_id], is_callback=False)

async def process_script_generation(target_msg, session: dict, is_callback: bool = True):
    """Generates the script and presents the approval UI."""
    script_data = await generate_script(language=session["lang"], topic=session["topic"])
    session["script"] = script_data["script"]
    session["topic"] = script_data["topic"]

    lang_names = {"bn": "বাংলা", "hi": "হিন্দি", "en": "ইংরেজি"}
    char_names = {"default": "ডিফল্ট কমেডিয়ান", "dynamic": "নতুন ক্যারেক্টার"}

    preview_text = (
        f"📝 **কমেডি স্ক্রিপ্ট প্রিভিউ:**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\"{session['script']}\"\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 **টপিক:** {session['topic']}\n"
        f"🗣️ **ভাষা:** {lang_names.get(session['lang'], 'বাংলা')}\n"
        f"🎭 **চরিত্র:** {char_names.get(session['character'], 'ডিফল্ট')}\n\n"
        f"স্ক্রিপ্টটি কি পছন্দ হয়েছে?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Approve & Video বানাও", callback_data="script_approve")],
        [InlineKeyboardButton("🔄 স্ক্রিপ্ট পরিবর্তন করো", callback_data="script_regenerate")],
        [InlineKeyboardButton("❌ বাতিল", callback_data="script_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await target_msg.edit_message_text(preview_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target_msg.edit_text(preview_text, reply_markup=reply_markup, parse_mode="Markdown")

async def execute_full_video_pipeline(query, session: dict):
    """Executes the 4-step zero-GPU production engine."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    try:
        # Step 1: Voice Generation (Edge-TTS)
        await query.message.reply_text("🎙️ **ধাপ ১/৪:** ন্যাচারাল নিউরাল ভয়েস এবং সাবটাইটেল টাইমকোড তৈরি হচ্ছে...")
        voice_res = await generate_speech(
            text=session["script"],
            language=session["lang"],
            gender="female",
            job_id=job_id
        )

        # Step 2: Character Image Retrieval / Cloud Generation
        await query.message.reply_text("🖼️ **ধাপ ২/৪:** কমেডিয়ান ক্যারেক্টার ফ্রেম প্রস্তুত করা হচ্ছে...")
        char_prompt = "default" if session["character"] == "default" else f"comedian on stage {session['topic']}"
        char_path = await get_or_create_character(char_prompt, job_id=job_id)

        # Step 3: Lip-Sync Animation
        await query.message.reply_text("🎭 **ধাপ ৩/৪:** লিপ-সিঙ্ক ও ফেস মুভমেন্ট অ্যানিমেশন রেন্ডার হচ্ছে...")
        raw_video = await render_lip_sync(char_path, voice_res["audio_path"], job_id=job_id)

        # Step 4: Video Compositing (Captions + Punchline Sound Effect)
        await query.message.reply_text("✨ **ধাপ ৪/৪:** রঙিন রিলস সাবটাইটেল ও পাঞ্চলাইন মিউজিক জোড়া লাগানো হচ্ছে...")
        final_video = await compose_final_video(
            raw_video_path=raw_video,
            ass_path=voice_res["ass_path"],
            job_id=job_id,
            add_beat=True
        )

        # Step 5: Deliver final video directly to Telegram chat
        await query.message.reply_text("📤 **ভিডিও তৈরি সম্পন্ন! টেলিগ্রামে পাঠানো হচ্ছে...**")
        with open(final_video, "rb") as video_file:
            caption = (
                f"🎉 **আপনার স্ট্যান্ড-আপ কমেডি রিলস প্রস্তুত!**\n\n"
                f"💡 টপিক: {session['topic']}\n"
                f"🗣️ ভাষা: {session['lang'].upper()}\n"
                f"⏱️ সময়কাল: {int(voice_res['duration'])} সেকেন্ড\n\n"
                f"📲 Instagram Reels, YouTube Shorts বা TikTok-এ আপলোড করতে ডাউনলোড করুন!"
            )
            await query.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True,
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.exception("Pipeline failed")
        await query.message.reply_text(f"⚠️ দুঃখিত, ভিডিও তৈরির সময় একটি সমস্যা হয়েছে: {e}")

def create_bot_app() -> Application:
    """Builds and returns the Telegram Application instance."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in environment!")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN or "DUMMY_TOKEN").build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("create", start_command))
    app.add_handler(CommandHandler("new", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    return app

