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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_chat.id
        if not context.args:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide a feed URL.")
            return

        source = context.args[0]
        if is_already_present(user, source):
            await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' already exists.')
        else:
            add_feed_source(user, source)
            feed_info = get_feed_info(source)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' added.')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=feed_info)
    except Exception as e:
        logger.error(f"Error in add_feed: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def remove_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_chat.id
        if not context.args:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide a feed URL to remove.")
            return

        source = context.args[0]
        if is_already_present(user, source):
            remove_feed_source(user, source)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' removed.')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=source + ' does not exist.')
    except Exception as e:
        logger.error(f"Error in remove_feed: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        userId = update.effective_chat.id
        sources = get_sources(userId)
        if len(sources):
            await context.bot.send_message(chat_id=userId, text="\n".join(sources))
        else:
            await context.bot.send_message(chat_id=userId, text="No sources added yet")
    except Exception as e:
        logger.error(f"Error in list_feeds: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def archive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_chat.id
        if not context.args:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please provide a URL to archive.")
            return

        source = context.args[0]
        url, captured = capture(source)
        await context.bot.send_message(chat_id=user, text=url)
    except Exception as e:
        logger.error(f"Error in archive_link: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_chat.id
        await context.bot.send_message(chat_id=user, text='To add a feed use /add feedurl')
    except Exception as e:
        logger.error(f"Error in text: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = update.effective_chat.id
        await context.bot.send_message(chat_id=user, text='To add a feed use /add feedurl')
    except Exception as e:
        logger.error(f"Error in help: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Hello {update.effective_chat.first_name}')
    except Exception as e:
        logger.error(f"Error in hello: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    try:
        await update.message.reply_text('An error occurred')
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}", exc_info=True)

async def fetch_feeds(context: ContextTypes.DEFAULT_TYPE):
    try:
        sources = get_all_sources()
        filter_words = os.getenv('EXCLUDE_WORDS').splitlines()
        for source in sources:
            feeds = read_feed(source["url"], filter_words)
            logger.info(f"Found {len(feeds)} feeds from {source['url']}")
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
                    logger.error(f"{source['url']} has no time info")
                    break
                last_updated_time = int(source["last_updated"])
                if post_updated_time > last_post_updated_time:
                    last_post_updated_time = post_updated_time
                if post_updated_time > last_updated_time:
                    await context.bot.send_message(chat_id=source["userId"],
                                                   text=format_feed_item(entry),
                                                   parse_mode=ParseMode.HTML)
                    if os.getenv('ARCHIVE_POSTS') == 'true':
                        # Add the link to archive.org
                        capture(entry.link)

            update_source_timestamp(source["userId"], source["url"], last_post_updated_time)
    except Exception as e:
        logger.error(f"Error in fetch_feeds: {str(e)}", exc_info=True)

def main():
    load_dotenv()  # take environment variables from .env.
    application = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    application.add_handler(CommandHandler('hello', hello))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler('add', add_feed))
    application.add_handler(CommandHandler('remove', remove_feed))
    application.add_handler(CommandHandler('list', list_feeds))
    application.add_handler(CommandHandler('archive', archive_link))

    # add an handler for normal text (not commands)
    application.add_handler(MessageHandler(filters.TEXT, text))
    # add an handler for errors
    application.add_error_handler(error)

    job_queue = application.job_queue
    job_queue.run_repeating(fetch_feeds, interval=int(os.getenv('FEED_UPDATE_INTERVAL')), first=10)
    application.run_polling()

if __name__ == '__main__':
    main()
