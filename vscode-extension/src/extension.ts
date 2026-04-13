/**
 * 404vault VS Code Extension
 *
 * Collective AI Coding Agent Brain - brings community knowledge
 * directly into your editor.
 *
 * Features:
 * - Log errors and solutions from the editor
 * - Find solutions when errors are detected
 * - Verify solutions with a click
 * - Status bar showing knowledge base stats
 */

import * as vscode from "vscode";
import {
  404vaultClient,
  Solution,
  Context,
  404vaultStats,
} from "./vault404Client";

// Global state
let client: 404vaultClient;
let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;
let lastLoggedRecordId: string | undefined;
let diagnosticsWatcher: vscode.Disposable | undefined;

/**
 * Extension activation
 */
export function activate(context: vscode.ExtensionContext): void {
  // Create output channel for logging
  outputChannel = vscode.window.createOutputChannel("404vault");
  context.subscriptions.push(outputChannel);

  // Initialize client
  client = new 404vaultClient(outputChannel);

  outputChannel.appendLine("[404vault] Extension activated");

  // Create status bar item
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = "vault404.showStats";
  context.subscriptions.push(statusBarItem);

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("vault404.logErrorFix", logErrorFixCommand),
    vscode.commands.registerCommand("vault404.findSolution", findSolutionCommand),
    vscode.commands.registerCommand(
      "vault404.findSolutionFromSelection",
      findSolutionFromSelectionCommand
    ),
    vscode.commands.registerCommand("vault404.verifySolution", verifySolutionCommand),
    vscode.commands.registerCommand("vault404.logDecision", logDecisionCommand),
    vscode.commands.registerCommand("vault404.logPattern", logPatternCommand),
    vscode.commands.registerCommand("vault404.showStats", showStatsCommand),
    vscode.commands.registerCommand("vault404.refreshStats", refreshStatsCommand)
  );

  // Initialize status bar
  const config = vscode.workspace.getConfiguration("vault404");
  if (config.get("enableStatusBar", true)) {
    updateStatusBar();
    // Refresh stats every 5 minutes
    const interval = setInterval(() => updateStatusBar(), 5 * 60 * 1000);
    context.subscriptions.push({ dispose: () => clearInterval(interval) });
  }

  // Watch for diagnostics changes (auto-query on error)
  if (config.get("autoQueryOnError", true)) {
    setupDiagnosticsWatcher(context);
  }

  // Watch for configuration changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("vault404")) {
        const newConfig = vscode.workspace.getConfiguration("vault404");
        if (newConfig.get("enableStatusBar", true)) {
          updateStatusBar();
        } else {
          statusBarItem.hide();
        }

        if (newConfig.get("autoQueryOnError", true)) {
          setupDiagnosticsWatcher(context);
        } else if (diagnosticsWatcher) {
          diagnosticsWatcher.dispose();
          diagnosticsWatcher = undefined;
        }
      }
    })
  );
}

/**
 * Extension deactivation
 */
export function deactivate(): void {
  outputChannel?.appendLine("[404vault] Extension deactivated");
}

// =============================================================================
// Commands
// =============================================================================

/**
 * Log an error and its solution
 */
async function logErrorFixCommand(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const selection = editor?.selection;
  const selectedText = editor?.document.getText(selection);

  // Get error message
  const errorMessage = await vscode.window.showInputBox({
    prompt: "Enter the error message",
    value: selectedText || "",
    placeHolder: "e.g., ECONNREFUSED 127.0.0.1:5432",
  });

  if (!errorMessage) return;

  // Get solution
  const solution = await vscode.window.showInputBox({
    prompt: "Enter the solution",
    placeHolder: "e.g., Use Railway internal hostname instead of localhost",
  });

  if (!solution) return;

  // Get context
  const context = await getContextFromUser();

  // Show progress
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Logging error fix to 404vault...",
      cancellable: false,
    },
    async () => {
      const result = await client.logErrorFix(errorMessage, solution, {
        ...context,
        file: editor?.document.fileName,
        language: client.detectLanguage(editor?.document),
      });

      if (result.success) {
        lastLoggedRecordId = result.record_id;

        const verifyAction = "Verify Solution";
        const action = await vscode.window.showInformationMessage(
          `Logged error fix: ${result.record_id}${result.secrets_redacted ? " (secrets redacted)" : ""}`,
          verifyAction
        );

        if (action === verifyAction) {
          verifySolutionCommand();
        }

        updateStatusBar();
      } else {
        vscode.window.showErrorMessage(`Failed to log: ${result.message}`);
      }
    }
  );
}

