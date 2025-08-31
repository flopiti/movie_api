# Movie Management REST API

A Python Flask-based REST API for managing movie file paths and discovering media files, with TMDB (The Movie Database) API integration for movie metadata.

## Features

- **File Path Management**: Add, remove, and list movie directory paths
- **Recursive File Discovery**: Automatically find all media files in configured directories
- **TMDB Integration**: Search for movie metadata using TMDB API
- **RESTful API**: Clean REST endpoints for all operations
- **Media File Support**: Supports common video formats (MP4, MKV, AVI, MOV, etc.)

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd /Users/nathanpieraut/movie_duplicates
   ```

2. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure TMDB API (optional but recommended):**
   - Copy `env.example` to `.env`
   - Get your API key from [TMDB](https://www.themoviedb.org/settings/api)
   - Add your API key to the `.env` file:
     ```
     TMDB_API_KEY=your_actual_api_key_here
     ```

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

#### TMDB Integration

**GET /search-movie?q=movie_title**
- Search for movie metadata using TMDB API
- Query parameter: `q` (movie title to search)
- Response: TMDB search results

#### Utility

**GET /health**
- Health check endpoint
- Response: `{"status": "healthy", "movie_paths_count": N, "tmdb_configured": boolean}`

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

### Search for Movie Metadata
```bash
curl "http://localhost:5000/search-movie?q=The+Matrix"
```

### Remove a Directory
```bash
curl -X DELETE http://localhost:5000/movie-file-paths \
  -H "Content-Type: application/json" \
  -d '{"path": "/Users/nathanpieraut/Movies"}'
```

## Configuration

The application stores its configuration in `config.json` which is automatically created and managed. The configuration includes:

- `movie_file_paths`: Array of directory paths to scan for movies
- `tmdb_api_key`: Your TMDB API key (also configurable via environment variable)

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
