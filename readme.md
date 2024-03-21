# Media Processing Suite

The Media Processing Suite is a comprehensive solution that combines a powerful FastAPI backend and a user-friendly React frontend to offer a wide range of media processing tools. This suite caters to various needs, from audio and video manipulation to social media content analysis, providing both developers and end-users with a robust set of functionalities.

## Features

### FastAPI Backend

#### User Authentication System

- **Secure Registration and Login**: Utilizes bcrypt for hashing passwords, ensuring secure storage and verification.
- **JWT Token Generation**: Leverages the jose library to generate JWT tokens for authenticated users, enabling secure access to protected endpoints.
- **OAuth2 Scheme**: Implements OAuth2PasswordBearer for token-based authentication, ensuring that requests to protected endpoints include valid JWT tokens.

#### Media Processing Endpoints

- **Audio/Video Separation**: Allows users to separate audio from video, accepting inputs from YouTube URLs or direct file uploads.
- **YouTube Video Downloading**: Enables the downloading of YouTube videos at the highest available quality, with sanitized filenames.
- **Media Transcription**: Uses faster_whisper for efficient audio transcription from video or audio files, providing the transcribed text in a downloadable ZIP archive.
- **Bulk Image Compression**: Supports compressing multiple images at once, with customizable quality and size settings, returning a ZIP file of the compressed images.
- **Instagram Reel Downloading**: Utilizes instaloader for downloading Instagram reels and associated captions, packaging them for download.
- **Instagram Audio/Video Analysis**: Offers a detailed analysis of Instagram reels by combining audio transcription and video frame analysis into a comprehensive report.

#### Logging and Monitoring

- **Action Logging**: Tracks and logs user activities, including authentication events and API usage.
- **Discord Integration**: For real-time monitoring, log messages and error notifications are sent to a designated Discord webhook.

### React Frontend Application

#### Core Features

- **Secure User Authentication**: Utilizes JWT for secure authentication, ensuring that only authorized users can access the application's functionalities.
- **Comprehensive Media Tools**: Features dedicated components for each media processing task, like audio/video separation, YouTube video downloading, media transcription, image compression, and Instagram content analysis.
- **Intuitive User Interface**: Designed to be accessible to users of all technical levels, with a focus on simplicity and efficiency.

#### Component Architecture

- **App.jsx**: The main component that orchestrates the application, including routing and the authentication context.
- **AuthContext.jsx**: Manages the authentication state across the application, facilitating secure access to features.
- **Feature Components**: Individual components for each media processing task, such as `AudioVideoSeparator.jsx` for extracting audio, `YoutubeDownloader.jsx` for video downloads, and `InstagramAnalyzer.jsx` for analyzing Instagram content.

### React Frontend Application

#### Core Features

- **Secure User Authentication**: Utilizes JWT for secure authentication, ensuring that only authorized users can access the application's functionalities.
- **Comprehensive Media Tools**: Features dedicated components for each media processing task, like audio/video separation, YouTube video downloading, media transcription, image compression, and Instagram content analysis.
- **Intuitive User Interface**: Designed to be accessible to users of all technical levels, with a focus on simplicity and efficiency.

#### Component Architecture

- **App.jsx**: The main component that orchestrates the application, including routing and the authentication context.
- **AuthContext.jsx**: Manages the authentication state across the application, facilitating secure access to features.
- **Feature Components**:
  - **AudioVideoSeparator.jsx**: Allows users to separate audio from video files or YouTube URLs, showcasing external API integration and state management for user inputs and outputs.
  - **YoutubeDownloader.jsx**: Enables users to download YouTube videos, featuring YouTube API integration, error handling, and progress feedback mechanisms.
  - **MediaTranscriber.jsx**: Transcribes audio and video files to text, handling asynchronous operations, complex state management, and user interaction.
  - **BulkImageCompressor.jsx**: Compresses multiple images simultaneously, utilizing the canvas API for image processing and managing file inputs/outputs.
  - **InstagramAnalyzer.jsx**: Analyzes Instagram posts by scraping content, integrating with third-party APIs, and providing a downloadable summary.


Media Processing Suite
The Media Processing Suite is a comprehensive solution that combines a powerful FastAPI backend and a user-friendly React frontend to offer a wide range of media processing tools. This suite caters to various needs, from audio and video manipulation to social media content analysis, providing both developers and end-users with a robust set of functionalities.

FastAPI Backend
The FastAPI backend serves as the core of the Media Processing Suite, handling the heavy lifting of media processing tasks and providing secure authentication and authorization mechanisms.

