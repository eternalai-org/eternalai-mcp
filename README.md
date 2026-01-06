# Eternal AI MCP Server (Local/stdio)

MCP Server for Eternal AI visual effects API, designed for local Claude integration using stdio transport.

## Features

- **get_visual_effects**: List available visual effects (image/video) with pagination
- **generate_with_effect**: Generate content using a specific visual effect
- **generate_custom_advanced**: Generate custom content using advanced prompts
- **smart_poll_result**: Smart polling for generation results (30s initial delay, 15s intervals, 120s max)
- **display_media**: Render images/videos from URLs

## Prerequisites

### Install Python

**macOS:**
```bash
# Using Homebrew
brew install python@3.11

# Or download from https://www.python.org/downloads/
```

**Windows:**
```bash
# Download and install from https://www.python.org/downloads/
# Make sure to check "Add Python to PATH" during installation
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### Create and Activate Virtual Environment

**macOS/Linux:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

**Windows:**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate
```

## Installation

```bash
# Make sure virtual environment is activated first
pip install -r requirements.txt
```

## Configuration

Set your Eternal AI API key as an environment variable:

```bash
export ETERNAL_AI_API_KEY="your-api-key-here"
```

Optional: Configure custom API base URL:

```bash
export ETERNAL_AI_API_BASE="https://open.eternalai.org"
```

## Usage with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "eternal-ai": {
      "command": "python",
      "args": ["/path/to/Eternal_AI_MCP_Local/main.py"],
      "env": {
        "ETERNAL_AI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```


## Running Directly

```bash
python main.py
```

The server communicates via stdio (stdin/stdout) using the MCP protocol.

## Tools

### 1. get_visual_effects

Get available visual effects.

**Parameters:**
- `effect_type` (optional): Filter by "image" or "video"
- `page` (optional): Page number for pagination (default: 1)

### 2. generate_with_effect

Generate content using a visual effect.

**Parameters:**
- `effect_id` (required): The effect ID to apply
- `images` (optional): Array of image URLs or base64 encoded images

**Returns:** `request_id` for polling

### 3. generate_custom_advanced

Generate custom content with prompts.

**Parameters:**
- `prompt` (required): Text description of desired output
- `type` (required): "image" or "video"
- `images` (optional): Array of image URLs or base64 encoded images

**Returns:** `request_id` for polling

### 4. smart_poll_result

Poll for generation results with smart retry logic.

**Parameters:**
- `request_id` (required): The request ID from generate calls

**Behavior:**
- 30 second initial delay before first poll
- Polls every 15 seconds
- Maximum 120 seconds total duration
- For video generation, call multiple times for progress updates

### 5. display_media

Display media from URL.

**Parameters:**
- `url` (required): Media URL (http/https)

**Behavior:**
- Images: Downloads and returns as base64 for inline display
- Videos: Returns markdown with URL

## License

MIT
