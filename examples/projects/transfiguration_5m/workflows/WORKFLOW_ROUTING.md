# Workflow Routing — Required Production Chain

## Characters
`CF-IMG-01` establishes candidates. `CF-IMG-02` maintains identity/style references. `CF-IMG-03` is conditional and may be used only after admission if Redux fails identity benchmarks.

## Storyboard and starting images
Every subscene requires a real approved starting image. Use `CF-IMG-05` for depth/pose/layout control where required. Production video may not start from an empty video latent.

## Preview video
Use `CF-VID-01` only for admitted draft/review previews. Apply `CF-VID-03` IC-LoRA control to shots flagged in the manifest. Use `CF-VID-05` for previous-frame/FLF/V2V continuity.

## Final video
Use `CF-VID-02`, the two-stage final-quality path with official upscalers. The 2× spatial upscale is mandatory. Smoke workflow templates are forbidden.

## Post
Use `CF-POST-01` for exact-duration trim, aspect-ratio conversion, crop/pad, audio mux, loudness, transitions, final encode and probe validation. Never submit directly to ComfyUI `/prompt`.
