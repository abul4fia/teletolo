#!/usr/bin/env python
from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass
import sys

import arrow
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import PeerChannel
import telethon.tl.types as _tl

import click
import click_config_file
import configobj


@dataclass
class Config:
    api_id: str = "Not specified"
    api_hash: str = "Not specified"
    phone:str = "Not specified"
    username:str = "Not specified"
    channel_id:str = "me"
    msg_limit:int = 100
    days_back:int = 7
    journal_folder:str = "./journals"
    assets_folder:str = "./assets"
    journal_date_fmt:str = "YYYY-MM-DD dddd"
    time_fmt:str = "HH:mm"
    tags:str = ""
    block_fmt:str = "**{time}** {tags} {message}"
    date_header_fmt:str = "## {date}"
    append_to_journal:bool = False
    delete_after_download:bool = False
    dry:bool = False


DEBUG = False

# Auxiliar function for debugging purposes
async def save_as_json(messages, filename):
    import json
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, bytes):
                return list(o)
            return json.JSONEncoder.default(self, o)
    messages = [msg.to_dict() for msg in messages]
    with open(filename, 'w') as outfile:
        json.dump(messages, outfile, cls=DateTimeEncoder)


class TelegramConnector:
    def __init__(self, cfg:Config):
        mandatory = set((cfg.api_id, cfg.api_hash, cfg.username, cfg.phone))
        if "Not specified" in mandatory or None in mandatory:
            print("You have to write a proper .teletolo.ini file, specifying your")
            print("api_id, api_hash, phone and username. See README.md")
            quit()
        self.cfg:Config = cfg
        self.client = TelegramClient(cfg.username, cfg.api_id, cfg.api_hash)

    async def authenticate(self):
        await self.client.start()
        if await self.client.is_user_authorized() == False:
            print("You have to authenticate. Check your Telegram client")
            await self.client.send_code_request(self.cfg.phone)
            try:
                await self.client.sign_in(self.cfg.phone, input('Input the code Telegram sent you: '))
            except SessionPasswordNeededError:
                await self.client.sign_in(password=input('Your password is also required: '))
        me = await self.client.get_me()
        return me

    async def get_channel(self):
        channel = self.cfg.channel_id
        if channel.isdigit():
            entity = PeerChannel(int(channel))
        else:
            entity = channel
        return await self.client.get_entity(entity)

    async def get_messages(self, chan):
        result = []
        date_limit = datetime.now(timezone.utc) - timedelta(self.cfg.days_back)
        async for msg in self.client.iter_messages(chan):
            if msg.date < date_limit:
                break
            if msg.media and DEBUG:
                f = await self.client.download_media(msg.media)
                print(f"{f} dumped")
            result.append(msg)
        return result


class MessagesProcessor:
    def __init__(self, cfg:Config, conn:TelegramConnector):
        self.cfg:Config = cfg
        self.conn = conn
        if self.cfg.append_to_journal:
            self.assets = "assets/"
        else:
            self.assets = ""

    @staticmethod
    def guess_type(msg):
        if isinstance(msg.media, _tl.MessageMediaPhoto):
            return msg.file.mime_type
        if isinstance(msg.media, _tl.MessageMediaDocument):
            return msg.file.mime_type

    async def download_media(self, msg, ts, kind, ext):
        message = msg.message
        fname = f"{self.assets}{kind}_{ts.timestamp()}.{ext}"
        f = await self.conn.client.download_media(msg.media, fname)
        print(f"{kind.title()} downloaded in {f}")
        if message:
            message += "\n"
        mdown = f"{message}![]({f})"
        return mdown

    def get_link_info(self, msg):
        message = msg.message
        url = msg.media.webpage.url
        title = msg.media.webpage.title
        descr = msg.media.webpage.description
        if "twitter" in url:
            embed = "\n{{twitter %s}}" % url
        elif "youtube" in url or "youtu.be" in url:
            embed = "\n{{youtube %s}}" % url
        else:
            embed = ""
        if message:
            message += "\n"
        mdown = f"{message}[{title}]({url})\n{descr}{embed}"
        return mdown

    def get_gps_info(self, msg):
        lat = msg.media.geo.lat
        long = msg.media.geo.long
        mdown = ( 'Localización GPS:\n'
            '[:div {:style {:margin "0 auto" :width 400 }} '
            '[:iframe {:src '
            f'"https://maps.google.com/maps?q={lat},{long}&hl=es&z=14&output=embed"'
            '}]]')
        return mdown

    async def format_message(self, msg):
        mdown = url = title = descr = ""
        _type = self.guess_type(msg)
        ts = arrow.get(msg.date).to("local")
        media = msg.media
        if isinstance(media, _tl.MessageMediaPhoto) or isinstance(media, _tl.MessageMediaDocument) and "gif" in _type:
            ext = "jpg" if "jpeg" in _type else _type.split("/")[-1]
            mdown = await self.download_media(msg, ts, "image", ext)
        elif isinstance(media, _tl.MessageMediaDocument) and "audio" in _type:
            ext = "ogg" if "oga" in _type else _type.split("/")[-1]
            mdown = await self.download_media(msg, ts, "audio", ext)
        elif isinstance(media, _tl.MessageMediaWebPage) and not isinstance(media.webpage, _tl.WebPageEmpty):
            mdown = self.get_link_info(msg)
        elif isinstance(media, _tl.MessageMediaGeo):
            mdown = self.get_gps_info(msg)
        else:
            mdown = msg.message
        if not mdown:
            print(f"Message skipped ({_type})")
        return ts, mdown


    async def preprocess_messages(self, messages):
        delta = timedelta(days=self.cfg.days_back)
        now = datetime.now(timezone.utc)
        results = defaultdict(list)
        ids = []
        for i, msg in enumerate(messages):
            if not isinstance(msg, _tl.Message):
                continue
            if now - msg.date > delta:
                continue
            ts, message = await self.format_message(msg)
            if message:
                results[msg.date.date()].append((ts, message))
                ids.append(msg.id)
        return results, ids

    def format_block_as_markdown(self, day, ts, note, had_header=False):
        time = ts.format(self.cfg.time_fmt)
        block = self.cfg.block_fmt.format(date=day, tags=self.cfg.tags, time=time, message=note)
        prefix = ""
        if had_header:
            prefix = "    "
        return f"{prefix}- {block}"

    def write_to_journal_files(self, results):
        for date, notes in results.items():
            journal_file = arrow.get(date).format("YYYY_MM_DD") + ".md"
            with open(Path("./journals") / journal_file, "a+", encoding="utf-8") as f:
                for ts, note in reversed(notes):
                    f.write("\n")
                    f.write(self.format_block_as_markdown("", ts, note, False))
            n = len(notes)
            if n>1:
                s="s"
            else:
                s=""
            print(f"{n} message{s} appended to journals/{journal_file}")

    def dump_messages(self, results):
        if self.cfg.append_to_journal:
            self.write_to_journal_files(results)
            return
        for date, notes in results.items():
            dump_header = True
            day = arrow.get(date).format(self.cfg.journal_date_fmt)
            date_hdr = self.cfg.date_header_fmt.format(date=day)
            if not date_hdr.strip():
                dump_header = False
            if dump_header:
                print(f"- {day}")
            for ts, note in reversed(notes):
                print(self.format_block_as_markdown(day, ts, note, dump_header))

    async def main(self):
        _ = await self.conn.authenticate()
        my_channel = await self.conn.get_channel()
        messages = await self.conn.get_messages(my_channel)
        if DEBUG:
            await save_as_json(messages, filename='channel_messages.json')
        results, ids = await self.preprocess_messages(messages)
        n = sum(len(msgs) for msgs in results.values())
        print(f"{n} messages downloaded for {len(results)} different dates\n")
        if n == 0:
            return
        self.dump_messages(results)
        if self.cfg.delete_after_download:
            await self.conn.client.delete_messages(my_channel, ids)
            print("The messages downloaded were deleted")



