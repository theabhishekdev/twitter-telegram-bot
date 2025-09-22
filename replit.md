# Overview

This is a Twitter/X to Telegram bot that monitors a specific X user's tweets and forwards them to a designated Telegram channel. The bot continuously checks for new tweets from a configured X user and automatically posts them to a specified Telegram channel, acting as a bridge between the two social media platforms.

**Latest Updates (September 22, 2025):**
- Added support for multiple X developer accounts (up to 5) with automatic rotation to avoid rate limits
- Implemented Telegram login functionality allowing multiple users to authenticate and use the bot
- Enhanced authorization system with user management capabilities
- Improved error handling with graceful degradation when API tokens are missing or invalid

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Components

**Bot Architecture**: Single-threaded Python application using Flask for web server functionality and separate libraries for X API and Telegram bot operations.

**Configuration Management**: JSON-based configuration storage with persistent settings including X user ID, username, Telegram channel, and last processed tweet ID for state management.

**API Integration Pattern**: 
- X API integration using Bearer token authentication for read-only tweet fetching
- Telegram Bot API integration for message posting to channels
- RESTful API calls with proper error handling and rate limiting considerations

**Monitoring System**: Polling-based approach with configurable intervals (60 seconds default) to check for new tweets rather than webhook-based real-time updates.

**Security Model**: Admin-only bot commands using Telegram user ID verification to prevent unauthorized configuration changes.

**Deployment Architecture**: Flask web server for health checks and uptime monitoring compatibility (designed for Replit deployment with UptimeRobot monitoring).

## Key Design Decisions

**Stateful Operation**: Maintains last processed tweet ID to avoid duplicate posts and ensure continuity across bot restarts.

**Environment-based Configuration**: Sensitive tokens stored as environment variables while user-configurable settings persist in JSON file.

**Threading Model**: Separate thread for Flask server to maintain bot operations independence from web server functionality.

# External Dependencies

**X/Twitter API**: Bearer token authentication required for accessing user timeline and tweet data.

**Telegram Bot API**: Bot token required for posting messages to channels and handling admin commands.

**Flask Web Framework**: Lightweight web server for health check endpoints and deployment monitoring.

**Python Standard Libraries**: Threading, JSON, OS modules for core functionality.

**HTTP Requests Library**: For making API calls to both X and Telegram services.

**Deployment Platform**: Configured for Replit hosting with UptimeRobot monitoring integration.