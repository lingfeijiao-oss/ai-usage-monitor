# Visual Usage Bars v1.4

The compact account quota bar remains provider VERIFIED.

The expanded model panel is project-token analytics and is intentionally
separate from provider quota billing.

## Model row

Progress length:

`model total tokens / project total tokens`

Suffix:

`<token count> · Project <xx.xx%>`

## Reasoning-effort row

Progress length:

`effort total tokens / model total tokens`

Suffix:

`<token count> · Project <xx.xx%> · Model <xx.xx%>`

## Cached / New row

The thin two-segment bar uses input tokens as its denominator:

`Cached % = cached input / input`

`New % = new input / input`

Suffixes include token counts and percentages to two decimal places.

## Current execution

The currently observed model and reasoning effort are highlighted. When
`turn_context` changes, the top compact view continues to show `MODEL SWITCH`
and the expanded panel moves the CURRENT marker.

## Provenance

- Top quota: VERIFIED
- Project/model/effort token bars: LOCAL_OBSERVED
- Project/model percentages: derived exactly from LOCAL_OBSERVED token totals
- They are not represented as provider quota percentages.
