# 404vault VS Code Extension

**Collective AI Coding Agent Brain** - Brings community knowledge directly into your editor.

Every verified fix makes ALL AI agents smarter. Automatic sharing, fully anonymized.

## Features

### Log Errors & Solutions
When you fix a bug, log it to 404vault so you (and the community) can find it later.

- Right-click on selected text > "404vault: Log Error & Solution"
- Or use Command Palette: `404vault: Log Error & Solution`

### Find Solutions
When you encounter an error, search the knowledge base for solutions.

- Select error text > Right-click > "404vault: Find Solution for Selected Text"
- Or use Command Palette: `404vault: Find Solution for Error`

### Auto-Query on Error (Optional)
When enabled, 404vault automatically searches for solutions when errors appear in the Problems panel.

### Verify Solutions
After applying a solution, verify it worked. Verified solutions are **automatically contributed** to the community brain.

- Command Palette: `404vault: Verify Solution Worked`

### Log Decisions & Patterns
Track architectural decisions and reusable patterns:

- `404vault: Log Architectural Decision`
- `404vault: Log Reusable Pattern`

### Status Bar
Shows current knowledge base stats. Click to view detailed statistics.

## Requirements

1. **Python 3.10+** installed
2. **vault404** Python package installed:
   ```bash
   pip install vault404
   # or
   uv pip install vault404
   ```

## Installation

### From VSIX (Local)
1. Download the `.vsix` file
2. In VS Code: Extensions > ... > Install from VSIX

### From Source
```bash
cd 404vault/vscode-extension
npm install
npm run compile
```

Then press F5 to launch Extension Development Host.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `vault404.pythonPath` | `python` | Path to Python executable |
| `vault404.enableStatusBar` | `true` | Show stats in status bar |
| `vault404.autoQueryOnError` | `true` | Auto-search when errors detected |
| `vault404.defaultLanguage` | `""` | Default language context (auto-detected) |
| `vault404.defaultFramework` | `""` | Default framework context |
| `vault404.communityEnabled` | `false` | Enable community brain search |

## Commands

| Command | Description |
|---------|-------------|
| `404vault: Log Error & Solution` | Log an error and its fix |
| `404vault: Find Solution for Error` | Search for solutions |
| `404vault: Find Solution for Selected Text` | Search using selected text |
| `404vault: Verify Solution Worked` | Mark solution as working |
| `404vault: Log Architectural Decision` | Record a decision |
| `404vault: Log Reusable Pattern` | Record a pattern |
| `404vault: Show Knowledge Base Stats` | View statistics |
| `404vault: Refresh Stats` | Refresh status bar |

## How It Works

```
1. You fix an error
   |
   v
2. Log it to 404vault (secrets auto-redacted)
   |
   v
3. Verify it worked
   |
   v
4. Automatically contributed to community brain (anonymized)
   |
   v
5. Other developers & AI agents can find your solution
```

## Privacy & Security

- **Secret Redaction**: API keys, passwords, tokens are stripped BEFORE storage
- **Anonymization**: Project paths, IPs, emails removed BEFORE sharing
- **Local Encryption**: AES-256 for your private copy
- **Verification Gate**: Only WORKING solutions get shared

## Troubleshooting

### "Command not found" errors
Make sure `vault404` is installed and accessible from your Python path:
```bash
python -m vault404 stats
```

### No solutions found
The knowledge base grows over time. Start by logging your own fixes!

### Status bar shows "?"
Check that Python and vault404 are properly installed. View the Output panel (View > Output > 404vault) for debug info.

## Development

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Watch mode
npm run watch

# Package extension
npm run package
```

## License

FSL-1.1-Apache-2.0 (Functional Source License)

- Free for personal use
- Free for company internal use
- Free to modify and self-host
- Cannot offer as a competing hosted service
- Becomes Apache 2.0 after 4 years
