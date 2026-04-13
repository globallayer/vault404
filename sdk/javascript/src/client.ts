/**
 * Vault404 TypeScript SDK - Client
 *
 * Main client class for interacting with the Vault404 API.
 * Provides methods for logging and querying error fixes, decisions, and patterns.
 *
 * @module vault404/client
 */

import {
  Vault404ClientOptions,
  LogErrorFixOptions,
  LogDecisionOptions,
  LogPatternOptions,
  FindSolutionOptions,
  FindDecisionOptions,
  FindPatternOptions,
  VerifySolutionOptions,
  LogResult,
  FindSolutionResult,
  FindDecisionResult,
  FindPatternResult,
  VerifySolutionResult,
  StatsResult,
  Solution,
  Decision,
  Pattern,
  ApiFindSolutionResponse,
  ApiFindDecisionResponse,
  ApiFindPatternResponse,
  ApiVerifySolutionResponse,
  ApiStatsResponse,
} from "./types.js";

import {
  Vault404Error,
  NetworkError,
  ApiError,
  TimeoutError,
  ValidationError,
  AuthenticationError,
  RateLimitError,
  NotFoundError,
} from "./errors.js";

/**
 * Default configuration values
 */
const DEFAULT_API_URL = "https://web-production-7e0e3.up.railway.app";
const DEFAULT_TIMEOUT = 30000;
const API_VERSION = "v1";

/**
 * Vault404Client - Main client for interacting with the Vault404 API
 *
 * The Vault404 client provides methods to:
 * - Find solutions to errors from the collective knowledge base
 * - Log error fixes to help other AI agents
 * - Record architectural decisions for future reference
 * - Store and retrieve reusable patterns
 * - Verify solutions and contribute to the community brain
 *
 * @example
 * ```typescript
 * import { Vault404Client } from 'vault404';
 *
 * const vault404 = new Vault404Client({
 *   apiUrl: 'https://api.vault404.dev',
 *   timeout: 30000
 * });
 *
 * // Find solutions for an error
 * const result = await vault404.findSolution({
 *   errorMessage: 'Cannot find module react',
 *   language: 'typescript',
 *   framework: 'nextjs'
 * });
 *
 * if (result.found) {
 *   console.log('Solutions:', result.solutions);
 * }
 * ```
 */
export class Vault404Client {
  private readonly apiUrl: string;
  private readonly apiKey?: string;
  private readonly timeout: number;
  private readonly headers: Record<string, string>;
  private readonly debug: boolean;

  /**
   * Creates a new Vault404Client instance
   *
   * @param options - Configuration options for the client
   *
   * @example
   * ```typescript
   * // With default settings (production API)
   * const vault404 = new Vault404Client();
   *
   * // With custom API URL (local development)
   * const vault404 = new Vault404Client({
   *   apiUrl: 'http://localhost:8000'
   * });
   *
   * // With API key and custom timeout
   * const vault404 = new Vault404Client({
   *   apiKey: 'your-api-key',
   *   timeout: 60000
   * });
   * ```
   */
  constructor(options: Vault404ClientOptions = {}) {
    this.apiUrl = this.normalizeUrl(options.apiUrl ?? DEFAULT_API_URL);
    this.apiKey = options.apiKey;
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
    this.debug = options.debug ?? false;

    this.headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
      "User-Agent": "vault404-sdk/0.1.0",
      ...options.headers,
    };

    if (this.apiKey) {
      this.headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
  }

  /**
   * Normalize URL by removing trailing slash
   */
  private normalizeUrl(url: string): string {
    return url.replace(/\/+$/, "");
  }

  /**
   * Log debug messages if debug mode is enabled
   */
  private log(message: string, data?: unknown): void {
    if (this.debug) {
      console.log(`[Vault404] ${message}`, data ?? "");
    }
  }

