import threading
import re

from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup

from bot import DOWNLOAD_DIR, dispatcher, DOWNLOAD_STATUS_UPDATE_INTERVAL, Interval
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper import button_build
from bot.helper.ext_utils.bot_utils import is_url
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.ext_utils.bot_utils import get_readable_file_size
from bot.helper.mirror_utils.download_utils.youtube_dl_download_helper import YoutubeDLHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from .mirror import MirrorListener

listener_dict = {}


def _watch(bot, update, isTar=False, isZip=False, isLeech=False, pswd=None):
    mssg = update.message.text
    message_args = mssg.split(' ', maxsplit=2)
    name_args = mssg.split('|', maxsplit=1)
    user_id = update.message.from_user.id
    msg_id = update.message.message_id

    try:
        link = message_args[1].strip()
        if link.startswith("|") or link.startswith("pswd: "):
            link = ''
    except IndexError:
        link = ''
    link = re.split(r"pswd:|\|", link)[0]
    link = link.strip()

    try:
        name = name_args[1]
        name = name.split(' pswd: ')[0]
        name = name.strip()
    except IndexError:
        name = ''

    pswdMsg = mssg.split(' pswd: ')
    if len(pswdMsg) > 1:
        pswd = pswdMsg[1]

    reply_to = update.message.reply_to_message
    if reply_to is not None:
        link = reply_to.text.strip()

    if not is_url(link):
        msg = f"/{BotCommands.WatchCommand} [yt_dl supported link] [quality] |[CustomName] to mirror with youtube_dl.\n\n"
        msg += "<b>Note :- Quality and custom name are optional</b>\n\nExample of quality :- audio, 144, 240, 360, 480, 720, 1080, 2160."
        msg += "\n\nIf you want to use custom filename, enter it after |"
        msg += "\n\nIf you want to add password to zip, enter it after pwsd:"
        msg += f"\n\nExample :-\n<code>/{BotCommands.ZipWatchCommand} https://youtu.be/X8Uf3hu0hWY |Raftaar Goat pswd: video123</code>\n\n"
        msg += "This will upload encrypted video zip, whose password will be <b>video123</b> And Custom name will be <b>Raftaar Goat</b> "
        return sendMessage(msg, bot, update)

    listener = MirrorListener(bot, update, isTar, isZip, isLeech=isLeech, pswd=pswd)
    listener_dict[msg_id] = listener, user_id, link, name

    buttons = button_build.ButtonMaker()
    best_video = "bv*+ba/b"
    best_audio = "ba/b"
    ydl = YoutubeDLHelper(listener)
    try:
        result = ydl.extractMetaData(link, name, True)
    except Exception as e:
        return sendMessage(str(e), bot, update)
    if 'entries' in result:
        for i in ['144', '240', '360', '480', '720', '1080', '1440', '2160']:
            video_format = f"bv*[height<={i}]+ba/b"
            buttons.sbutton(str(i), f"qual {msg_id} {video_format} true")
        buttons.sbutton("Best Videos", f"qual {msg_id} {best_video} true")
        buttons.sbutton("Best Audios", f"qual {msg_id} {best_audio} true")
    else:
        formats = result.get('formats')

        if formats is not None:
            formats_dict = {}

            for frmt in formats:
                if not frmt.get('tbr') or not frmt.get('height'):
                    continue
                if frmt.get('fps'):
                    quality = f"{frmt['height']}p{frmt['fps']}-{frmt['ext']}"
                else:
                    quality = f"{frmt['height']}p-{frmt['ext']}"
                if (
                    quality not in formats_dict
                    or formats_dict[quality][1] < frmt['tbr']
                ):
                    if frmt.get('filesize'):
                        size = frmt['filesize']
                    elif frmt.get('filesize_approx'):
                        size = frmt['filesize_approx']
                    else:
                        size = 0
                    formats_dict[quality] = [size, frmt['tbr']]

            for forDict in formats_dict:
                qual_fps_ext = re.split(r'p|-', forDict, maxsplit=2)
                if qual_fps_ext[1] != '':
                    video_format = f"bv*[height={qual_fps_ext[0]}][fps={qual_fps_ext[1]}][ext={qual_fps_ext[2]}]+ba/b"
                else:
                    video_format = f"bv*[height={qual_fps_ext[0]}][ext={qual_fps_ext[2]}]+ba/b"
                buttonName = f"{forDict} ({get_readable_file_size(formats_dict[forDict][0])})"
                buttons.sbutton(str(buttonName), f"qual {msg_id} {video_format} f")
        buttons.sbutton("Best Video", f"qual {msg_id} {best_video} f")
        buttons.sbutton("Best Audio", f"qual {msg_id} {best_audio} f")

    buttons.sbutton("Cancel", f"qual {msg_id} cancel f")
    YTBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
    sendMarkup('Choose video/playlist quality', bot, update, YTBUTTONS)


def select_format(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    task_id = int(data[1])
    listener, uid, link, name = listener_dict[task_id]
    if user_id != uid:
        return query.answer(text="Don't waste your time!", show_alert=True)
    elif data[2] != "cancel":
        query.answer()
        qual = data[2]
        playlist = data[3]
        ydl = YoutubeDLHelper(listener)
        threading.Thread(target=ydl.add_download,args=(link, f'{DOWNLOAD_DIR}{task_id}', name, qual, playlist)).start()
        if len(Interval) == 0:
            Interval.append(
                setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages)
            )
    del listener_dict[task_id]
    query.message.delete()

def watch(update, context):
    _watch(context.bot, update)

def watchTar(update, context):
    _watch(context.bot, update, True)

def watchZip(update, context):
    _watch(context.bot, update, True, True)

def leechWatch(update, context):
    _watch(context.bot, update, isLeech=True)

def leechWatchZip(update, context):
    _watch(context.bot, update, True, True, isLeech=True)

def leechWatchTar(update, context):
    _watch(context.bot, update, True, isLeech=True)

watch_handler = CommandHandler(BotCommands.WatchCommand, watch,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
zip_watch_handler = CommandHandler(BotCommands.ZipWatchCommand, watchZip,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
tar_watch_handler = CommandHandler(BotCommands.TarWatchCommand, watchTar,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
leech_watch_handler = CommandHandler(BotCommands.LeechWatchCommand, leechWatch,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
leech_zip_watch_handler = CommandHandler(BotCommands.LeechZipWatchCommand, leechWatchZip,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
leech_tar_watch_handler = CommandHandler(BotCommands.LeechTarWatchCommand, leechWatchTar,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
quality_handler = CallbackQueryHandler(select_format, pattern="qual", run_async=True)

dispatcher.add_handler(watch_handler)
dispatcher.add_handler(zip_watch_handler)
dispatcher.add_handler(tar_watch_handler)
dispatcher.add_handler(leech_watch_handler)
dispatcher.add_handler(leech_zip_watch_handler)
dispatcher.add_handler(leech_tar_watch_handler)
dispatcher.add_handler(quality_handler)