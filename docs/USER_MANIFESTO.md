# GitHub Tuner - User Manifesto

## User Vision

This program should operate according to the following principles:

### 1. User Only Defines Research Topics
- **User role:** Define missions (research topics)
- **Program role:** Search strategies, parameters, tactics - all automated

### 2. Program Must Self-Adapt
- If a search tactic isn't working → automatically switch tactics
- If star thresholds are inefficient → automatically adjust
- If results are irrelevant → try different keywords

### 3. Must Remember Its Experiences
- Record successes/failures in each research cycle
- Learn which tactics work for which missions
- Continuously improve its performance

### 4. Human Intervention Must Be Minimal
- User should only intervene to **review findings**
- User should only intervene for **critical decisions**
- Background optimizations must be fully autonomous

### 5. Smart Algorithms, Not Just Filters
- Great filtering ≠ great algorithm
- Different search angles (keyword rotation, time-based, trending, etc.)
- Different timing strategies
- Tactical diversity

### 6. Minimum AI Usage, Maximum Efficiency
- Don't use AI for routine tasks (embedding, basic filtering)
- AI should only activate when truly necessary
- When inefficiency is detected, AI should intervene intelligently

---

## Technical Requirements

To realize this manifesto:

1. **TacticEngine:** Pool of different search tactics
2. **ExperienceMemory:** Record tactic performance
3. **AdaptiveThresholds:** Dynamic threshold adjustment
4. **AutonomousOptimizer:** Self-modifying strategy

---

*This manifesto documents how the user wants to use the program.*
*All development should align with these principles.*
