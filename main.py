#!/usr/bin/env python3
"""
Eternal AI MCP Server - Local (stdio) transport
Provides visual effects listing, image/video generation, polling, and media display
"""

import asyncio
import base64
import json
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

# Eternal AI API Configuration
ETERNAL_AI_API_BASE = os.environ.get("ETERNAL_AI_API_BASE", "https://open.eternalai.org")
VISUAL_EFFECTS_ENDPOINT = "/uncensored-ai/effects"  # GET /uncensored-ai/effects
GENERATE_EFFECT_ENDPOINT = "/generate"  # POST /generate
GENERATE_CUSTOM_ENDPOINT = "/base/generate"  # POST /base/generate
POLL_RESULT_ENDPOINT = "/poll-result"  # GET /poll-result/{request_id}

# Initialize MCP Server
server = Server("eternal-ai-mcp")

# Store API key (set via environment or passed in tool calls)
_api_key: str | None = None


def get_api_key() -> str | None:
    """Get API key from environment variable"""
    global _api_key
    if _api_key:
        return _api_key
    return os.environ.get("ETERNAL_AI_API_KEY")


def set_api_key(key: str):
    """Set API key programmatically"""
    global _api_key
    _api_key = key


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        # Tool 1: get_visual_effects
        Tool(
            name="get_visual_effects",
            description="Get a list of available visual effects for content generation. Filter by type (image/video) and paginate through results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "effect_type": {
                        "type": "string",
                        "description": "Filter by effect type: 'image' or 'video'",
                        "enum": ["image", "video"]
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number for pagination (default: 1)",
                        "default": 1
                    }
                }
            }
        ),
        # Tool 2: generate_with_effect
        Tool(
            name="generate_with_effect",
            description="Generate image or video content using a specific visual effect. Returns a request_id for polling the result. Requires Authentication via Bearer token (set ETERNAL_AI_API_KEY environment variable).",
            inputSchema={
                "type": "object",
                "properties": {
                    "images": {
                        "type": "array",
                        "description": "Array of image URLs or Base64 encoded images",
                        "items": {
                            "type": "string"
                        }
                    },
                    "effect_id": {
                        "type": "string",
                        "description": "The ID of the visual effect to apply"
                    }
                },
                "required": ["effect_id"]
            }
        ),
        # Tool 3: generate_custom_advanced
        Tool(
            name="generate_custom_advanced",
            description="Generate custom image or video content using advanced prompts. Returns a request_id for polling the result. Requires Authentication via Bearer token (set ETERNAL_AI_API_KEY environment variable).",
            inputSchema={
                "type": "object",
                "properties": {
                    "images": {
                        "type": "array",
                        "description": "Array of image URLs or Base64 encoded images",
                        "items": {
                            "type": "string"
                        }
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Custom text prompt describing the desired output"
                    },
                    "type": {
                        "type": "string",
                        "description": "Output type: 'image' or 'video'",
                        "enum": ["image", "video"]
                    }
                },
                "required": ["prompt", "type"]
            }
        ),
        # Tool 4: smart_poll_result
        Tool(
            name="smart_poll_result",
            description="Smart polling tool that automatically checks the status of a generation task. Polls every 15s for up to 120s total. Returns final result or progress if still processing. Requires Authentication via Bearer token.\nTip for smart polling: In the video generation task, you should call this tool multiple times to get the latest progress.",
            inputSchema={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "The request ID returned from a generate call"
                    }
                },
                "required": ["request_id"]
            }
        ),
        # Tool 5: display_media
        Tool(
            name="display_media",
            description="Render media (image or video) from a URL in markdown format for display. Supports images (jpg, png, gif, webp) and videos (mp4, webm, mov). For images, downloads and returns as base64 for inline display.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Media URL to render (must be http or https)"
                    }
                },
                "required": ["url"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    """Handle tool calls"""
    if name == "get_visual_effects":
        return await handle_get_visual_effects(arguments)
    elif name == "generate_with_effect":
        return await handle_generate_with_effect(arguments)
    elif name == "generate_custom_advanced":
        return await handle_generate_custom_advanced(arguments)
    elif name == "smart_poll_result":
        return await handle_smart_poll_result(arguments)
    elif name == "display_media":
        return await handle_display_media(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_get_visual_effects(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Get a list of available visual effects.
    API endpoint: GET /uncensored-ai/effects
    """
    effect_type = arguments.get("effect_type", "")
    page = arguments.get("page", 1)

    params = {}
    if effect_type:
        params["effect_type"] = effect_type
    if page > 0:
        params["page"] = page

    headers = {}
    api_key = get_api_key()
    if api_key:
        headers["x-api-key"] = api_key

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{ETERNAL_AI_API_BASE}{VISUAL_EFFECTS_ENDPOINT}",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=f"API Error: {e.response.status_code} - {e.response.text}")]
        except httpx.RequestError as e:
            return [TextContent(type="text", text=f"Request Error: {str(e)}")]


async def handle_generate_with_effect(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Generate image/video using a visual effect.
    API endpoint: POST /generate
    """
    api_key = get_api_key()
    if not api_key:
        return [TextContent(
            type="text",
            text="API key is required. Please set ETERNAL_AI_API_KEY environment variable."
        )]

    effect_id = arguments.get("effect_id")
    if not effect_id:
        return [TextContent(type="text", text="Effect ID is required")]

    images = arguments.get("images", [])

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "effect_id": effect_id
    }
    if images:
        payload["images"] = images

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{ETERNAL_AI_API_BASE}{GENERATE_EFFECT_ENDPOINT}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            # Parse response (supports both simple and nested formats)
            result = parse_generate_response(data)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=f"API Error: {e.response.status_code} - {e.response.text}")]
        except httpx.RequestError as e:
            return [TextContent(type="text", text=f"Request Error: {str(e)}")]


