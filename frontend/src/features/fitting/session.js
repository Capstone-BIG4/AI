import { fetchJob, startRun } from "../../api/client.js";
import { renderJobProgress, renderProgress, startRuntime, stopRuntime } from "../../components/pipeline.js";
import { renderProofGrid, renderProofPlaceholders } from "../../components/proofGrid.js";
import { setViewer } from "../../components/viewer.js";
import { inputs } from "../../config/assets.js";
import { runtimeState } from "../../state/runtime.js";


export function createFittingSession(elements) {
  function currentRunMode() {
    const selected = elements.runModeInputs.find((input) => input.checked);
    return selected ? selected.value : "standard";
  }

  function setCompleteState() {
    runtimeState.running = false;
    runtimeState.complete = true;
    window.__virtualFittingReady = true;
    stopRuntime();
    elements.pipelineRuntime.textContent = "Complete";
    elements.runStatus.textContent = "Result ready";
    elements.runStatus.className = "status-pill done";
    if (elements.viewerStatus) elements.viewerStatus.textContent = "Result ready";
    elements.stageTitle.textContent = "Fitting result";
    elements.startButton.textContent = "Run Fitting";
    elements.startButton.disabled = false;
    elements.resultPanel.classList.remove("locked");
    elements.resultPanel.classList.add("has-result");
    if (elements.tryonImage) elements.tryonImage.src = "/assets/results/tryon-2d.png";
    if (elements.proofGrid) renderProofGrid(elements.proofGrid);
    elements.resultLock.classList.add("hidden");
    elements.viewerBlock.classList.remove("locked");
    elements.viewerLaunch.classList.add("hidden");
    elements.viewerContent.classList.remove("hidden");
    elements.openViewerButton.textContent = "Expand";
    setViewer("front", elements);
  }

  function setFailedState(message) {
    runtimeState.running = false;
    runtimeState.complete = false;
    window.__virtualFittingReady = false;
    stopRuntime();
    elements.pipelineRuntime.textContent = "Failed";
    elements.runStatus.textContent = "Run failed";
    elements.runStatus.className = "status-pill failed";
    if (elements.viewerStatus) elements.viewerStatus.textContent = "Failed";
    elements.stageTitle.textContent = message || "Pipeline failed";
    elements.startButton.textContent = "Run Fitting";
    elements.startButton.disabled = false;
  }

  function reset() {
    runtimeState.running = false;
    runtimeState.complete = false;
    window.__virtualFittingReady = false;
    runtimeState.viewerOpen = false;
    runtimeState.viewerZoom = 1;
    window.clearTimeout(runtimeState.pollTimer);
    runtimeState.pollTimer = null;
    window.clearInterval(runtimeState.runtimeTimer);
    runtimeState.runtimeTimer = null;
    elements.pipelineRuntime.textContent = "Ready";
    elements.runStatus.textContent = "Ready";
    elements.runStatus.className = "status-pill";
    if (elements.viewerStatus) elements.viewerStatus.textContent = "Ready";
    elements.stageTitle.textContent = "Ready to run";
    elements.startButton.textContent = "Run Fitting";
    elements.startButton.disabled = false;
    elements.resultPanel.classList.remove("locked");
    elements.resultPanel.classList.remove("has-result");
    if (elements.tryonImage) elements.tryonImage.removeAttribute("src");
    if (elements.proofGrid) renderProofPlaceholders(elements.proofGrid);
    elements.resultLock.classList.add("hidden");
    elements.viewerBlock.classList.add("locked");
    elements.viewerBlock.classList.remove("open");
    elements.viewerLaunch.classList.remove("hidden");
    elements.viewerContent.classList.add("hidden");
    elements.openViewerButton.textContent = "Locked";
    renderProgress(elements.progressList);
    setViewer("front", elements);
  }

  async function pollJob(jobId) {
    try {
      const job = await fetchJob(jobId);
      renderJobProgress(elements.progressList, job);
      if (job.status === "completed") {
        setCompleteState();
        return;
      }
      if (job.status === "failed") {
        setFailedState(job.error || "Pipeline failed");
        return;
      }
      runtimeState.pollTimer = window.setTimeout(() => pollJob(jobId), 650);
    } catch (error) {
      console.error(error);
      setFailedState("Backend connection failed");
    }
  }

  async function run() {
    if (runtimeState.running) return;
    const missingInputs = Math.max(0, inputs.length - runtimeState.uploadedFiles.size);
    if (missingInputs > 0) {
      elements.runStatus.textContent = `Upload ${missingInputs} more`;
      elements.runStatus.className = "status-pill failed";
      if (elements.viewerStatus) elements.viewerStatus.textContent = "Waiting";
      elements.stageTitle.textContent = "Upload every required photo first";
      return;
    }
    reset();
    runtimeState.running = true;
    elements.startButton.disabled = true;
    elements.runStatus.textContent = "Running";
    elements.runStatus.className = "status-pill running";
    if (elements.viewerStatus) elements.viewerStatus.textContent = "Running";
    const mode = currentRunMode();
    elements.stageTitle.textContent = mode === "gpu" ? "GPU pipeline running" : "Preparing fitting result";
    startRuntime(elements.pipelineRuntime);

    try {
      const payload = await startRun(mode);
      pollJob(payload.jobId);
    } catch (error) {
      console.error(error);
      setFailedState("Backend run request failed");
    }
  }

  return { reset, run };
}