/**
 * Find solutions for an error
 */
async function findSolutionCommand(): Promise<void> {
  const errorMessage = await vscode.window.showInputBox({
    prompt: "Enter the error message to search for",
    placeHolder: "e.g., Connection refused to postgres database",
  });

  if (!errorMessage) return;

  await searchAndShowSolutions(errorMessage);
}

/**
 * Find solutions for selected text
 */
async function findSolutionFromSelectionCommand(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("No text selected");
    return;
  }

  const selection = editor.selection;
  const selectedText = editor.document.getText(selection);

  if (!selectedText.trim()) {
    vscode.window.showWarningMessage("No text selected");
    return;
  }

  await searchAndShowSolutions(selectedText);
}

/**
 * Verify that a solution worked
 */
async function verifySolutionCommand(): Promise<void> {
  // Get record ID
  const recordId = await vscode.window.showInputBox({
    prompt: "Enter the record ID to verify",
    value: lastLoggedRecordId || "",
    placeHolder: "e.g., ef_20240115_123456",
  });

  if (!recordId) return;

  // Ask if it worked
  const worked = await vscode.window.showQuickPick(
    [
      { label: "Yes - Solution worked!", value: true },
      { label: "No - Solution didn't work", value: false },
    ],
    { placeHolder: "Did the solution work?" }
  );

  if (worked === undefined) return;

  // Verify
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Verifying solution...",
      cancellable: false,
    },
    async () => {
      const result = await client.verifySolution(recordId, worked.value);

      if (result.success) {
        let message = result.message;
        if (result.contributed) {
          message += " (Contributed to community brain!)";
        }
        vscode.window.showInformationMessage(message);
        updateStatusBar();
      } else {
        vscode.window.showErrorMessage(`Failed to verify: ${result.message}`);
      }
    }
  );
}

/**
 * Log an architectural decision
 */
async function logDecisionCommand(): Promise<void> {
  // Get title
  const title = await vscode.window.showInputBox({
    prompt: "Decision title",
    placeHolder: "e.g., Database choice for user data",
  });

  if (!title) return;

  // Get choice
  const choice = await vscode.window.showInputBox({
    prompt: "What did you choose?",
    placeHolder: "e.g., PostgreSQL with Supabase",
  });

  if (!choice) return;

  // Get alternatives (optional)
  const alternativesStr = await vscode.window.showInputBox({
    prompt: "What alternatives did you consider? (comma-separated, optional)",
    placeHolder: "e.g., MongoDB, DynamoDB, Firebase",
  });

  const alternatives = alternativesStr
    ? alternativesStr.split(",").map((s) => s.trim())
    : undefined;

  // Get deciding factor (optional)
  const decidingFactor = await vscode.window.showInputBox({
    prompt: "What was the deciding factor? (optional)",
    placeHolder: "e.g., Better SQL support and realtime subscriptions",
  });

  // Log it
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Logging decision to 404vault...",
      cancellable: false,
    },
    async () => {
      const result = await client.logDecision(title, choice, {
        alternatives,
        decidingFactor: decidingFactor || undefined,
        language: client.detectLanguage(),
        framework: await client.detectFramework(),
      });

      if (result.success) {
        vscode.window.showInformationMessage(
          `Logged decision: ${result.record_id}`
        );
        updateStatusBar();
      } else {
        vscode.window.showErrorMessage(`Failed to log: ${result.message}`);
      }
    }
  );
}

