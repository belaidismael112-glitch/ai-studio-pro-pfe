# AI Studio Pro - Desktop Application

Professional AI Image & Video Generation Platform - Desktop Client

## Features

- 🖼️ **AI Image Generation** - Create stunning images from text prompts
- 🎬 **AI Video Generation** - Transform ideas into videos
- 💎 **Credit System** - Pay-as-you-go with subscription options
- 📜 **Generation History** - Browse and manage your creations
- 🌙 **Dark/Light Theme** - Choose your preferred appearance

## Requirements

- Python 3.9+
- Windows 10/11

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-studio-pro.git
cd ai-studio-pro/desktop
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python main.py
```

### Build Executable

```bash
pyinstaller build.spec
```

The executable will be created in the `dist` folder.

## Configuration

Edit `config.json` in your user data directory:
- Windows: `%APPDATA%\AI Studio Pro\config.json`
- macOS: `~/Library/Application Support/AI Studio Pro/config.json`
- Linux: `~/.config/ai-studio-pro/config.json`

### Settings

- `api_base_url` - Backend API URL
- `dark_mode` - Enable dark theme
- `download_path` - Default download location
- `default_image_width/height` - Default image dimensions

## Usage

1. **Login/Register** - Create an account or sign in
2. **Get Credits** - Purchase credits or subscribe
3. **Generate** - Create images or videos from text
4. **Download** - Save your creations locally

## Development

### Project Structure

```
desktop/
├── main.py              # Entry point
├── src/
│   ├── core/           # Core functionality
│   │   ├── config.py   # Configuration management
│   │   └── theme.py    # Theme management
│   ├── api/            # API client
│   │   └── client.py   # HTTP client
│   └── ui/             # User interface
│       ├── main_window.py
│       ├── sidebar.py
│       ├── pages/
│       │   ├── login_page.py
│       │   ├── dashboard_page.py
│       │   ├── image_generation_page.py
│       │   ├── video_generation_page.py
│       │   ├── history_page.py
│       │   ├── credits_page.py
│       │   └── settings_page.py
│       └── dialogs/
│           └── register_dialog.py
├── assets/             # Images, fonts, icons
└── build.spec          # PyInstaller spec
```

## License

MIT License - See LICENSE file for details
