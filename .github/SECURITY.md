# Security Policy

### Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public issue
2. **Email** the maintainers directly or use GitHub's private vulnerability reporting
3. Include a clear description of the vulnerability and steps to reproduce

We will respond within 48 hours and work with you to resolve the issue.

### API Key Safety

- Never commit `.env` files or API keys to the repository
- Use `.env.example` as a template — it contains no secrets
- The `.gitignore` is configured to exclude `.env` and `.env.*`

### Known Considerations

- MAARS sends user input to Google Gemini API (in `gemini` and `agent` modes)
- Research outputs are stored as plaintext files in `research/`
- The SSE endpoint does not require authentication (intended for local development)
