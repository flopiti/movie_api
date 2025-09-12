# Movie Management REST API

A Python Flask-based REST API for managing movie file paths and discovering media files, with OpenAI and TMDB (The Movie Database) API integration for intelligent movie metadata search and automated download management.

## Project Structure

```
movie_duplicates/
├── src/                          # Source code
│   ├── app.py                   # Main Flask application
│   ├── download_monitor.py      # Download monitoring service
│   ├── file_discovery.py        # File discovery utilities
│   ├── cleanup_firebase_assignments.py  # Firebase cleanup utilities
│   ├── routes/                  # API route handlers
│   │   ├── files.py            # File management routes
│   │   ├── movies.py           # Movie search and management routes
│   │   ├── paths.py            # Path management routes
│   │   ├── plex.py             # Plex integration routes
│   │   ├── sms.py              # SMS webhook routes
│   │   └── system.py           # System status routes
│   └── clients/                 # External API clients
│       ├── openai_client.py    # OpenAI API client
│       ├── plex_client.py      # Plex API client
│       ├── radarr_client.py    # Radarr API client
│       ├── tmdb_client.py       # TMDB API client
│       ├── twilio_client.py     # Twilio SMS client
│       └── PROMPTS.py           # AI prompts and templates
├── tests/                       # Test files
│   ├── test_*.py               # Various test files
│   └── test_movies/            # Test movie data
├── config/                      # Configuration files
│   ├── config.py               # Main configuration
│   └── env                     # Environment variables
├── docs/                        # Documentation
│   ├── README.md               # Main documentation
│   └── DOWNLOAD_SYSTEM_README.md  # Download system documentation
├── logs/                        # Log files
│   ├── movie_api.log           # Application logs
│   └── server.log              # Server logs
├── main.py                     # Main entry point
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker configuration
└── .dockerignore              # Docker ignore file
```

## Features

- **File Path Management**: Add, remove, and list movie directory paths
- **Recursive File Discovery**: Automatically find all media files in configured directories
- **AI-Powered Filename Cleaning**: Uses OpenAI to clean messy movie filenames before searching
- **TMDB Integration**: Search for movie metadata using TMDB API with cleaned titles
- **SMS Movie Detection**: Automatically detects movie titles mentioned in SMS conversations
- **Radarr Integration**: Adds movies to Radarr for automatic downloading
- **Download Monitoring**: Continuously monitors download progress
- **SMS Notifications**: Sends SMS updates when downloads start, complete, or fail
- **RESTful API**: Clean REST endpoints for all operations
- **Media File Support**: Supports common video formats (MP4, MKV, AVI, MOV, etc.)
- **Comprehensive Logging**: Detailed logs of all processing steps

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd /Users/nathanpieraut/projects/movie_duplicates
   ```

2. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure APIs:**
   - Use the provided `config/env` file or create your own `.env` file
   - **TMDB API (required for movie search):**
     - Get your API key from [TMDB](https://www.themoviedb.org/settings/api)
     - Add to env file: `TMDB_API_KEY=your_actual_api_key_here`
   - **OpenAI API (required for filename cleaning):**
     - Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
     - Add to env file: `OPENAI_API_KEY=your_actual_api_key_here`

## Usage

### Start the Server

```bash
python3 main.py
```

The API will be available at `http://localhost:5000`

### API Endpoints

#### Movie File Paths Management

**GET /movie-file-paths**
- Get all configured movie directory paths
- Response: `{"movie_file_paths": [...], "count": N}`

**PUT /movie-file-paths**
- Add a new movie directory path
- Request body: `{"path": "/path/to/movies"}`
- Response: `{"message": "Path added successfully", "path": "...", "movie_file_paths": [...]}`

**DELETE /movie-file-paths**
- Remove a movie directory path
- Request body: `{"path": "/path/to/movies"}`
- Response: `{"message": "Path removed successfully", "path": "...", "movie_file_paths": [...]}`

#### File Discovery

**GET /all-files**
- Get all media files from all configured paths (recursive)
- Response: `{"files": [...], "count": N, "source_paths": [...]}`

#### AI-Enhanced Movie Search

**GET /search-movie?q=filename_or_title**
- Intelligent movie search using OpenAI + TMDB integration
- Query parameter: `q` (movie filename or title to search)
- **Process:**
  1. OpenAI cleans the filename/title (removes quality tags, release groups, etc.)
  2. TMDB searches using the cleaned title
  3. Returns comprehensive results with both OpenAI processing and TMDB results

#### SMS Download Management

**POST /api/sms/webhook**
- Twilio webhook for incoming SMS messages
- Automatically detects movie requests and initiates downloads

**GET /api/sms/downloads**
- Get all download requests

**GET /api/sms/download-monitor/status**
- Get monitoring service status

## Testing

Run the test scripts to verify functionality:

```bash
# Test movie search functionality
python3 tests/test_movie_search.py

# Test download system
python3 tests/test_download_system.py

# Test Plex connection
python3 tests/test_plex_connection.py

# Test Radarr connection
python3 tests/test_radarr_connection.py
```

## Configuration

The application stores its configuration in `config.json` which is automatically created and managed. The configuration includes:

- `movie_file_paths`: Array of directory paths to scan for movies
- `tmdb_api_key`: Your TMDB API key (also configurable via environment variable)

Environment variables (in `config/env` or `.env` file):
- `TMDB_API_KEY`: Your TMDB API key
- `OPENAI_API_KEY`: Your OpenAI API key
- `RADARR_URL`: Radarr server URL
- `RADARR_API_KEY`: Radarr API key
- `TWILIO_ACCOUNT_SID`: Twilio account SID
- `TWILIO_AUTH_TOKEN`: Twilio auth token
- `TWILIO_PHONE_NUMBER`: Twilio phone number
- `REDIS_HOST`: Redis server host
- `REDIS_PORT`: Redis server port
- `REDIS_DB`: Redis database number

## Logging

The application creates detailed logs in `logs/movie_api.log` and outputs to console. Logs include:
- API requests and responses
- OpenAI filename cleaning process
- TMDB search queries and results
- Download monitoring activities
- Error handling and debugging information

## Supported Media Formats

The API recognizes the following video file extensions:
- MP4, MKV, AVI, MOV, WMV, FLV, WEBM, M4V
- MPG, MPEG, 3GP, ASF, RM, RMVB, VOB, TS

## Docker Support

The application includes Docker support:

```bash
# Build the Docker image
docker build -t movie-api .

# Run the container
docker run -p 5000:5000 movie-api
```

## Development

To run in development mode with debug enabled, the server automatically starts with:
- Debug mode: On
- Host: 0.0.0.0 (accessible from other devices on network)
- Port: 5000
- CORS enabled for cross-origin requests

## Error Handling

The API includes comprehensive error handling:
- Path validation (existence, directory check)
- Duplicate path prevention
- Permission error handling during file discovery
- TMDB API error handling
- Download monitoring error handling
- Proper HTTP status codes and error messages

## Security Considerations

- All API keys are stored as environment variables
- SMS webhook validates Twilio signatures
- Redis data is stored with appropriate expiration
- Download requests are tied to specific phone numbers