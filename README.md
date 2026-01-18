# Quote-Image Pipeline MVP

Minimal Python pipeline for generating quote images for Instagram posts.

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

3. (Optional) Set up OpenAI API for DALL-E image generation:
   - Get your API key from https://platform.openai.com/api-keys
   - Create a `.env` file in the project root:
     ```
     OPENAI_API_KEY=your-api-key-here
     DEFAULT_IMAGE_GENERATOR=dalle
     ```
   - Or set environment variables:
     ```bash
     export OPENAI_API_KEY=your-api-key-here
     export DEFAULT_IMAGE_GENERATOR=dalle
     ```

## Database

SQLite database location: `db.sqlite` in the project root.

Can be overridden via `DB_PATH` environment variable.

## Running

### API Server

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

### Frontend (Vue.js)

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

### Pipeline Script

Execute the pipeline once:
```bash
python scripts/run_once.py
```

### Instagram Publishing

Publish a task to Instagram:
```bash
python scripts/publish.py <task_id>
```

Example:
```bash
python scripts/publish.py 123e4567-e89b-12d3-a456-426614174000
```

Dry run (validate without posting):
```bash
python scripts/publish.py <task_id> --dry-run
```

**Requirements:**
- Task must be in `READY` status
- Task must have an image path
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

The pipeline supports two image generation methods:

- **Pillow** (default): Renders quote text on template image from `templates/` directory
  - Set `task.image_generator = "pillow"` or leave empty
  - Requires template image in `templates/default.png`

- **DALL-E**: Generates images using OpenAI's DALL-E API
  - Set `task.image_generator = "dalle"` in your code
  - Requires `OPENAI_API_KEY` environment variable
  - Uses `task.image_generator_prompt` to generate the image

## Expected Output

On success:
- Task row created in database with status progression: `DRAFT` → `PROCESSING` → `READY`
- Image file with quote text rendered on template created in `output/images/{task_id}.png`
- Console output showing task ID and final status `READY`
- Exit code 0

On failure:
- Task marked as `FAILED` in database
- Error message printed to stderr
- Exit code 1

## API Endpoints

The FastAPI server provides REST endpoints for task management:

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
- `POST /api/v1/tasks/{task_id}/publish` - Publish task (from READY to PUBLISHED)
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
