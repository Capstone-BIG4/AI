# Privacy and Data Handling Notes

The MVP handles full-body user photos, so even the capstone demo should treat
inputs as sensitive local data.

## Local Development Rules

- Do not commit `uploads/`, `results/`, `checkpoints/`, or model outputs.
- Do not write original image paths or public URLs into logs.
- Use internal job ids in metadata instead of original filenames.
- Use only approved sample images for demos.
- Delete local test inputs and outputs when they are no longer needed.

## Product Rules

- Tell users when images are processed locally or sent to an external inference
  environment.
- Provide a job-level delete action for original files and generated results.
- Do not show estimated body measurements as real cm values.
- Keep UI wording to "preview", "fit impression", and "style combination";
  avoid "size guarantee" or "accurate body measurement".
