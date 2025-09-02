# Plex Movie Checker Tools

This collection of Python scripts helps you connect to your Plex server and analyze your movie library.

## Files

- `plex_movie_checker.py` - Main Plex API client for connecting and retrieving movies
- `quick_plex_check.py` - Simple script to quickly get movie count from Plex
- `movie_comparison.py` - Full comparison tool to compare local files with Plex movies
- `requirements.txt` - Python dependencies

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Optional: Set Plex token (if needed for remote access):**
   ```bash
   export PLEX_TOKEN="your_plex_token_here"
   ```
   
   You can get your Plex token from:
   - Plex Web → Settings → Account → Show Advanced → Get Token
   - Or visit: https://www.plex.tv/claim/

## Usage

### Quick Movie Count Check

To quickly get the number of movies Plex recognizes:

```bash
python quick_plex_check.py
```

This will:
- Connect to your Plex server at `natetrystuff.com:32400`
- Count all movies in all movie libraries
- Display the total count and breakdown by library

### Full Movie Analysis

To get detailed information about all movies in Plex:

```bash
python plex_movie_checker.py
```

This will:
- Connect to Plex and retrieve all movies
- Extract detailed information (title, year, rating, file paths, etc.)
- Save the data to a JSON file with timestamp
- Display a summary with movie counts by year

### Movie Comparison (Advanced)

To compare your local movie files with what Plex recognizes:

1. **Edit the script** to specify your local movie directories:
   ```python
   local_directories = [
       "/path/to/your/movies",  # Replace with your actual paths
       "/another/movie/path"
   ]
   ```

2. **Run the comparison:**
   ```bash
   python movie_comparison.py
   ```

This will:
- Scan your local directories for movie files
- Get all movies from Plex
- Compare the two lists
- Show which movies are missing from Plex
- Show which movies are in Plex but not in local files
- Save a detailed comparison report

## Configuration

### Plex Server URL

The scripts are configured to connect to `http://natetrystuff.com:32400`. If your Plex server is different, edit the `base_url` variable in the scripts.

### Authentication

For local network access, no token is usually needed. For remote access, you'll need to set the `PLEX_TOKEN` environment variable.

## Output Files

The scripts generate several types of output files:

- `plex_movies_YYYYMMDD_HHMMSS.json` - Detailed movie information from Plex
- `movie_comparison_YYYYMMDD_HHMMSS.json` - Full comparison report

## Troubleshooting

### Connection Issues

If you can't connect to Plex:

1. **Check if Plex server is running** and accessible
2. **Verify the URL** is correct (including port 32400)
3. **Try with a token** if accessing remotely
4. **Check firewall settings** if connecting from outside the network

### No Movies Found

If no movies are found:

1. **Check if you have movie libraries** set up in Plex
2. **Verify the libraries are properly configured** with movie content
3. **Check if the libraries are accessible** with your current permissions

### Permission Issues

If you get permission errors:

1. **Make sure your Plex account** has access to the libraries
2. **Check if the libraries are shared** with your account
3. **Verify the token** has the necessary permissions

## Example Output

```
🎬 Quick Plex Movie Count Check
========================================
✅ Successfully connected to Plex server: http://natetrystuff.com:32400
📁 Found movie library: Movies
   Found 847 movies in Movies
📁 Found movie library: 4K Movies
   Found 156 movies in 4K Movies

📊 PLEX MOVIE COUNT: 1003
📁 Total movie files recognized by Plex

📂 Breakdown by library:
   Movies: 847 movies
   4K Movies: 156 movies
```

## Next Steps

Once you have the Plex movie count, you can:

1. **Compare with your local count** to identify missing movies
2. **Check specific movies** that might not be recognized
3. **Analyze your library** for duplicates or missing metadata
4. **Generate reports** for library management

The JSON output files can be used for further analysis or integration with other tools.
