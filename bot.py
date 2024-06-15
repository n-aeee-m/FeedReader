import logging
import time
import os
from dotenv import load_dotenv
from telegram.constants import ParseMode
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CallbackContext, CommandHandler, filters,
    ContextTypes, MessageHandler, Updater
)
from db import (
    add_feed_source, get_all_sources, get_sources,
    is_already_present, remove_feed_source,
    update_source_timestamp
)
from feed import format_feed_item, get_feed_info, read_feed
from archive import capture

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_chat.id
    source = context.args[0]
    if is_already_present(user, source):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' already exists.')
    else:
        add_feed_source(user, source)
        feed_info = get_feed_info(source)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' added.')
        await context.bot.send_message(chat_id=update.effective_chat.id, text=feed_info)

async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_chat.id
    source = context.args[0]
    if is_already_present(user, source):
        remove_feed_source(user, source)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' removed.')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' does not exist.')

async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    userId = update.effective_chat.id
    sources = get_sources(userId)
    if len(sources):
        await context.bot.send_message(chat_id=userId, text="\n".join(sources))
    else:
        await context.bot.send_message(chat_id=userId, text="No sources added yet")

async def archive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_chat.id
    source = context.args[0]
    url, captured = capture(source)
    await context.bot.send_message(chat_id=user, text=url)

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_chat.id
    text_received = update.message.text
    await context.bot.send_message(chat_id=user, text='To add a feed use /add feedurl')

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_chat.id
    await context.bot.send_message(chat_id=user, text='To add a feed use /add feedurl')

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Hello {update.effective_chat.first_name}')

def error(update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text('An error occurred')
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

async def fetch_feeds(context: ContextTypes.DEFAULT_TYPE):
    sources = get_all_sources()
    filter_words = os.getenv('EXCLUDE_WORDS').splitlines()
    for source in sources:
        feeds = read_feed(source["url"], filter_words)
        logger.info(msg="Found " + str(len(feeds)) + " feeds from " + source["url"])
        entry_index = 0
        last_post_updated_time = 0
        for entry in feeds:
            entry_index += 1
            if entry_index > 10:
                break
            if hasattr(entry, 'published_parsed'):
                post_updated_time = int(time.strftime("%Y%m%d%H%M%S", entry.published_parsed))
            elif hasattr(entry, 'updated_parsed'):
                post_updated_time = int(time.strftime("%Y%m%d%H%M%S", entry.updated_parsed))
            else:
                logger.error(msg=source["url"] + " has no time info")
                break
            last_updated_time = int(source["last_updated"])
            if post_updated_time > last_post_updated_time:
                last_post_updated_time = post_updated_time
            if post_updated_time > last_updated_time:
                await context.bot.send_message(chat_id=source["userId"], text=format_feed_item(entry), parse_mode=ParseMode.HTML)
                if os.getenv('ARCHIVE_POSTS') == 'true':
                    capture(entry.link)
        update_source_timestamp(source["userId"], source["url"], last_post_updated_time)

def main():
    load_dotenv()  # Take environment variables from .env.

    # Get the Telegram bot token and feed update interval
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    feed_update_interval = os.getenv('FEED_UPDATE_INTERVAL')

    # Check if the environment variables are set
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    if not feed_update_interval:
        logger.error("FEED_UPDATE_INTERVAL environment variable not set.")
        return

    # Initialize the application
    application = ApplicationBuilder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler('hello', hello))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler('add', add_feed))
    application.add_handler(CommandHandler('remove', remove_feed))
    application.add_handler(CommandHandler('list', list_feeds))
    application.add_handler(CommandHandler('archive', archive_link))

    # Add handler for normal text (not commands)
    application.add_handler(MessageHandler(filters.TEXT, text))

    # Add error handler
    application.add_error_handler(error)

    # Access the job queue and schedule the recurring task
    job_queue = application.job_queue

    # Check if the job_queue is properly initialized
    if job_queue:
        job_queue.run_repeating(fetch_feeds, interval=int(feed_update_interval), first=10)
    else:
        logger.error("Job queue not initialized.")

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
