/**
 * Vault404 SDK - Basic Usage Example
 *
 * This example demonstrates the core functionality of the Vault404 SDK:
 * - Finding solutions for errors
 * - Logging error fixes
 * - Verifying solutions
 * - Logging decisions and patterns
 *
 * Run with: npx ts-node examples/basic-usage.ts
 */

import {
  Vault404Client,
  ValidationError,
  NetworkError,
  ApiError,
} from "../src/index.js";

async function main() {
  // Initialize the client
  // For local development, use: apiUrl: 'http://localhost:8000'
  const vault404 = new Vault404Client({
    apiUrl: "https://api.vault404.dev",
    debug: true, // Enable debug logging
  });

  console.log("=".repeat(60));
  console.log("Vault404 SDK - Basic Usage Example");
  console.log("=".repeat(60));

  // =========================================================================
  // 1. Find Solutions for an Error
  // =========================================================================
  console.log("\n1. Finding solutions for an error...\n");

  try {
    const solutions = await vault404.findSolution({
      errorMessage: "Cannot find module 'react'",
      language: "typescript",
      framework: "nextjs",
      limit: 5,
    });

    if (solutions.found) {
      console.log(`Found ${solutions.solutions.length} solution(s):\n`);
      for (const solution of solutions.solutions) {
        console.log(`  [${(solution.confidence * 100).toFixed(0)}%] ${solution.solution}`);
        console.log(`      Original error: ${solution.originalError}`);
        console.log(`      Verified: ${solution.verified ? "Yes" : "No"}`);
        console.log(`      Source: ${solution.source}`);
        console.log();
      }
    } else {
      console.log("No solutions found.");
      console.log(`Suggestion: ${solutions.suggestion}`);
    }
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 2. Log an Error Fix
  // =========================================================================
  console.log("\n2. Logging an error fix...\n");

  try {
    const logResult = await vault404.logErrorFix({
      errorMessage: "ECONNREFUSED 127.0.0.1:5432",
      solution: "Start the PostgreSQL service: sudo systemctl start postgresql",
      errorType: "ConnectionError",
      file: "src/db/connection.ts",
      line: 42,
      language: "typescript",
      framework: "express",
      database: "postgresql",
      category: "database",
      timeToSolve: "5m",
      verified: true,
    });

    console.log(`Success: ${logResult.success}`);
    console.log(`Message: ${logResult.message}`);
    console.log(`Record ID: ${logResult.recordId}`);
    if (logResult.secretsRedacted) {
      console.log("Note: Secrets were automatically redacted from the input");
    }
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 3. Verify a Solution
  // =========================================================================
  console.log("\n3. Verifying a solution...\n");

  try {
    // Note: In a real scenario, you would use the record ID from a previous
    // findSolution call. This is just an example.
    const verifyResult = await vault404.verifySolution({
      id: "ef_20240115_143052",
      success: true,
    });

    console.log(`Success: ${verifyResult.success}`);
    console.log(`Message: ${verifyResult.message}`);
    console.log(`Verified as: ${verifyResult.verifiedAs}`);
    if (verifyResult.contributed) {
      console.log("This solution was contributed to the community brain!");
    }
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 4. Log an Architectural Decision
  // =========================================================================
  console.log("\n4. Logging an architectural decision...\n");

  try {
    const decisionResult = await vault404.logDecision({
      title: "State management library",
      choice: "Zustand",
      alternatives: ["Redux", "Context API", "Jotai", "MobX"],
      pros: [
        "Simple API with minimal boilerplate",
        "Small bundle size (~1KB)",
        "No providers needed",
        "Works well with React 18",
      ],
      cons: [
        "Smaller ecosystem than Redux",
        "Less middleware options",
        "Fewer DevTools features",
      ],
      decidingFactor: "Project prioritizes simplicity and bundle size over extensive ecosystem",
      project: "my-webapp",
      component: "frontend",
      language: "typescript",
      framework: "nextjs",
    });

    console.log(`Success: ${decisionResult.success}`);
    console.log(`Message: ${decisionResult.message}`);
    console.log(`Record ID: ${decisionResult.recordId}`);
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 5. Find Past Decisions
  // =========================================================================
  console.log("\n5. Finding past decisions...\n");

  try {
    const decisions = await vault404.findDecision({
      topic: "state management",
      limit: 3,
    });

    if (decisions.found) {
      console.log(`Found ${decisions.decisions.length} decision(s):\n`);
      for (const decision of decisions.decisions) {
        console.log(`  [${(decision.relevance * 100).toFixed(0)}%] ${decision.title}`);
        console.log(`      Choice: ${decision.choice}`);
        console.log(`      Alternatives: ${decision.alternatives.join(", ")}`);
        console.log();
      }
    } else {
      console.log("No past decisions found.");
      console.log(`Suggestion: ${decisions.suggestion}`);
    }
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 6. Log a Reusable Pattern
  // =========================================================================
  console.log("\n6. Logging a reusable pattern...\n");

  try {
    const patternResult = await vault404.logPattern({
      name: "Optimistic UI Updates",
      category: "frontend",
      problem: "Slow UI feedback when waiting for API responses",
      solution: "Update UI state immediately before the API call completes, then reconcile with the actual response",
      languages: ["typescript", "javascript"],
      frameworks: ["react", "nextjs", "vue"],
      scenarios: [
        "Form submissions",
        "Toggle buttons",
        "List item modifications",
        "Like/unlike actions",
      ],
      beforeCode: `
// Slow approach - wait for API
const handleLike = async (postId: string) => {
  await api.likePost(postId);
  const updated = await api.getPost(postId);
  setPost(updated);
};
      `.trim(),
      afterCode: `
// Optimistic approach - update immediately
const handleLike = async (postId: string) => {
  // Update UI immediately
  setPost(prev => ({ ...prev, liked: true, likes: prev.likes + 1 }));

  try {
    await api.likePost(postId);
  } catch (error) {
    // Rollback on failure
    setPost(prev => ({ ...prev, liked: false, likes: prev.likes - 1 }));
    showError('Failed to like post');
  }
};
      `.trim(),
      explanation: "By updating the UI state before the API call, users get immediate feedback. If the API call fails, we rollback the change. This improves perceived performance significantly.",
    });

    console.log(`Success: ${patternResult.success}`);
    console.log(`Message: ${patternResult.message}`);
    console.log(`Record ID: ${patternResult.recordId}`);
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 7. Find Patterns
  // =========================================================================
  console.log("\n7. Finding patterns...\n");

  try {
    const patterns = await vault404.findPattern({
      problem: "slow API response handling",
      category: "frontend",
      language: "typescript",
      limit: 3,
    });

    if (patterns.found) {
      console.log(`Found ${patterns.patterns.length} pattern(s):\n`);
      for (const pattern of patterns.patterns) {
        console.log(`  [${(pattern.relevance * 100).toFixed(0)}%] ${pattern.name}`);
        console.log(`      Category: ${pattern.category}`);
        console.log(`      Problem: ${pattern.problem}`);
        console.log(`      Solution: ${pattern.solution.substring(0, 100)}...`);
        console.log();
      }
    } else {
      console.log("No patterns found.");
      console.log(`Suggestion: ${patterns.suggestion}`);
    }
  } catch (error) {
    handleError(error);
  }

  // =========================================================================
  // 8. Get Knowledge Base Stats
  // =========================================================================
  console.log("\n8. Getting knowledge base stats...\n");

  try {
    const stats = await vault404.getStats();

    console.log("Vault404 Knowledge Base Statistics:");
    console.log(`  Total Records: ${stats.stats.totalRecords}`);
    console.log(`  Error Fixes: ${stats.stats.errorFixes}`);
    console.log(`  Decisions: ${stats.stats.decisions}`);
    console.log(`  Patterns: ${stats.stats.patterns}`);
  } catch (error) {
    handleError(error);
  }

  console.log("\n" + "=".repeat(60));
  console.log("Example completed!");
  console.log("=".repeat(60));
}

/**
 * Handle errors with specific error type detection
 */
function handleError(error: unknown): void {
  if (error instanceof ValidationError) {
    console.log(`Validation Error: ${error.message}`);
    console.log(`  Field: ${error.field}`);
  } else if (error instanceof NetworkError) {
    console.log(`Network Error: ${error.message}`);
    console.log(`  URL: ${error.url}`);
  } else if (error instanceof ApiError) {
    console.log(`API Error: ${error.message}`);
    console.log(`  Status: ${error.statusCode}`);
    if (error.isRetryable()) {
      console.log("  This error may be resolved by retrying");
    }
  } else if (error instanceof Error) {
    console.log(`Error: ${error.message}`);
  } else {
    console.log("Unknown error:", error);
  }
}

// Run the example
main().catch(console.error);