/**
 * Log a reusable pattern
 */
async function logPatternCommand(): Promise<void> {
  // Get name
  const name = await vscode.window.showInputBox({
    prompt: "Pattern name",
    placeHolder: "e.g., Repository Pattern with TypeScript",
  });

  if (!name) return;

  // Get category
  const category = await vscode.window.showQuickPick(
    [
      "database",
      "auth",
      "api",
      "deployment",
      "testing",
      "caching",
      "error-handling",
      "logging",
      "security",
      "performance",
      "other",
    ],
    { placeHolder: "Select pattern category" }
  );

  if (!category) return;

  // Get problem
  const problem = await vscode.window.showInputBox({
    prompt: "What problem does this pattern solve?",
    placeHolder: "e.g., Need to abstract database access from business logic",
  });

  if (!problem) return;

  // Get solution
  const solution = await vscode.window.showInputBox({
    prompt: "How does the pattern solve it?",
    placeHolder: "e.g., Create repository interfaces with CRUD methods...",
  });

  if (!solution) return;

  // Get code from selection if available
  const editor = vscode.window.activeTextEditor;
  let afterCode: string | undefined;
  if (editor && !editor.selection.isEmpty) {
    afterCode = editor.document.getText(editor.selection);
  }

  // Log it
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Logging pattern to 404vault...",
      cancellable: false,
    },
    async () => {
      const result = await client.logPattern(name, category, problem, solution, {
        afterCode,
        languages: client.detectLanguage() ? [client.detectLanguage()!] : undefined,
      });

      if (result.success) {
        vscode.window.showInformationMessage(
          `Logged pattern: ${result.record_id}`
        );
        updateStatusBar();
      } else {
        vscode.window.showErrorMessage(`Failed to log: ${result.message}`);
      }
    }
  );
}

/**
 * Show knowledge base statistics
 */
async function showStatsCommand(): Promise<void> {
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Loading 404vault stats...",
      cancellable: false,
    },
    async () => {
      const stats = await client.getStats();

      const panel = vscode.window.createWebviewPanel(
        "vault404Stats",
        "404vault Knowledge Base",
        vscode.ViewColumn.One,
        {}
      );

      panel.webview.html = getStatsHtml(stats);
    }
  );
}

/**
 * Refresh status bar stats
 */
async function refreshStatsCommand(): Promise<void> {
  await updateStatusBar();
  vscode.window.showInformationMessage("404vault stats refreshed");
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Search for solutions and show in quick pick
 */
async function searchAndShowSolutions(errorMessage: string): Promise<void> {
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Searching 404vault for solutions...",
      cancellable: false,
    },
    async () => {
      const context: Context = {
        language: client.detectLanguage(),
        framework: await client.detectFramework(),
      };

      const result = await client.findSolution(errorMessage, context);

      if (!result.found || result.solutions.length === 0) {
        const logAction = "Log Solution";
        const action = await vscode.window.showInformationMessage(
          "No solutions found in 404vault. Want to log one?",
          logAction
        );
        if (action === logAction) {
          vscode.commands.executeCommand("vault404.logErrorFix");
        }
        return;
      }

      // Show solutions in quick pick
      const items: vscode.QuickPickItem[] = result.solutions.map(
        (sol: Solution) => ({
          label: `${sol.verified ? "$(verified)" : "$(question)"} ${(sol.confidence * 100).toFixed(0)}% - ${sol.solution.substring(0, 60)}...`,
          description: sol.source === "community" ? "(community)" : "(local)",
          detail: `Original error: ${sol.original_error.substring(0, 80)}`,
          solution: sol,
        })
      );

      const selected = await vscode.window.showQuickPick(items, {
        placeHolder: `Found ${result.solutions.length} solution(s)`,
        matchOnDescription: true,
        matchOnDetail: true,
      });

      if (selected) {
        const solution = (selected as any).solution as Solution;
        showSolutionDetail(solution);
      }
    }
  );
}

