# UltraDL: Universal Video Downloader

**UltraDL** is a **modern, premium** video download application with a stunning PySide6/Qt6 interface. Built with professional UI/UX design principles, it features a dark glassmorphism theme, smooth animations, and an intuitive workflow.

## ✨ Features

### Modern Premium Interface
- **Dark glassmorphism theme** with soft shadows and gradients
- **Animated UI components** with smooth transitions
- **Professional typography** and spacing
- **Responsive layout** that adapts to window size
- **Toast notifications** for user feedback

### Core Functionality
- **Video Analysis** - Extract metadata, thumbnails, and available qualities
- **Multi-Platform Support** - YouTube, Vimeo, and generic HTML extraction
- **Quality Selection** - Interactive resolution chips (144p to 4K)
- **Format Options** - MP4, MKV, WebM output formats
- **Subtitle Downloads** - SRT and VTT support
- **Thumbnail Downloads** - Save video thumbnails
- **Live Stream Recording** - HLS live stream capture

### Download Manager
- **Visual download cards** with animated progress rings
- **Real-time speed graphs** showing download performance
- **Pause/Resume/Cancel** controls for each download
- **ETA calculation** based on download speed
- **Parallel downloads** with configurable thread pool

### Settings & History
- **Download folder selector** with native file dialog
- **Configurable max parallel downloads**
- **Default quality preferences**
- **Download history** with search and filtering
- **Persistent settings** across sessions

## 🚀 Quick Start

### Installation

```bash
# Navigate to project directory
cd "Universal Video Downloader"

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Running the Modern GUI

```bash
# Using the launcher script (Windows)
launch_gui.bat

# Or using Python directly
python UltraDL/interface/modern_gui.py

# Or via CLI
python UltraDL/main.py --gui
```

### Command Line Usage

```bash
# Download a single video
python UltraDL/main.py "https://www.youtube.com/watch?v=..." -q 720 -o ./downloads

# List available formats
python UltraDL/main.py --list-formats "URL"

# Check ffmpeg installation
python UltraDL/main.py --check-ffmpeg
```

## 🏗️ Architecture

```
UltraDL/
├── ui/                    # Modern UI components
│   ├── styles.py         # Theme colors, fonts, animations
│   ├── base_card.py      # Glass card components
│   ├── buttons.py        # Gradient and action buttons
│   ├── inputs.py         # Modern input fields
│   ├── progress.py       # Progress rings and graphs
│   ├── notification.py   # Toast notification system
│   ├── video_card.py     # Video preview and download cards
│   ├── navigation.py     # Top navigation bar
│   └── dialogs.py        # File dialogs
├── interface/
│   └── modern_gui.py     # Main application window
├── core/                 # Download engine
├── extractors/           # Video site extractors
├── streaming/            # HLS/DASH streaming
└── utils/               # Utilities and config
```

## 🎨 Design System

### Colors
- **Primary Background**: `#0a0c12`
- **Glass Background**: `rgba(24, 26, 38, 180)`
- **Accent Blue**: `#508cff`
- **Accent Purple**: `#a05aff`
- **Text Primary**: `rgba(255, 255, 255, 240)`

### Typography
- **Font Family**: Segoe UI, Inter, Roboto
- **Weights**: Normal (400) to ExtraBold (800)
- **Sizes**: 11px to 22px scale

### Animations
- **Fast**: 150ms (micro-interactions)
- **Normal**: 250ms (state changes)
- **Slow**: 400ms (entrances)
- **Easing**: Cubic-bezier for natural motion

## ⚙️ Configuration

Settings are automatically saved to:
- **Windows**: `%APPDATA%\ultradl\config.yaml`
- **Linux/Mac**: `~/.config/ultradl/config.yaml`

Example configuration:

```yaml
download_dir: ~/Downloads
max_concurrent_downloads: 3
preferred_height: 720
timeout_seconds: 30
retry_attempts: 3
enable_metadata_cache: true
```

## 📋 Requirements

- **Python**: 3.10+
- **PySide6**: 6.6.0+
- **FFmpeg**: Required for video processing
- **httpx**: HTTP client
- **beautifulsoup4**: HTML parsing
- **lxml**: XML processing

## 🔧 Development

### Project Structure

The codebase follows clean architecture principles:

1. **UI Layer** (`UltraDL/ui/`)
   - Reusable components with no business logic
   - Signal/slot architecture for communication
   - Pure presentation concerns

2. **Interface Layer** (`UltraDL/interface/`)
   - Main window orchestration
   - Worker thread management
   - Component composition

3. **Core Layer** (`UltraDL/core/`)
   - Download engine
   - Segment downloading
   - Retry handling

4. **Extractor Layer** (`UltraDL/extractors/`)
   - Site-specific extraction logic
   - Registry pattern for extensibility

### Adding a New Site Extractor

1. Create a new file in `UltraDL/extractors/`
2. Subclass `BaseExtractor`
3. Implement `match_score()` and `extract()`
4. Register in `base_extractor.py`

## 🐛 Troubleshooting

### GUI Won't Launch
- Verify PySide6 is installed: `pip install PySide6`
- Check Python version: `python --version` (need 3.10+)
- Run directly: `python UltraDL/interface/modern_gui.py`

### Downloads Failing
- Verify FFmpeg is on PATH: `python UltraDL/main.py --check-ffmpeg`
- Check network connectivity
- Review logs for specific errors

### Performance Issues
- Reduce max parallel downloads in settings
- Clear metadata cache if needed

---

**UltraDL** - Download with style. 🎬⬇️
