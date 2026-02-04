# **Technical Feasibility Study: Integration of EVE Online Fitting Engines for Automated Advisory Systems**

> **[SUPERSEDED]** This feasibility study's recommendations have been superseded by the spike findings. EOS is now **vendored** at `src/aria_esi/_vendor/eos/` and data preparation is handled by `aria-esi eos-seed`. See `dev/spikes/eos-integration-FINDINGS.md` for the current architecture.

## **1\. Executive Overview and Architectural Context**

The development of a sophisticated advisory application for EVE Online represents a significant challenge in domain modeling. EVE Online is colloquially described as "spreadsheets in space," but this nomenclature understates the complexity of its underlying simulation engine, known internally at CCP Games as "Dogma." For a Python-based application intended to facilitate advice via a Large Language Model (LLM) context—specifically leveraging Claude Code Skills or the Model Context Protocol (MCP)—the fidelity of the underlying simulation is paramount. The system must not merely look up static statistics; it must dynamically simulate the interaction of thousands of variables, ranging from ship hull attributes and module meta-levels to character skills and environmental weather effects.

The user’s query posits a choice between two primary open-source candidates managed by the pyfa-org organization: **Pyfa** (Python Fitting Assistant) and **EOS** (Engine of Statistics). Research and subsequent spike investigations have clarified that this is not a choice between two competing applications, but rather a distinction between a graphical user interface and its underlying calculation kernel. **Crucially, the standalone kernel has diverged from the application's data format, making them incompatible.**

### **1.1. The Ecosystem of pyfa-org**

The open-source fitting ecosystem for EVE Online is dominated by the pyfa-org GitHub organization. Understanding the divergence between components is a prerequisite for architectural selection.

| Component | Repository | Primary Function | Technical Stack | Relevance to User |
| :---- | :---- | :---- | :---- | :---- |
| **Pyfa** | pyfa-org/Pyfa | GUI, Session Management, Update Orchestration | Python 3, wxPython, SQLite | **High**: The "Source of Truth" for both calculation logic and data. |
| **EOS (Internal)** | pyfa-org/Pyfa/eos | Mathematical Engine | Python 3 (Library) | **Critical**: The engine version compatible with `eve.db`. |
| **EOS (Standalone)** | pyfa-org/eos | Abandoned/Divergent Engine | Python 3 (Library) | **Deprecated**: Incompatible with modern `eve.db` schemas. |
| **Phobos** | pyfa-org/Phobos | Data Mining | Python 2.7, Reverence | **Moderate**: Source of raw data, but difficult to run. |

The analysis indicates that while **EOS** is the explicit library designed for calculating ship statistics 1, the standalone repository is significantly outdated (July 2025 vs Jan 2026). More importantly, the **Standalone EOS** engine expects a different data schema (Phobos JSON) than the **Pyfa EOS** engine (Pyfa-flavored `eve.db`).

### **1.2. The "Dogma" Challenge in Headless Environments**

For an advisory application managed by Git and utilizing Claude MCP, the requirement is for a "headless" operation—a system that runs without a graphical window.

The native EVE Online client performs these calculations locally. Third-party tools like Pyfa replicate this behavior by implementing a graph-based modifier system. This system allows for:

* **Dynamic Attributes:** Attributes that change based on state.
* **Projected Effects:** External influences from fleet members.
* **Stacking Penalties:** The non-linear diminishing returns applied when multiple modules affect the same attribute.4

The complexity of correctly implementing these mechanics from scratch is prohibitive. Therefore, the integration of an existing engine is the only viable path. The core finding of the technical spike is that **the user must integrate the EOS library specifically from the pyfa-org/Pyfa repository**, as the standalone library cannot read the community-maintained `eve.db` database.

### **1.3. Integration with Claude Code Skills and MCP**

The Model Context Protocol (MCP) requires tools to be deterministic and structured. Integrating EOS allows the Python application to expose a "Tool" to Claude—for example, `calculate_ship_stats(fit_id)`. When Claude invokes this tool, the Python backend utilizes EOS to simulate the ship and returns a JSON object containing the derived statistics. This allows the LLM to provide advice based on *actual* applied performance rather than generic heuristics.

## ---

**2. The Engine of Statistics (EOS): Architecture and Implementation**

To effectively utilize EOS in a custom application, one must understand its internal architecture. It is not merely a calculator; it is a state machine that models the relationships between game entities.

### **2.1. The Graph-Based Modifier System**

At the heart of EOS is a dependency graph. Unlike a spreadsheet which calculates cells based on static formulas, EOS builds a graph where nodes represent **Items** (Ships, Modules, Skills) and edges represent **Effects**.

#### **2.1.1. Attributes**

Every entity in EVE Online consists of a collection of attributes. These are defined in the `dgmTypeAttributes` table of the database.5

* **Base Attributes:** Static values defined by CCP.
* **Calculated Attributes:** Values derived from the interaction of base attributes and modifiers.

