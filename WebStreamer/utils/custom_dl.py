# (c) @AbirHasan2005

import math
import asyncio
import logging
from typing import Dict, Union
from WebStreamer.vars import Var
from WebStreamer.bot import StreamBot
from pyrogram import raw, Client, utils
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource

class ByteStreamer:
    def __init__(self, client: Client):
        """A custom class that holds the cache of a specific client and class functions.
        attributes:
            client: the client that the cache is for.
            cached_file_ids: a dict of cached file IDs.
        
        functions:
            generate_media_session: returns the media session for the file.
            yield_file: yields the file data.
            
        This is a modified version of the ByteStreamer class to work with newer versions of Pyrogram.
        """
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.cached_file_ids: Dict[int, FileId] = {}
        self.cached_file_properties: Dict[int, dict] = {}
        asyncio.create_task(self.clean_cache())

    async def clean_cache(self):
        """Cleans the cache of the client."""
        while True:
            await asyncio.sleep(self.clean_timer)
            self.cached_file_ids.clear()
            self.cached_file_properties.clear()

    async def get_file_properties(self, message_id: int) -> Dict[str, Union[str, int]]:
        """Returns the properties of a file.
        
        Parameters:
            message_id: The ID of the message.
            
        Returns:
            dict: The properties of the file.
        """
        if message_id not in self.cached_file_properties:
            await self.generate_file_properties(message_id)
        return self.cached_file_properties[message_id]

    async def generate_file_properties(self, message_id: int) -> None:
        """Generates the properties of a file.
        
        Parameters:
            message_id: The ID of the message.
        """
        message = await self.client.get_messages(Var.BIN_CHANNEL, message_id)
        
        if not message.media:
            raise ValueError("No media in the message")
        
        media = message.video or message.audio or message.document
        if not media:
            raise ValueError("No video, audio, or document in the message")
        
        self.cached_file_properties[message_id] = {
            "file_name": media.file_name,
            "mime_type": getattr(media, "mime_type", "application/octet-stream"),
            "file_size": media.file_size,
            "media_type": "video" if message.video else "audio" if message.audio else "document"
        }

    async def generate_media_session(self, client: Client, message_id: int) -> Session:
        """Generates a media session for the file.
        
        Parameters:
            client: The client.
            message_id: The ID of the message.
            
        Returns:
            Session: A media session for the file.
        """
        message = await client.get_messages(Var.BIN_CHANNEL, message_id)
        
        if not message.media:
            raise ValueError("No media in the message")
        
        media = message.video or message.audio or message.document
        if not media:
            raise ValueError("No video, audio, or document in the message")
        
        file_id_obj = None
        
        # Get file_id from the appropriate attribute
        file_id_str = getattr(media, "file_id", None)
        if file_id_str:
            try:
                file_id_obj = FileId.decode(file_id_str)
                self.cached_file_ids[message_id] = file_id_obj
            except Exception as e:
                logging.error(f"Failed to decode file_id: {e}")
        
        if not file_id_obj:
            raise ValueError("Could not decode file_id")

        # Create a new session for media downloading
        session = Session(client, await client.storage.dc_id(), await client.storage.auth_key(),
                          await client.storage.test_mode())
        
        # Connect to the correct DC if the file is located on a different DC
        if file_id_obj.dc_id != await client.storage.dc_id():
            # Export auth to the media DC
            auth_key = await Auth(client, file_id_obj.dc_id, await client.storage.test_mode()).create()
            session = Session(client, file_id_obj.dc_id, auth_key, await client.storage.test_mode())
            
            # Connect to the media DC
            await session.start()

        return session, file_id_obj

    async def yield_file(self, message_id: int, offset: int, first_part_cut: int,
                          last_part_cut: int, part_count: int, chunk_size: int) -> bytes:
        """Yields the file data.
        
        Parameters:
            message_id: The ID of the message.
            offset: The offset of the file.
            first_part_cut: The cut of the first part.
            last_part_cut: The cut of the last part.
            part_count: The number of parts.
            chunk_size: The size of a chunk.
            
        Yields:
            bytes: The file data.
        """
        client = self.client
        
        try:
            # Generate media session
            session, file_id_obj = await self.generate_media_session(client, message_id)
            
            # Calculate proper offset and limits for downloading
            proper_part_size = chunk_size
            end_offset = offset + proper_part_size
            
            # Get file reference from the message
            message = await client.get_messages(Var.BIN_CHANNEL, message_id)
            media = message.video or message.audio or message.document
            
            # Get file reference
            file_reference = getattr(media, "file_reference", b"")
            
            # Prepare the request to get the file
            request = raw.functions.upload.GetFile(
                location=raw.types.InputDocumentFileLocation(
                    id=file_id_obj.media_id,
                    access_hash=file_id_obj.access_hash,
                    file_reference=file_reference,
                    thumb_size=""  # Large thumbnail for photos, empty string for other files
                ),
                offset=offset,
                limit=proper_part_size
            )
            
            # Send the request and get the response
            r = await session.send(request)
            
            # If the response is a FileType.UPLOAD_NOPREMIUM, we need to handle it
            if isinstance(r, raw.types.upload.File):
                chunk = r.bytes
                if chunk:
                    yield chunk
            else:
                logging.error(f"Unknown response type: {type(r)}")
            
        except Exception as e:
            logging.error(f"Error in yield_file: {e}")
            yield b""

# Create a global instance of ByteStreamer
streamer = ByteStreamer(StreamBot)
