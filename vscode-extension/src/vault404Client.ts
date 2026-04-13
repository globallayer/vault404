/**
 * Vault404 Client - Communicates with vault404 CLI
 *
 * Provides methods to interact with the Vault404 knowledge base
 * by spawning the vault404 CLI or MCP server.
 */

import { spawn, ChildProcess } from "child_process";
import * as vscode from "vscode";

export interface Vault404Stats {
  error_fixes: number;
  decisions: number;
  patterns: number;
  total_records: number;
  data_directory: string;
}

export interface Solution {
  id: string;
  solution: string;
  original_error: string;
  context: Record<string, string>;
  confidence: number;
  verified: boolean;
  source: "local" | "community";
}

export interface FindSolutionResult {
  found: boolean;
  message: string;
  solutions: Solution[];
  suggestion?: string;
}

export interface LogResult {
  success: boolean;
  record_id: string;
  message: string;
  secrets_redacted?: boolean;
}

export interface VerifyResult {
  success: boolean;
  message: string;
  record_id: string;
  verified_as: string;
  contributed?: boolean;
  contribution_note?: string;
}

export interface Context {
  project?: string;
  language?: string;
  framework?: string;
  database?: string;
  platform?: string;
  category?: string;
}

/**
 * Client for interacting with Vault404 CLI
 */
export class Vault404Client {
  private pythonPath: string;
  private outputChannel: vscode.OutputChannel;

  constructor(outputChannel: vscode.OutputChannel) {
    this.outputChannel = outputChannel;
    this.pythonPath = this.getPythonPath();
  }

  private getPythonPath(): string {
    const config = vscode.workspace.getConfiguration("vault404");
    return config.get("pythonPath", "python");
  }

  /**
   * Execute a vault404 CLI command and return parsed JSON
   */
  private async executeCommand(
    args: string[],
    input?: string
  ): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const pythonPath = this.getPythonPath();
      const fullArgs = ["-m", "vault404", "--json", ...args];

      this.outputChannel.appendLine(
        `[Vault404] Running: ${pythonPath} ${fullArgs.join(" ")}`
      );

