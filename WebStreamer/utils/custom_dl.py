# (c) @AbirHasan2005

import os
import asyncio
import logging
import threading
from typing import Dict, Union
from WebStreamer.vars import Var
from pyrogram.types import Message
from pyrogram import Client, utils, raw
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.session import Session, Auth
from pyrogram.file_id import FileId, FileType, ThumbnailSource


class ByteStreamer:
    def __init__(self, client: Client):
        self.client = client
        self.cached_file_ids = {}
        # Change how we handle clean_cache to avoid the "no running event loop" error
        # Instead of using create_task here, we'll initialize it later when the bot starts
        self._cache_cleaner = None

    async def start_cache_cleaner(self):
        """Method to start the cache cleaner task after the bot is running"""
        self._cache_cleaner = asyncio.create_task(self.clean_cache())

    async def clean_cache(self):
        """A task that periodically cleans the cached file IDs"""
        while True:
            await asyncio.sleep(600)  # Clean every 10 minutes
            self.cached_file_ids.clear()
            logging.info("Cleaned cached file IDs")

    async def get_file_properties(self, message: Message) -> Dict[str, Union[str, int]]:
        """
        Returns file properties of the given Pyrogram message.
        """
        file_id = None
        file_size = None
        mime_type = None
        file_name = None

        if message.document:
            file_id = message.document.file_id
            file_size = message.document.file_size
            mime_type = message.document.mime_type
            file_name = message.document.file_name
        elif message.video:
            file_id = message.video.file_id
            file_size = message.video.file_size
            mime_type = message.video.mime_type
            file_name = message.video.file_name
        elif message.audio:
            file_id = message.audio.file_id
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type
            file_name = message.audio.file_name
        elif message.photo:
            largest_photo = message.photo.sizes[-1]
            file_id = largest_photo.file_id
            file_size = largest_photo.file_size
            mime_type = "image/jpeg"
            file_name = f"photo_{message.photo.file_id}.jpg"
        elif message.voice:
            file_id = message.voice.file_id
            file_size = message.voice.file_size
            mime_type = message.voice.mime_type
            file_name = f"voice_{message.voice.file_id}.{message.voice.mime_type.split('/')[-1]}"
        # Add more file types as needed

        return {
            "file_id": file_id,
            "file_size": file_size,
            "mime_type": mime_type or "application/octet-stream",
            "file_name": file_name or f"file_{file_id}"
        }

    async def get_location(self, file_id: str) -> str:
        """
        Gets the location of the given file_id.
        """
        if file_id in self.cached_file_ids:
            return self.cached_file_ids[file_id]

        try:
            message = await self.client.get_messages(Var.BIN_CHANNEL, message_ids=int(file_id))
            media = message.document or message.video or message.audio or message.photo or message.voice
            if not media:
                return None

            decoded = FileId.decode(media.file_id)
            file_reference = decoded.file_reference
            
            # Store in cache
            self.cached_file_ids[file_id] = file_reference
            return file_reference
        except Exception as e:
            logging.error(f"Error getting location: {str(e)}")
            return None

    async def yield_file(self, file_id: str, offset: int, first_part_cut: int,
                         last_part_cut: int, part_count: int, chunk_size: int) -> bytes:
        """
        Yield file from a specific offset with specific part cut.
        """
        logging.info(f"Yielding file {file_id} (offset: {offset}, part_cut: {first_part_cut})")
        
        try:
            message = await self.client.get_messages(Var.BIN_CHANNEL, message_ids=int(file_id))
            if not message:
                logging.error(f"Message not found for ID: {file_id}")
                return b""

            media = message.document or message.video or message.audio or message.photo or message.voice
            if not media:
                logging.error(f"No media found in message: {file_id}")
                return b""

            # Get file ID information
            file_id_obj = FileId.decode(media.file_id)
            
            # Get the file reference
            file_reference = file_id_obj.file_reference

            # Create session to download the chunk
            session = Session(self.client, await Auth(self.client, file_id_obj.dc_id, False).create())
            
            # Calculate download parameters
            download_args = (
                file_id_obj.media_id,
                file_id_obj.access_hash,
                file_reference,
                offset,
                chunk_size  # Download chunk by chunk
            )
            
            # Download the file chunk
            result = await session.send(
                raw.functions.upload.GetFile(
                    location=raw.types.InputDocumentFileLocation(*download_args),
                    offset=offset,
                    limit=chunk_size  # Maximum chunk size
                )
            )
            
            # Extract the bytes from the result
            await session.stop()
            return result.bytes
            
        except Exception as e:
            logging.error(f"Error yielding file: {str(e)}")
            return b""


# Initialize the streamer but don't create the cache cleaner task yet
streamer = ByteStreamer(None)  # We'll set the client later

# Function to properly initialize the streamer with the client
def initialize_streamer(client):
    global streamer
    streamer.client = client