  /**
   * Make an HTTP request to the Vault404 API
   */
  private async request<T>(
    method: "GET" | "POST" | "PUT" | "DELETE",
    endpoint: string,
    body?: Record<string, unknown>
  ): Promise<T> {
    const url = `${this.apiUrl}/api/${API_VERSION}${endpoint}`;

    this.log(`${method} ${url}`, body);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method,
        headers: this.headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Parse response body
      let responseBody: unknown;
      const contentType = response.headers.get("content-type");

      if (contentType?.includes("application/json")) {
        responseBody = await response.json();
      } else {
        responseBody = await response.text();
      }

      this.log(`Response ${response.status}`, responseBody);

      // Handle error responses
      if (!response.ok) {
        this.handleErrorResponse(response.status, responseBody, url, method);
      }

      return responseBody as T;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof Vault404Error) {
        throw error;
      }

      if (error instanceof Error) {
        if (error.name === "AbortError") {
          throw new TimeoutError(
            `Request timed out after ${this.timeout}ms`,
            this.timeout,
            { url }
          );
        }

        throw new NetworkError(`Network request failed: ${error.message}`, {
          cause: error,
          url,
        });
      }

      throw new Vault404Error("An unexpected error occurred", {
        context: { error },
      });
    }
  }

  /**
   * Handle error responses from the API
   */
  private handleErrorResponse(
    status: number,
    body: unknown,
    url: string,
    method: string
  ): never {
    const message =
      typeof body === "object" &&
      body !== null &&
      "message" in body &&
      typeof (body as { message: unknown }).message === "string"
        ? (body as { message: string }).message
        : `HTTP ${status} error`;

    switch (status) {
      case 400:
        throw new ValidationError(message, { context: { body } });
      case 401:
        throw new AuthenticationError(message);
      case 404:
        throw new NotFoundError(message);
      case 429: {
        const retryAfter =
          typeof body === "object" &&
          body !== null &&
          "retry_after" in body &&
          typeof (body as { retry_after: unknown }).retry_after === "number"
            ? (body as { retry_after: number }).retry_after
            : undefined;
        throw new RateLimitError(message, { retryAfter });
      }
      default:
        throw new ApiError(message, status, { body, url, method });
    }
  }

  // ===========================================================================
  // Error Fix Methods
  // ===========================================================================

  /**
   * Find solutions for an error from the Vault404 knowledge base.
   *
   * This should be the first thing you check when encountering an error.
   * Solutions are ranked by relevance based on error similarity and context match.
   *
   * @param options - Search options including the error message and optional context
   * @returns Promise resolving to search results with matching solutions
   *
   * @example
   * ```typescript
   * // Basic search
   * const result = await vault404.findSolution({
   *   errorMessage: 'Cannot find module react'
   * });
   *
   * // With context for better matching
   * const result = await vault404.findSolution({
   *   errorMessage: 'Connection refused',
   *   language: 'typescript',
   *   framework: 'nextjs',
   *   database: 'postgresql',
   *   platform: 'railway',
   *   limit: 5
   * });
   *
   * if (result.found) {
   *   for (const solution of result.solutions) {
   *     console.log(`[${solution.confidence}] ${solution.solution}`);
   *   }
   * }
   * ```
   */
  async findSolution(options: FindSolutionOptions): Promise<FindSolutionResult> {
    this.validateRequired(options.errorMessage, "errorMessage");

    const response = await this.request<ApiFindSolutionResponse>(
      "POST",
      "/solutions/search",
      {
        error_message: options.errorMessage,
        project: options.project,
        language: options.language,
        framework: options.framework,
        database: options.database,
        platform: options.platform,
        category: options.category,
        limit: options.limit ?? 5,
      }
    );

    return {
      found: response.found,
      message: response.message,
      solutions: response.solutions.map(
        (s): Solution => ({
          id: s.id,
          solution: s.solution,
          originalError: s.original_error,
          context: {
            project: s.context.project,
            language: s.context.language,
            framework: s.context.framework,
            database: s.context.database,
            platform: s.context.platform,
            category: s.context.category,
          },
          confidence: s.confidence,
          verified: s.verified,
          source: s.source,
        })
      ),
      suggestion: response.suggestion,
    };
  }

  /**
   * Log an error and its solution to the Vault404 knowledge base.
   *
   * Use this after fixing any error to help other AI agents. All inputs are
   * automatically scanned for secrets (API keys, passwords, tokens) and
   * redacted before storage.
   *
   * @param options - The error details and solution
   * @returns Promise resolving to the result of logging
   *
   * @example
   * ```typescript
   * // Basic logging
   * const result = await vault404.logErrorFix({
   *   errorMessage: 'Module not found: react',
   *   solution: 'Run npm install react to install the missing dependency'
   * });
   *
   * // With full context
   * const result = await vault404.logErrorFix({
   *   errorMessage: 'ECONNREFUSED 127.0.0.1:5432',
   *   solution: 'Start PostgreSQL service: sudo systemctl start postgresql',
   *   errorType: 'ConnectionError',
   *   file: 'src/db/connection.ts',
   *   line: 42,
   *   language: 'typescript',
   *   framework: 'nextjs',
   *   database: 'postgresql',
   *   category: 'database',
   *   verified: true
   * });
   *
   * console.log('Logged with ID:', result.recordId);
   * ```
   */
  async logErrorFix(options: LogErrorFixOptions): Promise<LogResult> {
    this.validateRequired(options.errorMessage, "errorMessage");
    this.validateRequired(options.solution, "solution");

    const response = await this.request<{
      success: boolean;
      record_id?: string;
      message: string;
      secrets_redacted?: boolean;
    }>("POST", "/solutions", {
      error_message: options.errorMessage,
      solution: options.solution,
      error_type: options.errorType,
      stack_trace: options.stackTrace,
      file: options.file,
      line: options.line,
      code_change: options.codeChange,
      files_modified: options.filesModified,
      project: options.project,
      language: options.language,
      framework: options.framework,
      database: options.database,
      platform: options.platform,
      category: options.category,
      time_to_solve: options.timeToSolve,
      verified: options.verified,
    });

    return {
      success: response.success,
      message: response.message,
      recordId: response.record_id,
      secretsRedacted: response.secrets_redacted,
    };
  }

  /**
   * Verify whether a solution worked or not.
   *
   * Call this after trying a suggested solution. If success=true, the
   * anonymized solution is automatically contributed to the community
   * brain, helping all AI agents get smarter.
   *
   * @param options - The solution ID and whether it worked
   * @returns Promise resolving to the verification result
   *
   * @example
   * ```typescript
   * // After trying a solution
   * const result = await vault404.verifySolution({
   *   id: 'ef_20240115_143052',
   *   success: true
   * });
   *
   * if (result.contributed) {
   *   console.log('Solution contributed to community brain!');
   * }
   * ```
   */
  async verifySolution(
    options: VerifySolutionOptions
  ): Promise<VerifySolutionResult> {
    this.validateRequired(options.id, "id");
    this.validateRequired(options.success, "success", "boolean");

    const response = await this.request<ApiVerifySolutionResponse>(
      "POST",
      `/solutions/${options.id}/verify`,
      {
        success: options.success,
      }
    );

    return {
      success: response.success,
      message: response.message,
      recordId: response.record_id,
      verifiedAs: response.verified_as as "successful" | "unsuccessful",
      contributed: response.contributed,
      contributionNote: response.contribution_note,
    };
  }

  // ===========================================================================
  // Decision Methods
  // ===========================================================================

  /**
   * Log an architectural decision to the Vault404 knowledge base.
   *
   * Use this when making significant technical choices. Recording decisions
   * helps remember why choices were made and their outcomes.
   *
   * @param options - The decision details
   * @returns Promise resolving to the result of logging
   *
   * @example
   * ```typescript
   * const result = await vault404.logDecision({
   *   title: 'State management library',
   *   choice: 'Zustand',
   *   alternatives: ['Redux', 'Context API', 'Jotai'],
   *   pros: ['Simple API', 'Small bundle size', 'No boilerplate'],
   *   cons: ['Smaller ecosystem', 'Less middleware'],
   *   decidingFactor: 'Project needs simplicity over complexity',
   *   project: 'my-app',
   *   component: 'frontend',
   *   framework: 'nextjs'
   * });
   * ```
   */
  async logDecision(options: LogDecisionOptions): Promise<LogResult> {
    this.validateRequired(options.title, "title");
    this.validateRequired(options.choice, "choice");

    const response = await this.request<{
      success: boolean;
      record_id?: string;
      message: string;
    }>("POST", "/decisions", {
      title: options.title,
      choice: options.choice,
      alternatives: options.alternatives,
      pros: options.pros,
      cons: options.cons,
      deciding_factor: options.decidingFactor,
      project: options.project,
      component: options.component,
      language: options.language,
      framework: options.framework,
    });

    return {
      success: response.success,
      message: response.message,
      recordId: response.record_id,
    };
  }

  /**
   * Find past decisions on a topic from the Vault404 knowledge base.
   *
   * Check this before making architectural choices to learn from history.
   *
   * @param options - Search options including the topic
   * @returns Promise resolving to search results with matching decisions
   *
   * @example
   * ```typescript
   * const result = await vault404.findDecision({
   *   topic: 'database choice',
   *   project: 'my-app',
   *   limit: 5
   * });
   *
   * if (result.found) {
   *   for (const decision of result.decisions) {
   *     console.log(`${decision.title}: chose ${decision.choice}`);
   *   }
   * }
   * ```
   */
  async findDecision(options: FindDecisionOptions): Promise<FindDecisionResult> {
    this.validateRequired(options.topic, "topic");

    const response = await this.request<ApiFindDecisionResponse>(
      "POST",
      "/decisions/search",
      {
        topic: options.topic,
        project: options.project,
        component: options.component,
        limit: options.limit ?? 3,
      }
    );

    return {
      found: response.found,
      message: response.message,
      decisions: response.decisions.map(
        (d): Decision => ({
          id: d.id,
          title: d.title,
          choice: d.choice,
          alternatives: d.alternatives ?? [],
          relevance: d.relevance,
        })
      ),
      suggestion: response.suggestion,
    };
  }

  // ===========================================================================
  // Pattern Methods
  // ===========================================================================

  /**
   * Log a reusable pattern to the Vault404 knowledge base.
   *
   * Use this to capture patterns that solve recurring problems. Code snippets
   * are automatically scanned for secrets and redacted.
   *
   * @param options - The pattern details
   * @returns Promise resolving to the result of logging
   *
   * @example
   * ```typescript
   * const result = await vault404.logPattern({
   *   name: 'Optimistic UI updates',
   *   category: 'frontend',
   *   problem: 'Slow UI feedback when waiting for API responses',
   *   solution: 'Update UI immediately, then sync with server response',
   *   languages: ['typescript', 'javascript'],
   *   frameworks: ['react', 'nextjs'],
   *   scenarios: ['Form submissions', 'Toggle states', 'List modifications'],
   *   beforeCode: 'await api.update(data); setState(data);',
   *   afterCode: 'setState(data); await api.update(data).catch(rollback);',
   *   explanation: 'By updating state before the API call completes...'
   * });
   * ```
   */
  async logPattern(options: LogPatternOptions): Promise<LogResult> {
    this.validateRequired(options.name, "name");
    this.validateRequired(options.category, "category");
    this.validateRequired(options.problem, "problem");
    this.validateRequired(options.solution, "solution");

    const response = await this.request<{
      success: boolean;
      record_id?: string;
      message: string;
    }>("POST", "/patterns", {
      name: options.name,
      category: options.category,
      problem: options.problem,
      solution: options.solution,
      languages: options.languages,
      frameworks: options.frameworks,
      databases: options.databases,
      scenarios: options.scenarios,
      before_code: options.beforeCode,
      after_code: options.afterCode,
      explanation: options.explanation,
    });

    return {
      success: response.success,
      message: response.message,
      recordId: response.record_id,
    };
  }

  /**
   * Find reusable patterns for a problem from the Vault404 knowledge base.
   *
   * Search for established patterns before implementing solutions.
   *
   * @param options - Search options including the problem description
   * @returns Promise resolving to search results with matching patterns
   *
   * @example
   * ```typescript
   * const result = await vault404.findPattern({
   *   problem: 'database connection pooling',
   *   category: 'database',
   *   language: 'typescript',
   *   framework: 'nodejs'
   * });
   *
   * if (result.found) {
   *   for (const pattern of result.patterns) {
   *     console.log(`${pattern.name}: ${pattern.solution}`);
   *   }
   * }
   * ```
   */
  async findPattern(options: FindPatternOptions): Promise<FindPatternResult> {
    this.validateRequired(options.problem, "problem");

    const response = await this.request<ApiFindPatternResponse>(
      "POST",
      "/patterns/search",
      {
        problem: options.problem,
        category: options.category,
        language: options.language,
        framework: options.framework,
        limit: options.limit ?? 3,
      }
    );

    return {
      found: response.found,
      message: response.message,
      patterns: response.patterns.map(
        (p): Pattern => ({
          id: p.id,
          name: p.name,
          category: p.category,
          problem: p.problem,
          solution: p.solution,
          relevance: p.relevance,
        })
      ),
      suggestion: response.suggestion,
    };
  }

  // ===========================================================================
  // Stats Methods
  // ===========================================================================

  /**
   * Get statistics about the Vault404 knowledge base.
   *
   * @returns Promise resolving to knowledge base statistics
   *
   * @example
   * ```typescript
   * const result = await vault404.getStats();
   *
   * console.log('Total records:', result.stats.totalRecords);
   * console.log('Error fixes:', result.stats.errorFixes);
   * console.log('Decisions:', result.stats.decisions);
   * console.log('Patterns:', result.stats.patterns);
   * ```
   */
  async getStats(): Promise<StatsResult> {
    const response = await this.request<ApiStatsResponse>("GET", "/stats");

    return {
      success: response.success,
      message: response.message,
      stats: {
        totalRecords: response.stats.total_records,
        errorFixes: response.stats.error_fixes,
        decisions: response.stats.decisions,
        patterns: response.stats.patterns,
        dataDirectory: response.stats.data_directory,
      },
    };
  }

  // ===========================================================================
  // Utility Methods
  // ===========================================================================

  /**
   * Validate that a required field is present
   */
  private validateRequired(
    value: unknown,
    fieldName: string,
    expectedType: "string" | "boolean" | "number" = "string"
  ): void {
    if (value === undefined || value === null) {
      throw new ValidationError(`${fieldName} is required`, {
        field: fieldName,
        rule: "required",
      });
    }

    if (expectedType === "string" && typeof value !== "string") {
      throw new ValidationError(`${fieldName} must be a string`, {
        field: fieldName,
        value,
        rule: "type",
      });
    }

    if (
      expectedType === "string" &&
      typeof value === "string" &&
      value.trim() === ""
    ) {
      throw new ValidationError(`${fieldName} cannot be empty`, {
        field: fieldName,
        value,
        rule: "notEmpty",
      });
    }

    if (expectedType === "boolean" && typeof value !== "boolean") {
      throw new ValidationError(`${fieldName} must be a boolean`, {
        field: fieldName,
        value,
        rule: "type",
      });
    }

    if (expectedType === "number" && typeof value !== "number") {
      throw new ValidationError(`${fieldName} must be a number`, {
        field: fieldName,
        value,
        rule: "type",
      });
    }
  }

  /**
   * Check if the API server is reachable
   *
   * @returns Promise resolving to true if the server is reachable
   *
   * @example
   * ```typescript
   * const isHealthy = await vault404.healthCheck();
   * if (!isHealthy) {
   *   console.log('Vault404 API is not reachable');
   * }
   * ```
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.request<{ status: string }>("GET", "/health");
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get the configured API URL
   *
   * @returns The base API URL
   */
  getApiUrl(): string {
    return this.apiUrl;
  }
}