/**
 * Show solution details in a webview
 */
function showSolutionDetail(solution: Solution): void {
  const panel = vscode.window.createWebviewPanel(
    "vault404Solution",
    "404vault Solution",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );

  panel.webview.html = getSolutionHtml(solution);
}

/**
 * Update status bar with current stats
 */
async function updateStatusBar(): Promise<void> {
  try {
    const stats = await client.getStats();
    statusBarItem.text = `$(brain) ${stats.total_records}`;
    statusBarItem.tooltip = `404vault: ${stats.error_fixes} fixes, ${stats.decisions} decisions, ${stats.patterns} patterns`;
    statusBarItem.show();
  } catch (error) {
    statusBarItem.text = "$(brain) ?";
    statusBarItem.tooltip = "404vault: Unable to load stats";
    statusBarItem.show();
  }
}

/**
 * Setup diagnostics watcher for auto-query
 */
function setupDiagnosticsWatcher(context: vscode.ExtensionContext): void {
  if (diagnosticsWatcher) {
    diagnosticsWatcher.dispose();
  }

  // Debounce to avoid too many queries
  let debounceTimer: NodeJS.Timeout | undefined;

  diagnosticsWatcher = vscode.languages.onDidChangeDiagnostics((e) => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    debounceTimer = setTimeout(async () => {
      for (const uri of e.uris) {
        const diagnostics = vscode.languages.getDiagnostics(uri);
        const errors = diagnostics.filter(
          (d) => d.severity === vscode.DiagnosticSeverity.Error
        );

        if (errors.length > 0) {
          // Query for the first error
          const error = errors[0];
          const result = await client.findSolution(error.message, {
            language: client.detectLanguage(),
          });

          if (result.found && result.solutions.length > 0) {
            const sol = result.solutions[0];
            if (sol.confidence > 0.7) {
              const viewAction = "View Solution";
              const action = await vscode.window.showInformationMessage(
                `404vault found a ${(sol.confidence * 100).toFixed(0)}% match: ${sol.solution.substring(0, 50)}...`,
                viewAction
              );

              if (action === viewAction) {
                showSolutionDetail(sol);
              }
            }
          }
        }
      }
    }, 2000); // 2 second debounce
  });

  context.subscriptions.push(diagnosticsWatcher);
}

/**
 * Get context from user input
 */
async function getContextFromUser(): Promise<Context> {
  const config = vscode.workspace.getConfiguration("vault404");

  const categories = [
    "database",
    "auth",
    "api",
    "deployment",
    "build",
    "testing",
    "networking",
    "permissions",
    "configuration",
    "other",
  ];

  const category = await vscode.window.showQuickPick(categories, {
    placeHolder: "Select category (optional)",
  });

  return {
    language: config.get("defaultLanguage") || client.detectLanguage(),
    framework: config.get("defaultFramework") || (await client.detectFramework()),
    category: category || undefined,
  };
}

/**
 * Generate HTML for stats panel
 */
function getStatsHtml(stats: 404vaultStats): string {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404vault Knowledge Base</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 20px;
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
        }
        h1 {
            color: var(--vscode-textLink-foreground);
            border-bottom: 1px solid var(--vscode-panel-border);
            padding-bottom: 10px;
        }
        .stat-card {
            background-color: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 8px;
            padding: 20px;
            margin: 10px 0;
            display: inline-block;
            min-width: 150px;
            text-align: center;
        }
        .stat-value {
            font-size: 36px;
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
        }
        .stat-label {
            font-size: 14px;
            color: var(--vscode-descriptionForeground);
            margin-top: 5px;
        }
        .info {
            margin-top: 20px;
            padding: 10px;
            background-color: var(--vscode-textBlockQuote-background);
            border-left: 3px solid var(--vscode-textLink-foreground);
        }
    </style>
