import { uploadInput } from "../api/client.js";
import { inputs } from "../config/assets.js";
import { runtimeState } from "../state/runtime.js";


export function renderInputs(inputCards, uploadCount) {
  const byId = Object.fromEntries(inputs.map((item) => [item.id, item]));
  inputCards.innerHTML = `
    <section class="upload-section">
      <h2>Your Photo</h2>
      <div class="upload-grid single">
        ${renderSlot(byId.person, "Full Body", "person", true)}
      </div>
    </section>
    <section class="upload-section">
      <h2>Top Garment</h2>
      <div class="upload-grid pair">
        ${renderSlot(byId["top-front"], "Front", "hanger", false)}
        ${renderSlot(byId["top-back"], "Back", "hanger", false)}
      </div>
    </section>
    <section class="upload-section">
      <h2>Bottom Garment</h2>
      <div class="upload-grid pair">
        ${renderSlot(byId["pants-front"], "Front", "pants", false)}
        ${renderSlot(byId["pants-back"], "Back", "pants", false)}
      </div>
    </section>
  `;
  bindUploadInputs(inputCards, uploadCount);
  updateUploadCount(uploadCount);
}

function renderSlot(item, label, icon, isLarge) {
  return `
    <label class="upload-slot ${isLarge ? "large" : ""}" for="upload-${item.id}" data-input-id="${item.id}">
      <input class="file-input" id="upload-${item.id}" type="file" accept="${item.accept}" data-upload="${item.id}">
      <img class="slot-preview" alt="${item.label}" data-preview="${item.id}">
      <span class="slot-icon ${icon}" aria-hidden="true"></span>
      <span class="slot-label">${label}</span>
      <span class="slot-state" data-input-state="${item.id}">Ready</span>
      <span class="slot-file" data-file-name="${item.id}">${item.file}</span>
    </label>
  `;
}

function bindUploadInputs(inputCards, uploadCount) {
  inputCards.querySelectorAll("[data-upload]").forEach((input) => {
    input.addEventListener("change", async (event) => {
      const target = event.currentTarget;
      const id = target.dataset.upload;
      const file = target.files && target.files[0];
      if (!file) return;

      if (runtimeState.objectUrls.has(id)) {
        URL.revokeObjectURL(runtimeState.objectUrls.get(id));
      }
      const url = URL.createObjectURL(file);
      runtimeState.objectUrls.set(id, url);
      runtimeState.uploadedFiles.set(id, file.name);

      const preview = inputCards.querySelector(`[data-preview="${id}"]`);
      const fileName = inputCards.querySelector(`[data-file-name="${id}"]`);
      const state = inputCards.querySelector(`[data-input-state="${id}"]`);
      const slot = inputCards.querySelector(`[data-input-id="${id}"]`);
      if (preview) preview.src = url;
      if (preview) preview.classList.add("visible");
      if (slot) slot.classList.add("has-file");
      if (id === "person") {
        const originalImage = document.querySelector("#originalImage");
        const originalFrame = document.querySelector(".original-asset");
        if (originalImage) originalImage.src = url;
        if (originalFrame) originalFrame.classList.add("has-user-photo");
      }
      if (fileName) fileName.textContent = file.name;
      if (state) state.textContent = "Uploading";
      updateUploadCount(uploadCount);

      try {
        await uploadInput(id, file);
        if (state) state.textContent = "Uploaded";
      } catch (error) {
        if (state) state.textContent = "Local";
        console.error(error);
      }
    });
  });
}

function updateUploadCount(uploadCount) {
  uploadCount.textContent = `${runtimeState.uploadedFiles.size} / ${inputs.length}`;
}
