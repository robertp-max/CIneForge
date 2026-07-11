# Storyboard Data Model

The planning hierarchy is `projects -> stories -> chapters -> scenes -> shots`, with UUID identities and unique ordered indexes at each hierarchy level. Display labels such as CH01, SC01, SH01 and A/B/C are presentation-only.

Phase A adds Characters, Planning Media Assets, Character Reference Assets, Voice Profiles, Shot Characters, Shot Narrations, Shot Prompt Packages, Shot Model Recommendations, Storyboard Versions, Provider Profiles, and Task Provider Assignments. Planning assets use managed URIs and are intentionally separate from `generated_assets`, which remains tied to completed render output.

Continuity links are validated in the service layer: no self-reference, cross-story source, non-preceding source, or cycle.
