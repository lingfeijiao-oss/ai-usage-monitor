# Architecture

## Core

Provider-independent services:

- Usage Engine
- Quota Engine
- Token Engine
- Cost Engine
- Forecast Engine
- Alert Engine

## Provider adapters

Each provider adapter should expose capabilities such as:

- account metadata
- token usage
- quota/rate-limit state
- reset time
- cost
- live updates, when officially available

The core must not assume every provider supports every capability.

## Metric provenance

Every metric must carry one of:

- VERIFIED — returned by an official/local provider interface
- OBSERVED — measured locally from execution
- ESTIMATED — calculated from historical observations
- UNSUPPORTED — provider does not expose the metric
