/**
 * Vault404 SDK - LangChain Integration Example
 *
 * This example demonstrates how to integrate Vault404 with LangChain
 * to enhance AI agent error handling and knowledge sharing.
 *
 * Prerequisites:
 * - npm install langchain @langchain/openai
 *
 * Run with: npx ts-node examples/with-langchain.ts
 */

import { Vault404Client, Solution } from "../src/index.js";

// Note: In a real application, you would import from langchain
// import { ChatOpenAI } from "@langchain/openai";
// import { DynamicTool } from "@langchain/core/tools";
// import { AgentExecutor, createOpenAIFunctionsAgent } from "langchain/agents";
// import { ChatPromptTemplate } from "@langchain/core/prompts";

/**
 * Example of creating a LangChain tool for finding solutions
 *
 * This tool allows an AI agent to search the Vault404 knowledge base
 * for solutions to errors it encounters.
 */
function createFindSolutionTool(vault404: Vault404Client) {
  // In a real implementation, you would return a DynamicTool:
  // return new DynamicTool({
  //   name: "vault404_find_solution",
  //   description: "Search the Vault404 knowledge base for solutions to an error. Input should be the error message.",
  //   func: async (errorMessage: string) => { ... }
  // });

  return {
    name: "vault404_find_solution",
    description:
      "Search the Vault404 knowledge base for solutions to an error. Input should be the error message.",
    func: async (input: string): Promise<string> => {
      const result = await vault404.findSolution({
        errorMessage: input,
        limit: 3,
      });

      if (!result.found) {
        return "No solutions found in the knowledge base. Please try a different approach.";
      }

      const solutionText = result.solutions
        .map(
          (s: Solution, i: number) =>
            `${i + 1}. [${(s.confidence * 100).toFixed(0)}% match] ${s.solution}${s.verified ? " (verified)" : ""}`
        )
        .join("\n");

      return `Found ${result.solutions.length} potential solution(s):\n${solutionText}`;
    },
  };
}

/**
 * Example of creating a LangChain tool for logging error fixes
 *
 * This tool allows an AI agent to contribute its discoveries
 * back to the Vault404 knowledge base.
 */
function createLogErrorFixTool(vault404: Vault404Client) {
  return {
    name: "vault404_log_error_fix",
    description:
      "Log a successful error fix to the Vault404 knowledge base. Input should be JSON with errorMessage and solution fields.",
    func: async (input: string): Promise<string> => {
      try {
        const { errorMessage, solution, language, framework } = JSON.parse(input);

        if (!errorMessage || !solution) {
          return "Error: Both errorMessage and solution are required.";
        }

        const result = await vault404.logErrorFix({
          errorMessage,
          solution,
          language,
          framework,
          verified: true,
        });

        if (result.success) {
          return `Successfully logged error fix with ID: ${result.recordId}. This solution will help other AI agents!`;
        } else {
          return `Failed to log error fix: ${result.message}`;
        }
      } catch (error) {
        return `Error parsing input: ${error instanceof Error ? error.message : "Unknown error"}`;
      }
    },
  };
}

/**
 * Example of creating a LangChain tool for finding patterns
 */
function createFindPatternTool(vault404: Vault404Client) {
  return {
    name: "vault404_find_pattern",
    description:
      "Search the Vault404 knowledge base for reusable patterns. Input should be a description of the problem you're trying to solve.",
    func: async (input: string): Promise<string> => {
      const result = await vault404.findPattern({
        problem: input,
        limit: 3,
      });

      if (!result.found) {
        return "No patterns found. Consider implementing a custom solution.";
      }

      const patternText = result.patterns
        .map(
          (p, i) =>
            `${i + 1}. ${p.name} (${p.category})\n   Problem: ${p.problem}\n   Solution: ${p.solution}`
        )
        .join("\n\n");

      return `Found ${result.patterns.length} relevant pattern(s):\n\n${patternText}`;
    },
  };
}

/**
 * Example agent that uses Vault404 for enhanced error handling
 */
class Vault404EnhancedAgent {
  private vault404: Vault404Client;
  private tools: Array<{
    name: string;
    description: string;
    func: (input: string) => Promise<string>;
  }>;

  constructor(apiUrl?: string) {
    this.vault404 = new Vault404Client({
      apiUrl: apiUrl ?? "https://api.vault404.dev",
      debug: false,
    });

    this.tools = [
      createFindSolutionTool(this.vault404),
      createLogErrorFixTool(this.vault404),
      createFindPatternTool(this.vault404),
    ];
  }

