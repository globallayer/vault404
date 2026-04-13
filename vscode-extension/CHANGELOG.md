# Changelog

All notable changes to the vault404 VS Code extension will be documented in this file.

## [0.1.0] - 2024-01-15

### Added
- Initial release
- **Log Error & Solution** command - Save errors and their fixes to the knowledge base
- **Find Solution** command - Search for solutions to errors
- **Find Solution from Selection** - Right-click context menu for selected text
- **Verify Solution** command - Mark solutions as working (auto-contributes to community)
- **Log Decision** command - Record architectural decisions
- **Log Pattern** command - Record reusable patterns
- **Status Bar** - Shows current knowledge base stats
- **Auto-Query** - Automatically searches for solutions when errors detected
- Context menu integration for quick access
- Language and framework auto-detection
- Secret redaction (API keys, passwords stripped before storage)

### Technical
- Communicates with vault404 CLI via child process
- MCP (Model Context Protocol) support for detailed queries
- WebView panels for solution details and stats
- Configurable Python path and defaults
