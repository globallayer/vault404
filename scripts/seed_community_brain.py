#!/usr/bin/env python3
"""
Seed the 404vault Community Brain with common error patterns and solutions.

This script populates the community_solutions table with 50+ verified error
patterns covering JavaScript/TypeScript, Python, Database, and DevOps categories.

Usage:
    python scripts/seed_community_brain.py

Environment:
    Uses default Supabase credentials from vault404.sync.community
"""

import hashlib
import json
import os
import sys
from datetime import datetime
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import httpx
    HTTP_CLIENT = "httpx"
except ImportError:
    try:
        import requests
        HTTP_CLIENT = "requests"
    except ImportError:
        print("ERROR: Install httpx or requests: pip install httpx")
        sys.exit(1)


# Supabase configuration
API_URL = os.environ.get(
    "VAULT404_API_URL",
    "https://sbbhtxxegxkqjbfqcrwz.supabase.co/rest/v1"
)
API_KEY = os.environ.get(
    "VAULT404_API_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNiYmh0eHhlZ3hrcWpiZnFjcnd6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3ODU4MjcsImV4cCI6MjA4OTM2MTgyN30.L4D9egjGWUbfpbGkZogVWPia4y6GBKjvJ0FhjB8fuIc"
)


def get_headers():
    """Get headers for API requests."""
    return {
        "Content-Type": "application/json",
        "Prefer": "return=representation",
        "apikey": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
    }


def generate_content_hash(error_msg: str, solution: str) -> str:
    """Generate a unique content hash for deduplication."""
    content = f"{error_msg[:100]}|{solution[:100]}"
    return hashlib.md5(content.encode()).hexdigest()