async def handle_generate_custom_advanced(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Generate custom image/video using advanced prompts.
    API endpoint: POST /base/generate
    """
    api_key = get_api_key()
    if not api_key:
        return [TextContent(
            type="text",
            text="API key is required. Please set ETERNAL_AI_API_KEY environment variable."
        )]

    prompt = arguments.get("prompt")
    output_type = arguments.get("type")

    if not prompt:
        return [TextContent(type="text", text="Prompt is required")]
    if not output_type:
        return [TextContent(type="text", text="Type is required (image or video)")]

    images = arguments.get("images", [])

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "type": output_type
    }
    if images:
        payload["images"] = images

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{ETERNAL_AI_API_BASE}{GENERATE_CUSTOM_ENDPOINT}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            # Parse response (supports both simple and nested formats)
            result = parse_generate_response(data)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=f"API Error: {e.response.status_code} - {e.response.text}")]
        except httpx.RequestError as e:
            return [TextContent(type="text", text=f"Request Error: {str(e)}")]


async def handle_smart_poll_result(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Smart polling with automatic retry.
    - Initial delay: 30 seconds
    - Poll interval: 15 seconds
    - Max duration: 120 seconds
    API endpoint: GET /poll-result/{request_id}
    """
    api_key = get_api_key()
    if not api_key:
        return [TextContent(
            type="text",
            text="API key is required. Please set ETERNAL_AI_API_KEY environment variable."
        )]

    request_id = arguments.get("request_id")
    if not request_id:
        return [TextContent(type="text", text="Request ID is required")]

    headers = {
        "x-api-key": api_key
    }

    # Step 1: Initial delay of 30 seconds
    print(f"[MCP] [smart_poll_result] Waiting 30 seconds before first poll for request_id: {request_id}")
    await asyncio.sleep(30)

    start_time = time.time()
    max_duration = 120  # seconds
    poll_interval = 15  # seconds

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            elapsed = time.time() - start_time

            try:
                response = await client.get(
                    f"{ETERNAL_AI_API_BASE}{POLL_RESULT_ENDPOINT}/{request_id}",
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()

                status = str(data.get("status", "")).lower()
                progress = data.get("progress", 0)

                # Check if completed
                if status == "success" or status == "completed":
                    print(f"[MCP] [smart_poll_result] Task completed successfully")
                    return [TextContent(type="text", text=json.dumps(data, indent=2))]

                if status == "failed" or status == "error":
                    print(f"[MCP] [smart_poll_result] Task failed")
                    return [TextContent(type="text", text=json.dumps(data, indent=2))]

                print(f"[MCP] [smart_poll_result] Still processing (progress: {progress}%)...")

                # Check timeout
                if elapsed >= max_duration:
                    print(f"[MCP] [smart_poll_result] Timeout reached after {max_duration}s")
                    timeout_response = {
                        "request_id": data.get("request_id", request_id),
                        "status": data.get("status", "pending"),
                        "progress": progress,
                        "result_url": data.get("result_url", ""),
                        "effect_type": data.get("effect_type", ""),
                        "message": "Task is still processing, please call this tool again"
                    }
                    return [TextContent(type="text", text=json.dumps(timeout_response, indent=2))]

                # Wait before next poll
                await asyncio.sleep(poll_interval)

            except httpx.HTTPStatusError as e:
                return [TextContent(type="text", text=f"API Error: {e.response.status_code} - {e.response.text}")]
            except httpx.RequestError as e:
                print(f"[MCP] [smart_poll_result] Poll error (will retry): {e}")
                if elapsed >= max_duration:
                    return [TextContent(type="text", text=f"Request Error after timeout: {str(e)}")]
                await asyncio.sleep(poll_interval)


async def handle_display_media(arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    """
    Display media from URL.
    For images: downloads and returns as ImageContent (base64)
    For videos: returns markdown with URL
    """
    url = arguments.get("url", "")

    if not url:
        return [TextContent(type="text", text="URL is required")]

    # Validate URL
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return [TextContent(type="text", text="URL must use http or https protocol")]

    # Detect media type
    url_lower = url.lower()
    mime_type = detect_mime_type(url_lower)

    # Handle images
    if mime_type.startswith("image/"):
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()

                image_data = base64.b64encode(response.content).decode("utf-8")

                return [ImageContent(
                    type="image",
                    data=image_data,
                    mimeType=mime_type
                )]

            except httpx.HTTPStatusError as e:
                return [TextContent(type="text", text=f"Failed to download image: {e.response.status_code}")]
            except httpx.RequestError as e:
                return [TextContent(type="text", text=f"Failed to download image: {str(e)}")]

    # Handle videos and other media - return as markdown
    markdown = f"![Media]({url})\n\nMedia URL: {url}"
    return [TextContent(type="text", text=markdown)]


def parse_generate_response(data: dict) -> dict:
    """
    Parse generate response - supports both simple and nested formats.
    Simple: {"request_id": "...", "status": "...", "result": "...", "progress": 0}
    Nested: {"status": 1, "data": {...}, "request_id": "..."}
    """
    # Check if nested format (has "data" field with dict value)
    if "data" in data and isinstance(data.get("data"), dict):
        nested_data = data["data"]
        return {
            "request_id": nested_data.get("request_id", data.get("request_id", "")),
            "status": nested_data.get("status", ""),
            "result": nested_data.get("result", ""),
            "progress": nested_data.get("progress", 0),
            "status_code": data.get("status")
        }

    # Simple format
    return {
        "request_id": data.get("request_id", ""),
        "status": data.get("status", ""),
        "result": data.get("result", ""),
        "progress": data.get("progress", 0)
    }


def detect_mime_type(url_lower: str) -> str:
    """Detect MIME type from URL extension"""
    if url_lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif url_lower.endswith(".png"):
        return "image/png"
    elif url_lower.endswith(".gif"):
        return "image/gif"
    elif url_lower.endswith(".webp"):
        return "image/webp"
    elif url_lower.endswith(".bmp"):
        return "image/bmp"
    elif url_lower.endswith(".svg"):
        return "image/svg+xml"
    elif url_lower.endswith(".mp4"):
        return "video/mp4"
    elif url_lower.endswith(".webm"):
        return "video/webm"
    elif url_lower.endswith(".mov"):
        return "video/quicktime"
    elif url_lower.endswith(".avi"):
        return "video/x-msvideo"
    elif url_lower.endswith(".mkv"):
        return "video/x-matroska"
    else:
        return "application/octet-stream"


async def main():
    """Run the MCP server with stdio transport"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
