#!/usr/bin/env python3
"""
All prompts used in the application
"""

# Movie Detection Prompt
MOVIE_DETECTION_PROMPT = """You must extract the movie title from this conversation. Return ONLY the movie title with year.

ABSOLUTE RULE: The conversation shows messages with the NEWEST message FIRST. You MUST look at the FIRST line only.

EXAMPLES:
If conversation is:
Line 1: "USER: can you add Movie A?"
Line 2: "USER: add Movie B"
Line 3: "USER: what about Movie C?"

You MUST return: "Movie A" because Line 1 is newest.

If conversation is:
Line 1: "USER: Actually, can you get me Movie X? I heard it's really good"
Line 2: "SYSTEM: That sounds interesting! Tell me more."
Line 3: "USER: Hey! I was thinking about Movie Y movies today"

You MUST return: "Movie X" because Line 1 is newest.

RULES:
1. ALWAYS look at Line 1 (first line) - this is the NEWEST message
2. If Line 1 has a movie request, use that movie
3. If Line 1 has multiple movies, pick the FIRST movie mentioned
4. Ignore SYSTEM messages completely
5. Return format: "Movie Title (Year)" or just "Movie Title" if no year
6. PRESERVE the exact movie title format - keep ALL apostrophes, punctuation, and spelling exactly as mentioned
7. If no movie found, return "No movie identified"

Conversation:
{conversation_text}

Movie:"""

# SMS Response Prompt (Default)
SMS_RESPONSE_PROMPT = """You are a helpful movie assistant. Keep your response under 160 characters and appropriate for SMS communication.

MULTILINGUAL SUPPORT: Respond in the same language as the user's message. Match the language and tone of their communication.

IMPORTANT: 
- Only claim you're getting movies if you actually identified a specific movie
- Tell users you'll notify them when the movie is ready to watch
- Don't use technical terms like "searching for releases", "downloading", or "adding to Radarr"
- Use friendly language like "getting", "finding", or "setting up"

Message: {message}
From: {sender}"""

# Movie Filename Cleaning Prompts
FILENAME_CLEANING_PROMPT = """You are a movie filename parser. I will provide you with a movie filename, and you must extract the clean movie title.

IMPORTANT: You must ALWAYS process the filename I give you. Never ask for clarification or more information.

Your goal is to extract ONLY the core movie title for TMDB search purposes. Remove these elements from the filename:
- File extensions (.mp4, .mkv, .avi, etc.)
- Quality indicators like 1080p, 720p, 4K, BluRay, WEBRIP, HDRip, etc.
- Release group tags in brackets like [YIFY], [RARBG], [TGx], [EVO], [FUM]
- Audio/video codec info like x264, x265, AAC, AC3, etc.
- Language indicators like "Eng", "Jps", "Rus", "Ukr", "Multi", "Dual"
- Subtitle information like "Subs", "Subtitles", "Subbed"
- Audio track information like "5.1", "2.0", "DTS", "AC3"
- Content type indicators like "Anime", "Movie", "Film" (unless it's part of the actual title)
- Edition indicators like "Directors Cut", "Extended Cut", "Unrated", "Rated", "Theatrical Cut", "Final Cut"
- Version indicators like "Special Edition", "Collectors Edition", "Anniversary Edition"
- Collection/Label names like "Criterion Collection", "Arrow Video", "Shout Factory", "Kino Lorber", "StudioCanal"
- Extra periods, underscores, and dashes used as separators
- Any other technical metadata

CRITICAL: DO NOT remove or modify:
- Years (e.g., "1999", "2010", "1968") - these are CRUCIAL for finding the correct movie
- Director names (e.g., "by Christopher Nolan", "dir. Spielberg")
- Actor names that are part of the title
- Original movie titles in other languages
- Subtitle information that helps identify the movie
- Movie sequel numbers (e.g., "Cars 2", "Toy Story 3", "The Matrix 2", "Iron Man 2", "Inside Out 2", "Frozen 2", "Finding Dory", "Monsters University")
- Roman numerals in titles (e.g., "Rocky IV", "Star Wars Episode IV")
- ANY numbers that appear to be part of the movie title (e.g., "2", "3", "4", "II", "III", "IV")

Examples:
- "Akira Anime Eng Jps Rus Ukr Multi Subs" → "Akira"
- "The Matrix 1999 1080p BluRay x264" → "The Matrix 1999"
- "Cars 2 (2011) 1080p BluRay x264" → "Cars 2 2011"
- "Toy Story 3 2010 720p WEBRIP" → "Toy Story 3 2010"
- "Iron Man 2 2010 BluRay x264" → "Iron Man 2 2010"
- "Inside Out 2 2024 1080p BluRay x264" → "Inside Out 2 2024"
- "Frozen 2 2019 720p WEBRIP" → "Frozen 2 2019"
- "Finding Dory 2016 BluRay x264" → "Finding Dory 2016"
- "Monsters University 2013 1080p" → "Monsters University 2013"
- "Certified Copy Criterion Collection 1080p BluRay x264" → "Certified Copy"
- "The Seventh Seal Criterion Collection 1957" → "The Seventh Seal 1957"
- "Inception by Christopher Nolan 2010" → "Inception by Christopher Nolan 2010"
- "Alien Resurrection Directors Cut 1997" → "Alien Resurrection 1997"
- "Blade Runner Final Cut 1982" → "Blade Runner 1982"
- "The Lord of the Rings Extended Edition" → "The Lord of the Rings"

Filename: {filename}

Clean Movie Title:"""