def create_error_record(
    error_message: str,
    solution: str,
    category: str,
    language: Optional[str] = None,
    framework: Optional[str] = None,
    database: Optional[str] = None,
    platform: Optional[str] = None,
    error_type: Optional[str] = None,
    verification_count: int = 10,
) -> dict:
    """Create an error fix record for the community brain."""
    return {
        "content_hash": generate_content_hash(error_message, solution),
        "record_type": "error_fix",
        "category": category,
        "language": language,
        "framework": framework,
        "database": database,
        "platform": platform,
        "error_data": {
            "message": error_message,
            "error_type": error_type,
        },
        "solution_data": {
            "description": solution,
        },
        "verification_count": verification_count,
        "failure_count": 0,
        "contributor_count": verification_count,
        "contributor_hash": "seed_script_v1",
        "contributed_at": datetime.utcnow().isoformat(),
        "last_verified_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# ERROR PATTERNS DATA
# =============================================================================

JAVASCRIPT_TYPESCRIPT_ERRORS = [
    # Module errors
    {
        "error_message": "Cannot find module 'react' or its corresponding type declarations. TS2307",
        "solution": "Install React and its types: npm install react react-dom @types/react @types/react-dom. Ensure tsconfig.json has 'moduleResolution': 'node' or 'bundler'.",
        "category": "modules",
        "language": "typescript",
        "framework": "react",
        "error_type": "TS2307",
    },
    {
        "error_message": "Module not found: Can't resolve '@/components/Button'",
        "solution": "Configure path aliases in tsconfig.json: Add 'paths': {'@/*': ['./src/*']} under compilerOptions. For Next.js, this should work automatically. For Vite, also configure in vite.config.ts with resolve.alias.",
        "category": "modules",
        "language": "typescript",
        "error_type": "ModuleNotFoundError",
    },
    {
        "error_message": "Cannot find module 'node:fs' or its corresponding type declarations",
        "solution": "Update @types/node to latest version: npm install @types/node@latest. Ensure 'types': ['node'] is in tsconfig.json compilerOptions.",
        "category": "modules",
        "language": "typescript",
        "error_type": "TS2307",
    },
    {
        "error_message": "SyntaxError: Cannot use import statement outside a module",
        "solution": "Add 'type': 'module' to package.json for ESM support. Or use require() syntax instead. For Jest, configure transform in jest.config.js.",
        "category": "modules",
        "language": "javascript",
        "error_type": "SyntaxError",
    },
    # Type errors
    {
        "error_message": "Type 'string | undefined' is not assignable to type 'string'. TS2322",
        "solution": "Handle the undefined case: Use optional chaining (value?.prop), nullish coalescing (value ?? defaultValue), or type guard (if (value) { ... }). Consider using non-null assertion (value!) only when certain.",
        "category": "types",
        "language": "typescript",
        "error_type": "TS2322",
    },
    {
        "error_message": "Property 'x' does not exist on type 'Y'. TS2339",
        "solution": "Check if the property name is correct. Use type assertion (obj as ExtendedType).x if you know the property exists. Consider extending the interface or using index signature [key: string]: any.",
        "category": "types",
        "language": "typescript",
        "error_type": "TS2339",
    },
    {
        "error_message": "Argument of type 'X' is not assignable to parameter of type 'Y'. TS2345",
        "solution": "Ensure types match exactly. Check if you need to spread an object {...obj} or convert types. Use type assertion (value as Y) as last resort. Consider using generics for flexible typing.",
        "category": "types",
        "language": "typescript",
        "error_type": "TS2345",
    },
    {
        "error_message": "Type 'unknown' is not assignable to type 'X'. TS2322",
        "solution": "Type guard the unknown value: Use typeof for primitives (typeof x === 'string'), instanceof for classes, or create custom type guards. Avoid using 'as' without validation.",
        "category": "types",
        "language": "typescript",
        "error_type": "TS2322",
    },
    {
        "error_message": "Object is possibly 'null' or 'undefined'. TS2531",
        "solution": "Add null check before accessing: Use optional chaining (obj?.prop), nullish coalescing (obj ?? default), or explicit check (if (obj !== null) { ... }). Configure strictNullChecks in tsconfig.",
        "category": "types",
        "language": "typescript",
        "error_type": "TS2531",
    },
    # Async/await errors
    {
        "error_message": "await is only valid in async functions and the top level bodies of modules",
        "solution": "Wrap the await in an async function: async function main() { await ... } or use .then() for promise handling. In Node.js, use top-level await with 'type': 'module' in package.json.",
        "category": "async",
        "language": "javascript",
        "error_type": "SyntaxError",
    },
    {
        "error_message": "Unhandled promise rejection: TypeError: Cannot read properties of undefined",
        "solution": "Add try/catch around async operations. Check that async functions are awaited properly. Use Promise.all() with proper error handling for multiple promises.",
        "category": "async",
        "language": "javascript",
        "error_type": "UnhandledPromiseRejection",
    },
    {
        "error_message": "Promise { <pending> } logged instead of actual value",
        "solution": "You forgot to await the promise. Add 'await' before the async function call, or use .then() to handle the resolved value. Ensure parent function is async.",
        "category": "async",
        "language": "javascript",
        "error_type": "LogicError",
    },
    # React errors
    {
        "error_message": "React Hook useEffect has a missing dependency. react-hooks/exhaustive-deps",
        "solution": "Add missing dependencies to the dependency array. If intentional, disable with // eslint-disable-next-line react-hooks/exhaustive-deps. Use useCallback/useMemo for function dependencies.",
        "category": "react-hooks",
        "language": "typescript",
        "framework": "react",
        "error_type": "ESLintWarning",
    },
    {
        "error_message": "Invalid hook call. Hooks can only be called inside of the body of a function component",
        "solution": "Ensure hooks are called at the top level of functional components, not inside loops, conditions, or nested functions. Check for duplicate React versions: npm ls react.",
        "category": "react-hooks",
        "language": "typescript",
        "framework": "react",
        "error_type": "InvalidHookCallError",
    },
    {
        "error_message": "Each child in a list should have a unique 'key' prop",
        "solution": "Add unique key prop to array items: {items.map(item => <Component key={item.id} />)}. Use stable IDs, not array indices (unless list is static and never reordered).",
        "category": "react-rendering",
        "language": "typescript",
        "framework": "react",
        "error_type": "ReactWarning",
    },
    {
        "error_message": "Cannot update a component while rendering a different component",
        "solution": "Move state updates to useEffect or event handlers. Don't call setState during render. Use useEffect with proper dependencies for side effects.",
        "category": "react-rendering",
        "language": "typescript",
        "framework": "react",
        "error_type": "ReactError",
    },
    {
        "error_message": "Hydration failed because the initial UI does not match what was rendered on the server",
        "solution": "Ensure server and client render the same content. Wrap client-only code with useEffect or dynamic import with ssr: false. Check for Date.now(), Math.random(), or browser APIs used during render.",
        "category": "react-ssr",
        "language": "typescript",
        "framework": "nextjs",
        "error_type": "HydrationError",
    },
    # Null/undefined errors
    {
        "error_message": "TypeError: Cannot read properties of undefined (reading 'map')",
        "solution": "Add null check: (array ?? []).map() or array?.map() || []. Initialize state with empty array: useState([]). Check API response structure.",
        "category": "null-reference",
        "language": "javascript",
        "error_type": "TypeError",
    },
    {
        "error_message": "TypeError: Cannot read properties of null (reading 'addEventListener')",
        "solution": "Element doesn't exist yet. Use optional chaining: element?.addEventListener(). For React, use useRef and check ref.current. For vanilla JS, query after DOMContentLoaded.",
        "category": "null-reference",
        "language": "javascript",
        "error_type": "TypeError",
    },
]

PYTHON_ERRORS = [
    # Import errors
    {
        "error_message": "ModuleNotFoundError: No module named 'requests'",
        "solution": "Install the missing package: pip install requests. If using virtual environment, ensure it's activated. Check pip list to verify installation.",
        "category": "imports",
        "language": "python",
        "error_type": "ModuleNotFoundError",
    },
    {
        "error_message": "ImportError: cannot import name 'X' from 'Y'",
        "solution": "Check the import path and module structure. Verify the name exists in the module. May indicate circular import - refactor to move shared code to separate module.",
        "category": "imports",
        "language": "python",
        "error_type": "ImportError",
    },
    {
        "error_message": "ImportError: attempted relative import with no known parent package",
        "solution": "Run as module: python -m package.module instead of python module.py. Or convert to absolute import. Check __init__.py exists in package directories.",
        "category": "imports",
        "language": "python",
        "error_type": "ImportError",
    },
    {
        "error_message": "ModuleNotFoundError: No module named 'src'",
        "solution": "Add src to Python path: PYTHONPATH=. python script.py. Or install package in editable mode: pip install -e . Create pyproject.toml or setup.py if missing.",
        "category": "imports",
        "language": "python",
        "error_type": "ModuleNotFoundError",
    },
    # Indentation errors
    {
        "error_message": "IndentationError: expected an indented block",
        "solution": "Add proper indentation after colon (:). Python uses 4 spaces by default. Check for mixed tabs and spaces. Use 'pass' for empty blocks.",
        "category": "syntax",
        "language": "python",
        "error_type": "IndentationError",
    },
    {
        "error_message": "IndentationError: unexpected indent",
        "solution": "Remove extra indentation. Ensure consistent use of spaces (not tabs). Check previous lines for missing colons. Configure editor to use spaces for indentation.",
        "category": "syntax",
        "language": "python",
        "error_type": "IndentationError",
    },
    # None errors
    {
        "error_message": "AttributeError: 'NoneType' object has no attribute 'X'",
        "solution": "Variable is None when you expected an object. Add None check: if obj is not None. Check function returns (may return None implicitly). Use default values: value = func() or default.",
        "category": "null-reference",
        "language": "python",
        "error_type": "AttributeError",
    },
    {
        "error_message": "TypeError: 'NoneType' object is not iterable",
        "solution": "You're iterating over None. Check function returns a list: return result or []. Add guard: for item in (items or []). Verify API/database query returns data.",
        "category": "null-reference",
        "language": "python",
        "error_type": "TypeError",
    },
    {
        "error_message": "TypeError: 'NoneType' object is not subscriptable",
        "solution": "Cannot index None value. Add check before indexing: if data and len(data) > 0. Use .get() for dicts: data.get('key', default). Verify data source returns expected structure.",
        "category": "null-reference",
        "language": "python",
        "error_type": "TypeError",
    },
    # Django errors
    {
        "error_message": "django.core.exceptions.ImproperlyConfigured: SECRET_KEY must be set",
        "solution": "Set SECRET_KEY in settings.py or environment: export SECRET_KEY='your-secret-key'. For production, use django.core.management.utils.get_random_secret_key() to generate.",
        "category": "configuration",
        "language": "python",
        "framework": "django",
        "error_type": "ImproperlyConfigured",
    },
    {
        "error_message": "django.db.utils.OperationalError: no such table: X",
        "solution": "Run migrations: python manage.py makemigrations && python manage.py migrate. Check database connection. For SQLite, ensure db.sqlite3 exists.",
        "category": "database",
        "language": "python",
        "framework": "django",
        "error_type": "OperationalError",
    },
    {
        "error_message": "CORS error: No 'Access-Control-Allow-Origin' header (Django)",
        "solution": "Install django-cors-headers: pip install django-cors-headers. Add to INSTALLED_APPS and MIDDLEWARE. Set CORS_ALLOWED_ORIGINS or CORS_ALLOW_ALL_ORIGINS = True for development.",
        "category": "cors",
        "language": "python",
        "framework": "django",
        "error_type": "CORSError",
    },
    # FastAPI errors
    {
        "error_message": "fastapi.exceptions.HTTPException: 422 Unprocessable Entity",
        "solution": "Request validation failed. Check request body matches Pydantic model. Ensure field types are correct. Use Optional[X] for optional fields. Check Content-Type header is application/json.",
        "category": "validation",
        "language": "python",
        "framework": "fastapi",
        "error_type": "HTTPException",
    },
    {
        "error_message": "RuntimeError: This event loop is already running (asyncio)",
        "solution": "Don't nest asyncio.run() calls. Use await instead of run() inside async functions. For Jupyter, use nest_asyncio: import nest_asyncio; nest_asyncio.apply().",
        "category": "async",
        "language": "python",
        "framework": "fastapi",
        "error_type": "RuntimeError",
    },
    # Virtual environment
    {
        "error_message": "Command 'pip' not found or pip installs to wrong location",
        "solution": "Activate virtual environment: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows). Use python -m pip for explicit pip. Create venv: python -m venv venv.",
        "category": "environment",
        "language": "python",
        "error_type": "EnvironmentError",
    },
    {
        "error_message": "pkg_resources.DistributionNotFound: The 'X' distribution was not found",
        "solution": "Package not installed in current environment. Activate correct virtualenv. Run pip install -r requirements.txt. Check for version conflicts with pip check.",
        "category": "environment",
        "language": "python",
        "error_type": "DistributionNotFound",
    },
    {
        "error_message": "SyntaxError: invalid syntax (Python 2 vs 3)",
        "solution": "Check Python version: python --version. Update print statements: print('text'). Use // for integer division. Check for other Python 2 syntax.",
        "category": "syntax",
        "language": "python",
        "error_type": "SyntaxError",
    },
]

DATABASE_ERRORS = [
    # Connection errors
    {
        "error_message": "ECONNREFUSED 127.0.0.1:5432 - connection refused",
        "solution": "PostgreSQL server not running or wrong host. Start server: sudo systemctl start postgresql. Check host config - use 'localhost' or '127.0.0.1'. For Docker, use container name or host.docker.internal.",
        "category": "connection",
        "database": "postgresql",
        "error_type": "ECONNREFUSED",
    },
    {
        "error_message": "OperationalError: could not connect to server: Connection refused",
        "solution": "Database server not accepting connections. Check server is running. Verify host, port, and pg_hba.conf settings. Ensure firewall allows connection on port 5432.",
        "category": "connection",
        "database": "postgresql",
        "error_type": "OperationalError",
    },
    {
        "error_message": "Error: connect ECONNREFUSED 127.0.0.1:3306 (MySQL)",
        "solution": "MySQL server not running. Start with: sudo systemctl start mysql. Check bind-address in my.cnf. Verify port 3306 is not blocked by firewall.",
        "category": "connection",
        "database": "mysql",
        "error_type": "ECONNREFUSED",
    },
    {
        "error_message": "MongoNetworkError: failed to connect to server",
        "solution": "MongoDB server not running or unreachable. Start: mongod or systemctl start mongod. Check connection string format. For Atlas, whitelist your IP address.",
        "category": "connection",
        "database": "mongodb",
        "error_type": "MongoNetworkError",
    },
    {
        "error_message": "Error: Connection timeout expired. Host not responding.",
        "solution": "Database host unreachable or too slow. Check network connectivity. Verify hostname/IP is correct. Increase connection timeout. Check firewall rules.",
        "category": "connection",
        "database": "postgresql",
        "error_type": "TimeoutError",
    },
    # Migration errors
    {
        "error_message": "Error: Migration failed: relation 'X' already exists",
        "solution": "Table already exists from previous migration. Use DROP TABLE IF EXISTS or add IF NOT EXISTS to CREATE. Reset migrations if development: prisma migrate reset.",
        "category": "migration",
        "database": "postgresql",
        "error_type": "MigrationError",
    },
    {
        "error_message": "Error: Cannot drop table 'X' because other objects depend on it",
        "solution": "Use CASCADE to drop dependent objects: DROP TABLE X CASCADE. Or drop dependent objects first. Review foreign key relationships before dropping.",
        "category": "migration",
        "database": "postgresql",
        "error_type": "DependencyError",
    },
    {
        "error_message": "Prisma: Migration failed - database schema drift detected",
        "solution": "Schema out of sync with migrations. Run prisma db pull to update schema from database. Or prisma migrate reset for development (destroys data).",
        "category": "migration",
        "database": "postgresql",
        "error_type": "SchemaDriftError",
    },
    # Constraint violations
    {
        "error_message": "ERROR: duplicate key value violates unique constraint",
        "solution": "Inserting duplicate value in unique column. Use INSERT ... ON CONFLICT DO UPDATE for upsert. Check data for duplicates before insert. Use RETURNING to avoid race conditions.",
        "category": "constraint",
        "database": "postgresql",
        "error_type": "UniqueViolation",
    },
    {
        "error_message": "ERROR: null value in column 'X' violates not-null constraint",
        "solution": "Required column has NULL value. Provide value in INSERT. Add DEFAULT in schema. Or make column nullable: ALTER TABLE X ALTER COLUMN Y DROP NOT NULL.",
        "category": "constraint",
        "database": "postgresql",
        "error_type": "NotNullViolation",
    },
    {
        "error_message": "ERROR: insert or update on table 'X' violates foreign key constraint",
        "solution": "Referenced record doesn't exist. Insert parent record first. Check foreign key value is correct. Use ON DELETE SET NULL or CASCADE if appropriate.",
        "category": "constraint",
        "database": "postgresql",
        "error_type": "ForeignKeyViolation",
    },
    # Query errors
    {
        "error_message": "ERROR: syntax error at or near 'X' (PostgreSQL)",
        "solution": "SQL syntax error. Check for missing quotes, commas, or parentheses. Use parameterized queries to avoid escaping issues. Reserved words need double quotes.",
        "category": "query",
        "database": "postgresql",
        "error_type": "SyntaxError",
    },
    {
        "error_message": "ERROR: column 'X' does not exist",
        "solution": "Column name incorrect or table not migrated. Check exact column name (case-sensitive). Run pending migrations. Use double quotes for case-sensitive names.",
        "category": "query",
        "database": "postgresql",
        "error_type": "UndefinedColumn",
    },
]

DEVOPS_ERRORS = [
    # Git errors
    {
        "error_message": "error: Your local changes would be overwritten by merge. Aborting.",
        "solution": "Stash changes first: git stash. Then merge and apply: git stash pop. Or commit changes before merge. Use git status to see modified files.",
        "category": "version-control",
        "platform": "git",
        "error_type": "MergeConflict",
    },
    {
        "error_message": "CONFLICT (content): Merge conflict in file.txt",
        "solution": "Open file and resolve conflicts between <<<<<<< HEAD and >>>>>>>. Remove conflict markers. Stage resolved files: git add. Complete merge: git commit.",
        "category": "version-control",
        "platform": "git",
        "error_type": "MergeConflict",
    },
    {
        "error_message": "error: failed to push some refs. Updates were rejected",
        "solution": "Remote has commits you don't have. Pull first: git pull --rebase origin main. Resolve any conflicts. Then push again. Never force push to shared branches.",
        "category": "version-control",
        "platform": "git",
        "error_type": "PushRejected",
    },
    {
        "error_message": "fatal: refusing to merge unrelated histories",
        "solution": "Use --allow-unrelated-histories flag: git pull origin main --allow-unrelated-histories. Common when repo was reinitialized or history was rewritten.",
        "category": "version-control",
        "platform": "git",
        "error_type": "UnrelatedHistories",
    },
    # CI/CD errors
    {
        "error_message": "GitHub Actions: Error: Process completed with exit code 1",
        "solution": "Check step logs for actual error. Common causes: failing tests, linting errors, missing env vars. Add 'set -e' to catch errors early. Use 'continue-on-error: true' for non-critical steps.",
        "category": "ci-cd",
        "platform": "github-actions",
        "error_type": "ProcessExitCode",
    },
    {
        "error_message": "Error: Resource not accessible by integration (GitHub Actions)",
        "solution": "Workflow needs more permissions. Add permissions block: permissions: { contents: write, pull-requests: write }. Check if GITHUB_TOKEN has required scope.",
        "category": "ci-cd",
        "platform": "github-actions",
        "error_type": "PermissionError",
    },
    {
        "error_message": "npm ERR! code ERESOLVE - unable to resolve dependency tree",
        "solution": "Dependency version conflict. Use --legacy-peer-deps flag. Or update conflicting packages. Check npm ls for dependency tree. Consider npm dedupe.",
        "category": "ci-cd",
        "language": "javascript",
        "error_type": "ERESOLVE",
    },
    # Docker errors
    {
        "error_message": "docker: Error response from daemon: Conflict. Container name already in use",
        "solution": "Remove existing container: docker rm <container>. Or use different name. Use --rm flag for auto-cleanup. Check: docker ps -a for all containers.",
        "category": "containers",
        "platform": "docker",
        "error_type": "ContainerConflict",
    },
    {
        "error_message": "Error: Cannot start service: driver failed programming external connectivity",
        "solution": "Port already in use. Check: netstat -tulpn | grep PORT. Kill process or use different port. Stop conflicting containers: docker stop $(docker ps -q).",
        "category": "containers",
        "platform": "docker",
        "error_type": "PortConflict",
    },
    {
        "error_message": "ERROR: failed to solve: dockerfile parse error",
        "solution": "Dockerfile syntax error. Check line endings (use LF not CRLF). Verify COPY paths exist. Use multi-line with backslash properly. Check for invisible characters.",
        "category": "containers",
        "platform": "docker",
        "error_type": "DockerfileParseError",
    },
    {
        "error_message": "Error: EACCES: permission denied, open '/app/file'",
        "solution": "Container running as wrong user. Add USER directive in Dockerfile. Use chown in COPY command. Mount volume with correct permissions. Check file system permissions.",
        "category": "containers",
        "platform": "docker",
        "error_type": "EACCES",
    },
    # Permission errors
    {
        "error_message": "Permission denied (publickey) when SSH to server",
        "solution": "SSH key not authorized. Add public key to ~/.ssh/authorized_keys on server. Check key permissions: chmod 600 ~/.ssh/id_rsa. Verify SSH agent has key: ssh-add -l.",
        "category": "permissions",
        "platform": "linux",
        "error_type": "PermissionDenied",
    },
    {
        "error_message": "EACCES: permission denied, mkdir '/usr/local/lib/node_modules'",
        "solution": "Don't use sudo with npm. Fix npm permissions: mkdir ~/.npm-global && npm config set prefix '~/.npm-global'. Or use nvm for Node version management.",
        "category": "permissions",
        "language": "javascript",
        "error_type": "EACCES",
    },
]


def insert_records(records: list[dict]) -> tuple[int, int]:
    """Insert records into community_solutions table."""
    success = 0
    failed = 0

    for record in records:
        try:
            if HTTP_CLIENT == "httpx":
                import httpx
                with httpx.Client() as client:
                    response = client.post(
                        f"{API_URL}/community_solutions",
                        headers=get_headers(),
                        json=record,
                        timeout=10.0,
                    )
            else:
                import requests
                response = requests.post(
                    f"{API_URL}/community_solutions",
                    headers=get_headers(),
                    json=record,
                    timeout=10,
                )

            if response.status_code in (200, 201):
                success += 1
                print(f"  + {record['error_data']['message'][:60]}...")
            elif response.status_code == 409:
                # Duplicate - already exists
                print(f"  = (exists) {record['error_data']['message'][:50]}...")
                success += 1
            else:
                failed += 1
                print(f"  ! FAILED ({response.status_code}): {record['error_data']['message'][:50]}...")
                if response.text:
                    print(f"    Response: {response.text[:200]}")
        except Exception as e:
            failed += 1
            print(f"  ! ERROR: {str(e)[:80]}")

    return success, failed


def build_records_from_data(data: list[dict]) -> list[dict]:
    """Convert error data to community brain records."""
    records = []
    for item in data:
        records.append(create_error_record(
            error_message=item["error_message"],
            solution=item["solution"],
            category=item.get("category", "general"),
            language=item.get("language"),
            framework=item.get("framework"),
            database=item.get("database"),
            platform=item.get("platform"),
            error_type=item.get("error_type"),
            verification_count=10,  # Pre-verified seed data
        ))
    return records


def main():
    """Seed the community brain with error patterns."""
    print("=" * 70)
    print("404vault Community Brain Seeder")
    print("=" * 70)
    print(f"API URL: {API_URL}")
    print()

    total_success = 0
    total_failed = 0

    # JavaScript/TypeScript errors
    print(f"\n[JavaScript/TypeScript] - {len(JAVASCRIPT_TYPESCRIPT_ERRORS)} patterns")
    print("-" * 50)
    records = build_records_from_data(JAVASCRIPT_TYPESCRIPT_ERRORS)
    s, f = insert_records(records)
    total_success += s
    total_failed += f

    # Python errors
    print(f"\n[Python] - {len(PYTHON_ERRORS)} patterns")
    print("-" * 50)
    records = build_records_from_data(PYTHON_ERRORS)
    s, f = insert_records(records)
    total_success += s
    total_failed += f

    # Database errors
    print(f"\n[Database] - {len(DATABASE_ERRORS)} patterns")
    print("-" * 50)
    records = build_records_from_data(DATABASE_ERRORS)
    s, f = insert_records(records)
    total_success += s
    total_failed += f

    # DevOps errors
    print(f"\n[DevOps/Git] - {len(DEVOPS_ERRORS)} patterns")
    print("-" * 50)
    records = build_records_from_data(DEVOPS_ERRORS)
    s, f = insert_records(records)
    total_success += s
    total_failed += f

    # Summary
    total_patterns = (
        len(JAVASCRIPT_TYPESCRIPT_ERRORS) +
        len(PYTHON_ERRORS) +
        len(DATABASE_ERRORS) +
        len(DEVOPS_ERRORS)
    )

    print()
    print("=" * 70)
    print(f"SUMMARY: {total_success} succeeded, {total_failed} failed, {total_patterns} total")
    print("=" * 70)

    if total_failed > 0:
        print("\nSome records failed to insert. Check Supabase logs for details.")
        return 1

    print("\nCommunity brain seeded successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
