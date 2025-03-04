# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import math
import logging
import secrets
import mimetypes
from ..vars import Var
from aiohttp import web
from ..bot import StreamBot
from ..utils.custom_dl import TGCustomYield, chunk_size, offset_fix

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    bot_details = await StreamBot.get_me()
    return web.json_response({"status": "running",
                              "server_permission": "Open",
                              "telegram_bot": '@'+bot_details.username})


@routes.get("/{message_id}")
@routes.get("/{message_id}/")
@routes.get(r"/{message_id:\d+}/{name}")
async def stream_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        return await media_streamer(request, message_id)
    except ValueError as e:
        logging.error(e)
        raise web.HTTPNotFound


async def media_streamer(request, message_id: int):
    range_header = request.headers.get('Range', 0)
    media_msg = await StreamBot.get_messages(Var.BIN_CHANNEL, message_id)
    file_properties = await TGCustomYield().generate_file_properties(media_msg)
    file_size = file_properties.file_size
    
    # Check if this is a download request
    is_download = False
    if request.query.get('download'):
        is_download = True

    # Determine the file name and MIME type
    file_name = file_properties.file_name if file_properties.file_name \
        else f"{secrets.token_hex(2)}.jpeg"
    mime_type = file_properties.mime_type if file_properties.mime_type \
        else mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    if range_header:
        from_bytes, until_bytes = range_header.replace('bytes=', '').split('-')
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = request.http_range.stop or file_size - 1

    req_length = until_bytes - from_bytes

    new_chunk_size = await chunk_size(req_length)
    offset = await offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % new_chunk_size) + 1
    part_count = math.ceil(req_length / new_chunk_size)
    body = TGCustomYield().yield_file(media_msg, offset, first_part_cut, last_part_cut, part_count,
                                      new_chunk_size)

    # Set appropriate Content-Disposition header
    content_disposition = 'attachment' if is_download else 'inline'
    
    # Determine if this is a streamable media type (video or audio)
    is_streamable = mime_type.startswith(('video/', 'audio/'))
    
    # Define headers for the response
    headers = {
        "Content-Type": mime_type,
        "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
        "Content-Disposition": f'{content_disposition}; filename="{file_name}"',
        "Accept-Ranges": "bytes",
    }

    # Add additional headers for video streaming
    if is_streamable and not is_download:
        # Add headers for better HTML5 player compatibility
        if mime_type.startswith('video/'):
            headers["X-Content-Duration"] = str(getattr(file_properties, 'duration', 0))
    
    # Create and return response
    return_resp = web.Response(
        status=206 if range_header else 200,
        body=body,
        headers=headers
    )

    if return_resp.status == 200:
        return_resp.headers.add("Content-Length", str(file_size))

    return return_resp


# New route for HTML5 player page (optional)
@routes.get(r"/{message_id:\d+}/{name}/player")
async def video_player_page(request):
    try:
        message_id = int(request.match_info['message_id'])
        file_name = request.match_info['name']
        
        # Generate direct link to the video/audio
        stream_url = f"/{message_id}/{file_name}"
        download_url = f"/{message_id}/{file_name}?download=1"
        
        # Get file properties to determine media type
        media_msg = await StreamBot.get_messages(Var.BIN_CHANNEL, message_id)
        file_properties = await TGCustomYield().generate_file_properties(media_msg)
        mime_type = file_properties.mime_type if file_properties.mime_type \
            else mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        
        # Create appropriate player HTML
        is_video = mime_type.startswith('video/')
        is_audio = mime_type.startswith('audio/')
        
        # Generate appropriate HTML5 player based on media type
        player_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Media Player - {file_name}</title>
            <style>
                body {{ margin: 0; padding: 0; background-color: #000; color: #fff; font-family: Arial, sans-serif; }}
                .container {{ display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; width: 100%; }}
                .player-wrapper {{ width: 100%; max-width: 900px; }}
                .video-player {{ width: 100%; height: auto; max-height: 80vh; }}
                .audio-player {{ width: 100%; margin: 20px 0; }}
                .title {{ margin-bottom: 20px; text-align: center; }}
                .download-btn {{ margin-top: 20px; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 4px; }}
                .download-btn:hover {{ background-color: #45a049; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="title">{file_name}</h2>
                <div class="player-wrapper">
        """
        
        if is_video:
            player_html += f"""
                    <video class="video-player" controls autoplay>
                        <source src="{stream_url}" type="{mime_type}">
                        Your browser does not support the video tag.
                    </video>
            """
        elif is_audio:
            player_html += f"""
                    <audio class="audio-player" controls autoplay>
                        <source src="{stream_url}" type="{mime_type}">
                        Your browser does not support the audio tag.
                    </audio>
            """
        else:
            player_html += f"""
                    <p>This file type ({mime_type}) is not supported for streaming playback.</p>
            """
        
        player_html += f"""
                </div>
                <a href="{download_url}" class="download-btn">Download File</a>
            </div>
        </body>
        </html>
        """
        
        return web.Response(text=player_html, content_type='text/html')
    except Exception as e:
        logging.error(e)
        raise web.HTTPNotFound