EOS maps these attributes to Python objects. When a query is made for a specific attribute, the engine traverses the modifier graph to compute the final value.

#### **2.1.2. Effects and Modifiers**

Effects are the "verbs" of the Dogma system. They describe *how* one item changes another.

* **Pre-Assignment vs. Post-Assignment:** Effects have strict timing.
* **Scope:** Effects have scopes (Item, Ship, Character, Gang).

The user's application does not need to manually define these. By instantiating an EOS `Fit` object, the library automatically loads the relevant effects from the `eve.db` database.

### **2.2. State Management**

For an advisory tool, state is a critical variable. A fit performs differently depending on whether modules are active, overheated, or loaded with specific ammunition.

#### **2.2.1. Module States**

EOS defines several states for items 1:

* **Offline:** The module is fitted but inactive.
* **Online:** The module is active. Passive effects are applied.
* **Active:** The module is cycling. Active effects are calculated.
* **Overloaded:** The module is running hot.

The Python application can programmatically toggle these states.

#### **2.2.2. Drone Management**

Drones are unique entities in EVE. They are items loaded into a "Drone Bay" but operate as independent ships when launched.

* **Bandwidth:** EOS enforces bandwidth restrictions.
* **Control:** The application can simulate different drone sets to optimize DPS.1

### **2.3. Handling Stacking Penalties**

One of the most complex mathematical aspects of EVE Online is the stacking penalty. When multiple modules affect the same attribute, the magnitude of the effect is reduced for each subsequent module.

$$Penalty \= e^{-(n-1)^2 / 7.1289}$$

EOS correctly identifies the `stackingPenaltyGroup` of each effect. If the advisory application detects a user fitting four ballistic control systems, it can use EOS to calculate the marginal utility of the fourth module.

### **2.4. Python Implementation Pattern**

To integrate EOS, the application will follow a specific pattern of instantiation.

#### **2.4.1. The Source Manager**

The entry point for EOS is the data source.

```python
from eos.source import SourceManager
source_manager = SourceManager(database_path='staticdata/eve.db')
```

This manager handles the SQL queries to the SQLite database.

#### **2.4.2. The Fit Object**

The Fit object is the container for the simulation.

```python
from eos.fit import Fit
fit = Fit(source_manager)
```

#### **2.4.3. Item Injection**

Items are added to the fit by ID.

```python
# Fetch Item Definitions
ship_item = source_manager.get_item(type_id=626) # Vexor
module_item = source_manager.get_item(type_id=2048) # Structure module

# Assign to Fit
fit.ship = Ship(ship_item)
fit.modules.add(Module(module_item))
```

#### **2.4.4. Calculation and Output**

Triggering the calculation updates the graph.

```python
fit.calculate()
stats = fit.stats
```

## ---

**3. The Data Pipeline: Phobos, Static Data, and eve.db**

The engine is only as good as its data. In the EVE Online ecosystem, data volatility is high. CCP Games frequently balances ship attributes. The user's application requires a robust pipeline to maintain synchronization with the live game.

### **3.1. Phobos: The Data Miner**

The tool responsible for generating the data used by EOS is **Phobos**.6

* **Function:** Phobos connects to the EVE Online client's installation directory to extract data.
* **Incompatibility Warning:** Phobos generates data in a format suitable for the *original* EOS, but the Pyfa team post-processes this data into a modified `eve.db` schema. This modified schema is what the Pyfa-internal EOS engine expects.

### **3.2. The eve.db Schema**

The output of Phobos is processed into a SQLite database, universally referred to as `eve.db`. The Pyfa version of this database includes additional tables and modified columns that are **required** for the current calculation engine to function without error.

| Table Name | Description |
| :---- | :---- |
| invTypes | Definitions of all items in the game. |
| dgmTypeAttributes | Links items to their base attributes. |
| dgmTypeEffects | Links items to their effects. |
| dgmEffects | Definitions of effect logic. |

### **3.3. Database Update Strategy**

For the user's application, managing the `eve.db` update cycle is a critical non-functional requirement.

#### **3.3.1. Strategy A: Self-Hosted Phobos (Strongly Discouraged)**

* **Process:** Running Phobos manually.
* **Risks:** High complexity, Python 2.7 requirements, and most importantly, **schema mismatch**. Unless the user also runs Pyfa's database migration scripts (which are complex and undocumented), the resulting database will crash the engine.
* **Verdict:** **Do Not Use.**

#### **3.3.2. Strategy B: Pyfa Release Consumption (Mandatory)**

* **Process:** The pyfa-org team releases updates shortly after every major EVE patch. These releases contain a compiled `eve.db`.
* **Implementation:** The user's application should include a scraper or GitHub API client that monitors `pyfa-org/Pyfa/releases`.7
  * When a new release is detected, the script downloads the asset (often `pyfa-vX.Y.Z-src.zip`).
  * It extracts the `eve.db` file from the `staticdata` directory.
* **Advantages:** Ensures the database schema is perfectly compatible with the EOS library version being used (as both come from the same release tag).