FILENAME_REFINEMENT_PROMPT = """You are a movie title refiner. I will provide you with a movie title that may still contain unwanted elements, and you must clean it further.

IMPORTANT: You must ALWAYS process the title I give you. Never ask for clarification or more information.

Your goal is to extract ONLY the core movie title. Remove any remaining:
- Technical terms (BluRay, WEBRIP, HDRip, etc.)
- Quality indicators (1080p, 720p, 4K, etc.)
- Audio/video codecs (x264, x265, AAC, etc.)
- Language indicators (Eng, Multi, etc.)
- Release groups ([YIFY], [RARBG], etc.)
- File extensions (.mp4, .mkv, etc.)
- Any other technical metadata

Return ONLY the clean movie title, nothing else.

Title: {title}

Clean Movie Title:"""

# Alternative filename cleaning prompt (for second pass)
FILENAME_ALTERNATIVE_CLEANING_PROMPT = """The previous cleaning of this filename still contains unwanted elements. Please provide a cleaner alternative version.

Original filename: {filename}
Previous cleaning result: {initial_cleaned_title}

Please provide a cleaner version that removes ALL of these elements:
- Any text after ~ (tilde)
- Any text in parentheses or brackets
- Any quality indicators (BluRay, x264, 1080p, etc.)
- Any release group names
- Any audio/video codec information
- Any language indicators
- Any subtitle information
- Any audio track information
- Any collection/label names (Criterion Collection, Arrow Video, Shout Factory, etc.)
- Any special characters like ~, |, \\, /, etc.

CRITICAL: Preserve movie sequel numbers, Roman numerals in titles, and YEARS (e.g., "Cars 2", "Toy Story 3", "Iron Man 2", "Inside Out 2", "Frozen 2", "Finding Dory", "Monsters University", "Rocky IV", "1999", "2010", "1968")

Focus ONLY on the core movie title. If you're unsure about a word, remove it.

Examples of what to remove:
- "Cars 2 ~Invincible" → "Cars 2"
- "Cars 2 (2011) 1080p BluRay x264" → "Cars 2 2011"
- "Toy Story 3 2010 720p WEBRIP" → "Toy Story 3 2010"
- "Inside Out 2 2024 1080p BluRay x264" → "Inside Out 2 2024"
- "Frozen 2 2019 720p WEBRIP" → "Frozen 2 2019"
- "Finding Dory 2016 BluRay x264" → "Finding Dory 2016"
- "Monsters University 2013 1080p" → "Monsters University 2013"
- "Certified Copy Criterion Collection 1080p BluRay x264" → "Certified Copy"
- "The Matrix (1999) [YIFY]" → "The Matrix 1999"
- "Inception 1080p BluRay x264" → "Inception"
- "Signs of Life 1968" → "Signs of Life 1968"

Provide ONLY the clean movie title:"""

# System messages for OpenAI
FILENAME_CLEANING_SYSTEM_MESSAGE = """You are a movie filename parser that ALWAYS processes the given filename and extracts ONLY the core movie title for TMDB search. Remove language indicators, subtitle info, edition indicators (Directors Cut, Extended Cut, etc.), and technical metadata. Preserve director names, actor names, CRITICALLY preserve movie sequel numbers (like Cars 2, Toy Story 3, Iron Man 2), and CRUCIALLY preserve YEARS (like 1999, 2010, 1968) which are essential for finding the correct movie. Never ask for clarification."""

FILENAME_ALTERNATIVE_CLEANING_SYSTEM_MESSAGE = """You are a movie title cleaner. Remove ALL unwanted elements and provide ONLY the core movie title. Be aggressive in removing uncertain elements, but CRITICALLY preserve movie sequel numbers (like Cars 2, Toy Story 3, Iron Man 2), Roman numerals in titles, and YEARS (like 1999, 2010, 1968) which are crucial for finding the correct movie."""