</head>
<body>
    <h1>404vault Knowledge Base</h1>

    <div class="stats-container">
        <div class="stat-card">
            <div class="stat-value">${stats.error_fixes}</div>
            <div class="stat-label">Error Fixes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.decisions}</div>
            <div class="stat-label">Decisions</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.patterns}</div>
            <div class="stat-label">Patterns</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${stats.total_records}</div>
            <div class="stat-label">Total Records</div>
        </div>
    </div>

    <div class="info">
        <strong>Data Directory:</strong> ${stats.data_directory || "~/.vault404/"}
        <br><br>
        <strong>Tip:</strong> Verified solutions are automatically contributed to the community brain,
        making all AI coding agents smarter!
    </div>
</body>
</html>
`;
}

/**
 * Generate HTML for solution detail panel
 */
function getSolutionHtml(solution: Solution): string {
  const contextStr = Object.entries(solution.context || {})
    .filter(([_, v]) => v)
    .map(([k, v]) => `<span class="tag">${k}: ${v}</span>`)
    .join(" ");

  return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404vault Solution</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 20px;
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
        }
        h1 {
            color: var(--vscode-textLink-foreground);
            font-size: 18px;
        }
        .section {
            margin: 15px 0;
            padding: 15px;
            background-color: var(--vscode-editor-inactiveSelectionBackground);
            border-radius: 8px;
        }
        .section-title {
            font-weight: bold;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 10px;
            font-size: 12px;
            text-transform: uppercase;
        }
        .solution-text {
            font-size: 16px;
            line-height: 1.6;
        }
        .error-text {
            font-family: var(--vscode-editor-font-family);
            font-size: 13px;
            color: var(--vscode-errorForeground);
            white-space: pre-wrap;
        }
        .confidence {
            display: inline-block;
            padding: 4px 12px;
            background-color: ${solution.confidence > 0.7 ? "var(--vscode-testing-iconPassed)" : "var(--vscode-testing-iconQueued)"};
            color: var(--vscode-editor-background);
            border-radius: 12px;
            font-weight: bold;
            margin-right: 10px;
        }
        .verified {
            display: inline-block;
            padding: 4px 12px;
            background-color: ${solution.verified ? "var(--vscode-testing-iconPassed)" : "var(--vscode-testing-iconQueued)"};
            color: var(--vscode-editor-background);
            border-radius: 12px;
        }
        .source {
            display: inline-block;
            padding: 4px 12px;
            background-color: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            border-radius: 12px;
        }
        .tags {
            margin-top: 10px;
        }
        .tag {
            display: inline-block;
            padding: 2px 8px;
            background-color: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            border-radius: 4px;
            font-size: 12px;
            margin-right: 5px;
        }
        .meta {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        .record-id {
            font-family: var(--vscode-editor-font-family);
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
        }
    </style>
</head>
<body>
    <h1>Solution Found</h1>

    <div class="meta">
        <span class="confidence">${(solution.confidence * 100).toFixed(0)}% match</span>
        <span class="verified">${solution.verified ? "Verified" : "Unverified"}</span>
        <span class="source">${solution.source}</span>
    </div>

    <div class="section">
        <div class="section-title">Solution</div>
        <div class="solution-text">${escapeHtml(solution.solution)}</div>
    </div>

    <div class="section">
        <div class="section-title">Original Error</div>
        <div class="error-text">${escapeHtml(solution.original_error)}</div>
    </div>

    ${
      contextStr
        ? `
    <div class="section">
        <div class="section-title">Context</div>
        <div class="tags">${contextStr}</div>
    </div>
    `
        : ""
    }

    <div class="record-id">Record ID: ${solution.id}</div>
</body>
</html>
`;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/\n/g, "<br>");
}
