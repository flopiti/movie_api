# Movie Download System

This system allows users to request movie downloads via SMS and automatically monitors the download progress, sending notifications when downloads start and complete.

## Features

- **SMS Movie Detection**: Automatically detects movie titles mentioned in SMS conversations
- **TMDB Integration**: Searches for movie metadata using The Movie Database (TMDB)
- **Radarr Integration**: Adds movies to Radarr for automatic downloading
- **Download Monitoring**: Continuously monitors download progress
- **SMS Notifications**: Sends SMS updates when downloads start, complete, or fail
- **Persistent Storage**: Uses Redis to store download requests and status

## How It Works

### 1. SMS Movie Detection
When someone sends an SMS mentioning a movie:
1. The system analyzes the conversation using OpenAI to extract movie titles
2. Searches TMDB for the movie metadata
3. Automatically adds the movie to Radarr for downloading
4. Sends a confirmation SMS to the user

### 2. Download Monitoring
The system continuously monitors:
- Movies being added to Radarr
- Download progress in the Radarr queue
- Download completion status
- Any download failures

### 3. SMS Notifications
Users receive SMS notifications for:
- **Download Started**: "🎬 Great! I'm getting [Movie Title] ([Year]) ready for you. I'll text you when it's ready to watch!"
- **Download Completed**: "🎉 [Movie Title] ([Year]) is ready to watch! Enjoy your movie!"
- **Download Failed**: "😔 Sorry, I couldn't get [Movie Title] ([Year]) ready for you. [Error message]"

## Configuration

### Required Environment Variables
```bash
# Radarr Configuration
RADARR_URL=http://192.168.0.10:7878
RADARR_API_KEY=your_radarr_api_key

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

# TMDB Configuration
TMDB_API_KEY=your_tmdb_api_key

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Redis Configuration
REDIS_HOST=172.17.0.1
REDIS_PORT=6379
REDIS_DB=0
```

### Radarr Setup
1. Ensure Radarr is running and accessible
2. Configure a root folder for movie downloads
3. Set up quality profiles
4. Configure indexers for torrent/usenet downloads
5. Get your API key from Radarr Settings > General > Security

## API Endpoints

### Download Management
- `GET /api/sms/downloads` - Get all download requests
- `GET /api/sms/downloads/<tmdb_id>` - Get specific download request
- `POST /api/sms/downloads` - Create new download request
- `GET /api/sms/download-monitor/status` - Get monitoring service status
- `POST /api/sms/download-monitor/start` - Start monitoring service
- `POST /api/sms/download-monitor/stop` - Stop monitoring service

### SMS Webhook
- `POST /api/sms/webhook` - Twilio webhook for incoming SMS messages

## Usage Examples

### SMS Request
User sends: "Can you get The Dark Knight for me?"
System responds: "🎬 Great! I found 'The Dark Knight (2008)' and added it to your download queue. I'll send you updates as the download progresses!"

### Download Started Notification
System sends: "🎬 Great! I'm getting The Dark Knight (2008) ready for you. I'll text you when it's ready to watch!"

### Download Completed Notification
System sends: "🎉 The Dark Knight (2008) is ready to watch! Enjoy your movie!"

## Testing

Run the test script to verify the system is working:
```bash
python test_download_system.py
```

This will test:
- Radarr connection
- Twilio configuration
- Redis connection
- Download request creation
- Monitoring service functionality

## Monitoring Service

The download monitoring service runs as a background thread and:
- Checks download status every 30 seconds
- Processes new download requests
- Sends SMS notifications for status changes
- Stores all data in Redis for persistence

## Error Handling

The system handles various error scenarios:
- Movie not found in TMDB
- Radarr connection failures
- Download failures
- SMS sending failures
- Redis connection issues

All errors are logged and appropriate fallback responses are sent to users.

## Security Considerations

- All API keys are stored as environment variables
- SMS webhook validates Twilio signatures
- Redis data is stored with appropriate expiration
- Download requests are tied to specific phone numbers

## Troubleshooting

### Common Issues

1. **Radarr Connection Failed**
   - Check RADARR_URL and RADARR_API_KEY
   - Ensure Radarr is running and accessible
   - Verify API key permissions

2. **Twilio SMS Not Working**
   - Check TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
   - Verify webhook URL is set correctly in Twilio console
   - Check phone number format (+1234567890)

3. **Redis Connection Issues**
   - Check REDIS_HOST, REDIS_PORT, REDIS_DB
   - Ensure Redis server is running
   - Verify network connectivity

4. **Movie Not Found**
   - Check TMDB_API_KEY
   - Verify movie title is correct
   - Check if movie exists in TMDB database

### Logs
Check the application logs for detailed error information:
- `movie_api.log` - Application logs
- `server.log` - Server logs

## Future Enhancements

- Support for TV shows (Sonarr integration)
- Multiple quality profile selection
- Download priority management
- User preferences and settings
- Download history and statistics
- Web interface for managing downloads
