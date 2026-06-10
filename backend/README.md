# Backend

FastAPI backend for the virtual fitting studio.

## Run

```bash
python scripts/dev/run_server.py --port 8000
```

## API Surface

- `GET /api/health`
- `POST /api/uploads/{slot}`
- `POST /api/runs`
- `GET /api/jobs/{job_id}`
- `GET /api/results`

The backend serves the frontend, selected result assets, and runtime uploads from repository-relative paths.