      const proc = spawn(pythonPath, fullArgs, {
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
        },
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data: Buffer) => {
        stdout += data.toString();
      });

      proc.stderr.on("data", (data: Buffer) => {
        stderr += data.toString();
      });

      if (input) {
        proc.stdin.write(input);
        proc.stdin.end();
      }

      proc.on("close", (code: number | null) => {
        this.outputChannel.appendLine(`[Vault404] Exit code: ${code}`);
        if (stderr) {
          this.outputChannel.appendLine(`[Vault404] Stderr: ${stderr}`);
        }

        if (code === 0 || stdout.trim()) {
          try {
            // Try to parse JSON from stdout
            const jsonMatch = stdout.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
              resolve(JSON.parse(jsonMatch[0]));
            } else {
              resolve({ raw: stdout });
            }
          } catch {
            this.outputChannel.appendLine(
              `[Vault404] JSON parse error: ${stdout}`
            );
            resolve({ raw: stdout, error: "Failed to parse JSON" });
          }
        } else {
          reject(new Error(`Command failed: ${stderr || "Unknown error"}`));
        }
      });

      proc.on("error", (err: Error) => {
        this.outputChannel.appendLine(`[Vault404] Process error: ${err.message}`);
        reject(err);
      });
    });
  }

  /**
   * Execute a vault404 MCP tool call via stdin/stdout
   */
  private async executeMcpTool(
    toolName: string,
    args: Record<string, unknown>
  ): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const pythonPath = this.getPythonPath();
      const mcpArgs = ["-m", "vault404.mcp_server"];

      this.outputChannel.appendLine(
        `[Vault404 MCP] Calling tool: ${toolName} with args: ${JSON.stringify(args)}`
      );

      const proc = spawn(pythonPath, mcpArgs, {
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
        },
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data: Buffer) => {
        stdout += data.toString();
      });

      proc.stderr.on("data", (data: Buffer) => {
        stderr += data.toString();
      });

      // Send MCP initialize and tool call
      const initMessage = {
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "vscode-vault404", version: "0.1.0" },
        },
      };

      const toolMessage = {
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: {
          name: toolName,
          arguments: args,
        },
      };

      // MCP uses newline-delimited JSON
      proc.stdin.write(JSON.stringify(initMessage) + "\n");

      // Give server time to initialize
      setTimeout(() => {
        proc.stdin.write(JSON.stringify(toolMessage) + "\n");

        // Close stdin after sending
        setTimeout(() => {
          proc.stdin.end();
        }, 100);
      }, 200);

      // Set timeout
      const timeout = setTimeout(() => {
        proc.kill();
        reject(new Error("MCP call timed out"));
      }, 10000);

      proc.on("close", () => {
        clearTimeout(timeout);
        this.outputChannel.appendLine(`[Vault404 MCP] Response: ${stdout}`);

        try {
          // Parse the last JSON response
          const lines = stdout.trim().split("\n");
          for (let i = lines.length - 1; i >= 0; i--) {
            try {
              const response = JSON.parse(lines[i]);
              if (response.result) {
                // Extract text content from MCP response
                const content = response.result.content;
                if (Array.isArray(content) && content[0]?.text) {
                  try {
                    resolve(JSON.parse(content[0].text));
                  } catch {
                    resolve({ raw: content[0].text });
                  }
                  return;
                }
                resolve(response.result);
                return;
              }
            } catch {
              continue;
            }
          }
          resolve({ raw: stdout });
        } catch {
          resolve({ raw: stdout });
        }
      });

      proc.on("error", (err: Error) => {
        clearTimeout(timeout);
        reject(err);
      });
    });
  }

  /**
   * Get knowledge base statistics
   */
  async getStats(): Promise<Vault404Stats> {
    try {
      const result = (await this.executeCommand(["stats"])) as {
        stats?: Vault404Stats;
      };
      return (
        result.stats || {
          error_fixes: 0,
          decisions: 0,
          patterns: 0,
          total_records: 0,
          data_directory: "",
        }
      );
    } catch (error) {
      this.outputChannel.appendLine(`[Vault404] Stats error: ${error}`);
      return {
        error_fixes: 0,
        decisions: 0,
        patterns: 0,
        total_records: 0,
        data_directory: "",
      };
    }
  }

  /**
   * Find solutions for an error
   */
  async findSolution(
    errorMessage: string,
    context?: Context
  ): Promise<FindSolutionResult> {
    try {
      const args = ["search", "--type", "solution", errorMessage];
      if (context?.language) {
        args.push("--language", context.language);
      }

      const result = (await this.executeCommand(args)) as {
        solutions?: FindSolutionResult;
      };

      // The search command returns a different structure
      if (result.solutions) {
        return result.solutions;
      }

      // Try MCP fallback for more detailed results
      return (await this.executeMcpTool("find_solution", {
        error_message: errorMessage,
        ...context,
      })) as FindSolutionResult;
    } catch (error) {
      this.outputChannel.appendLine(`[Vault404] Find solution error: ${error}`);
      return {
        found: false,
        message: `Error querying Vault404: ${error}`,
        solutions: [],
      };
    }
  }

  /**
   * Log an error and its solution
   */
  async logErrorFix(
    errorMessage: string,
    solution: string,
    context?: Context & {
      errorType?: string;
      stackTrace?: string;
      file?: string;
      line?: number;
      codeChange?: string;
      filesModified?: string[];
    }
  ): Promise<LogResult> {
    try {
      const args: Record<string, unknown> = {
        error_message: errorMessage,
        solution: solution,
      };

      if (context?.errorType) args.error_type = context.errorType;
      if (context?.stackTrace) args.stack_trace = context.stackTrace;
      if (context?.file) args.file = context.file;
      if (context?.line) args.line = context.line;
      if (context?.codeChange) args.code_change = context.codeChange;
      if (context?.filesModified) args.files_modified = context.filesModified;
      if (context?.project) args.project = context.project;
      if (context?.language) args.language = context.language;
      if (context?.framework) args.framework = context.framework;
      if (context?.database) args.database = context.database;
      if (context?.platform) args.platform = context.platform;
      if (context?.category) args.category = context.category;

      return (await this.executeMcpTool("log_error_fix", args)) as LogResult;
    } catch (error) {
      this.outputChannel.appendLine(`[Vault404] Log error fix error: ${error}`);
      return {
        success: false,
        record_id: "",
        message: `Failed to log error fix: ${error}`,
      };
    }
  }

  /**
   * Log an architectural decision
   */
  async logDecision(
    title: string,
    choice: string,
    options?: {
      alternatives?: string[];
      pros?: string[];
      cons?: string[];
      decidingFactor?: string;
      project?: string;
      component?: string;
      language?: string;
      framework?: string;
    }
  ): Promise<LogResult> {
    try {
      const args: Record<string, unknown> = {
        title,
        choice,
      };

      if (options?.alternatives) args.alternatives = options.alternatives;
      if (options?.pros) args.pros = options.pros;
      if (options?.cons) args.cons = options.cons;
      if (options?.decidingFactor) args.deciding_factor = options.decidingFactor;
      if (options?.project) args.project = options.project;
      if (options?.component) args.component = options.component;
      if (options?.language) args.language = options.language;
      if (options?.framework) args.framework = options.framework;

      return (await this.executeMcpTool("log_decision", args)) as LogResult;
    } catch (error) {
      this.outputChannel.appendLine(`[Vault404] Log decision error: ${error}`);
      return {
        success: false,
        record_id: "",
        message: `Failed to log decision: ${error}`,
      };
    }
  }

  /**
   * Log a reusable pattern
   */
  async logPattern(
    name: string,
    category: string,
    problem: string,
    solution: string,
    options?: {
      languages?: string[];
      frameworks?: string[];
      databases?: string[];
      scenarios?: string[];
      beforeCode?: string;
      afterCode?: string;
      explanation?: string;
    }
  ): Promise<LogResult> {
    try {
      const args: Record<string, unknown> = {
        name,
        category,
        problem,
        solution,
      };

      if (options?.languages) args.languages = options.languages;
      if (options?.frameworks) args.frameworks = options.frameworks;
      if (options?.databases) args.databases = options.databases;
      if (options?.scenarios) args.scenarios = options.scenarios;
      if (options?.beforeCode) args.before_code = options.beforeCode;
      if (options?.afterCode) args.after_code = options.afterCode;
      if (options?.explanation) args.explanation = options.explanation;

      return (await this.executeMcpTool("log_pattern", args)) as LogResult;
    } catch (error) {
      this.outputChannel.appendLine(`[Vault404] Log pattern error: ${error}`);
      return {
        success: false,
        record_id: "",
        message: `Failed to log pattern: ${error}`,
      };
    }
  }

  /**
   * Verify that a solution worked (or didn't)
   */
  async verifySolution(recordId: string, success: boolean): Promise<VerifyResult> {
    try {
      return (await this.executeMcpTool("verify_solution", {
        record_id: recordId,
        success,
      })) as VerifyResult;
    } catch (error) {
      this.outputChannel.appendLine(`[Vault404] Verify solution error: ${error}`);
      return {
        success: false,
        message: `Failed to verify solution: ${error}`,
        record_id: recordId,
        verified_as: success ? "successful" : "unsuccessful",
      };
    }
  }

  /**
   * Detect language from file extension or VS Code language ID
   */
  detectLanguage(document?: vscode.TextDocument): string | undefined {
    if (!document) {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return undefined;
      document = editor.document;
    }

    const langMap: Record<string, string> = {
      typescript: "typescript",
      typescriptreact: "typescript",
      javascript: "javascript",
      javascriptreact: "javascript",
      python: "python",
      go: "go",
      rust: "rust",
      java: "java",
      csharp: "csharp",
      cpp: "cpp",
      c: "c",
      php: "php",
      ruby: "ruby",
      swift: "swift",
      kotlin: "kotlin",
    };

    return langMap[document.languageId] || document.languageId;
  }

  /**
   * Detect framework from project files
   */
  async detectFramework(): Promise<string | undefined> {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) return undefined;

    const root = workspaceFolders[0].uri;

    // Check for common framework indicators
    const checks: Array<{ file: string; framework: string }> = [
      { file: "next.config.js", framework: "nextjs" },
      { file: "next.config.mjs", framework: "nextjs" },
      { file: "next.config.ts", framework: "nextjs" },
      { file: "nuxt.config.js", framework: "nuxt" },
      { file: "nuxt.config.ts", framework: "nuxt" },
      { file: "angular.json", framework: "angular" },
      { file: "vue.config.js", framework: "vue" },
      { file: "svelte.config.js", framework: "svelte" },
      { file: "remix.config.js", framework: "remix" },
      { file: "astro.config.mjs", framework: "astro" },
      { file: "vite.config.ts", framework: "vite" },
      { file: "vite.config.js", framework: "vite" },
      { file: "requirements.txt", framework: "python" },
      { file: "pyproject.toml", framework: "python" },
      { file: "Cargo.toml", framework: "rust" },
      { file: "go.mod", framework: "go" },
    ];

    for (const check of checks) {
      try {
        await vscode.workspace.fs.stat(vscode.Uri.joinPath(root, check.file));
        return check.framework;
      } catch {
        // File doesn't exist, continue
      }
    }

    return undefined;
  }
}
