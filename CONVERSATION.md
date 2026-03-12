this is the very first prompt

lets create a project md and a plan md file for this project, i first tell you what i want and you keep asking questions until we have a full understand of what the project is and we need to do.

the project called 12, its a subsystem in my bigger application, the main app called tracer 42 and it collect all the flights in middle east (in the future more) airspace and analyze them, mainly to find and alert on anomalies and dengures events, the system have a lot of features and options but the main thing is to find and alert anomalies in real time. 
we have a big postgress db full with flights metadata and courses also a anomaly reports, i already created a lot of logics and functions to analyze planes and behaviors, i will provide all off them after in a file, the main mission here is to create a system that is very generic that can query the db and activate the functions on planes and groups of planes and return stractured result on data, i want a ui that have a list cubes that you can choose from each gets some type of data do something then returns some type of data,each qube have its own options and configerable params, the idea is to have the user to build his own logics and apply to our database and analysist, for example: the user takes a qube for all the flights in middle east then inside the qube filters for all the flights in the last 1 day that landed in israel, then connects the cude data with a line to another cude that is for analyze course i quality and in that qubes he fills a parameter named quality type then enter jamming so he want to see all the flights that landed in israel that had a jamming. thats just one example of many but the idea is clear, create a generic system for the user to use program developed functions and data sources to answer questions just by adding cubes and connecting outputs and inputs, in this example the quality cube just takes the flight ids as a list then query the db and analyze them but that is not relevent, first we need to create a schema that all the cubes need to enforce, then add a way to edit delete and add cubes then create the ui to present it, you dont need to implement the functions just the infrastructre 
# Project 12 — Planning Session Transcript

This document records the full planning conversation that shaped the design of Project 12.
Every question, option, and decision is preserved so any reader can trace how the design was derived.

---

## Original Project Description

> The project is called **12**. It's a subsystem in my bigger application. The main app is called
> **Tracer 42** and it collects all the flights in Middle East (in the future more) airspace and
> analyzes them, mainly to find and alert on anomalies and dangerous events. The system has a lot
> of features and options but the main thing is to find and alert anomalies in real time.
>
> We have a big Postgres DB full with flights metadata and courses, also anomaly reports. I already
> created a lot of logics and functions to analyze planes and behaviors (I will provide all of them
> later in a file).
>
> The main mission here is to create a system that is very generic — one that can query the DB and
> activate the functions on planes and groups of planes and return structured results on data.
>
> I want a UI that has a list of cubes that you can choose from. Each cube gets some type of data,
> does something, then returns some type of data. Each cube has its own options and configurable
> params. The idea is to have the user build his own logics and apply them to our database and
> analysis.
>
> **Example:** The user takes a cube for "all the flights in Middle East", then inside the cube
> filters for all the flights in the last 1 day that landed in Israel. Then he connects the cube's
> data with a line to another cube that is for "analyze course quality", and in that cube he fills
> a parameter named "quality type" and enters "jamming" — so he wants to see all the flights that
> landed in Israel that had a jamming event. That's just one example of many, but the idea is
> clear: create a generic system for the user to use developer-built functions and data sources to
> answer questions just by adding cubes and connecting outputs and inputs.
>
> In this example the quality cube just takes the flight IDs as a list then queries the DB and
> analyzes them, but that is not relevant right now. First we need to create a schema that all the
> cubes need to enforce, then add a way to edit, delete, and add cubes, then create the UI to
> present it. You don't need to implement the functions — just the infrastructure.

---

## Round 1 — Foundational Questions

### Q1: Tech Stack

**Question:** What tech stack do you want for this project? (Frontend framework + Backend)