User Authentication System
The backend implements a robust user authentication system to ensure that only authorized users can access the application's features. Here's how it works:

Secure Registration and Login: The backend utilizes the bcrypt library for hashing passwords, ensuring secure storage and verification during the registration and login processes.
JWT Token Generation: Once a user is authenticated, the backend generates a JSON Web Token (JWT) using the jose library. This token is used for secure access to protected endpoints.
OAuth2 Scheme: The backend implements the OAuth2PasswordBearer scheme for token-based authentication. Requests to protected endpoints must include a valid JWT token in the Authorization header.
Media Processing Endpoints
The FastAPI backend provides a variety of endpoints for media processing tasks, leveraging third-party libraries and services to handle complex operations. Here are the key endpoints:

Audio/Video Separation: This endpoint allows users to separate the audio from a video file. It accepts inputs from YouTube URLs or direct file uploads (supported formats: mp4, mov, avi, mkv). Users can choose to receive either the separated audio file (in mp3 format) or the video file itself.
YouTube Video Downloading: This endpoint enables users to download YouTube videos by providing the video URL. The backend automatically selects the highest available video resolution and sanitizes the filename for compatibility.
Media Transcription: This endpoint transcribes the audio content from an audio or video file into text. It utilizes the faster_whisper library, a high-performance implementation of the Whisper speech recognition model. The transcribed text is saved in a text file and returned as a ZIP archive, along with the original media file.
Bulk Image Compression: This endpoint allows users to compress multiple images in bulk, reducing their file sizes while maintaining reasonable quality. Users can upload individual image files or a ZIP archive containing multiple images (supported formats: jpg, jpeg, png). They can also specify the desired compression quality level and a size threshold to determine which images should be compressed.
Instagram Reel Downloading: This endpoint enables users to download Instagram reels by providing the reel URL. The backend uses the instaloader library to download the reel video and any associated metadata. The caption text of the reel is extracted and saved as a separate text file.
Instagram Audio/Video Analysis: This endpoint performs comprehensive analysis on the audio and video components of an Instagram reel. The backend downloads the reel video using instaloader, extracts the audio and transcribes it using faster_whisper, and sends video frames to OpenAI's GPT-4 model for analysis and description. A final summary is generated by combining the transcription and frame descriptions, highlighting relevant technologies, software, or coding practices.
Logging and Monitoring
The FastAPI backend includes logging and monitoring capabilities to track user activities and ensure proper functioning of the application:

Action Logging: Whenever a user performs an action (e.g., authentication, API request), the application logs the user's username, action details, and a timestamp.
Discord Webhook Integration: The log messages are sent to a Discord webhook for centralized monitoring and alerting.
Error Logging: Any errors or exceptions that occur during API requests are also logged and sent to the Discord webhook.
React Frontend
The Media Processing Suite also includes a React-based frontend application that provides a user-friendly interface for accessing the various media processing tools offered by the FastAPI backend.

Core Features
Secure User Authentication: The frontend implements JWT-based authentication, ensuring that only authorized users can access the application's functionalities.
Comprehensive Media Tools: The frontend features dedicated components for each media processing task, such as audio/video separation, YouTube video downloading, media transcription, image compression, and Instagram content analysis.
Intuitive User Interface: The application is designed with a focus on simplicity and efficiency, making it accessible to users of all technical levels.
Component Architecture
The React frontend follows a well-structured component architecture, with key components responsible for different aspects of the application:

App.jsx: The main component that orchestrates the application, including routing and the authentication context.
AuthContext.jsx: Manages the authentication state across the application, facilitating secure access to features.
Feature Components:
AudioVideoSeparator.jsx: Allows users to separate audio from video files or YouTube URLs, showcasing external API integration and state management for user inputs and outputs.
YoutubeDownloader.jsx: Enables users to download YouTube videos, featuring YouTube API integration, error handling, and progress feedback mechanisms.
MediaTranscriber.jsx: Transcribes audio and video files to text, handling asynchronous operations, complex state management, and user interaction.
BulkImageCompressor.jsx: Compresses multiple images simultaneously, utilizing the canvas API for image processing and managing file inputs/outputs.
InstagramAnalyzer.jsx: Analyzes Instagram posts by scraping content, integrating with third-party APIs, and providing a downloadable summary.
These feature components are responsible for rendering the user interface, handling user interactions, and communicating with the FastAPI backend to perform media processing tasks.