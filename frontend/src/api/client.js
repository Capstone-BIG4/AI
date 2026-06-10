export async function uploadInput(slot, file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`/api/uploads/${slot}`, {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    throw new Error(`upload failed: ${response.status}`);
  }
  return response.json();
}

export async function startRun(mode) {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode })
  });
  if (!response.ok) {
    throw new Error(`run failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`job status failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchHealth() {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`health failed: ${response.status}`);
  }
  return response.json();
}
