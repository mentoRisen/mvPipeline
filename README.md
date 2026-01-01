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
   pip install sqlmodel python-dotenv pillow
   ```

## Database

SQLite database location: `db.sqlite` in the project root.

Can be overridden via `DB_PATH` environment variable.

## Running

Execute the pipeline once:
```bash
python scripts/run_once.py
```

## Expected Output

On success:
- Task row created in database with status progression: `PENDING` → `PROCESSING` → `QUOTE_READY` → `IMAGE_READY`
- Image file with quote text rendered on template created in `output/images/{task_id}.png`
- Console output showing task ID and final status `IMAGE_READY`
- Exit code 0

On failure:
- Task marked as `FAILED` in database
- Error message printed to stderr
- Exit code 1

