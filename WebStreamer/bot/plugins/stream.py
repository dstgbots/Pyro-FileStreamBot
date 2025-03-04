# (c) @EverythingSuckz | @AbirHasan2005

import asyncio
import urllib.parse
from WebStreamer.bot import StreamBot
from WebStreamer.utils.database import Database
from WebStreamer.utils.human_readable import humanbytes
from WebStreamer.vars import Var
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
db = Database(Var.DATABASE_URL, Var.SESSION_NAME)


def get_media_file_size(m):
    media = m.video or m.audio or m.document
    if media and media.file_size:
        return media.file_size
    else:
        return None


def get_media_file_name(m):
    media = m.video or m.document or m.audio
    if media and media.file_name:
        return urllib.parse.quote_plus(media.file_name)
    else:
        return None


def is_streamable(m):
    """Check if the media is suitable for streaming"""
    if not m:
        return False
    if m.video:
        return True
    if m.audio:
        return True
    if m.document:
        mime_type = m.document.mime_type or ""
        if mime_type.startswith(('video/', 'audio/')):
            return True
    return False


@StreamBot.on_message(filters.private & (filters.document | filters.video | filters.audio), group=4)
async def private_receive_handler(c: Client, m: Message):
    if not await db.is_user_exist(m.from_user.id):
        await db.add_user(m.from_user.id)
        await c.send_message(
            Var.BIN_CHANNEL,
            f"#NEW_USER: \n\nNew User [{m.from_user.first_name}](tg://user?id={m.from_user.id}) Started !!"
        )
    if Var.UPDATES_CHANNEL != "None":
        try:
            user = await c.get_chat_member(Var.UPDATES_CHANNEL, m.chat.id)
            if user.status == "kicked":
                await c.send_message(
                    chat_id=m.chat.id,
                    text="Sorry Sir, You are Banned to use me. Contact my [Support Group](https://t.me/JoinOT).",
                    parse_mode="markdown",
                    disable_web_page_preview=True
                )
                return
        except UserNotParticipant:
            await c.send_message(
                chat_id=m.chat.id,
                text="**Please Join My Updates Channel to use this Bot!**\n\nDue to Overload, Only Channel Subscribers can use the Bot!",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("🤖 Join Updates Channel", url=f"https://t.me/{Var.UPDATES_CHANNEL}")
                        ]
                    ]
                ),
                parse_mode="markdown"
            )
            return
        except Exception:
            await c.send_message(
                chat_id=m.chat.id,
                text="Something went Wrong. Contact my [Support Group](https://t.me/JoinOT).",
                parse_mode="markdown",
                disable_web_page_preview=True)
            return
    try:
        log_msg = await m.forward(chat_id=Var.BIN_CHANNEL)
    
        file_name = get_media_file_name(m)
        file_size = humanbytes(get_media_file_size(m))
        
        # Fix for compatibility with different Pyrogram versions
        if hasattr(log_msg, 'message_id'):
            msg_id = log_msg.message_id
        elif hasattr(log_msg, 'id'):
            msg_id = log_msg.id
        else:
            # Fallback with debug info
            print("Available attributes:", dir(log_msg))
            msg_id = getattr(log_msg, 'id', 0)
        
        base_url = "https://{}".format(Var.FQDN) if Var.ON_HEROKU or Var.NO_PORT else \
            "http://{}:{}".format(Var.FQDN, Var.PORT)
            
        stream_link = f"{base_url}/{msg_id}/{file_name}"
        download_link = f"{stream_link}?download=1"
        
        is_media_streamable = is_streamable(m)
        
        # Customize the message based on the media type
        if is_media_streamable:
            msg_text = "Bruh! 😁\nYour Link Generated! 🤓\n\n📂 **File Name:** `{}`\n**File Size:** `{}`\n\n🎬 **Stream Link:** `{}`\n📥 **Download Link:** `{}`"
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Stream Now", url=stream_link)],
                [InlineKeyboardButton("📥 Download Now", url=download_link)]
            ])
        else:
            msg_text = "Bruh! 😁\nYour Link Generated! 🤓\n\n📂 **File Name:** `{}`\n**File Size:** `{}`\n\n📥 **Download Link:** `{}`"
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("📥 Download Now", url=download_link)
            ]])
        
        await log_msg.reply_text(
            text=f"Requested by [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n**User ID:** `{m.from_user.id}`\n**Stream Link:** {stream_link}\n**Download Link:** {download_link}",
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.MARKDOWN,
            quote=True
        )
        
        # Send appropriate message based on media type
        if is_media_streamable:
            await m.reply_text(
                text=msg_text.format(file_name, file_size, stream_link, download_link),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.MARKDOWN,
                quote=True
            )
        else:
            await m.reply_text(
                text=msg_text.format(file_name, file_size, download_link),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.MARKDOWN,
                quote=True
            )
        
    except FloodWait as e:
        print(f"Sleeping for {str(e.x)}s")
        await asyncio.sleep(e.x)
        await c.send_message(
            chat_id=Var.BIN_CHANNEL,
            text=f"Got FloodWait of {str(e.x)}s from [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n\n**User ID:** `{str(m.from_user.id)}`",
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )


@StreamBot.on_message(filters.channel & (filters.document | filters.video), group=-1)
async def channel_receive_handler(bot, broadcast):
    if int(broadcast.chat.id) in Var.BANNED_CHANNELS:
        await bot.leave_chat(broadcast.chat.id)
        return
    try:
        log_msg = await broadcast.forward(chat_id=Var.BIN_CHANNEL)
        
        file_name = get_media_file_name(broadcast)
        
        base_url = "https://{}".format(Var.FQDN) if Var.ON_HEROKU or Var.NO_PORT else \
            "http://{}:{}".format(Var.FQDN, Var.PORT)
            
        stream_link = f"{base_url}/{log_msg.message_id}/{file_name}"
        download_link = f"{stream_link}?download=1"
        
        is_media_streamable = is_streamable(broadcast)
        
        await log_msg.reply_text(
            text=f"**Channel Name:** `{broadcast.chat.title}`\n**Channel ID:** `{broadcast.chat.id}`\n**Stream Link:** {stream_link}\n**Download Link:** {download_link}",
            quote=True,
            parse_mode="Markdown"
        )
        
        if is_media_streamable:
            await bot.edit_message_reply_markup(
                chat_id=broadcast.chat.id,
                message_id=broadcast.message_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎬 Stream Now", url=stream_link)],
                    [InlineKeyboardButton("📥 Download", url=download_link)]
                ])
            )
        else:
            await bot.edit_message_reply_markup(
                chat_id=broadcast.chat.id,
                message_id=broadcast.message_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download", url=download_link)]
                ])
            )
    except FloodWait as w:
        print(f"Sleeping for {str(w.x)}s")
        await asyncio.sleep(w.x)
        await bot.send_message(chat_id=Var.BIN_CHANNEL,
                             text=f"Got FloodWait of {str(w.x)}s from {broadcast.chat.title}\n\n**Channel ID:** `{str(broadcast.chat.id)}`",
                             disable_web_page_preview=True, parse_mode="Markdown")
    except Exception as e:
        await bot.send_message(chat_id=Var.BIN_CHANNEL, text=f"#ERROR_TRACEBACK: `{e}`", disable_web_page_preview=True, parse_mode="Markdown")
        print(f"Can't Edit Broadcast Message!\nError: {e}")
