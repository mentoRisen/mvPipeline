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
   pip install sqlmodel python-dotenv pillow requests
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

Execute the pipeline once:
```bash
python scripts/run_once.py
```

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
- Task row created in database with status progression: `PENDING` → `PROCESSING` → `QUOTE_READY` → `IMAGE_READY`
- Image file with quote text rendered on template created in `output/images/{task_id}.png`
- Console output showing task ID and final status `IMAGE_READY`
- Exit code 0

On failure:
- Task marked as `FAILED` in database
- Error message printed to stderr
- Exit code 1

