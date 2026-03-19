# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-03-19

### Added
- **UI Frontend:** Complete React-based web interface with TypeScript, Tailwind CSS, and Vite
  - Chat interface with agent selection and conversation history
  - User authentication (login, registration, logout) with httpOnly cookies
  - Workspace and agent management
  - API key management UI
  - Usage dashboard for token and cost tracking
  - Theme switching (light/dark modes)
  - Command palette for quick navigation
  - Playwright E2E tests for critical user flows
- **Auth improvements:** httpOnly cookie-based authentication for browser clients
- **Conversation search:** Filter conversations by title with case-insensitive search
- **Logout endpoint:** Secure cookie clearing on user logout
- **Docker/Nginx:** Reverse proxy configuration for serving UI and API together
- **Comprehensive test coverage:** New unit and functional tests for auth, API, and services

### Changed
- Auth endpoints now set httpOnly cookies automatically on login/register/refresh
- Conversation list endpoints support search filtering via query parameter
- Database schema expanded with user API keys and conversation titles

### Fixed
- Improved auth flow stability with cookie-based session management
- Enhanced error handling across API endpoints

---

[0.1.1]: https://github.com/lestherll/personal_assistant/releases/tag/v0.1.1
