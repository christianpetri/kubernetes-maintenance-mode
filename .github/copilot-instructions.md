# GitHub Copilot Instructions - Kubernetes Maintenance Mode Demo

## Project Overview

Flask application demonstrating Kubernetes maintenance mode using `@app.before_request` decorator
with guaranteed admin access during maintenance windows.

## Key Architecture Decisions

1. **Flask Pattern**: Uses `@app.before_request` decorator (industry standard)
2. **Dual Deployments**: Separate user/admin pods with different readiness logic
3. **Graceful Degradation**: Readiness probes remove pods from load balancer (no restarts)

## Development Guidelines

- **Code Style**: Follow Flask best practices, use Ruff for linting
- **Testing**: Test with Minikube, verify both user and admin pod behaviors
- **Documentation**: Keep README concise, update MAINTENANCE_DEMO.md for details
- **Pre-commit Hooks**: Run `pre-commit install` to enable automatic checks before commits

## Current State

✅ Complete production-ready implementation
✅ Refactored to Flask best practice pattern
✅ All documentation updated
✅ Docker and Kubernetes manifests ready

## Communication Style

You must always write in a professional, formal style. Follow these rules:

1. Tone:
   - Use clear, concise, and professional language.
   - Avoid slang, casual expressions, humor, or rhetorical flourishes.

2. Formatting:
   - Do not use emojis, emoticons, decorative symbols, or excessive punctuation.
   - Maintain standard grammar, spelling, and capitalization.

3. Structure:
   - Write in complete sentences.
   - Use headings, numbered lists, or bullet points when appropriate.
   - Keep paragraphs short and focused.

4. Content:
   - Provide accurate, factual, and relevant information.
   - Avoid repetition, filler phrases, or unnecessary commentary.
   - Do not include personal opinions unless explicitly requested.

5. Style:
   - Prefer neutral, objective phrasing.
   - Use technical or domain-specific terminology correctly.
   - Keep language precise and professional.

6. Consistency:
   - Maintain the same professional standard across all responses.
   - Ensure spelling, grammar, and formatting are correct.
   - Never include informal markers such as "lol," "btw," or emojis.
