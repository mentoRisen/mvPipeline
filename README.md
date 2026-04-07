# Mentoverse Pipeline

Pipeline for generating quote images and publishing to Instagram. Multi-tenant: manage projects (tenants) with separate configs and Instagram accounts.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   Or manually:
   ```bash
   pip install sqlmodel python-dotenv pillow requests fastapi uvicorn[standard] pydantic>=2.0.0
   ```

3. (Optional) Set up OpenAI API for image generation:
   - Get your API key from https://platform.openai.com/api-keys
   - Create a `.env` file in the project root:
     ```
     OPENAI_API_KEY=your-api-key-here
     ```
   - Or set environment variables:
     ```bash
     export OPENAI_API_KEY=your-api-key-here
     ```

4. Configure authentication secrets:
   ```
   AUTH_SECRET_KEY=replace-with-random-string
   AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=300  # optional
   ```
   `AUTH_SECRET_KEY` is required for signing JWT access tokens. Set these in your environment or `.env` file before starting the API.

## Database

### MySQL Setup

The application uses MySQL for data storage. Make sure MySQL is installed and running on your system.

1. **Create the database** (if it doesn't exist):
   ```bash
   mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS mvpipeline;"
   ```
   Or connect to MySQL and run:
   ```sql
   CREATE DATABASE IF NOT EXISTS mvpipeline;
   ```

2. **Configure the connection**:
   
   The default connection string in code is: `mysql+pymysql://mentor:mentor@localhost:3306/mvpipeline`
   
   You can override it via the `DATABASE_URL` environment variable or in your `.env` file:
   ```
   DATABASE_URL=mysql+pymysql://username:password@host:port/database
   ```
   
   Examples:
   ```
   DATABASE_URL=mysql+pymysql://root@localhost/mvpipeline
   DATABASE_URL=mysql+pymysql://myuser:mypassword@localhost:3306/mydb
   ```
   
   The format is: `mysql+pymysql://user:password@host:port/database`

### Optional: Cursor MCP MySQL config

If you use the MySQL MCP server in Cursor, keep local credentials in `.cursor/mcp-mysql.env`.

1. Create your local MCP env file from the example:
   ```bash
   cp .cursor/mcp-mysql-example.env .cursor/mcp-mysql.env
   ```
2. Fill `MYSQL_USER` and `MYSQL_PASS` with your local/tenant-safe DB credentials.
3. Adjust host/port if needed (for SSH tunnels, set the forwarded local port).

`mcp-mysql.env` is gitignored. Commit only the example file when defaults/comments need updating.

## Authentication & Users

All API routes under `/api/v1/*` now require a valid Bearer token. Only the root (`/`) and `/health` endpoints remain public.

1. **Create the first user** (one-time bootstrap):
   ```bash
   python scripts/create_user.py --username admin --email you@example.com
   ```
   Omit `--password` to be prompted securely. Run the script again any time you need to add more users.
2. **Sign in** with the Vue UI by visiting `http://localhost:3000/login` (or the `/login` route in production). After logging in, the token is stored in `localStorage` and attached to all API calls automatically.
3. **API login** is also available programmatically:
   - `POST /api/v1/auth/login` with JSON `{ "username": "...", "password": "..." }` returns `{ access_token, token_type, user }`.
   - Include `Authorization: Bearer <token>` on every subsequent request.
4. **User management** endpoints:
   - `GET /api/v1/users` – list users (requires authentication)
   - `POST /api/v1/users` – create user
   - `PATCH /api/v1/users/{id}` – update email, password, or activation state

Tokens expire after `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` (default 300). When a token expires, the frontend automatically returns to the login screen.

### Manual Verification
1. Start the API (`python -m app.main`) and frontend (`npm run dev` from `frontend/`).
2. Create a user with `scripts/create_user.py` if you haven't already.
3. Visit `http://localhost:3000/login`, sign in, and confirm the Tasks view loads.
4. Try calling a protected endpoint without `Authorization` (e.g., `curl http://localhost:8000/api/v1/tasks`) and observe the `401 Unauthorized` response.
5. Call the same endpoint with the `Authorization: Bearer <token>` header returned from `/auth/login` and confirm it succeeds.

## Running

### Quick Start (Recommended)

**Start both servers (background mode):**
```bash
./startup.sh
```

**Run one service in foreground mode:**
```bash
./startup.sh -f --api
./startup.sh -f --gui
./startup.sh -f --worker
# Optional: limit to one tenant — ./startup.sh -f --worker --tenant-id=<UUID>
```

**Start only API server:**
```bash
./startup.sh --api
# or
./startup.sh -api
```

**Start only Frontend server:**
```bash
./startup.sh --gui
# or
./startup.sh -gui
```

**Combine options:**
```bash
./startup.sh --api --foreground    # Start only API in foreground
./startup.sh --gui -f              # Start only Frontend in foreground
```

By default, servers run in the background with logs in `logs/`. Foreground mode only supports one of `--api`, `--gui`, or `--worker`. Press `Ctrl+C` to stop.

**Note:** This script is Linux and Bash only.

### Manual Start

#### API Server

Start the FastAPI server:
```bash
python -m app.main
```

Or using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

#### Frontend (Vue.js)

The Vue frontend is located in the `frontend/` directory. To run it:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

   Make sure the FastAPI backend is running on port 8000.

See `frontend/README.md` for more details.

#### Worker

One process cycles all **active** tenants (tenant context is set per tenant each pass). Optional filter:

```bash
python -m app.worker
python -m app.worker --tenant-id=<tenant-uuid>
```

Or using the startup script:
```bash
./startup.sh --worker
./startup.sh -f --worker
# Optional: WORKER_TENANT_ID=... or --tenant-id=<uuid>
```

### Instagram Publishing

Publish a task to Instagram:
```bash
python scripts/publish_task.py <task_id>
```

Example:
```bash
python scripts/publish_task.py 123e4567-e89b-12d3-a456-426614174000
```

**Requirements:**
- Task should normally be in `READY` status
- The publisher service currently accepts tasks in `READY`, `PUBLISHING`, or `FAILED`
- Task must have at least one `imagecontent` job with a usable public image URL, or enough data to construct one from `PUBLIC_URL`
- Instagram API credentials must be configured (see Setup below)

**Setup Instagram API:**
1. Create a Facebook App and get Instagram Business Account access
2. Get a long-lived access token from Facebook Graph API
3. Find your Instagram Business Account ID:
   ```bash
   python scripts/find_instagram_account_id.py
   ```
   This will show you the correct ID to use.
4. Set environment variables:
   ```bash
   export INSTAGRAM_ACCESS_TOKEN=your-access-token
   export INSTAGRAM_ACCOUNT_ID=your-account-id
   ```
   Or add to `.env` file:
   ```
   INSTAGRAM_ACCESS_TOKEN=your-access-token
   INSTAGRAM_ACCOUNT_ID=your-account-id
   ```

**Important:** `INSTAGRAM_ACCOUNT_ID` must be the **Instagram Business Account ID**, not:
- ❌ Facebook Page ID
- ❌ Facebook User ID  
- ❌ Instagram User ID (personal account)

It's the ID you get from your Facebook Page's `instagram_business_account` field. Use the helper script above to find it.

**Note:** The Instagram Graph API requires images to be publicly accessible via URL. For local files, you may need to:
- Upload images to a public URL (e.g., cloud storage) first
- Or use a local file server that makes images publicly accessible

### Image Generators

Image generation is handled by job processors under `app/services/jobs/`:

- **DALL-E** via `processor_dalle.py`
  - Uses the job's `generator` and `prompt.prompt` fields
  - Requires `OPENAI_API_KEY`
- **GPT-Image-1.5** via `processor_gptimage15.py`
  - Uses the job's `generator` and `prompt.prompt` fields
  - Requires `OPENAI_API_KEY`
- Generated files are written under `output/{task_id}/{job_id}.jpeg`

## Expected Output

### Current Task Lifecycle

Typical runtime flow:
- Task is created in `DRAFT`
- User submits task: `DRAFT` → `PENDING_APPROVAL`
- User approves processing: `PENDING_APPROVAL` → `PROCESSING`
- All `NEW` jobs on the task become `READY`
- Job processing runs per job: `READY` → `PROCESSING` → `PROCESSED` or `ERROR`
- When all jobs are `PROCESSED`, task moves to `PENDING_CONFIRMATION`
- User approves publication: `PENDING_CONFIRMATION` → `READY`
- Publish runs: `READY` → `PUBLISHING` → `PUBLISHED` or `FAILED`

Generated image output is written to:
- `output/{task_id}/{job_id}.jpeg`

## API Endpoints

The FastAPI server provides REST endpoints for task management:

> **Note:** All endpoints below (except `/` and `/health`) require `Authorization: Bearer <token>`.

### Authentication
- `POST /api/v1/auth/login` – obtain an access token
- `GET /api/v1/auth/me` – fetch the current user tied to the provided token
- `GET /api/v1/users` – list users
- `POST /api/v1/users` – create a user
- `PATCH /api/v1/users/{user_id}` – update password/email/active flag

### Task CRUD
- `GET /api/v1/tasks` - List all tasks (with pagination and optional status filter)
- `GET /api/v1/tasks/{task_id}` - Get a specific task
- `POST /api/v1/tasks` - Create a new task
- `PUT /api/v1/tasks/{task_id}` - Update a task
- `DELETE /api/v1/tasks/{task_id}` - Delete a task
- `GET /api/v1/tasks/status/{status}` - List tasks by status

### Task Status Transitions
- `POST /api/v1/tasks/{task_id}/submit` - Submit draft task for approval
- `POST /api/v1/tasks/{task_id}/approve-processing` - Approve task for processing
- `POST /api/v1/tasks/{task_id}/disapprove` - Disapprove task
- `POST /api/v1/tasks/{task_id}/approve-publication` - Approve task for publication
- `POST /api/v1/tasks/{task_id}/publish` - Publish task (normally from READY; service also accepts PUBLISHING or FAILED)
- `POST /api/v1/tasks/{task_id}/reject` - Reject task from publication

See the interactive API documentation at `/docs` for detailed request/response schemas.

## Project Structure

```
mvPipeline/
├── app/              # Python FastAPI backend
│   ├── api/          # API routes and schemas
│   ├── models/       # Database models
│   ├── services/     # Business logic
│   └── main.py       # FastAPI application
├── frontend/         # Vue.js frontend (separate folder)
│   ├── src/
│   │   ├── components/  # Vue components
│   │   ├── services/     # API service
│   │   └── main.js     # Vue app entry
│   └── package.json
├── scripts/          # Pipeline scripts
└── requirements.txt  # Python dependencies
```
