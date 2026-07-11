# Provider Routing Specification

A Provider Model is a planning/reasoning model. A Generation Model is a ComfyUI image/video model. A Workflow Template is a validated ComfyUI API workflow. These terms are never collapsed into an ambiguous “model”.

Provider Profiles hold identifier, model ID, capabilities, privacy class, and a configuration reference only—never secrets, tokens, passwords, command strings, or arbitrary executable arguments. This release stores proposals for human review; it implements no vendor calls, local CLI execution, or provider-authored database mutation.