| Option | Description |
|--------|-------------|
| A | React (TypeScript) + Node.js/Express backend |
| B | React (TypeScript) + Python/FastAPI backend |
| C | Vue.js + Node.js backend |
| D | Next.js (full-stack, TypeScript) |
| E | Other (I'll specify) |

**Answer:** **B — React (TypeScript) + Python/FastAPI backend**

---

### Q2: Canvas Library

**Question:** For the visual cube/node editor canvas, which approach do you prefer?

| Option | Description |
|--------|-------------|
| A | React Flow (most popular node-based UI library, drag & drop, connections) |
| B | Custom canvas (HTML5 Canvas / SVG from scratch) |
| C | No preference — pick the best fit |

**Answer:** **A — React Flow**

---

### Q3: Execution Model

**Question:** How should a workflow (chain of cubes) execute?

| Option | Description |
|--------|-------------|
| A | User builds the flow, then clicks "Run" to execute the whole pipeline |
| B | Each cube executes as soon as its inputs are connected and ready (live/reactive) |
| C | Both modes — manual run + option for live/reactive |
| D | Not sure yet — suggest what's best |

**Answer:** **A — Run button (user builds the flow, then clicks "Run")**

---

### Q4: Persistence

**Question:** Should workflows (cube arrangements + connections) be saved and loaded?

| Option | Description |
|--------|-------------|
| A | Yes — save to the existing Postgres DB |
| B | Yes — save as JSON files / export-import |
| C | Yes — both DB and file export/import |
| D | Not in the first version, add later |

**Answer:** **Yes — save to DB only when the user explicitly saves; load previously saved workflows on demand.**

---

## Round 2 — Cube System Design

### Q5: Cube Categories

**Question:** Which cube categories do you envision? (select all that apply)

| Option | Description |
|--------|-------------|
| A | Data Source cubes — query flights from DB (by region, time, airport, etc.) |
| B | Filter cubes — filter/narrow down flight lists by criteria |
| C | Analysis cubes — run analysis functions (quality, anomaly detection, etc.) |
| D | Aggregation cubes — group, count, statistics on data |
| E | Output/Display cubes — show results as table, chart, map, alert |
| F | All of the above + more I'll define later |

**Answer:** **A, B, C, D, E — All five categories selected**

---

### Q6: Data Types Between Cubes

**Question:** What data types flow between cubes (on the connection lines)?

| Option | Description |
|--------|-------------|
| A | Mainly flight ID lists + metadata objects |
| B | Generic JSON — each cube defines its own input/output schema |
| C | Typed system — predefined types like FlightList, AnomalyReport, CourseData, etc. |
| D | Not sure — suggest what's best |

**Answer:** **B — Generic JSON (each cube defines its own input/output schema)**

---

### Q7: Cube I/O Cardinality

**Question:** Can a cube have multiple inputs and/or multiple outputs?

| Option | Description |
|--------|-------------|
| A | Single input, single output |
| B | Multiple inputs, single output |
| C | Single input, multiple outputs |
| D | Multiple inputs, multiple outputs (most flexible) |

**Answer:** **D — Multiple inputs, multiple outputs**

---

### Q8: Connection Validation

**Question:** Should the system validate connections between cubes?

| Option | Description |
|--------|-------------|
| A | Yes, strict type validation — only compatible cubes can connect |
| B | Warn but allow — show warning for incompatible types but let user connect |
| C | No validation — any cube can connect to any cube |

**Answer:** **B — Warn but allow**

---

## Round 3 — Parameter-Level Connections

### Q9: Confirm Connection Model

**Question:** Let me confirm I understand the connection model correctly:

1. Each cube has NAMED input params (left side) and NAMED output params (right side)
2. A user drags a line from a specific OUTPUT param of cube A to a specific INPUT param of cube B
3. Each cube also has a special "Full Result" output port that bundles ALL outputs together
4. An input param can be marked as "accepts full result" so you can connect a Full Result output to it

Is this correct?

| Option | Description |
|--------|-------------|
| A | Yes, exactly |
| B | Mostly — I'll clarify |
| C | No, let me re-explain |

**Answer:** **A — Yes, exactly**

---

### Q10: Parameter Type System

**Question:** Each parameter (input/output) has a data type. What type system do you want for parameters?

| Option | Description |
|--------|-------------|
| A | Basic types: string, number, boolean, list_of_strings, list_of_numbers, JSON object |
| B | Domain types: flight_id_list, course_data, anomaly_report, coordinates, etc. + basic types |
| C | Flexible: each cube defines its own param types as strings, loose matching |
| D | Suggest what's best |

**Answer:** **A — Basic types (string, number, boolean, list_of_strings, list_of_numbers, json_object)**

---

### Q11: Manual Parameter Values

**Question:** Can a user also manually fill in a parameter value (not just connect a line)? For example, typing "jamming" into a "quality_type" input param instead of connecting it from another cube.

| Option | Description |
|--------|-------------|
| A | Yes — params can be either connected via line OR manually filled by user |
| B | No — params can only be filled by connections from other cubes |
| C | Depends on the param — some are connectable only, some are manual only, some are both |

**Answer:** **A — Yes, params can be either connected via line OR manually filled by user**

---

### Q12: Config Params vs Connection Params

**Question:** You mentioned cubes have configurable params. Are "configuration params" (like selecting "jamming" from a dropdown) DIFFERENT from "connection params" (inputs that receive data via lines)?

| Option | Description |
|--------|-------------|
| A | Same thing — a param can either be filled manually or via connection |
| B | Separate — cubes have config fields (inside the cube UI) AND connection ports (on the sides) |
| C | Not sure — suggest the best approach |

**Answer:** **A — Same thing (a param can either be filled manually or via connection)**

---

## Round 4 — UI & Remaining Details

### Q13: Cube Registry

**Question:** How are new cube types added to the system? (the catalog of available cubes)

| Option | Description |
|--------|-------------|
| A | Developer adds them in code (Python backend) — no UI for creating cube types |
| B | Admin UI to register new cube types (name, params, function reference) |
| C | Both — code for the function logic, admin UI to register/configure the metadata |

**Answer:** **A — Developer adds them in code (Python backend)**

---

### Q14: Results Display

**Question:** When a workflow finishes running, how should results be displayed?

| Option | Description |
|--------|-------------|
| A | Only in Output/Display cubes — user must add one to see results |
| B | Each cube shows its own results (expandable panel on the cube itself) |
| C | Both — each cube shows its result + dedicated output cubes for richer display |
| D | Side panel — click any cube to see its results in a detail panel |

**Answer:** **C — Both (each cube shows its result + dedicated output cubes for richer display)**

---

### Q15: UI Layout

**Question:** What should the main UI layout look like?

| Option | Description |
|--------|-------------|
| A | Full-screen canvas with a collapsible sidebar for the cube catalog |
| B | Left panel = cube catalog, Right = canvas |
| C | Top = toolbar + cube catalog, Bottom = full-width canvas |
| D | No preference — design something good |

**Answer:** **A — Full-screen canvas with a collapsible sidebar for the cube catalog**

---

### Q16: Multiple Workflows

**Question:** Can a user have multiple saved workflows (flows/pipelines)?

| Option | Description |
|--------|-------------|
| A | Yes — a list/dashboard of saved workflows they can open, rename, delete |
| B | No — just one active workspace at a time |
| C | Yes but simple — just save/load by name, no fancy dashboard |

**Answer:** **A — Yes, a list/dashboard of saved workflows (open, rename, delete)**

---

## Final — Conversation Export

### Q17: Conversation File Location

**Question:** Where should I save the conversation summary file?

| Option | Description |
|--------|-------------|
| A | CONVERSATION.md in the project root (alongside PROJECT.md and PLAN.md) |
| B | docs/conversation.md in a docs folder |
| C | Other location — I'll specify |

**Answer:** **A — CONVERSATION.md in the project root**

---

## Summary of All Decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Tech stack | React (TypeScript) + Python/FastAPI |
| 2 | Canvas library | React Flow |
| 3 | Execution model | Run button |
| 4 | Persistence | Save/load to PostgreSQL DB on user action |
| 5 | Cube categories | Data Source, Filter, Analysis, Aggregation, Output/Display |
| 6 | Data types between cubes | Generic JSON |
| 7 | I/O cardinality | Multiple inputs, multiple outputs |
| 8 | Connection validation | Warn but allow |
| 9 | Connection model | Parameter-level (named input/output params + Full Result port) |
| 10 | Parameter types | Basic: string, number, boolean, list_of_strings, list_of_numbers, json_object |
| 11 | Manual values | Yes — any input param can be filled manually or via connection |
| 12 | Config vs connection params | Same thing — unified param model |
| 13 | Cube registry | Developer adds in code (no admin UI) |
| 14 | Results display | Both per-cube results + dedicated output cubes |
| 15 | UI layout | Full-screen canvas + collapsible sidebar |
| 16 | Multiple workflows | Yes — dashboard with list, open, rename, delete |
