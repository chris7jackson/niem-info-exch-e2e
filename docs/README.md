# Documentation

Essential documentation for the NIEM Information Exchange project.

## Core Documentation

### [API Architecture](API_ARCHITECTURE.md)
**Backend architecture and design patterns**

Learn about:
- Layered architecture (handlers → services → clients)
- Request/response flow
- Business logic organization
- Error handling patterns
- External service integration

**When to read:** Before making backend changes or adding new features

### [Ingestion and Mapping Guide](INGESTION_AND_MAPPING.md)
**Data ingestion architecture and mapping specification**

Learn about:
- XSD → CMF → mapping.yaml flow
- XML and JSON ingestion process
- Graph structure generation
- Mapping specification format
- How schemas define graph structure

**When to read:** Before working on ingestion, mapping, or graph structure

### [Unit Testing Guide](UNIT_TESTING.md)
**Testing guide with examples and best practices**

Covers:
- API testing with pytest
- UI testing with Vitest and React Testing Library
- Test structure and patterns
- Coverage requirements
- Running tests locally and in CI

**When to read:** Before writing tests or when test coverage is insufficient

## Additional Resources

### Main README
The [project README](../README.md) contains:
- Quick start guide
- Docker setup instructions
- Complete CrashDriver walkthrough
- Troubleshooting common issues

### Contributing Guide
See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Development setup
- Code style standards
- PR process
- Commit conventions

### Development Guidelines
See [CLAUDE.md](../CLAUDE.md) for:
- Architecture boundaries
- Quality standards
- Security requirements
- Testing minimums

### API Documentation
Interactive API documentation (when system is running):
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI Schema:** http://localhost:8000/openapi.json

## Documentation Philosophy

We keep docs **minimal and maintainable**:

✅ **Keep:** Architecture, patterns, testing guides
❌ **Avoid:** Feature changelogs, TODO lists, duplicating code

**Questions or missing info?**
1. Check the main [README](../README.md)
2. Review [CONTRIBUTING.md](../CONTRIBUTING.md)
3. Search the codebase for examples
4. Create a GitHub issue
