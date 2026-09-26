# Site Corpus Search and Decode Stories

## EPIC: Site Corpus Decode Workflow

### User Story

As a researcher,  
I want to discover usable corpora for a site, select and import a corpus, decode it into structured transform information, and display the results,  
so that I can move from an archaeological site to a usable transform dataset through one connected workflow.

### Epic Flow

```text
SITE
  ↓
CORPUS SEARCH ENGINE PROCESS
  ↓
CORPUS SELECTION PROCESS
  ↓
CORE SITE CORPUS IMPORT
  ↓
DECODE PROCESS
  ↓
DISPLAY PROCESS
```

### Acceptance Criteria

- The user can begin with a site.
- The system can find consumable corpus options for that site.
- The user can select a corpus.
- The selected corpus is linked to the site.
- The corpus can be imported through its supported access path.
- The imported corpus can be handed to the Decode Agent.
- The Decode Agent can populate an independent transform dataset.
- The resulting decoded information can be displayed in the context of the site.

---

## STORY 1: Corpus Search Engine Process

### User Story

As a researcher,  
I want the system to find available corpora for a site and return only sources that can actually be consumed,  
so that I can choose from usable research material.

### Process

```text
CORPUS SEARCH ENGINE PROCESS

SITE
  ↓
find candidate sources
  ↓
check Source Registry
  ↓
KNOWN VALID ─────→ use
KNOWN INVALID ───→ skip
UNKNOWN ─────────→ validate
                     ↓
                 persist result
  ↓
search valid sources for corpus
  ↓
return consumable corpus options
```

### Acceptance Criteria

- The process accepts a site as input.
- Candidate corpus sources are discovered for the site.
- Every candidate source is checked against the Source Registry.
- Known valid sources are used without unnecessary revalidation.
- Known invalid sources are skipped.
- Unknown sources are validated.
- New validation results are persisted.
- Only consumable corpus options are returned.
- Each returned option includes enough source and access information for selection.

---

## STORY 2: Corpus Selection Process

### User Story

As a researcher,  
I want to select one or more returned corpus options,  
so that the system knows exactly which source material should be imported for the site.

### Process

```text
CORPUS SELECTION PROCESS

USER SELECTS CORPUS
      ↓
retrieve selected source record
      ↓
link selected source to site
      ↓
pass source API / access path
      ↓
INTAKE AGENT
```

### Acceptance Criteria

- The user is shown the valid corpus options returned by the search process.
- The user can select a corpus.
- The selected source record is retrieved.
- The source is linked to the current site.
- The source API or access path is preserved.
- The selected corpus is handed to the Intake Agent.
- No decoding occurs during selection.

---

## STORY 3: Core Site Corpus Import

### User Story

As a researcher,  
I want the selected corpus to be imported and linked to its site,  
so that the source material is available for decoding.

### Process

```text
CORE SITE CORPUS IMPORT

SELECTED CORPUS
      ↓
INTAKE AGENT
      ↓
consume source API / access path
      ↓
import corpus
      ↓
link imported corpus to site
      ↓
make corpus available to Decode Agent
```

### Acceptance Criteria

- The Intake Agent receives the selected source and site association.
- The Intake Agent uses the supplied API or access path.
- The corpus is consumed from the selected source.
- Imported corpus material remains linked to the site.
- Source provenance is retained.
- Successfully imported material becomes available to the Decode Agent.
- Import failure does not produce a decoded dataset.

---

## STORY 4: Decode Process

### User Story

As a researcher,  
I want the Decode Agent to consume an imported corpus and extract transforms into an independent dataset,  
so that the source material becomes structured transform knowledge.

### Process

```text
DECODE PROCESS

SOURCE CORPUS
  ↓
consume data
  ↓
extract observations
  ↓
identify transforms
  ↓
normalize transforms
  ↓
link transforms
  ↓
write results to independent dataset
  ↓
was anything new learned?
  ├─ YES → recurse
  └─ NO  → closure
```

### Acceptance Criteria

- The Decode Agent receives an imported site corpus.
- Source data is consumed without making the dataset part of the decoder.
- Observations are extracted.
- Transforms are identified.
- Equivalent transforms are normalized.
- Related transforms are linked.
- Results are written to an independent persistent dataset.
- New knowledge can trigger another decode pass.
- Decoding continues until no additional information can be extracted.
- Closure ends the decode process.

---

## STORY 5: Site Decode Display

### User Story

As a researcher,  
I want to view the decoded transform information associated with a site,  
so that I can inspect what was learned from the selected corpus.

### Process

```text
DISPLAY PROCESS

SITE
  ↓
retrieve linked corpus
  ↓
retrieve transform dataset
  ↓
resolve decoded information for site
  ↓
display transforms
  ↓
display source provenance
```

### Acceptance Criteria

- The display begins from a selected site.
- The system retrieves the corpus linked to that site.
- The system retrieves decoded transform records associated with that corpus.
- Transforms are displayed in the context of the site.
- Relationships between transforms can be displayed.
- Source provenance remains available with decoded information.
- Display logic does not modify the corpus or transform dataset.

---

## End-to-End Story Relationship

```text
EPIC: SITE CORPUS DECODE WORKFLOW
              │
              ├── STORY 1
              │   Corpus Search Engine
              │
              ├── STORY 2
              │   Corpus Selection
              │
              ├── STORY 3
              │   Core Site Corpus Import
              │
              ├── STORY 4
              │   Decode Process
              │
              └── STORY 5
                  Site Decode Display
```
