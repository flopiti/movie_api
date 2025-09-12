# Movie Management REST API

A Python Flask-based REST API for managing movie file paths and discovering media files, with OpenAI and TMDB (The Movie Database) API integration for intelligent movie metadata search.

## Features

- **File Path Management**: Add, remove, and list movie directory paths
- **Recursive File Discovery**: Automatically find all media files in configured directories
- **AI-Powered Filename Cleaning**: Uses OpenAI to clean messy movie filenames before searching
- **TMDB Integration**: Search for movie metadata using TMDB API with cleaned titles
- **RESTful API**: Clean REST endpoints for all operations
- **Media File Support**: Supports common video formats (MP4, MKV, AVI, MOV, etc.)
- **Comprehensive Logging**: Detailed logs of all processing steps

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd /Users/nathanpieraut/movie_duplicates
   ```

2. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure APIs:**
   - Use the provided `env` file or create your own `.env` file
   - **TMDB API (required for movie search):**
     - Get your API key from [TMDB](https://www.themoviedb.org/settings/api)
     - Add to env file: `TMDB_API_KEY=your_actual_api_key_here`
   - **OpenAI API (required for filename cleaning):**
     - Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
     - Add to env file: `OPENAI_API_KEY=your_actual_api_key_here`

## Usage

### Start the Server

```bash
python3 app.py
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

Each file object includes:
- `path`: Full file path
- `name`: File name
- `size`: File size in bytes
- `modified`: Last modified timestamp
- `directory`: Parent directory
- `source_path`: The configured root path where this file was found

#### AI-Enhanced Movie Search

**GET /search-movie?q=filename_or_title**
- Intelligent movie search using OpenAI + TMDB integration
- Query parameter: `q` (movie filename or title to search)
- **Process:**
  1. OpenAI cleans the filename/title (removes quality tags, release groups, etc.)
  2. TMDB searches using the cleaned title
  3. Returns comprehensive results with both OpenAI processing and TMDB results
- **Response includes:**
  - `original_query`: Your input
  - `openai_processing`: OpenAI cleaning results
  - `tmdb_search_query`: The cleaned query used for TMDB
  - `tmdb_results`: TMDB search results

**Example:**
```bash
# Input: "The.Matrix.1999.1080p.BluRay.x264-YIFY.mp4"
# OpenAI cleans to: "The Matrix"
# TMDB finds: The Matrix (1999) movie data
```

#### Utility

**GET /health**
- Health check endpoint
- Response: `{"status": "healthy", "movie_paths_count": N, "tmdb_configured": boolean, "openai_configured": boolean}`

## Example Usage

### Add Movie Directories
```bash
curl -X PUT http://localhost:5000/movie-file-paths \
  -H "Content-Type: application/json" \
  -d '{"path": "/Users/nathanpieraut/Movies"}'

curl -X PUT http://localhost:5000/movie-file-paths \
  -H "Content-Type: application/json" \
  -d '{"path": "/Volumes/ExternalDrive/Movies"}'
```

### Get All Movie Files
```bash
curl http://localhost:5000/all-files
```

### Search for Movie Metadata (AI-Enhanced)
```bash
# Clean search
curl "http://localhost:5000/search-movie?q=The+Matrix"

# Messy filename search (OpenAI will clean it)
curl "http://localhost:5000/search-movie?q=The.Matrix.1999.1080p.BluRay.x264-YIFY.mp4"
```

### Remove a Directory
```bash
curl -X DELETE http://localhost:5000/movie-file-paths \
  -H "Content-Type: application/json" \
  -d '{"path": "/Users/nathanpieraut/Movies"}'
```

## Testing

A test script is included to demonstrate the new AI-enhanced functionality:

```bash
python3 test_movie_search.py
```

This script will:
- Test the health endpoint to verify API configuration
- Run several messy movie filenames through the OpenAI + TMDB pipeline
- Show the complete processing flow and results

## Configuration

The application stores its configuration in `config.json` which is automatically created and managed. The configuration includes:

- `movie_file_paths`: Array of directory paths to scan for movies
- `tmdb_api_key`: Your TMDB API key (also configurable via environment variable)

Environment variables (in `env` or `.env` file):
- `TMDB_API_KEY`: Your TMDB API key
- `OPENAI_API_KEY`: Your OpenAI API key

## Logging

The application creates detailed logs in `movie_api.log` and outputs to console. Logs include:
- API requests and responses
- OpenAI filename cleaning process
- TMDB search queries and results
- Error handling and debugging information

## Supported Media Formats

The API recognizes the following video file extensions:
- MP4, MKV, AVI, MOV, WMV, FLV, WEBM, M4V
- MPG, MPEG, 3GP, ASF, RM, RMVB, VOB, TS

## Error Handling

The API includes comprehensive error handling:
- Path validation (existence, directory check)
- Duplicate path prevention
- Permission error handling during file discovery
- TMDB API error handling
- Proper HTTP status codes and error messages

## Development

To run in development mode with debug enabled, the server automatically starts with:
- Debug mode: On
- Host: 0.0.0.0 (accessible from other devices on network)
- Port: 5000
- CORS enabled for cross-origin requests