# To read config file
def myprovider(file_path, _):
    filename = Path(file_path).name
    # print(filename)
    return configobj.ConfigObj(filename)

@click.command()
@click.option("--api_id", help="API id from the Telegram developer's console")
@click.option("--api_hash", help="API hash from the Telegram developer's console")
@click.option("--phone", help="Your phone number (with international prefix)")
@click.option("--username", help="Your username in Telegram")
@click.option("--msg_limit", default=100, help="Maximum number of messages to check (from today backwards)")
@click.option("--date_header_fmt", default="## {date}", help="Format for date headers (not used if --append_to_journal was used)")
@click.option("--block_fmt", default = "**{time}** {tags} {message}", help="Format for each dumped message, it can include {time}, {tags}, {date} and {message}")
@click.option("--journal_folder", default="./journals", help="Folder in which journal pages are stored")
@click.option("--assets_folder", default="./assets", help="Folder in which assets (images, audios) are stored")
@click.option("--journal_date_fmt", default="YYYY-MM-DD dddd", help="Format for the {date} part, when used in block_fmt or date_header_fmt")
@click.option("--time_fmt", default="YYYY-MM-DD dddd", help="Format for the {time} part, when used in block_fmt")
@click.option("--channel_id","-c", default="me", help="Channel id from which the messages will be retrieved")
@click.option("--days_back", "-b", default=7, help="Retrieve messages only for the last --days_back days")
@click.option("--tags", "-t", default="", help="String prepended to the message. Eg: #telegram #quick-note")
@click.option("--append_to_journal", "-a", default=True, help="If True, the messages will be appended to the appropriate journal file, acoording with the date. If false, the messages will be dumped in the standard output, grouped by date which will appear in headings")
@click.option("--delete_after_download", "-d", default=False, help="Delete the downloaded messages from the Telegram channel")
@click.option("--dry", "-n", default=False, is_flag=True, help="Do not perform any action, only check parameters and Telegram credentials")
@click_config_file.configuration_option(config_file_name=".teletolo.ini", provider=myprovider)
@click.pass_context
def main(ctx, api_id, api_hash, phone, username, channel_id, msg_limit, days_back,
        delete_after_download, append_to_journal, date_header_fmt, block_fmt,
        journal_folder, assets_folder, journal_date_fmt, time_fmt, tags, dry):
    if sys.platform.startswith("win"):
        sys.stdout.reconfigure(encoding='utf-8')
    cfg = Config(**ctx.params)
    if DEBUG:
        print(cfg)
    conn = TelegramConnector(cfg)
    print(f"Retrieving a maximum of {cfg.msg_limit} messages from past {cfg.days_back} days from '{cfg.channel_id}' Telegram channel")
    print(f"The results will be {'dumped in stdout' if not cfg.append_to_journal else 'appended to journal files'} and the messages will be", end=" ")
    if cfg.delete_after_download:
        print("deleted from Telegram channel after download completes")
    else:
        print("kept in the Telegram channel")
    print()
    # Conectar con la API de telegram
    if dry:
        print("DRY MODE. No action performed")
        return
    with conn.client:
        processor = MessagesProcessor(cfg, conn)
        conn.client.loop.run_until_complete(processor.main())


if __name__ == "__main__":
    main()
