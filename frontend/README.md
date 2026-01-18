# Task Management Admin Frontend

Vue 3 frontend for managing Instagram post pipeline tasks.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

3. Make sure the FastAPI backend is running on `http://localhost:8000`

## Build

To build for production:
```bash
npm run build
```

The built files will be in the `dist` directory.

## Configuration

You can configure the API URL by creating a `.env` file:
```
VITE_API_URL=http://localhost:8000/api/v1
```

If not set, it defaults to `http://localhost:8000/api/v1`.

## Features

- View all tasks with status filtering
- Create new tasks
- View and edit task details
- Perform status transitions (submit, approve, disapprove, publish, reject)
- Real-time status updates
- Responsive design