  /**
   * Handle an error by first checking Vault404, then trying to solve it
   */
  async handleError(errorMessage: string, context?: { language?: string; framework?: string }): Promise<{
    solved: boolean;
    solution?: string;
    source?: "vault404" | "generated";
    contributedBack?: boolean;
  }> {
    console.log(`\nHandling error: "${errorMessage}"`);

    // Step 1: Check Vault404 for existing solutions
    console.log("Checking Vault404 knowledge base...");
    const existingSolutions = await this.vault404.findSolution({
      errorMessage,
      language: context?.language,
      framework: context?.framework,
      limit: 3,
    });

    if (existingSolutions.found && existingSolutions.solutions.length > 0) {
      const bestSolution = existingSolutions.solutions[0];

      // Only use solutions with confidence > 70%
      if (bestSolution && bestSolution.confidence > 0.7) {
        console.log(`Found existing solution with ${(bestSolution.confidence * 100).toFixed(0)}% confidence`);

        // Verify the solution worked
        const verifyResult = await this.vault404.verifySolution({
          id: bestSolution.id,
          success: true,
        });

        return {
          solved: true,
          solution: bestSolution.solution,
          source: "vault404",
          contributedBack: verifyResult.contributed,
        };
      }
    }

    // Step 2: Generate a new solution (simulated)
    console.log("No matching solution found, generating new solution...");
    const generatedSolution = await this.generateSolution(errorMessage, context);

    if (generatedSolution) {
      // Step 3: Log the new solution to Vault404
      console.log("Logging new solution to Vault404...");
      const logResult = await this.vault404.logErrorFix({
        errorMessage,
        solution: generatedSolution,
        language: context?.language,
        framework: context?.framework,
        verified: true,
      });

      return {
        solved: true,
        solution: generatedSolution,
        source: "generated",
        contributedBack: logResult.success,
      };
    }

    return { solved: false };
  }

  /**
   * Simulated solution generation (in reality, this would use an LLM)
   */
  private async generateSolution(
    errorMessage: string,
    _context?: { language?: string; framework?: string }
  ): Promise<string | null> {
    // This is a placeholder. In a real implementation, you would:
    // 1. Use an LLM to analyze the error
    // 2. Generate a solution based on the error context
    // 3. Optionally test the solution

    if (errorMessage.includes("module") && errorMessage.includes("not found")) {
      return "Run npm install to install missing dependencies, then restart the development server.";
    }

    if (errorMessage.includes("ECONNREFUSED")) {
      return "Check that the required service is running. For database connections, ensure the database server is started.";
    }

    // Could not generate a solution
    return null;
  }

  /**
   * Get all available tools for LangChain integration
   */
  getTools() {
    return this.tools;
  }
}

/**
 * Demonstrate the enhanced agent in action
 */
async function main() {
  console.log("=".repeat(60));
  console.log("Vault404 SDK - LangChain Integration Example");
  console.log("=".repeat(60));

  const agent = new Vault404EnhancedAgent();

  // Example 1: Handle a common error
  console.log("\n--- Example 1: Module Not Found Error ---");
  const result1 = await agent.handleError(
    "Cannot find module 'lodash' or its corresponding type declarations",
    { language: "typescript", framework: "nextjs" }
  );

  console.log("\nResult:", result1);

  // Example 2: Handle a database error
  console.log("\n--- Example 2: Database Connection Error ---");
  const result2 = await agent.handleError("ECONNREFUSED 127.0.0.1:5432", {
    language: "typescript",
    framework: "express",
  });

  console.log("\nResult:", result2);

  // Example 3: Show available tools
  console.log("\n--- Available LangChain Tools ---");
  const tools = agent.getTools();
  for (const tool of tools) {
    console.log(`\n${tool.name}:`);
    console.log(`  ${tool.description}`);
  }

  // Example 4: Direct tool usage
  console.log("\n--- Direct Tool Usage ---");
  const findSolutionTool = tools.find((t) => t.name === "vault404_find_solution");
  if (findSolutionTool) {
    const toolResult = await findSolutionTool.func("React useState is not defined");
    console.log("\nTool result:", toolResult);
  }

  console.log("\n" + "=".repeat(60));
  console.log("Example completed!");
  console.log("=".repeat(60));

  // LangChain Integration Notes
  console.log(`
=================================================================
LangChain Integration Notes
=================================================================

To use these tools with a real LangChain agent, install the
required packages:

  npm install langchain @langchain/openai

Then create an agent like this:

  import { ChatOpenAI } from "@langchain/openai";
  import { DynamicTool } from "@langchain/core/tools";
  import { AgentExecutor, createOpenAIFunctionsAgent } from "langchain/agents";

  const model = new ChatOpenAI({ modelName: "gpt-4" });

  const tools = [
    new DynamicTool({
      name: "vault404_find_solution",
      description: "...",
      func: async (input) => { ... }
    }),
    // ... more tools
  ];

  const agent = await createOpenAIFunctionsAgent({ model, tools, prompt });
  const executor = new AgentExecutor({ agent, tools });

  const result = await executor.invoke({
    input: "Fix this error: Cannot find module 'react'"
  });

The Vault404 tools enable your LangChain agents to:
- Learn from past solutions
- Share discoveries with other agents
- Build a collective knowledge base
- Improve over time
=================================================================
`);
}

// Run the example
main().catch(console.error);