## ---

**4. Entity Modeling: Ships, Modules, and Subsystems**

(This section remains unchanged as the modeling logic is consistent within the Pyfa ecosystem.)

### **4.1. Ships and Hull Bonuses**
Ships are containers defined by stats, Role Bonuses, and Skill Bonuses.

### **4.2. Tech 3 Cruisers and Subsystems**
Tech 3 Cruisers rely on Subsystems to define their slots and stats. EOS validates these configurations.

### **4.3. Modules: Mutated and Abyssal**
EOS allows for the injection of **Runtime Attributes** to simulate Mutaplasmid effects (e.g., `module.attributes = 10500` for range).

### **4.4. The Resource Economy: CPU, PG, and Calibration**
EOS calculates load vs output and enforces hard stops for fitting validity.

## ---

**5. Character Modeling: Skills, Implants, and Boosters**

(This section remains unchanged.)

## ---

**6. Environmental and Projected Effects**

(This section remains unchanged.)

## ---

**7. Comparative Analysis: Advantages and Disadvantages**

With the architecture and mechanics understood, we can definitively compare the options for the user's specific use case.

### **7.1. Pyfa (The Application & Internal Engine)**

**Advantages:**
*   **Accuracy:** The only engine version guaranteed to calculate 2026-era mechanics correctly.
*   **Data Integrity:** Its `eve.db` is community-verified and syncs perfectly with the engine code.
*   **Active Maintenance:** Updated days after every game patch.

**Disadvantages:**
*   **Extraction:** Requires using `git` magic to extract just the library folder, or cloning the full repo.

### **7.2. EOS (The Standalone Library)**

**Advantages:**
*   **Cleanliness:** Isolated repository structure.

**Disadvantages:**
*   **Schema Incompatibility:** Cannot read the modern `eve.db` used by Pyfa.
*   **Staleness:** Codebase lags behind the live game by months.
*   **Silent Failures:** May calculate stats incorrectly for new ships or modules without throwing errors.

## ---

**8. Integration Roadmap and Architectural Decisions**

Based on the spike findings, the following architectural decisions have been finalized.

### **8.1. Decision 1: Dependency Management (Pyfa Repo is Source)**

> **[SUPERSEDED]** EOS is now vendored directly at `src/aria_esi/_vendor/eos/` (commit `c2cc80fd`). The git subdirectory approach described below was not implemented.

The project **must** use the EOS library located *inside* the Pyfa repository. The standalone repository is rejected due to data incompatibility.

**Action:**
1. Pin Pyfa/EOS as a Git dependency in `pyproject.toml` using `uv`, pointing specifically to the subdirectory.

   ```toml
   [project]
   dependencies = [
     "pyfa-eos @ git+https://github.com/pyfa-org/Pyfa.git@v2.60.1#subdirectory=eos",
   ]
   ```

2. Treat the version as part of the system contract.

### **8.2. Decision 2: Deterministic Data Pipeline via Releases**

> **[SUPERSEDED]** The `eve.db` approach was not implemented. Instead, `aria-esi eos-seed` fetches Pyfa's FSD JSON staticdata and merges split files. See `dev/spikes/eos-integration-FINDINGS.md` for details.

The project will ship **no data**. It will provide a tool to fetch `eve.db` from Pyfa releases.

**Action:**
1.  Implement a seeding script (e.g., `scripts/update_data.py`).
2.  The script must:
    - Check the installed version of the `pyfa-eos` package.
    - Fetch the corresponding release from GitHub (e.g., if package is v2.60.1, fetch Release 2.60.1).
    - Unzip and place `eve.db` in the configured data path.

### **8.3. Decision 3: Natural Language Interface via MCP**

The **primary interface** will be natural language.

**Action:**
Create a wrapper class `EVEAdvisorTool` to interface between the LLM's JSON requirements and EOS's object model.

### **8.4. Recommendation 4: Application vs. Raw Stats**

The greatest value an automated advisor can provide is interpreting **Application**. By calculating derived metrics (e.g. application to specific signatures), the application moves from being a simple calculator to a true "Advisor."

## **9. Compliance and Legal Metadata**

### **9.1 Explicit Attribution**
`ATTRIBUTION.md` must be updated to include clear attribution for the pyfa-org team and the `eve.db` data source.

### **9.2 Redistribution Constraints**
The eve.db dataset is derived from CCP Games data. The "ship minimal data" decision aligns with this by shifting the data acquisition to the user's runtime environment.

## **11. Conclusion**

The integration of **EOS**, sourced directly from the **Pyfa repository**, represents the optimal architectural decision. The spike investigation confirmed that the standalone EOS library is incompatible with modern community data sources. By pinning dependency to the Pyfa repository and automating the retrieval of the matching `eve.db`, the application ensures it provides accurate, "Dogma-compliant" advice that reflects the current reality of EVE Online.

#### **Works cited**
(Citations remain unchanged)
