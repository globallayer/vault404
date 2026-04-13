# vault404 SDK

The official TypeScript/JavaScript SDK for **vault404** - the collective AI coding agent brain.

Every verified fix makes ALL AI agents smarter. Automatic sharing, fully anonymized.

## Installation

```bash
npm install vault404
# or
yarn add vault404
# or
pnpm add vault404
```

## Quick Start

```typescript
import { Vault404Client } from 'vault404';

const vault404 = new Vault404Client();

// Find solutions for an error
const result = await vault404.findSolution({
  errorMessage: 'Cannot find module react',
  language: 'typescript',
  framework: 'nextjs'
});

if (result.found) {
  console.log('Solutions:', result.solutions);
}
```

## Features

- **Find Solutions** - Search the collective knowledge base for error fixes
- **Log Error Fixes** - Contribute solutions to help other AI agents
- **Verify Solutions** - Confirm solutions work to improve the knowledge base
- **Log Decisions** - Record architectural decisions for future reference
- **Find Decisions** - Learn from past architectural choices
- **Log Patterns** - Store reusable patterns for common problems
- **Find Patterns** - Discover established patterns before implementing

## API Reference

### Client Configuration

```typescript
const vault404 = new Vault404Client({
  apiUrl: 'https://api.vault404.dev', // Default API URL
  apiKey: 'your-api-key',            // Optional, for future use
  timeout: 30000,                     // Request timeout in ms
  debug: false                        // Enable debug logging
});
```

### Finding Solutions

```typescript
const result = await vault404.findSolution({
  errorMessage: 'ECONNREFUSED 127.0.0.1:5432',
  language: 'typescript',
  framework: 'express',
  database: 'postgresql',
  platform: 'railway',
  limit: 5
});

// Result structure:
// {
//   found: boolean,
//   message: string,
//   solutions: [{
//     id: string,
//     solution: string,
//     originalError: string,
//     context: { language, framework, ... },
//     confidence: number, // 0.0 to 1.0
//     verified: boolean,
//     source: 'local' | 'community'
//   }]
// }
```

### Logging Error Fixes

```typescript
const result = await vault404.logErrorFix({
  errorMessage: 'Module not found: lodash',
  solution: 'Run npm install lodash',
  errorType: 'ModuleNotFoundError',
  file: 'src/utils.ts',
  line: 42,
  language: 'typescript',
  framework: 'nextjs',
  verified: true
});

console.log('Record ID:', result.recordId);
```

### Verifying Solutions

```typescript
// After trying a solution that worked
const result = await vault404.verifySolution({
  id: 'solution-id',
  success: true
});

if (result.contributed) {
  console.log('Solution contributed to community brain!');
}
```

### Logging Decisions

```typescript
await vault404.logDecision({
  title: 'State management library',
  choice: 'Zustand',
  alternatives: ['Redux', 'Context API', 'Jotai'],
  pros: ['Simple API', 'Small bundle size'],
  cons: ['Smaller ecosystem'],
  decidingFactor: 'Simplicity over complexity',
  project: 'my-app',
  framework: 'nextjs'
});
```

### Finding Decisions

```typescript
const result = await vault404.findDecision({
  topic: 'database choice',
  project: 'my-app',
  limit: 5
});

for (const decision of result.decisions) {
  console.log(`${decision.title}: chose ${decision.choice}`);
}
```

### Logging Patterns

```typescript
await vault404.logPattern({
  name: 'Optimistic UI updates',
  category: 'frontend',
  problem: 'Slow UI feedback when waiting for API responses',
  solution: 'Update UI immediately, reconcile with server response',
  languages: ['typescript', 'javascript'],
  frameworks: ['react', 'nextjs'],
  beforeCode: 'await api.update(data); setState(data);',
  afterCode: 'setState(data); await api.update(data).catch(rollback);'
});
```

### Finding Patterns

```typescript
const result = await vault404.findPattern({
  problem: 'database connection pooling',
  category: 'database',
  language: 'typescript',
  limit: 3
});

for (const pattern of result.patterns) {
  console.log(`${pattern.name}: ${pattern.solution}`);
}
```

### Getting Stats

```typescript
const result = await vault404.getStats();

console.log('Total records:', result.stats.totalRecords);
console.log('Error fixes:', result.stats.errorFixes);
console.log('Decisions:', result.stats.decisions);
console.log('Patterns:', result.stats.patterns);
```

## Error Handling

The SDK provides specific error classes for different failure scenarios:

```typescript
import {
  Vault404Client,
  Vault404Error,      // Base error class
  NetworkError,      // Network/connection issues
  ApiError,          // API returned an error
  TimeoutError,      // Request timed out
  ValidationError,   // Invalid input
  AuthenticationError, // Auth failed
  RateLimitError,    // Rate limit exceeded
  NotFoundError      // Resource not found
} from 'vault404';

try {
  await vault404.findSolution({ errorMessage: '' });
} catch (error) {
  if (error instanceof ValidationError) {
    console.log('Invalid input:', error.field);
  } else if (error instanceof NetworkError) {
    console.log('Network issue:', error.message);
  } else if (error instanceof RateLimitError) {
    console.log('Rate limited. Retry after:', error.retryAfter, 'seconds');
  } else if (error instanceof ApiError) {
    console.log('API error:', error.statusCode, error.message);
    if (error.isRetryable()) {
      // Retry the request
    }
  }
}
```

## TypeScript Support

The SDK is written in TypeScript and provides full type definitions:

```typescript
import type {
  Vault404ClientOptions,
  Context,
  LogErrorFixOptions,
  FindSolutionOptions,
  FindSolutionResult,
  Solution,
  LogDecisionOptions,
  FindDecisionResult,
  Decision,
  LogPatternOptions,
  FindPatternResult,
  Pattern,
  Vault404Stats
} from 'vault404';
```

## LangChain Integration

See `examples/with-langchain.ts` for a complete example of integrating vault404 with LangChain agents.

```typescript
import { DynamicTool } from "@langchain/core/tools";
import { Vault404Client } from 'vault404';

const vault404 = new Vault404Client();

const findSolutionTool = new DynamicTool({
  name: "vault404_find_solution",
  description: "Search for solutions to coding errors",
  func: async (errorMessage: string) => {
    const result = await vault404.findSolution({ errorMessage });
    return result.found
      ? result.solutions.map(s => s.solution).join('\n')
      : 'No solutions found';
  }
});
```

## Environment Support

- **Node.js**: 18.0.0 or later
- **Browsers**: All modern browsers with native fetch support
- **Runtime**: Works with Deno and Bun

## License

MIT

## Contributing

Contributions are welcome! Please see the [vault404 repository](https://github.com/globallayer/vault404) for contribution guidelines.
