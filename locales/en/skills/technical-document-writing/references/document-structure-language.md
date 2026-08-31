# Structure, Language, Tables, Code, and Diagrams

## Contents

- 4. Structural Principles
- 5. Language and Expression
- 6. Tables, Lists, Code, and Diagrams

## 4. Structural Principles

### 4.1 Minimum Sufficient Structure

Cover the information required for the current purpose without mechanically including every possible section.

A common baseline is:

1. summary or executive summary;
2. background and current state;
3. problem and goals;
4. scope and non-goals;
5. design or analysis;
6. impact and risks;
7. implementation or validation;
8. rollback, monitoring, and acceptance;
9. unverified items and follow-up.

A simple note may contain only background, conclusion, and operating steps. A production design also requires risks, stopping conditions, rollback, and validation.

### 4.2 Heading Hierarchy

- Use the level-one heading only for the document topic.
- Use level-two headings for major decisions or work phases.
- Use level-three headings for specific questions within a section.
- Avoid skipping heading levels.
- Avoid a heading followed by only one sentence.
- Avoid fragmenting a document into excessive peer headings.

### 4.3 Summary

A summary should quickly answer:

- Why is this document needed?
- What is the most important current fact?
- What is the recommendation or conclusion?
- What are the impact and primary risks?
- What action or decision comes next?

Do not introduce conclusions in the summary that the body does not support.

### 4.4 Scope and Non-Goals

Complex tasks must state:

- covered systems, modules, environments, and data;
- explicitly excluded work;
- premises and external dependencies;
- interfaces, business definitions, or legacy compatibility that must not change.

This prevents a document from being misread as broader authorization or commitment.

---

## 5. Language and Expression

### 5.1 Default Style

Use by default:

- the current package language;
- formal, professional, and neutral wording;
- direct, concrete, actionable statements;
- facts and decisions as the organizing center;
- accurate domain terminology;
- no slogans, emotional attribution, or marketing language.

### 5.2 Avoid Vague Wording

Avoid standalone phrases such as:

- “optimize”;
- “improve performance”;
- “enhance functionality”;
- “resolve the problem”;
- “ensure stability”;
- “improve the user experience”;
- “handle as needed”;
- “monitor later.”

State the target, action, validation, and boundary. For example:

> Replace per-row queries inside the loop with one batch query, then verify query count and index usage through targeted API tests and the SQL execution plan.

### 5.3 Neutral Language

When discussing organizations, people, responsibility, or evaluation:

- describe facts, processes, and impact without emotional attribution;
- do not assign responsibility without evidence;
- distinguish system, process, configuration, and operator causes;
- prefer “current design,” “existing implementation,” and “current scope” over disparaging language.

### 5.4 Technical Terminology

- Expand or briefly explain abbreviations on first use when helpful.
- Prefer established project terms over generic substitutes.
- Use one name consistently for each concept.
- Do not confuse or misuse Java, Python, database, message-queue, or AI terminology.

---

## 6. Tables, Lists, Code, and Diagrams

### 6.1 Tables

Tables work well for:

- comparing alternatives;
- module responsibilities and boundaries;
- API and database fields;
- risk matrices;
- phases, milestones, and acceptance criteria;
- environment, configuration, and deployment differences;
- test results and evidence inventories.

When a table has too many columns or long cells, replace it with sections to avoid unreadable horizontal layouts.

### 6.2 Lists

- Keep list items at the same grammatical form and level of detail.
- Express one complete action or judgment per item.
- Use numbered lists for ordered dependencies.
- Use bullets for unordered categories.
- Do not replace normal prose with deeply nested lists.

### 6.3 Code and Commands

Code, SQL, configuration, and commands must:

- match the current version and environment;
- use code fences with the correct language label;
- state environment, prerequisites, and risk;
- pair production writes with a query, backup, impact scope, and rollback;
- exclude real passwords, tokens, keys, cookies, and private data;
- never be described as executed when they are examples only.

### 6.4 Mermaid

Use Mermaid for:

- system architecture;
- service call chains;
- business flows;
- state machines;
- sequences;
- deployment topology;
- data flow.

Constraints:

- use the same node names as the body;
- label system boundaries and external dependencies;
- do not add services absent from the source material;
- split complex diagrams into focused diagrams;
- explain critical and exceptional paths after the diagram;
- ensure the Mermaid syntax parses.

---
