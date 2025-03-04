# (c) @AbirHasan2005

import math
import logging
import time
from WebStreamer.vars import Var
from aiohttp import web
from WebStreamer.bot import StreamBot
from WebStreamer.utils.custom_dl import streamer
import urllib.parse

# Import the time_format module
try:
    from WebStreamer.utils.time_format import get_readable_time
    from WebStreamer import StartTime
except ImportError:
    # Fallback if import fails
    def get_readable_time(seconds: int) -> str:
        count = 0
        ping_time = ""
        time_list = []
        time_suffix_list = ["s", "m", "h", "days"]

        while count < 4:
            count += 1
            if count < 3:
                remainder, result = divmod(seconds, 60)
            else:
                remainder, result = divmod(seconds, 24)
            if seconds == 0 and remainder == 0:
                break
            time_list.append(int(result))
            seconds = int(remainder)

        for x in range(len(time_list)):
            time_list[x] = str(time_list[x]) + time_suffix_list[x]
        if len(time_list) == 4:
            ping_time += f"{time_list.pop()}, "

        time_list.reverse()
        ping_time += ":".join(time_list)

        return ping_time
    
    # Define StartTime if not available
    StartTime = time.time()

routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response({"status": "running",
                             "maintained_by": "AbirHasan2005",
                             "uptime": get_readable_time(time.time() - StartTime),
                             "telegram_bot": '@'+(await StreamBot.get_me()).username})

@routes.get("/{message_id}", allow_head=True)
async def stream_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        return await media_streamer(request, message_id)
    except ValueError as e:
        logging.error(e)
        raise web.HTTPNotFound

@routes.get("/{message_id}/{file_name}", allow_head=True)
async def stream_handler_with_name(request):
    try:
        message_id = int(request.match_info['message_id'])
        file_name = request.match_info['file_name']
        return await media_streamer(request, message_id, file_name)
    except ValueError as e:
        logging.error(e)
        raise web.HTTPNotFound

@routes.get("/player/{message_id}", allow_head=True)
async def player_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        return await serve_player_page(request, message_id)
    except ValueError as e:
        logging.error(e)
        raise web.HTTPNotFound

async def serve_player_page(request, message_id):
    try:
        # Get file properties
        file_properties = await streamer.get_file_properties(message_id)
        file_name = file_properties.get("file_name", "Unknown")
        mime_type = file_properties.get("mime_type", "application/octet-stream")
        media_type = file_properties.get("media_type", "document")
        
        # Generate stream URL
        stream_url = f"{request.url.scheme}://{request.url.host}"
        if request.url.port and request.url.port != 80 and request.url.port != 443:
            stream_url += f":{request.url.port}"
        stream_url += f"/{message_id}/{urllib.parse.quote(file_name)}"
        
        # Generate download URL
        download_url = f"{stream_url}?download=1"
        
        # Determine if media is streamable
        is_video = media_type == "video" or mime_type.startswith("video/")
        is_audio = media_type == "audio" or mime_type.startswith("audio/")
        
        # Generate HTML for player
        player_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{file_name} - Stream Player</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f0f0f0;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }}
                .container {{
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                    width: 90%;
                    max-width: 800px;
                }}
                .title {{
                    background-color: #2196F3;
                    color: white;
                    padding: 15px;
                    text-align: center;
                    font-size: 18px;
                    margin: 0;
                    word-break: break-all;
                }}
                .player-wrapper {{
                    padding: 20px;
                }}
                .video-player {{
                    width: 100%;
                    max-height: 500px;
                    background-color: #000;
                }}
                .audio-player {{
                    width: 100%;
                    margin: 20px 0;
                }}
                .download-btn {{
                    display: block;
                    text-align: center;
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px;
                    text-decoration: none;
                    border-radius: 4px;
                    margin: 20px auto;
                    width: 200px;
                }}
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
        logging.error(f"Error in player page: {e}")
        raise web.HTTPNotFound

async def media_streamer(request, message_id, file_name=None):
    try:
        range_header = request.headers.get('Range', 0)
        is_download = 'download' in request.query and request.query['download'] == '1'
        
        # Get file properties
        file_properties = await streamer.get_file_properties(message_id)
        if not file_name:
            file_name = file_properties.get("file_name", f"file_{message_id}")
        mime_type = file_properties.get("mime_type", "application/octet-stream")
        file_size = file_properties.get("file_size", 0)
        
        if range_header:
            from_bytes, until_bytes = range_header.replace('bytes=', '').split('-')
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
        else:
            from_bytes = 0
            until_bytes = file_size - 1

        # Calculate chunk size
        chunk_size = 1024 * 1024  # 1MB chunk
        total_size = until_bytes - from_bytes + 1
        
        part_count = math.ceil(total_size / chunk_size)
        last_part_cut = total_size % chunk_size
        
        if last_part_cut == 0:
            last_part_cut = chunk_size
        
        headers = {
            'Content-Type': mime_type,
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {from_bytes}-{until_bytes}/{file_size}',
            'Content-Length': str(total_size),
        }
        
        # Set appropriate Content-Disposition header
        if is_download:
            headers['Content-Disposition'] = f'attachment; filename="{file_name}"'
        else:
            headers['Content-Disposition'] = f'inline; filename="{file_name}"'
        
        # For video streaming, add more headers
        if mime_type.startswith('video/'):
            headers.update({
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'max-age=604800'  # 1 week
            })
        
        response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
        await response.prepare(request)
        
        for chunk_index in range(part_count):
            offset = from_bytes + (chunk_index * chunk_size)
            first_part_cut = min(chunk_size, total_size - (chunk_index * chunk_size))
            
            if chunk_index == 0:
                first_part_cut = chunk_size - from_bytes % chunk_size
            
            chunk = await streamer.yield_file(message_id, offset, first_part_cut, last_part_cut, part_count, chunk_size)
            await response.write(chunk)
        
        return response
    except Exception as e:
        logging.error(f"Error in media_streamer: {str(e)}")
        raise web.HTTPInternalServerError(text=f"Error: {str(e)}")
