# Model Accordion v1.5

The selected project is the primary user-facing unit.

The MODELS panel is now a vertical accordion instead of a wide table.

Each model card shows:
- model name;
- total tokens;
- percentage of project tokens to 0.01%;
- a full-width progress bar.

Clicking a model expands only that model's reasoning-depth history.

Each reasoning-depth row shows:
- reasoning depth;
- total tokens;
- percentage of that model to 0.01%;
- a full-width progress bar;
- percentage of project tokens;
- cached tokens / cached-input percentage;
- new-input tokens / new-input percentage.

Numeric values are above/below the bars rather than attached to the right edge,
so a narrow floating window remains readable.

The current model is expanded by default. Other models remain collapsed until
the user opens them.

Quota percentages remain provider VERIFIED. Model/effort percentages are local
token shares and are not presented as provider quota percentages.
